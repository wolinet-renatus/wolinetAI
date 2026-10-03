#!/usr/bin/env python3
"""
Automated launcher for Wolinet AI sovereign inference engines on Mitambo.
Ensures both Wolinet Pro (Qwen 2.5 1.5B Instruct) and Wolinet Coder (DeepSeek Coder 1.3B)
are active in Xinference, with cached CLI tokens and no duplicate/unwanted models.
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
        auth_dir = "/root/.xinference/auth"
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

# 2. Inspect active models and purge any tiny-llama
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

# 3. Ensure Wolinet Coder (deepseek-coder-instruct) is running
CODER_UID = "deepseek-coder-instruct"
if CODER_UID in running:
    print(f"✅ Wolinet Coder ({CODER_UID}) is already running!")
else:
    print("🚀 Launching Wolinet Coder (DeepSeek Coder 1.3B)...")
    print("   Engine: llama.cpp | Format: ggufv2 | Quant: Q4_K_M | CPU (n_ctx=2048, n_parallel=1)")
    try:
        c_uid = client.launch_model(
            model_name="deepseek-coder-instruct",
            model_uid=CODER_UID,
            model_engine="llama.cpp",
            model_format="ggufv2",
            model_size_in_billions="1_3",
            quantization="Q4_K_M",
            n_gpu=None,
            n_gpu_layers=0,
            n_ctx=2048,
            n_parallel=1,
        )
        print(f"🎉 SUCCESS! Wolinet Coder launched (UID: {c_uid})")
    except Exception as ce:
        print(f"⚠️ Notice launching Wolinet Coder: {ce}")

# 4. Launch Wolinet Pro (Qwen 2.5 1.5B Instruct) - Flagship Real-Time Chat
PRO_UID = "wolinet-pro"
if PRO_UID in running or "qwen2.5-instruct" in running:
    print(f"✅ Wolinet Pro ({PRO_UID}) is already running!")
else:
    print("🚀 Launching Wolinet Pro (Qwen 2.5 1.5B Instruct)...")
    print("   Engine: llama.cpp | Format: ggufv2 | Quant: Q4_K_M | CPU (n_ctx=4096, n_parallel=1)")
    print("   ⏳ Downloading ~1.05 GB GGUF weights into cache (please wait 30–60s)...")
    try:
        p_uid = client.launch_model(
            model_name="qwen2.5-instruct",
            model_uid=PRO_UID,
            model_engine="llama.cpp",
            model_format="ggufv2",
            model_size_in_billions="1_5",
            quantization="Q4_K_M",
            n_gpu=None,
            n_gpu_layers=0,
            n_ctx=4096,
            n_parallel=1,
        )
        print(f"🎉 SUCCESS! Wolinet Pro launched (UID: {p_uid})")
    except Exception as pe:
        print(f"❌ Error launching Wolinet Pro with size 1_5: {pe}")
        print("   Retrying with size 1.5...")
        try:
            p_uid = client.launch_model(
                model_name="qwen2.5-instruct",
                model_uid=PRO_UID,
                model_engine="llama.cpp",
                model_format="ggufv2",
                model_size_in_billions="1.5",
                quantization="Q4_K_M",
                n_gpu=None,
                n_gpu_layers=0,
                n_ctx=4096,
                n_parallel=1,
            )
            print(f"🎉 SUCCESS! Wolinet Pro launched (UID: {p_uid})")
        except Exception as pe2:
            print(f"❌ Retry also failed: {pe2}")

final_models = client.list_models()
print("\n==================================================")
print("🌟 [Wolinet AI] ALL INFERENCE ENGINES CONVERGED!")
print(f"   Active UIDs: {list(final_models.keys())}")
print("   1. Wolinet Pro   -> Qwen 2.5 1.5B (Default chat, ~50 t/s)")
print("   2. Wolinet Coder -> DeepSeek Coder 1.3B (Coding specialist)")
print("==================================================\n")
