# Copyright 2022-2026 Xinference Holdings Pte. Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import io
import logging
import os
import re
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .core import AudioModelFamilyV2

logger = logging.getLogger(__name__)


class F5TTSModel:
    def __init__(
        self,
        model_uid: str,
        model_path: str,
        model_spec: "AudioModelFamilyV2",
        device: Optional[str] = None,
        **kwargs,
    ):
        self.model_family = model_spec
        self._model_uid = model_uid
        self._model_path = model_path
        self._model_spec = model_spec
        self._device = device
        self._model = None
        self._vocoder = None
        self._kwargs = kwargs

    @property
    def model_ability(self):
        return self._model_spec.model_ability

    @staticmethod
    def _download_modelscope_vocos() -> str:
        from ..utils import ModelArtifactSource

        return ModelArtifactSource("modelscope").snapshot_download(
            "pengzhendong/vocos-mel-24khz",
            allow_patterns=["config.yaml", "pytorch_model.bin"],
        )

    def _resolve_vocoder_path(
        self, vocoder_name: str, vocoder_path: Optional[str]
    ) -> Optional[str]:
        if (
            vocoder_name == "vocos"
            and vocoder_path is None
            and getattr(self._model_spec, "model_hub", None) == "modelscope"
        ):
            return self._download_modelscope_vocos()
        return vocoder_path

    def load(self):
        import os
        import sys

        # The yaml config loaded from model has hard-coded the import paths. please refer to: load_hyperpyyaml
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../thirdparty"))

        from f5_tts.infer.utils_infer import load_model, load_vocoder
        from f5_tts.model import DiT

        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

        vocoder_name = self._kwargs.get("vocoder_name", "vocos")
        vocoder_path = self._kwargs.get("vocoder_path")

        if vocoder_name not in ["vocos", "bigvgan"]:
            raise Exception(f"Unsupported vocoder name: {vocoder_name}")

        target_device = self._device
        if target_device is None:
            import platform
            import torch

            if torch.cuda.is_available():
                target_device = "cuda"
            elif platform.machine() == "arm64" and torch.backends.mps.is_available():
                target_device = "mps"
            else:
                target_device = "cpu"

        vocoder_path = self._resolve_vocoder_path(vocoder_name, vocoder_path)
        if vocoder_path is not None:
            self._vocoder = load_vocoder(
                vocoder_name=vocoder_name, is_local=True, local_path=vocoder_path, device=target_device
            )
        else:
            self._vocoder = load_vocoder(vocoder_name=vocoder_name, is_local=False, device=target_device)

        model_cls = DiT
        model_cfg = dict(
            dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4
        )
        if vocoder_name == "vocos":
            exp_name = "F5TTS_Base"
            ckpt_step = 1200000
        elif vocoder_name == "bigvgan":
            exp_name = "F5TTS_Base_bigvgan"
            ckpt_step = 1250000
        else:
            assert False
        ckpt_file = os.path.join(
            self._model_path, exp_name, f"model_{ckpt_step}.safetensors"
        )
        if not os.path.exists(ckpt_file):
            for fname in [
                "model.safetensors",
                "model.pt",
                f"model_{ckpt_step}.safetensors",
            ]:
                cand = os.path.join(self._model_path, fname)
                if os.path.exists(cand):
                    ckpt_file = cand
                    break

        config_path = os.path.join(self._model_path, "config.json")
        if os.path.exists(config_path):
            try:
                import json

                with open(config_path, "r", encoding="utf-8") as f:
                    cfg_json = json.load(f)
                if "model_cfg" in cfg_json:
                    model_cfg = cfg_json["model_cfg"]
            except Exception as e:
                logger.warning("Could not read config.json in %s: %s", self._model_path, e)

        vocab_file = os.path.join(self._model_path, "vocab.txt")
        if not os.path.exists(vocab_file):
            vocab_file = ""

        logger.info(f"Loading %s onto %s...", ckpt_file, target_device)
        try:
            self._model = load_model(
                model_cls,
                model_cfg,
                ckpt_file,
                mel_spec_type=vocoder_name,
                vocab_file=vocab_file,
                device=target_device,
            )
            self._target_device = target_device
        except Exception as e:
            logger.warning(
                "Failed to load F5-TTS on %s (%s), falling back to cpu",
                target_device,
                e,
            )
            self._model = load_model(
                model_cls,
                model_cfg,
                ckpt_file,
                mel_spec_type=vocoder_name,
                vocab_file=vocab_file,
                device="cpu",
            )
            self._target_device = "cpu"

    def _infer(
        self,
        ref_audio,
        ref_text,
        text_gen,
        model_obj,
        mel_spec_type,
        speed,
        nfe_step=16,
    ):
        import numpy as np
        from f5_tts.infer.utils_infer import infer_process, preprocess_ref_audio_text

        config = {}
        main_voice = {"ref_audio": ref_audio, "ref_text": ref_text}
        if "voices" not in config:
            voices = {"main": main_voice}
        else:
            voices = config["voices"]
            voices["main"] = main_voice
        for voice in voices:
            (
                voices[voice]["ref_audio"],
                voices[voice]["ref_text"],
            ) = preprocess_ref_audio_text(
                voices[voice]["ref_audio"], voices[voice]["ref_text"]
            )
            logger.info("Voice: %s", voice)
            logger.info("Ref_audio: %s", voices[voice]["ref_audio"])
            logger.info("Ref_text: %s", voices[voice]["ref_text"])

        final_sample_rate = None
        generated_audio_segments = []
        reg1 = r"(?=\[\w+\])"
        chunks = re.split(reg1, text_gen)
        reg2 = r"\[(\w+)\]"
        device = getattr(self, "_target_device", "cpu")
        for text in chunks:
            if not text.strip():
                continue
            match = re.match(reg2, text)
            if match:
                voice = match[1]
            else:
                logger.info("No voice tag found, using main.")
                voice = "main"
            if voice not in voices:
                logger.info(f"Voice {voice} not found, using main.")
                voice = "main"
            text = re.sub(reg2, "", text)
            gen_text = text.strip()
            ref_audio = voices[voice]["ref_audio"]
            ref_text = voices[voice]["ref_text"]
            logger.info(f"Voice: {voice}")
            audio, final_sample_rate, spectragram = infer_process(
                ref_audio,
                ref_text,
                gen_text,
                model_obj,
                self._vocoder,
                mel_spec_type=mel_spec_type,
                speed=speed,
                nfe_step=nfe_step,
                device=device,
            )
            generated_audio_segments.append(audio)

        if generated_audio_segments:
            final_wave = np.concatenate(generated_audio_segments)
            return final_sample_rate, final_wave
        return None, None

    def speech(
        self,
        input: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
        stream: bool = False,
        **kwargs,
    ):
        import f5_tts
        import soundfile
        import tomli

        from .utils import apply_audio_seed

        apply_audio_seed(kwargs)

        prompt_speech: Optional[bytes] = kwargs.pop("prompt_speech", None)
        prompt_text: Optional[str] = kwargs.pop("prompt_text", None)
        nfe_step: int = int(kwargs.pop("nfe_step", 8))

        ref_audio: Union[str, io.BytesIO]
        if prompt_speech is not None:
            ref_audio = io.BytesIO(prompt_speech)
            if prompt_text is None:
                raise ValueError("`prompt_text` cannot be empty when `prompt_speech` is provided")
        else:
            resolved = False
            speakers_file = os.path.join(self._model_path, "speakers.json")
            if os.path.exists(speakers_file):
                import json

                try:
                    with open(speakers_file, "r", encoding="utf-8") as f:
                        spk_meta = json.load(f)
                    speakers = spk_meta.get("speakers", [])
                    v_query = (voice or "").strip().lower()

                    matched_spk = None
                    for spk in speakers:
                        label = str(spk.get("label", "")).lower()
                        gender = str(spk.get("gender", "")).lower()
                        if v_query and (v_query in label or v_query in gender):
                            matched_spk = spk
                            break

                    if matched_spk is None and speakers:
                        if v_query in ("witness", "angela", "female", "zawadi", "nova", "shimmer"):
                            for spk in speakers:
                                if "female" in str(spk.get("gender", "")).lower():
                                    matched_spk = spk
                                    break
                        if matched_spk is None:
                            for spk in speakers:
                                if "male" in str(spk.get("gender", "")).lower():
                                    matched_spk = spk
                                    break
                            if matched_spk is None:
                                matched_spk = speakers[0]

                    if matched_spk:
                        wav_filename = matched_spk.get("reference_wav", "")
                        candidate_audio = os.path.join(self._model_path, "references", wav_filename)
                        if not os.path.exists(candidate_audio):
                            candidate_audio = os.path.join(self._model_path, wav_filename)
                        if os.path.exists(candidate_audio):
                            ref_audio = candidate_audio
                            prompt_text = matched_spk.get("ref_text", "")
                            resolved = True
                except Exception as e:
                    logger.warning("Error reading speakers.json from %s: %s", self._model_path, e)

            if not resolved:
                base = os.path.dirname(f5_tts.__file__)
                config = os.path.join(base, "infer/examples/basic/basic.toml")
                with open(config, "rb") as f:
                    config_dict = tomli.load(f)
                ref_audio = os.path.join(base, config_dict["ref_audio"])
                prompt_text = config_dict["ref_text"]

        assert self._model is not None
        vocoder_name = self._kwargs.get("vocoder_name", "vocos")
        sample_rate, wav = self._infer(
            ref_audio=ref_audio,
            ref_text=prompt_text,
            text_gen=input,
            model_obj=self._model,
            mel_spec_type=vocoder_name,
            speed=speed,
            nfe_step=nfe_step,
        )

        with BytesIO() as out:
            with soundfile.SoundFile(
                out, "w", sample_rate, 1, format=response_format.upper()
            ) as f:
                f.write(wav)
            audio_bytes = out.getvalue()

        if stream:
            async def audio_stream():
                chunk_size = 4096
                for i in range(0, len(audio_bytes), chunk_size):
                    yield audio_bytes[i : i + chunk_size]

            return audio_stream()

        return audio_bytes
