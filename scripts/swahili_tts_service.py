import io
import json
import os
import sys
from typing import Optional

UNDERDOG_PATH = "/Users/apple/Documents/wolinetai/models/underdog_woof"
if UNDERDOG_PATH not in sys.path:
    sys.path.insert(0, UNDERDOG_PATH)

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from underdog_woof import Woof

app = FastAPI(title="Wolinet Sovereign Voice Synthesis Service")

MODEL_DIR = "/Users/apple/Documents/wolinetai/models/swahili_tts"
CKPT_PATH = os.path.join(MODEL_DIR, "model.safetensors")
SPEAKERS_CONFIG = os.path.join(MODEL_DIR, "speakers.json")

woof_voices: dict[str, Woof] = {}
sauti_model = None
vocoder = None
speakers_map: dict[str, dict[str, str]] = {}


class SpeechRequest(BaseModel):
    model: Optional[str] = "Wolinet Voice"
    input: str
    voice: Optional[str] = "Renatus"
    response_format: Optional[str] = "wav"
    speed: Optional[float] = 1.0
    nfe_step: Optional[int] = None


def change_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    if abs(speed - 1.0) < 0.01 or speed <= 0:
        return audio
    indices = np.arange(0, len(audio), speed)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def format_audio_response(audio_data: np.ndarray, sample_rate: int, fmt: Optional[str] = "wav") -> Response:
    format_key = (fmt or "wav").lower()
    media_map = {
        "wav": ("WAV", "audio/wav"),
        "mp3": ("MP3", "audio/mpeg"),
        "flac": ("FLAC", "audio/flac"),
        "ogg": ("OGG", "audio/ogg"),
    }
    sf_fmt, media_type = media_map.get(format_key, ("WAV", "audio/wav"))
    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format=sf_fmt)
    buffer.seek(0)
    return Response(content=buffer.read(), media_type=media_type)


def get_lazy_sauti_model():
    global sauti_model, vocoder, speakers_map
    if sauti_model is not None and vocoder is not None:
        return sauti_model, vocoder

    import torch
    torch.set_num_threads(min(4, os.cpu_count() or 4))
    from f5_tts.infer.utils_infer import load_model, load_vocoder
    from f5_tts.model import DiT

    vocoder = load_vocoder(vocoder_name="vocos", is_local=False)
    model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
    sauti_model = load_model(DiT, model_cfg, CKPT_PATH, mel_spec_type="vocos")

    if os.path.exists(SPEAKERS_CONFIG):
        with open(SPEAKERS_CONFIG) as f:
            speakers_data = json.load(f)
        for spk in speakers_data.get("speakers", []):
            ref_file = os.path.join(MODEL_DIR, "references", spk["reference_wav"])
            gender = spk.get("gender", "").lower()
            profile = {"ref_audio": ref_file, "ref_text": spk["ref_text"]}
            if gender == "male":
                speakers_map["renatus"] = profile
            elif spk.get("waxal_speaker_id") == 1:
                speakers_map["witness"] = profile

    return sauti_model, vocoder


@app.on_event("startup")
def startup_event():
    global woof_voices
    try:
        woof_voices["juno"] = Woof(voice="juno")
        woof_voices["mira"] = Woof(voice="mira")
    except Exception as e:
        print(f"[Startup Warning] Could not initialize Underdog-Woof: {e}", file=sys.stderr)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "wolinet-sovereign-voice",
        "model": "Wolinet Voice",
        "voices": ["Renatus (Male)", "Witness (Female)"],
        "sample_rate": "24000Hz",
        "engine": "underdog-woof-int8"
    }


@app.get("/v1/models")
@app.get("/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "Wolinet Voice", "object": "model", "owned_by": "wolinet"}
        ]
    }


@app.get("/v1/audio/voices")
@app.get("/audio/voices")
def list_voices():
    return {
        "voices": [
            {"id": "Renatus", "name": "Renatus (Male)"},
            {"id": "Witness", "name": "Witness (Female)"}
        ]
    }


@app.post("/v1/audio/speech")
@app.post("/audio/speech")
def generate_speech(req: SpeechRequest):
    voice_key = (req.voice or "Renatus").lower().strip()
    model_name = (req.model or "Wolinet Voice").lower()

    if "sauti" in model_name or "diffusion" in model_name:
        s_model, s_vocoder = get_lazy_sauti_model()
        from f5_tts.infer.utils_infer import infer_process
        target_voice = "witness" if voice_key in ("witness", "angela", "female", "mira") else "renatus"
        profile = speakers_map.get(target_voice)
        if not profile:
            raise HTTPException(status_code=400, detail=f"No speaker profile for {target_voice}")
        steps = req.nfe_step if req.nfe_step and req.nfe_step > 0 else 8
        audio, sample_rate, _ = infer_process(
            ref_audio=profile["ref_audio"],
            ref_text=profile["ref_text"],
            gen_text=req.input,
            model_obj=s_model,
            vocoder=s_vocoder,
            mel_spec_type="vocos",
            speed=req.speed or 1.0,
            nfe_step=steps,
        )
        return format_audio_response(audio, sample_rate, req.response_format)

    target_engine_voice = "mira" if voice_key in ("witness", "angela", "female", "mira", "zawadi", "nova", "shimmer") else "juno"
    engine = woof_voices.get(target_engine_voice)
    if not engine:
        raise HTTPException(status_code=503, detail="Voice engine is not initialized")

    try:
        audio = engine(req.input)
        if req.speed and abs(req.speed - 1.0) >= 0.01:
            audio = change_speed(audio, req.speed)
        return format_audio_response(audio, 24000, req.response_format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8089, log_level="info")
