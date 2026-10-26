import json
import time
import requests
import re
import sys

BASE_URL = "http://127.0.0.1:8081"

# Generate fresh admin token
sys.path.insert(0, "/Users/apple/Documents/wolinetai/apps/web-client/backend")
from open_webui.models.users import Users
from open_webui.utils.auth import create_token
import asyncio

async def get_admin_token():
    res = await Users.get_users()
    for u in res.get("users", []):
        if u.role == "admin":
            return create_token(data={"id": u.id})
    return create_token(data={"id": res.get("users", [])[0].id})

token = asyncio.run(get_admin_token())
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "text/event-stream"
}

def stream_chat(prompt: str, test_name: str, model: str = "Wolinet Max"):
    print(f"\n{'='*70}\n[TEST] {test_name}\n[PROMPT] {prompt}\n[MODEL] {model}\n{'='*70}")
    t0 = time.time()
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": True
    }
    
    events_received = []
    content_chunks = []
    sources_received = []
    
    try:
        with requests.post(f"{BASE_URL}/api/chat/completions", headers=headers, json=payload, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
                return False, resp.text, []
            
            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_obj = json.loads(data_str)
                        # Check for source/citation events
                        if "sources" in chunk_obj:
                            sources_received.extend(chunk_obj["sources"])
                        if "data" in chunk_obj and isinstance(chunk_obj["data"], dict):
                            if "urls" in chunk_obj["data"]:
                                events_received.append(chunk_obj["data"])
                        # Check for message deltas
                        choices = chunk_obj.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            c = delta.get("content")
                            if c:
                                content_chunks.append(c)
                                print(c, end="", flush=True)
                    except Exception:
                        pass
    except Exception as e:
        print(f"\n[EXCEPTION] {e}")
        return False, str(e), []
        
    full_content = "".join(content_chunks).strip()
    elapsed = time.time() - t0
    print(f"\n\n[COMPLETED in {elapsed:.2f}s]")
    print(f"[SOURCES COUNT]: {len(sources_received)}")
    if sources_received:
        for s in sources_received:
            src_info = s.get("source", {})
            print(f" - Source: {src_info.get('name') or src_info.get('url')} (id: {src_info.get('id')})")
            
    return True, full_content, sources_received

if __name__ == "__main__":
    print(f"Testing Wolinet AI Sovereign System with Token: {token[:25]}...")
    
    # 1. Test Item 1: Autonomous Web Search
    s1, c1, src1 = stream_chat("team score for tanzania league today", "ITEM 1: Autonomous Web Search")
    
    # Check for refusal keywords in response
    refusal_keywords = [
        "cannot browse", "can't browse", "don't have real-time", "do not have real-time",
        "unable to browse", "unable to access", "don't have access to current",
        "primary function is to assist with general information", "i cannot provide real-time"
    ]
    refusal_found_1 = any(kw in c1.lower() for kw in refusal_keywords)
    print(f"\n--- Item 1 Evaluation ---")
    print(f"Refusal Detected: {refusal_found_1}")
    print(f"Contains Scores / League data: {any(kw in c1.lower() for kw in ('score', 'tanzania', 'union', 'namungo', 'sugar', 'azam', 'league', 'postponed', 'vs', '-'))}")
    
    # 2. Test Item 2: Direct URL Web Browsing
    s2, c2, src2 = stream_chat("check here https://www.livescore.com/en/football/tanzania/premier-league/", "ITEM 2: Direct URL Live Web Browsing")
    refusal_found_2 = any(kw in c2.lower() for kw in refusal_keywords)
    print(f"\n--- Item 2 Evaluation ---")
    print(f"Refusal Detected: {refusal_found_2}")
    print(f"Contains Live Match Data: {any(kw in c2.lower() for kw in ('namungo', 'coastal', 'jkt', 'kagera', 'azam', 'postponed', 'results', 'fixtures', '2 - 1', '1 - 0'))}")
    
    # 3. Test Item 3: SVG Logo Graphic
    s3, c3, src3 = stream_chat("design a logo for Wolinet AI in SVG", "ITEM 3: SVG Vector Graphics Creation")
    print(f"\n--- Item 3 Evaluation ---")
    print(f"Contains SVG XML Code: {'<svg' in c3.lower()}")
    print(f"Brand Rationale Included: {any(kw in c3.lower() for kw in ('wolinet', 'sovereign', 'intelligence', 'design', 'brand'))}")
