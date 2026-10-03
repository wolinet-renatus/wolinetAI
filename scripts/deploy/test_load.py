#!/usr/bin/env python3
"""
Direct diagnostic to test XllamaCppModel loading for Qwen 2.5 1.5B and capture C++ errors.
"""

import os
import sys
import inspect
from xinference.model.llm import BUILTIN_LLM_FAMILIES
from xinference.model.llm.llama_cpp.core import XllamaCppModel

target_family = None
target_spec = None
for f in BUILTIN_LLM_FAMILIES:
    if f.model_name == 'qwen2.5-instruct':
        for s in f.model_specs:
            if s.model_format == 'ggufv2' and s.model_size_in_billions == '1_5' and s.quantization == 'q4_k_m':
                target_family = f
                target_spec = s
                break

if not target_family or not target_spec:
    print("❌ Could not find model family or spec")
    sys.exit(1)

print("==> Target model family:", target_family.model_name)
print("==> Target model spec:", target_spec.model_file_name_template)
print("==> XllamaCppModel.__init__ signature:", inspect.signature(XllamaCppModel.__init__))

model_path = "/root/.xinference/cache/v2/qwen2.5-instruct-ggufv2-1_5b-q4_k_m/qwen2.5-1.5b-instruct-q4_k_m.gguf"
print(f"==> Testing model file at {model_path} (size: {os.path.getsize(model_path) / (1024*1024):.2f} MB)")

# Initialize XllamaCppModel with actual model_path and safe context
init_kwargs = {
    "model_uid": "test-qwen",
    "model_family": target_family,
    "model_path": model_path,
    "n_ctx": 2048,
    "n_parallel": 1,
}

sig = inspect.signature(XllamaCppModel.__init__)
filtered_kwargs = {k: v for k, v in init_kwargs.items() if k in sig.parameters}
print("==> Passing kwargs to XllamaCppModel:", filtered_kwargs)

model = XllamaCppModel(**filtered_kwargs)

print("\n==> Calling model.load() — capturing C++ llama.cpp output below:")
try:
    model.load()
    print("\n🎉 SUCCESS! Qwen 2.5 1.5B loaded directly into llama.cpp without errors!")
except Exception as e:
    print(f"\n❌ Python exception caught: {type(e).__name__}: {e}")
