#!/usr/bin/env python3
"""
Direct diagnostic to test XllamaCppModel and Server(params) loading for Qwen 2.5 1.5B,
capturing exact tracebacks and C++ llama.cpp errors without buffer overflow.
"""

import os
import sys
import inspect
import traceback

print("==> 1. Verifying Qwen 2.5 1.5B GGUF file on disk...")
model_path = "/root/.xinference/cache/v2/qwen2.5-instruct-ggufv2-1_5b-q4_k_m/qwen2.5-1.5b-instruct-q4_k_m.gguf"
if not os.path.exists(model_path):
    print(f"❌ File not found at {model_path}")
    sys.exit(1)

size_mb = os.path.getsize(model_path) / (1024 * 1024)
print(f"   Path: {model_path}")
print(f"   Size: {size_mb:.2f} MB")

with open(model_path, "rb") as f:
    magic = f.read(4)
print(f"   GGUF Magic: {magic} ({'VALID' if magic == b'GGUF' else 'INVALID'})")

print("\n==> 2. Inspecting core llama_cpp module and CommonParams...")
try:
    import xinference.model.llm.llama_cpp.core as core
    print("   core.py loaded successfully.")
    Server = getattr(core, "Server", None)
    CommonParams = getattr(core, "CommonParams", None)
    XllamaCppModel = getattr(core, "XllamaCppModel", None)
    print(f"   Server class: {Server}")
    print(f"   CommonParams class: {CommonParams}")
    print(f"   XllamaCppModel class: {XllamaCppModel}")
except Exception as e:
    print(f"❌ Failed to import core: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n==> 3. Testing raw Server(params) initialization...")
try:
    params = CommonParams()
    try:
        params.model = model_path
    except Exception:
        params.model.path = model_path

    # Set safe CPU parameters
    if hasattr(params, "n_ctx"):
        params.n_ctx = 2048
    if hasattr(params, "n_parallel"):
        params.n_parallel = 1
    if hasattr(params, "n_gpu_layers"):
        params.n_gpu_layers = 0

    print("   Configured params: n_ctx=2048, n_parallel=1, n_gpu_layers=0")
    print("   Instantiating raw Server(params)...")
    srv = Server(params)
    print("   🎉 SUCCESS! Raw Server(params) initialized without error!")
except Exception as e:
    print(f"   ❌ Raw Server(params) failed: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n==> 4. Finding model_family and testing XllamaCppModel.load()...")
try:
    from xinference.model.llm import BUILTIN_LLM_FAMILIES
    target_family = None
    target_spec = None
    for f in BUILTIN_LLM_FAMILIES:
        if f.model_name == 'qwen2.5-instruct':
            for s in f.model_specs:
                if s.model_format == 'ggufv2' and str(s.model_size_in_billions) == '1_5' and s.quantization == 'q4_k_m':
                    target_family = f
                    target_spec = s
                    break

    if not target_family:
        print("❌ Could not find qwen2.5-instruct in BUILTIN_LLM_FAMILIES")
        sys.exit(1)

    print(f"   Found family: {target_family.model_name}")
    print(f"   Context length: {target_family.context_length}")
    print(f"   Chat template: {bool(target_family.chat_template)}")

    llamacpp_config = {
        "n_ctx": 2048,
        "n_parallel": 1,
        "n_gpu_layers": 0,
        "n_threads": 4,
    }

    model = XllamaCppModel(
        model_uid="test-qwen",
        model_family=target_family,
        model_path=model_path,
        llamacpp_model_config=llamacpp_config,
    )
    print("   Instantiated XllamaCppModel. Calling model.load()...")
    model.load()
    print("   🎉 SUCCESS! model.load() completed successfully!")

    print("\n==> 5. Testing quick inference generation...")
    prompt = "Hello! Who are you?"
    print(f"   Prompt: {prompt}")
    res = model.chat(prompt=[{"role": "user", "content": prompt}], generate_config={"max_tokens": 30})
    print(f"   Response: {res}")
    print("   🎉 Qwen 2.5 1.5B is fully operational on CPU!")

except Exception as e:
    print(f"   ❌ XllamaCppModel test failed: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n==> 6. Testing Xinference client launch_model()...")
try:
    from xinference.client import RESTfulClient
    client = RESTfulClient("http://127.0.0.1:9997")
    client.login("admin", "Woli@1211")
    print("   Logged in to Xinference client.")
    running = client.list_models()
    print(f"   Currently running models: {list(running.keys())}")

    if "wolinet-pro" in running:
        print("   wolinet-pro already running. Terminating for clean test...")
        client.terminate_model("wolinet-pro")

    print("   Launching wolinet-pro via client.launch_model...")
    uid = client.launch_model(
        model_name="qwen2.5-instruct",
        model_uid="wolinet-pro",
        model_engine="llama.cpp",
        model_format="ggufv2",
        model_size_in_billions="1_5",
        quantization="q4_k_m",
        n_gpu_layers=0,
        n_ctx=2048,
        n_parallel=1,
    )
    print(f"   🎉 SUCCESS! Launched model with UID: {uid}")
    print(f"   Active models now: {list(client.list_models().keys())}")
except Exception as e:
    print(f"   ❌ client.launch_model failed: {type(e).__name__}: {e}")
    traceback.print_exc()
