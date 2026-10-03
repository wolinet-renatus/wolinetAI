#!/usr/bin/env python3
"""
Direct diagnostic to test XllamaCppModel loading for Qwen 2.5 1.5B and capture C++ errors.
"""

import os
import sys
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

model = XllamaCppModel(
    model_uid="test-qwen",
    model_family=target_family,
    model_spec=target_spec,
    quantization="q4_k_m",
    n_ctx=2048,
    n_parallel=1,
)

print("==> Calling model.load() — capturing C++ engine output:")
try:
    model.load()
    print("🎉 SUCCESS! Qwen 2.5 1.5B loaded directly into llama.cpp without errors!")
except Exception as e:
    print(f"\n❌ Python exception caught: {type(e).__name__}: {e}")
