import io
import json
import os
import sys

os.environ["F5_DEVICE"] = "cpu"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Add Underdog-Woof path
UNDERDOG_PATH = "/Users/apple/Documents/wolinetai/models/underdog_woof"
if UNDERDOG_PATH not in sys.path:
    sys.path.insert(0, UNDERDOG_PATH)

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder
from f5_tts.model import DiT
from underdog_woof import Woof, write_wav

app = FastAPI(title="Wolinet Sovereign Voice Synthesis Service")

MODEL_DIR = "/Users/apple/Documents/wolinetai/models/swahili_tts"
CKPT_PATH = os.path.join(MODEL_DIR, "model.safetensors")
SPEAKERS_CONFIG = os.path.join(MODEL_DIR, "speakers.json")

# State
vocoder = None
sauti_model = None
speakers_map = {}
woof_voices = {}

class SpeechRequest(BaseModel):
    model: Optional[str] = "swahili-voice-ad"
    input: str
    voice: Optional[str] = "juno"
    response_format: Optional[str] = "wav"
    speed: Optional[float] = 1.0
    nfe_step: Optional[int] = None

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

@app.on_event("startup")
def startup_event():
    global vocoder, sauti_model, speakers_map, woof_voices

    print("[Startup 1/3] Preloading ConwayResearch/Underdog-Woof (Juno and Mira)...")
    try:
        woof_voices["juno"] = Woof(voice="juno")
        woof_voices["mira"] = Woof(voice="mira")
        print("[Startup] Underdog-Woof initialized successfully!")
    except Exception as e:
        print(f"[Startup Warning] Could not initialize Underdog-Woof: {e}")

    print("[Startup 2/3] Loading Vocos 24kHz neural vocoder...")
    vocoder = load_vocoder(vocoder_name="vocos", is_local=False)

    print("[Startup 3/3] Loading Sauti-TTS DiT model weights...")
    model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
    sauti_model = load_model(DiT, model_cfg, CKPT_PATH, mel_spec_type="vocos")

    with open(SPEAKERS_CONFIG) as f:
        speakers_data = json.load(f)

    for spk in speakers_data.get("speakers", []):
        ref_file = os.path.join(MODEL_DIR, "references", spk["reference_wav"])
        gender = spk.get("gender", "").lower()
        key = "male" if gender == "male" else ("female_1" if spk["waxal_speaker_id"] == 1 else "female_2")
        speakers_map[key] = {
            "ref_audio": ref_file,
            "ref_text": spk["ref_text"],
        }
        if gender == "male":
            speakers_map["alloy"] = speakers_map[key]
            speakers_map["onyx"] = speakers_map[key]
        elif spk["waxal_speaker_id"] == 1:
            speakers_map["nova"] = speakers_map[key]
            speakers_map["shimmer"] = speakers_map[key]

    print("[Startup] Sovereign Voice Service ready on port 8089!")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "wolinet-sovereign-voice",
        "models": {
            "underdog_woof": {"voices": ["juno", "mira"], "size": "40.6MB", "speed": "13.8x realtime"},
            "swahili_sauti_tts": {"voices": list(speakers_map.keys()), "resolution": "24kHz broadcast"},
        },
    }

@app.get("/v1/models")
@app.get("/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "underdog-woof", "object": "model", "owned_by": "wolinet"},
            {"id": "swahili-voice-ad", "object": "model", "owned_by": "wolinet"},
            {"id": "tts-1", "object": "model", "owned_by": "wolinet"}
        ]
    }

@app.post("/v1/audio/speech")
@app.post("/audio/speech")
def generate_speech(req: SpeechRequest):
    model_name = (req.model or "swahili-voice-ad").lower()
    voice_key = (req.voice or "juno").lower()

    # Route 1: Underdog-Woof (Ultra-fast English edge synthesis)
    if "woof" in model_name or "underdog" in model_name or voice_key in ("juno", "mira"):
        tts = woof_voices.get(voice_key) or woof_voices.get("juno")
        if not tts:
            raise HTTPException(status_code=503, detail="Underdog-Woof model not loaded")
        try:
            audio = tts(req.input, seed=0)
            return format_audio_response(audio, 24000, req.response_format)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Underdog-Woof synthesis failed: {str(e)}")

    # Route 2: Sauti-TTS Swahili (High-fidelity native commercial speech)
    if not sauti_model or not vocoder:
        raise HTTPException(status_code=503, detail="Sauti-TTS model is still initializing")

    speaker_profile = speakers_map.get(voice_key) or speakers_map.get("male")
    if not speaker_profile:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {req.voice}")

    steps = req.nfe_step if req.nfe_step and req.nfe_step > 0 else int(os.environ.get("F5_NFE_STEPS", "16"))

    try:
        audio, sample_rate, _ = infer_process(
            ref_audio=speaker_profile["ref_audio"],
            ref_text=speaker_profile["ref_text"],
            gen_text=req.input,
            model_obj=sauti_model,
            vocoder=vocoder,
            mel_spec_type="vocos",
            speed=req.speed or 1.0,
            nfe_step=steps,
        )

        return format_audio_response(audio, sample_rate, req.response_format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sauti-TTS synthesis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8089, log_level="info")
