import io
import os
import sys
from typing import Optional

UNDERDOG_PATH = "/Users/apple/Documents/wolinetai/models/underdog_woof"
if UNDERDOG_PATH not in sys.path:
    sys.path.insert(0, UNDERDOG_PATH)

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from underdog_woof import Woof

from f5_tts.infer.utils_infer import load_model, load_vocoder
from f5_tts.model import DiT
from f5_tts.model.utils import convert_char_to_pinyin

app = FastAPI(title="Wolinet Sovereign Voice Synthesis Service")

MODEL_DIR = "/Users/apple/Documents/wolinetai/models/swahili_tts"
CKPT_PATH = os.path.join(MODEL_DIR, "model.safetensors")

device = "mps" if torch.backends.mps.is_available() else "cpu"
sauti_model: Optional[DiT] = None
vocoder = None
cached_profiles: dict[str, dict[str, object]] = {}
woof_voices: dict[str, Woof] = {}


class SpeechRequest(BaseModel):
    model: Optional[str] = "Wolinet Voice"
    input: str
    voice: Optional[str] = "Renatus"
    response_format: Optional[str] = "mp3"
    speed: Optional[float] = 1.0
    nfe_step: Optional[int] = None


def format_audio_response(audio_data: np.ndarray, sample_rate: int, fmt: Optional[str] = "mp3") -> Response:
    format_key = (fmt or "mp3").lower()
    media_map = {
        "mp3": ("MP3", "audio/mpeg"),
        "wav": ("WAV", "audio/wav"),
        "flac": ("FLAC", "audio/flac"),
        "ogg": ("OGG", "audio/ogg"),
    }
    sf_fmt, media_type = media_map.get(format_key, ("MP3", "audio/mpeg"))
    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format=sf_fmt)
    buffer.seek(0)
    return Response(content=buffer.read(), media_type=media_type)


def synthesize_swahili_mps(profile: dict[str, object], gen_text: str, nfe_steps: int = 8) -> np.ndarray:
    if sauti_model is None or vocoder is None:
        raise RuntimeError("Sauti-TTS model is not initialized")

    cond_mel = profile["cond_mel"]
    assert isinstance(cond_mel, torch.Tensor)
    ref_text = str(profile["ref_text"])

    text_list = convert_char_to_pinyin([ref_text + " " + gen_text])
    ref_frames = cond_mel.shape[1]
    gen_frames = max(32, int(ref_frames / max(1, len(ref_text)) * len(gen_text)))
    total_duration = ref_frames + gen_frames

    with torch.inference_mode():
        out_mel, _ = sauti_model.sample(
            cond=cond_mel,
            text=text_list,
            duration=total_duration,
            steps=nfe_steps,
            cfg_strength=2.0,
        )

    gen_mel = out_mel[:, ref_frames:, :].permute(0, 2, 1).cpu()
    wave = vocoder.decode(gen_mel).squeeze().cpu().numpy()
    return wave


@app.on_event("startup")
def startup_event():
    global sauti_model, vocoder, cached_profiles, woof_voices

    try:
        woof_voices["juno"] = Woof(voice="juno")
        woof_voices["mira"] = Woof(voice="mira")
    except Exception as e:
        print(f"[Voice Warning] Could not initialize Underdog-Woof: {e}", file=sys.stderr)

    try:
        model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
        sauti_model = load_model(DiT, model_cfg, CKPT_PATH, mel_spec_type="vocos", device=device)
        vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device="cpu")
        mel_spec_cpu = sauti_model.mel_spec.cpu()

        male_ref = os.path.join(MODEL_DIR, "references/waxal_speaker_04.wav")
        m_audio, sr = sf.read(male_ref)
        m_audio_4s = m_audio[: sr * 4]
        m_tensor = torch.from_numpy(m_audio_4s).float().unsqueeze(0)
        m_mel = mel_spec_cpu(m_tensor).permute(0, 2, 1).to(device)
        m_text = "Majira ya asubuhi, hali ya mvua imeonekana kuwa asilimia kumi na nane."
        cached_profiles["renatus"] = {"cond_mel": m_mel, "ref_text": m_text}
        cached_profiles["baraka"] = {"cond_mel": m_mel, "ref_text": m_text}
        cached_profiles["male"] = {"cond_mel": m_mel, "ref_text": m_text}

        fem_ref = os.path.join(MODEL_DIR, "references/waxal_speaker_01.wav")
        f_audio, sr = sf.read(fem_ref)
        f_audio_4s = f_audio[: sr * 4]
        f_tensor = torch.from_numpy(f_audio_4s).float().unsqueeze(0)
        f_mel = mel_spec_cpu(f_tensor).permute(0, 2, 1).to(device)
        f_text = "Wakati wa asubuhi jua huonekana likiwa na rangi ya manjano."
        cached_profiles["witness"] = {"cond_mel": f_mel, "ref_text": f_text}
        cached_profiles["angela"] = {"cond_mel": f_mel, "ref_text": f_text}
        cached_profiles["female"] = {"cond_mel": f_mel, "ref_text": f_text}

        print(f"[Voice Startup] Sovereign Sauti-TTS Swahili Engine loaded on {device} with pre-cached profiles")
    except Exception as e:
        print(f"[Voice Warning] Could not initialize Sauti-TTS on {device}: {e}", file=sys.stderr)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "wolinet-sovereign-voice",
        "model": "Wolinet Voice",
        "voices": ["Renatus (Baraka Male)", "Witness (Female)"],
        "sample_rate": "24000Hz",
        "device": device,
        "engine": "msingiai/sauti-tts-sm + vocos-24khz (Metal GPU / Underdog Hybrid)",
    }


@app.get("/v1/models")
@app.get("/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": "Wolinet Voice", "object": "model", "owned_by": "wolinet"}],
    }


@app.get("/v1/audio/voices")
@app.get("/audio/voices")
def list_voices():
    return {
        "voices": [
            {"id": "Renatus", "name": "Renatus (Baraka Male Native)"},
            {"id": "Witness", "name": "Witness (Female Native)"},
        ]
    }


@app.post("/v1/audio/speech")
@app.post("/audio/speech")
def generate_speech(req: SpeechRequest):
    voice_key = (req.voice or "Renatus").lower().strip()
    model_name = (req.model or "Wolinet Voice").lower()

    if "underdog" in model_name or voice_key in ("juno", "mira"):
        woof_key = "mira" if voice_key in ("mira", "witness", "angela", "female") else "juno"
        engine = woof_voices.get(woof_key)
        if not engine:
            raise HTTPException(status_code=503, detail="Underdog engine not initialized")
        audio = engine(req.input)
        return format_audio_response(audio, 24000, req.response_format)

    target_profile_key = "witness" if voice_key in ("witness", "angela", "female", "zawadi", "nova") else "renatus"
    profile = cached_profiles.get(target_profile_key)
    if not profile or sauti_model is None:
        if woof_voices:
            woof_key = "mira" if target_profile_key == "witness" else "juno"
            audio = woof_voices[woof_key](req.input)
            return format_audio_response(audio, 24000, req.response_format)
        raise HTTPException(status_code=503, detail="Voice engine is not initialized")

    steps = req.nfe_step if req.nfe_step and req.nfe_step > 0 else 8
    try:
        audio = synthesize_swahili_mps(profile, req.input, nfe_steps=steps)
        return format_audio_response(audio, 24000, req.response_format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Native voice synthesis failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8089, log_level="info")
