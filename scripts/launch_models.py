#!/usr/bin/env python3
"""Launch and verify sovereign single lightweight model (Deepseeker Coder) in Mitambo."""

import os
import sys
import time

# Ensure repo path
WS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(WS_ROOT)

from xinference.client import RESTfulClient

def main():
    print(f"Connecting to Mitambo at http://127.0.0.1:9997 (Workspace: {WS_ROOT})...")
    client = RESTfulClient("http://127.0.0.1:9997")
    client.login("admin", "Woli@1211")

    running = client.list_models()
    print("Currently running models:", list(running.keys()))

    # Terminate any obsolete models if still present
    for obsolete in [
        "deepseek-v4-pro-4b",
        "spark-x2.6-1.7b",
        "glm-5.3-flash-speculative",
        "wolinet-coder-v2",
        "deepseek-r1-coder-0.5b"
    ]:
        if obsolete in running:
            try:
                print(f"Terminating obsolete model: {obsolete}")
                client.terminate_model(obsolete)
            except Exception as e:
                print(f"Notice terminating {obsolete}: {e}")

    # Unregister obsolete custom registrations
    for obsolete_reg in ["deepseek-r1-coder-0.5b", "spark-x2.6-1.7b", "deepseek-v4-pro-4b"]:
        try:
            client.unregister_model(model_type="LLM", model_name=obsolete_reg)
        except Exception:
            pass

    # Register deepseeker-coder if needed
    reg_file = os.path.join(WS_ROOT, "inference/models/registrations/deepseeker-coder.json")
    if os.path.exists(reg_file):
        try:
            with open(reg_file, "r") as f:
                model_spec = f.read()
            client.register_model(model_type="LLM", model=model_spec, persist=True)
            print("Registered deepseeker-coder")
        except Exception as e:
            print(f"Registration notice: {e}")

    # Register wolinet-voice if needed
    voice_reg_file = os.path.join(WS_ROOT, "inference/models/registrations/wolinet-voice.json")
    if os.path.exists(voice_reg_file):
        try:
            with open(voice_reg_file, "r") as f:
                voice_spec = f.read()
            client.register_model(model_type="audio", model=voice_spec, persist=True)
            print("Registered wolinet-voice")
        except Exception as e:
            print(f"Registration notice for wolinet-voice: {e}")

    # Single Unified Model: deepseeker-coder
    model_uid = "deepseeker-coder"
    running = client.list_models()
    if model_uid not in running:
        model_path = os.path.join(WS_ROOT, "inference/models/llm/DeepSeek-R1-DRAFT-Qwen2.5-Coder-0.5B-Q4_K_M.gguf")
        print(f"Launching {model_uid} from {model_path}...")
        try:
            uid = client.launch_model(
                model_name="deepseeker-coder",
                model_uid=model_uid,
                model_engine="llama.cpp",
                model_format="ggufv2",
                model_size_in_billions="0_5",
                quantization="Q4_K_M",
                model_path=model_path,
                n_gpu_layers=-1,
                n_ctx=32768,
                n_parallel=1,
                n_threads=8,
                n_batch=2048,
                n_ubatch=512,
                cache_ram_mib=2048,
                cache_type_k=8,
                cache_type_v=8,
                flash_attn_type=1,
            )
            print(f"✅ Launched {model_uid} (UID: {uid})")
        except Exception as e:
            print(f"Error launching {model_uid}: {e}")
            sys.exit(1)
    else:
        print(f"✅ {model_uid} is already running.")

    time.sleep(1)
    updated = client.list_models()
    print("Final active models in Mitambo:", list(updated.keys()))

if __name__ == "__main__":
    main()
