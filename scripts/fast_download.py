#!/usr/bin/env python3
"""
Fast Parallel Range Downloader for Large Model Weights from Hugging Face.
Uses concurrent range requests to bypass single-stream CDN throttling.
"""
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def fast_download(url: str, output_path: str, token: str = None, num_threads: int = 16):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # Resolve redirects to get direct CDN download URL and total size
    session = requests.Session()
    resp = session.get(url, headers={**headers, "Range": "bytes=0-0"}, stream=True, allow_redirects=True)
    if resp.status_code not in (200, 206):
        raise RuntimeError(f"Failed to initiate download, status {resp.status_code}: {resp.text}")
    
    final_url = resp.url
    content_range = resp.headers.get("Content-Range", "")
    if "bytes 0-0/" in content_range:
        total_size = int(content_range.split("/")[-1])
    else:
        total_size = int(resp.headers.get("Content-Length", 0))
    
    print(f"Total size: {total_size:,} bytes ({total_size / (1024*1024):.2f} MB)")
    print(f"Target file: {output_path}")
    print(f"Threads: {num_threads}")
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_path = output_path + ".tmp"
    
    # Pre-allocate sparse file
    with open(temp_path, "wb") as f:
        f.seek(total_size - 1)
        f.write(b"\0")
    
    chunk_size = (total_size + num_threads - 1) // num_threads
    ranges = []
    for i in range(num_threads):
        start = i * chunk_size
        end = min(start + chunk_size - 1, total_size - 1)
        if start <= end:
            ranges.append((i, start, end))
    
    downloaded_bytes = 0
    t0 = time.time()
    
    def download_range(part_id: int, start: int, end: int):
        range_header = {"Range": f"bytes={start}-{end}"}
        req_headers = {**headers, **range_header}
        max_retries = 5
        for attempt in range(max_retries):
            try:
                r = requests.get(final_url, headers=req_headers, stream=True, timeout=30)
                if r.status_code not in (200, 206):
                    raise RuntimeError(f"Unexpected status: {r.status_code}")
                
                with open(temp_path, "r+b") as fp:
                    fp.seek(start)
                    written = 0
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            fp.write(chunk)
                            written += len(chunk)
                return part_id, written
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(1 + attempt)
    
    print("Starting parallel stream download...")
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(download_range, pid, s, e): (pid, s, e) for pid, s, e in ranges}
        completed = 0
        for future in as_completed(futures):
            part_id, written = future.result()
            completed += 1
            downloaded_bytes += written
            elapsed = time.time() - t0
            speed = (downloaded_bytes / (1024 * 1024)) / max(elapsed, 0.1)
            pct = (completed / len(ranges)) * 100
            print(f"[{completed:2d}/{len(ranges)}] Part {part_id:2d} done ({written/(1024*1024):.1f} MB) | Total: {pct:5.1f}% | Speed: {speed:5.2f} MB/s | Elapsed: {elapsed:.1f}s")
    
    total_elapsed = time.time() - t0
    avg_speed = (total_size / (1024 * 1024)) / total_elapsed
    print(f"Download complete in {total_elapsed:.1f}s (Average: {avg_speed:.2f} MB/s)")
    
    # Rename temp to target
    if os.path.exists(output_path):
        os.remove(output_path)
    os.rename(temp_path, output_path)
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    url = sys.argv[1]
    out = sys.argv[2]
    token = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("HF_TOKEN")
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    fast_download(url, out, token, threads)
