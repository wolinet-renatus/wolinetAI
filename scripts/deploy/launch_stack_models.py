#!/usr/bin/env python3
"""
Automated launcher for Wolinet AI sovereign inference engines on Mitambo.
Ensures both Wolinet Pro (Qwen 2.5 1.5B Instruct) and Wolinet Coder (DeepSeek Coder 1.3B)
are active in Xinference, with cached CLI tokens, pre-cached GGUF files, and clean routing.
"""

import os
import sys
import time
import hashlib
import subprocess
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

# 2. Check running models and clean up any tiny-llama
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

# 4. Pre-seed and verify Qwen 2.5 1.5B Instruct GGUF weights in cache
# Target cache directories for both lowercase and uppercase quantization keys
PRO_UID = "wolinet-pro"
running = client.list_models()

if PRO_UID in running or "qwen2.5-instruct" in running:
    print(f"✅ Wolinet Pro ({PRO_UID}) is already running!")
else:
    cache_base = "/root/.xinference/cache/v2"
    target_dir = os.path.join(cache_base, "qwen2.5-instruct-ggufv2-1_5b-q4_k_m")
    target_dir_upper = os.path.join(cache_base, "qwen2.5-instruct-ggufv2-1_5b-Q4_K_M")
    file_name = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    file_path = os.path.join(target_dir, file_name)

    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(target_dir_upper, exist_ok=True)

    # Clean up any stale lock files
    locks_dir = os.path.join(cache_base, ".download-locks")
    if os.path.exists(locks_dir):
        for lock in os.listdir(locks_dir):
            try:
                os.remove(os.path.join(locks_dir, lock))
            except Exception:
                pass

    current_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    EXPECTED_SIZE = 1117320736  # ~1.04 GiB

    if current_size < 1000 * 1024 * 1024:
        print(f"📥 Downloading Qwen 2.5 1.5B GGUF weights (~1.05 GB)...")
        url = f"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/{file_name}"
        # Direct curl download with resume support and progress
        cmd = ["curl", "-L", "-C", "-", "--retry", "5", "--retry-delay", "2", "-o", file_path, url]
        print(f"   Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print("   HuggingFace download returned non-zero, trying ModelScope mirror...")
            ms_url = f"https://modelscope.cn/models/qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/master/{file_name}"
            subprocess.run(["curl", "-L", "-C", "-", "--retry", "5", "-o", file_path, ms_url], check=True)
        print(f"✅ Download complete! Size on disk: {os.path.getsize(file_path) / (1024*1024):.2f} MB")

    # Link into uppercase folder to satisfy any path resolver
    file_path_upper = os.path.join(target_dir_upper, file_name)
    if not os.path.exists(file_path_upper):
        try:
            os.symlink(file_path, file_path_upper)
        except Exception:
            pass

    print("🚀 Launching Wolinet Pro (Qwen 2.5 1.5B Instruct)...")
    print("   Engine: llama.cpp | Format: ggufv2 | Quant: q4_k_m | CPU (n_ctx=4096, n_parallel=1)")

    launched = False
    for quant_candidate in ("q4_k_m", "Q4_K_M"):
        try:
            p_uid = client.launch_model(
                model_name="qwen2.5-instruct",
                model_uid=PRO_UID,
                model_engine="llama.cpp",
                model_format="ggufv2",
                model_size_in_billions="1_5",
                quantization=quant_candidate,
                n_gpu=None,
                n_gpu_layers=0,
                n_ctx=4096,
                n_parallel=1,
            )
            print(f"🎉 SUCCESS! Wolinet Pro launched (UID: {p_uid}) with quant={quant_candidate}")
            launched = True
            break
        except Exception as pe:
            print(f"⚠️ Launch attempt with quant={quant_candidate} failed: {pe}")

    if not launched:
        print("❌ Could not start Wolinet Pro automatically. See logs above.")

final_models = client.list_models()
print("\n==================================================")
print("🌟 [Wolinet AI] INFERENCE ENGINES STATUS:")
print(f"   Active UIDs in Xinference: {list(final_models.keys())}")
if "wolinet-pro" in final_models or "qwen2.5-instruct" in final_models:
    print("   ✅ 1. Wolinet Pro   -> Qwen 2.5 1.5B (Default chat, ~50 t/s)")
if "deepseek-coder-instruct" in final_models:
    print("   ✅ 2. Wolinet Coder -> DeepSeek Coder 1.3B (Coding specialist)")
print("==================================================\n")
