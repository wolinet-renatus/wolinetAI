import os
os.environ["F5_DEVICE"] = "cpu"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import time
import soundfile as sf
import torch
from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder
from f5_tts.model import DiT

def main():
    print("=" * 60)
    print("Wolinet AI: Generating Native Swahili Commercial Advertisement Voice")
    print("Model: msingiai/sauti-tts-sm (F5-TTS DiT + Vocos 24kHz)")
    print("=" * 60)

    model_dir = "/Users/apple/Documents/wolinetai/models/swahili_tts"
    ckpt_path = os.path.join(model_dir, "model.safetensors")
    ref_audio = os.path.join(model_dir, "references", "waxal_speaker_04.wav")
    ref_text = (
        "Majira ya asubuhi, hali ya mvua imeonekana kuwa asilimia kumi na nane "
        "lakini imebadilika saa saba mchana na kufikia asilimia tatu. "
        "Kwa hiyo wakati wa mchana kumekuwa na jua pamoja na upepo kiasi."
    )

    ad_script = (
        "Habari za asubuhi! Karibu kwenye maduka yetu ya Wolinet AI ujipatie punguzo kabambe la bei wiki hii. "
        "Nunua sasa bidhaa bora zenye kiwango cha juu!"
    )

    print("\n[1/4] Loading Vocos 24kHz neural vocoder...")
    t0 = time.time()
    vocoder = load_vocoder(vocoder_name="vocos", is_local=False)
    print(f"Vocoder loaded in {time.time() - t0:.2f}s")

    print("\n[2/4] Loading DiT diffusion transformer weights...")
    t1 = time.time()
    model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
    model = load_model(DiT, model_cfg, ckpt_path, mel_spec_type="vocos")
    print(f"DiT model loaded in {time.time() - t1:.2f}s")

    print("\n[3/4] Synthesizing native commercial speech...")
    print(f"Reference Audio: {os.path.basename(ref_audio)} (Male Native Speaker)")
    print(f"Ad Script: '{ad_script}'")

    t2 = time.time()
    audio, sample_rate, _ = infer_process(
        ref_audio=ref_audio,
        ref_text=ref_text,
        gen_text=ad_script,
        model_obj=model,
        vocoder=vocoder,
        mel_spec_type="vocos",
        speed=1.0,
        nfe_step=32,
    )
    t3 = time.time()
    print(f"Speech synthesized in {t3 - t2:.2f}s (Sample Rate: {sample_rate} Hz)")

    output_path = "/Users/apple/Documents/wolinetai/swahili_sauti_advert.wav"
    sf.write(output_path, audio, sample_rate)
    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"\n[4/4] Output successfully saved to:")
    print(f"  {output_path} ({file_size_kb:.1f} KB, 24000 Hz, Broadcast-Quality WAV)")
    print("=" * 60)

if __name__ == "__main__":
    main()
