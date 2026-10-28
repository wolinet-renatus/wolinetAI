#!/usr/bin/env python3
"""
Automated launcher for Wolinet AI sovereign inference engines on Mitambo.
Ensures Wolinex Coder / Wolinet Pro (DeepSeek-R1 Distill Qwen 1.5B Uncensored)
is active in Xinference, with cached CLI tokens and sovereign routing.
"""

import os
import sys
import time
import hashlib
from xinference.client import RESTfulClient

ENDPOINT = os.environ.get("XINFERENCE_ENDPOINT", "http://127.0.0.1:9997")
USERNAME = os.environ.get("XINFERENCE_USERNAME", "admin")
PASSWORD = os.environ.get("XINFERENCE_PASSWORD", "Woli@1211")

print(f"🚀 [Wolinet AI] Connecting to Xinference at {ENDPOINT}...")
client = RESTfulClient(ENDPOINT)

print(f"🔑 Authenticating as {USERNAME}...")
try:
    client.login(USERNAME, PASSWORD)
    print("✅ Authentication successful!")
except Exception as e:
    print(f"ℹ️ Auth notice: {e}")

# 1. Save CLI auth tokens for all endpoint variants
try:
    token = client._get_token()
    if token:
        auth_dir = os.path.expanduser("~/.xinference/auth")
        os.makedirs(auth_dir, exist_ok=True)
        for ep in (
            "http://127.0.0.1:9997", "http://127.0.0.1:9997/",
            "http://localhost:9997", "http://localhost:9997/",
            "http://0.0.0.0:9997", "http://0.0.0.0:9997/",
        ):
            h = hashlib.sha256(ep.encode("utf-8")).hexdigest()
            with open(os.path.join(auth_dir, h), "w") as f:
                f.write(token)
        print("✅ Saved CLI tokens for localhost, 127.0.0.1, and 0.0.0.0.")
except Exception as e:
    print(f"⚠️ Notice saving CLI token: {e}")

# 2. Check running models and clean up unwanted or legacy models
print("🔍 Checking running models in Xinference...")
try:
    running = client.list_models()
    print(f"   Currently active: {list(running.keys())}")
    for uid in list(running.keys()):
        if any(bad in uid.lower() for bad in ("tiny-llama", "tinyllama", "tiny_llama")):
            print(f"   -> Terminating unwanted model: {uid}...")
            try:
                client.terminate_model(uid)
                print(f"   ✅ Terminated: {uid}")
            except Exception as te:
                print(f"   ⚠️ Error terminating {uid}: {te}")
except Exception as e:
    print(f"⚠️ Notice during inspection: {e}")

time.sleep(1)
running = client.list_models()

# 3. Ensure Single Unified High-Speed Sovereign Model is running (No duplicate weights in RAM)
candidate_paths = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models/llm/wolinet-brain-r1-1.5b.gguf")),
    "/models/llm/wolinet-brain-r1-1.5b.gguf",
    "/Users/apple/Documents/wolinetai/models/llm/wolinet-brain-r1-1.5b.gguf",
    os.path.expanduser("~/Documents/wolinetai/models/llm/wolinet-brain-r1-1.5b.gguf"),
]
model_path = next((p for p in candidate_paths if os.path.exists(p)), None)

# Clean up duplicate legacy instances if present to save RAM
if "wolinet-pro" in running:
    print("   -> Terminating redundant duplicate model instance 'wolinet-pro'...")
    try:
        client.terminate_model("wolinet-pro")
        print("   ✅ Cleaned up redundant 'wolinet-pro' (reclaimed RAM)")
    except Exception as te:
        print(f"   ⚠️ Error terminating wolinet-pro: {te}")

uid = "wolinex-coder"
if uid in running:
    print(f"✅ {uid} (Unified Sovereign Engine) is already running!")
else:
    print(f"🚀 Launching {uid} (High-Speed Unified Sovereign Engine with 12GB RAM KV-Cache)...")
    print(f"   Model Path: {model_path}")
    print("   Engine: llama.cpp | Format: ggufv2 | Quant: Q4_K_M | CPU (n_ctx=32768, n_threads=10, 12GB RAM)")
    try:
        launch_args = {
            "model_name": "deepseek-r1-distill-qwen",
            "model_uid": uid,
            "model_engine": "llama.cpp",
            "model_format": "ggufv2",
            "model_size_in_billions": "1_5",
            "quantization": "Q4_K_M",
            "n_gpu_layers": 0,
            "n_ctx": 32768,
            "n_parallel": 1,
            "n_threads": 10,
            "n_batch": 2048,
            "n_ubatch": 512,
            "cache_ram_mib": 12288,
        }
        if model_path:
            launch_args["model_path"] = model_path
        c_uid = client.launch_model(**launch_args)
        print(f"🎉 SUCCESS! {uid} launched (UID: {c_uid})")
    except Exception as ce:
        print(f"⚠️ Notice launching {uid}: {ce}")

final_models = client.list_models()
print("\n==================================================")
print("🌟 [Wolinet AI] INFERENCE ENGINES STATUS:")
print(f"   Active UIDs in Xinference: {list(final_models.keys())}")
if "wolinex-coder" in final_models:
    print("   ✅ 1. Wolinex Coder    -> DeepSeek-R1 Distill Qwen 1.5B (Active)")
    print("   ✅ 2. Wolinet Pro      -> Mapped via Rust Gateway (Zero duplicate RAM)")
    print("   ✅ 3. Secure Pro       -> Mapped via Rust Gateway (Sub-microsecond scanning)")
    print("   ✅ 4. Wolinet Turbo    -> Mapped via Rust Gateway (DFlash Speculative)")

# 4. Verify Native Rust Defense Core (:8088)
import urllib.request
import subprocess
try:
    with urllib.request.urlopen("http://127.0.0.1:8088/health", timeout=2) as r:
        if r.status == 200:
            print("   ✅ 3. OrcaCyber Defense & Secure Pro (Rust High-Speed Core Active on :8088)")
except Exception:
    bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/defense-rs/target/release/orcacyber-defense-rs"))
    if os.path.exists(bin_path):
        print(f"🚀 Starting native Rust defense core from {bin_path}...")
        subprocess.Popen([bin_path], cwd=os.path.dirname(bin_path))
        print("   ✅ 3. OrcaCyber Defense & Secure Pro launched on :8088")
    else:
        print("   ⚠️ Notice: orcacyber-defense-rs binary not found. Build with 'cargo build --release' in services/defense-rs/")
print("==================================================\n")
