#!/usr/bin/env python3
"""
Wolinet Max — Real-Time Sub-Second Streaming Client
Demonstrates instant token-by-token streaming from Wolinet Max with <0.7s TTFT.
"""

import json
import sys
import time
import urllib.request

API_BASE = "http://localhost:4000/v1"
API_KEY = "sk-XvKFiwDoOtOe8i4lwbzb8Q"
MODEL = "Wolinet Max"


def stream_chat(prompt: str, model: str = MODEL):
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": True,  # Enables real-time server-sent token streaming
        "temperature": 0.7,
    }

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
    )

    print(f"\n[Wolinet Max Client] Sending prompt: '{prompt}'")
    print("[Wolinet Max Client] Awaiting stream (watch instant token-by-token output):\n")

    t0 = time.time()
    first_token_time = None
    chunk_count = 0

    total_tokens_approx = 0
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or line == "data: [DONE]":
                continue
            if line.startswith("data: "):
                chunk_count += 1
                if first_token_time is None:
                    first_token_time = time.time()
                    ttft = first_token_time - t0
                    print(f"⚡ [First token received in {ttft:.2f}s]\n")

                data = json.loads(line[6:])
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    total_tokens_approx += len(content.split())
                    sys.stdout.write(content)
                    sys.stdout.flush()

    total_time = time.time() - t0
    gen_time = (total_time - ttft) if (first_token_time and total_time > ttft) else total_time
    tps = (total_tokens_approx * 1.33) / gen_time if gen_time > 0 else 0
    print(f"\n\n⚡ Summary: TTFT={ttft:.2f}s | Gen Time={gen_time:.2f}s | Velocity=~{tps:.1f} tokens/s across {chunk_count} chunks.")


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Write a short 3-line poem about sovereign artificial intelligence."
    stream_chat(prompt)
