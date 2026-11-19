#!/usr/bin/env python3
import os
import sys
import time
import urllib.request
import concurrent.futures

def download_file_parallel(url: str, dest_path: str, num_threads: int = 8, chunk_size: int = 16 * 1024 * 1024):
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    
    # 1. Get file size
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
    with urllib.request.urlopen(req, timeout=15) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        accept_ranges = resp.headers.get("Accept-Ranges", "none")

    print(f"[{os.path.basename(dest_path)}] Size: {total_size / (1024**3):.2f} GB ({total_size} bytes), Ranges: {accept_ranges}")

    if os.path.exists(dest_path) and os.path.getsize(dest_path) == total_size:
        print(f"[{os.path.basename(dest_path)}] Already downloaded completely. Skipping.")
        return

    part_dest = dest_path + ".download"
    # Pre-allocate or open file
    with open(part_dest, "wb") as f:
        f.seek(total_size - 1)
        f.write(b"\0")

    # Generate chunk ranges
    ranges = []
    start = 0
    while start < total_size:
        end = min(start + chunk_size - 1, total_size - 1)
        ranges.append((start, end))
        start = end + 1

    total_chunks = len(ranges)
    downloaded_bytes = 0
    start_time = time.time()
    last_print = start_time

    # Thread worker
    def fetch_chunk(byte_range):
        b_start, b_end = byte_range
        chunk_req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Range": f"bytes={b_start}-{b_end}"
            }
        )
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(chunk_req, timeout=30) as r:
                    data = r.read()
                    if len(data) != (b_end - b_start + 1):
                        raise IOError(f"Incomplete chunk {b_start}-{b_end}: got {len(data)}")
                    return (b_start, data)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(1 + attempt)

    print(f"[{os.path.basename(dest_path)}] Downloading {total_chunks} blocks with {num_threads} parallel threads...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        with open(part_dest, "r+b") as out_f:
            future_to_range = {executor.submit(fetch_chunk, r): r for r in ranges}
            for future in concurrent.futures.as_completed(future_to_range):
                b_start, data = future.result()
                out_f.seek(b_start)
                out_f.write(data)
                downloaded_bytes += len(data)
                
                now = time.time()
                if now - last_print >= 5:
                    elapsed = now - start_time
                    speed_mb = (downloaded_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = (downloaded_bytes / total_size) * 100
                    print(f"  {os.path.basename(dest_path)}: {downloaded_bytes / (1024*1024):.1f} / {total_size / (1024*1024):.1f} MB ({pct:.1f}%) @ {speed_mb:.2f} MB/s")
                    last_print = now

    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(part_dest, dest_path)
    elapsed = time.time() - start_time
    print(f"[{os.path.basename(dest_path)}] ✅ Complete in {elapsed:.1f}s ({total_size / (1024**3):.2f} GB)!")

if __name__ == "__main__":
    tasks = [
        ("https://huggingface.co/mradermacher/DeepSeek-V4-Pro-Qwen3.5-4B-GGUF/resolve/main/DeepSeek-V4-Pro-Qwen3.5-4B.Q4_K_M.gguf",
         "inference/models/llm/DeepSeek-V4-Pro-Qwen3.5-4B.Q4_K_M.gguf"),
        ("https://huggingface.co/XHToken/Spark-X2.6-1.7B-GGUF/resolve/main/Spark-X2.6-1.7B-Q8_0.gguf",
         "inference/models/llm/Spark-X2.6-1.7B-Q8_0.gguf"),
        ("https://huggingface.co/Solstice-AI/GLM-5.3-Flash-UNCENSORED-GGUF/resolve/main/speculative/GLM-5.3-Flash-DFlash2-Q8_0.gguf",
         "inference/models/dflash/GLM-5.3-Flash-DFlash2-Q8_0.gguf"),
    ]
    
    for url, dest in tasks:
        download_file_parallel(url, dest, num_threads=8)

