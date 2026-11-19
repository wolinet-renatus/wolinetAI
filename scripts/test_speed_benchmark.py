#!/usr/bin/env python3
"""Real generation speed, TTFT, and latency benchmark for single lightweight model."""

import json
import os
import time
import requests

MITAMBO_URL = "http://127.0.0.1:9997"
RUST_CORE_URL = "http://127.0.0.1:8088"
LANGO_URL = "http://127.0.0.1:4000"

# 1. Login to Mitambo to get auth token
from xinference.client import RESTfulClient
client = RESTfulClient(MITAMBO_URL)
client.login(os.environ.get("UI_USERNAME", "admin"), os.environ.get("UI_PASSWORD", ""))
mitambo_headers = client._headers

test_prompt = (
    "Explain the core architectural differences between Monolithic and Microservices "
    "systems in terms of throughput, fault isolation, and deployment. "
    "Provide a concise, highly technical summary with concrete trade-offs."
)

models_to_test = [
    {
        "name": "Deepseeker Coder (Direct Mitambo Engine :9997)",
        "endpoint": f"{MITAMBO_URL}/v1/chat/completions",
        "headers": mitambo_headers,
        "payload": {
            "model": "deepseeker-coder",
            "messages": [{"role": "user", "content": test_prompt}],
            "max_tokens": 150,
            "temperature": 0.2,
            "stream": True,
        },
    },
    {
        "name": "Deepseeker Coder (via Rust Defense Core :8088)",
        "endpoint": f"{RUST_CORE_URL}/v1/chat/completions",
        "headers": {"Content-Type": "application/json"},
        "payload": {
            "model": "Deepseeker Coder",
            "messages": [{"role": "user", "content": test_prompt}],
            "max_tokens": 150,
            "temperature": 0.2,
            "stream": True,
        },
    },
    {
        "name": "Deepseeker Coder (via Lango Sovereign Gateway :4000)",
        "endpoint": f"{LANGO_URL}/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q",
            "Content-Type": "application/json",
        },
        "payload": {
            "model": "Deepseeker Coder",
            "messages": [{"role": "user", "content": test_prompt}],
            "max_tokens": 150,
            "temperature": 0.2,
            "stream": True,
        },
    },
    {
        "name": "Legacy Alias: Wolinet Pro -> Deepseeker Coder (Lango :4000)",
        "endpoint": f"{LANGO_URL}/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q",
            "Content-Type": "application/json",
        },
        "payload": {
            "model": "Wolinet Pro",
            "messages": [{"role": "user", "content": test_prompt}],
            "max_tokens": 150,
            "temperature": 0.2,
            "stream": True,
        },
    },
]

print("=" * 80)
print("🚀 RUNNING REAL GENERATION SPEED & LATENCY BENCHMARK")
print("Target: Single Lightweight Fallback Model (DeepSeek-R1-Coder-0.5B)")
print("Hardware: Intel Core i9 (32GB Host RAM, 8-Thread Execution)")
print("Target Threshold: >= 65 tokens/sec")
print("=" * 80)

results = []

for item in models_to_test:
    name = item["name"]
    endpoint = item["endpoint"]
    headers = item["headers"]
    payload = item["payload"]

    print(f"\n[Benchmarking] {name}...")
    t0 = time.perf_counter()

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=120)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        continue

    if resp.status_code != 200:
        print(f"❌ Error {resp.status_code}: {resp.text}")
        continue

    ttft = None
    chunks_count = 0
    generated_text = ""
    first_token_time = None

    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            data_content = line_str[6:].strip()
            if data_content == "[DONE]":
                break
            try:
                parsed = json.loads(data_content)
                delta = parsed.get("choices", [{}])[0].get("delta", {})
                content_chunk = delta.get("content", "")
                if content_chunk:
                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                        ttft = (first_token_time - t0) * 1000.0  # ms
                    generated_text += content_chunk
                    chunks_count += 1
            except Exception:
                pass

    t_end = time.perf_counter()
    total_time = t_end - t0
    gen_time = (t_end - first_token_time) if first_token_time else total_time
    tok_per_sec = (chunks_count / gen_time) if gen_time > 0 else 0.0

    print(f"  ⚡ TTFT (Time to First Token): {ttft:.1f} ms" if ttft else "  ⚡ TTFT: N/A")
    print(f"  🏎️  Throughput: {tok_per_sec:.2f} tokens/second")
    print(f"  📊 Generated Tokens: {chunks_count} tokens in {total_time:.2f}s total ({gen_time:.2f}s gen)")
    status = "✅ EXCEEDS 65+ TOK/S TARGET" if tok_per_sec >= 65 else "⚠️ BELOW 65 TOK/S"
    print(f"  🎯 Status: {status}")
    print(f"  📝 Preview: {generated_text[:120].strip()}...")

    results.append({
        "name": name,
        "ttft_ms": ttft,
        "tok_per_sec": tok_per_sec,
        "tokens": chunks_count,
        "status": status,
    })

print("\n" + "=" * 80)
print("BENCHMARK SUMMARY")
print("=" * 80)
for r in results:
    print(f"- {r['name']}: {r['tok_per_sec']:.1f} tok/s | TTFT: {r['ttft_ms']:.1f} ms | {r['status']}")
print("=" * 80)
