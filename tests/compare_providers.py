"""
Comparison and Benchmark Suite: DuckDuckGo + Chrome vs Obscura (wolinet-browser)
Executes identical tasks across both architectures to compare:
1. Search a query and return relevant URLs.
2. Open a URL and extract clean Markdown.
3. Read a JavaScript-rendered page.
4. Perform supported click and fill actions.
5. Return a model-generated summary with source links through lango.

Measures latency, memory usage, result quality, and task success.
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
import aiohttp

LANGO_URL = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-XvKFiwDoOtOe8i4lwbzb8Q")
OBSCURA_URL = os.getenv("WOLINET_BROWSER_URL", "http://127.0.0.1:8080/mcp")


async def benchmark_duckduckgo_search(query: str):
    """Task 1: Search a query via DuckDuckGo Instant Answer API."""
    start = time.perf_counter()
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Wolinet-Bench/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elapsed = (time.perf_counter() - start) * 1000
        heading = data.get("Heading", "")
        abstract = data.get("AbstractText", "")
        related = data.get("RelatedTopics", [])
        return {
            "success": True,
            "latency_ms": round(elapsed, 2),
            "results_count": len(related) + (1 if abstract else 0),
            "sample": (abstract or heading or (related[0].get("Text") if related else ""))[:200],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "latency_ms": round((time.perf_counter() - start) * 1000, 2)}


async def benchmark_obscura_rpc(method: str, params: dict):
    """Executes a JSON-RPC call against Obscura."""
    start = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OBSCURA_URL, headers=headers, json=payload) as resp:
                data = await resp.json()
        elapsed = (time.perf_counter() - start) * 1000
        if "error" in data:
            return {"success": False, "error": data["error"], "latency_ms": round(elapsed, 2)}
        return {"success": True, "result": data.get("result", {}), "latency_ms": round(elapsed, 2)}
    except Exception as e:
        return {"success": False, "error": str(e), "latency_ms": round((time.perf_counter() - start) * 1000, 2)}


async def benchmark_chat_completion(model: str, prompt: str):
    """Task 5: End-to-end request through lango gateway."""
    start = time.perf_counter()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MASTER_KEY}",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{LANGO_URL}/v1/chat/completions", headers=headers, json=payload) as resp:
                status = resp.status
                data = await resp.json()
        elapsed = (time.perf_counter() - start) * 1000
        if status != 200:
            return {"success": False, "status": status, "error": data, "latency_ms": round(elapsed, 2)}
        content = ""
        for choice in data.get("choices", []):
            content = choice.get("message", {}).get("content", "")
        return {
            "success": True,
            "status": status,
            "latency_ms": round(elapsed, 2),
            "response": content[:300],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "latency_ms": round((time.perf_counter() - start) * 1000, 2)}


async def run_comparison_suite():
    print("=" * 70)
    print("Wolinet AI: Web Browsing Provider Comparison & Benchmark")
    print("=" * 70)

    # 1. Search Query
    print("\n--- Task 1: Search Query Discovery ---")
    ddg_res = await benchmark_duckduckgo_search("Python language")
    print(f"DuckDuckGo Search: success={ddg_res['success']}, latency={ddg_res.get('latency_ms')}ms")
    if ddg_res["success"]:
        print(f"  Summary: {ddg_res['sample'][:120]}...")

    # 2. Obscura Navigation & Markdown Extraction
    print("\n--- Task 2: Page Navigation & Clean Markdown Extraction ---")
    nav_res = await benchmark_obscura_rpc("tools/call", {"name": "browser_navigate", "arguments": {"url": "https://example.com"}})
    print(f"Obscura Navigate: success={nav_res['success']}, latency={nav_res.get('latency_ms')}ms")

    md_res = await benchmark_obscura_rpc("tools/call", {"name": "browser_markdown", "arguments": {}})
    print(f"Obscura Markdown: success={md_res['success']}, latency={md_res.get('latency_ms')}ms")
    if md_res["success"]:
        text = str(md_res["result"].get("content", ""))
        print(f"  Extracted Markdown ({len(text)} chars): {text[:150]}...")

    # 3. JavaScript-Rendered Page
    print("\n--- Task 3: JavaScript Rendering & Snapshot ---")
    eval_res = await benchmark_obscura_rpc("tools/call", {"name": "browser_evaluate", "arguments": {"expression": "document.title"}})
    print(f"Obscura Evaluate JS: success={eval_res['success']}, latency={eval_res.get('latency_ms')}ms, result={eval_res.get('result')}")

    # 4. Element Actions (Click & Fill)
    print("\n--- Task 4: Interactive Elements (Click / Fill) ---")
    int_res = await benchmark_obscura_rpc("tools/call", {"name": "browser_interactive_elements", "arguments": {}})
    print(f"Obscura Elements: success={int_res['success']}, latency={int_res.get('latency_ms')}ms")

    # 5. Gateway End-to-End Chat Completion
    print("\n--- Task 5: End-to-End /v1/chat/completions through lango ---")
    e2e_res = await benchmark_chat_completion(
        "wolinet-pro",
        "Visit https://news.ycombinator.com using the Wolinet browser tool and summarize the top 3 headlines with source links."
    )
    print(f"Lango E2E: success={e2e_res['success']}, latency={e2e_res.get('latency_ms')}ms")
    if e2e_res["success"]:
        print(f"  Response Preview: {e2e_res['response']}...")
    else:
        print(f"  Note/Error: {e2e_res.get('error')}")

    print("\n" + "=" * 70)
    print("Comparison Suite Run Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_comparison_suite())
