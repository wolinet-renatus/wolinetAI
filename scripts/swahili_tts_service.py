import io
import json
import os
import re
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
        profile = {
            "ref_audio": ref_file,
            "ref_text": spk["ref_text"],
        }

        if gender == "male":
            speakers_map["Renatus"] = profile
            speakers_map["renatus"] = profile
            speakers_map["male"] = profile
            speakers_map["baraka"] = profile
            speakers_map["alloy"] = profile
            speakers_map["onyx"] = profile
            speakers_map["echo"] = profile
        elif spk["waxal_speaker_id"] == 1:
            speakers_map["Witness"] = profile
            speakers_map["witness"] = profile
            speakers_map["Angela"] = profile
            speakers_map["angela"] = profile
            speakers_map["female"] = profile
            speakers_map["zawadi"] = profile
            speakers_map["nova"] = profile
            speakers_map["shimmer"] = profile

    print("[Startup] Wolinet Sovereign Voice Service ready on port 8089!")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "wolinet-sovereign-voice",
        "model": "Wolinet Voice",
        "voices": ["Renatus (Male)", "Witness (Female)"],
        "sample_rate": "24000Hz"
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

def is_swahili_text(text: str) -> bool:
    swahili_markers = [
        "habari", "jambo", "karibu", "kwa", "katika", "mimi", "wewe", "sisi",
        "wao", "yangu", "yetu", "yenu", "wote", "kuja", "kutumia", "mifumo",
        "bei", "nafuu", "tumeijenga", "tuijenga", "ajili", "lugha", "adhimu",
        "kiswahili", "asubuhi", "jua", "mvua", "watu", "sana", "ndio", "hapa",
        "nchi", "taifa", "mji", "kazi", "nzuri", "gani", "nawakaribisha",
        "nawakalibisha", "wote", "huku", "mbona", "lakini", "kwamba"
    ]
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return any(token in swahili_markers for token in tokens)

@app.post("/v1/audio/speech")
@app.post("/audio/speech")
def generate_speech(req: SpeechRequest):
    voice_key = (req.voice or "Renatus").lower()

    if not sauti_model or not vocoder:
        raise HTTPException(status_code=503, detail="Wolinet Voice model is still initializing")

    # Resolve voice: Renatus (Male) or Witness/Angela (Female)
    if voice_key in ("witness", "angela", "female", "nova", "shimmer", "mira", "zawadi"):
        speaker_profile = speakers_map.get("Witness")
    else:
        speaker_profile = speakers_map.get("Renatus")

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
