# Xinference CPU Model Deployment & Troubleshooting Guide

This guide documents the exact procedure for downloading, caching, and safely launching CPU-based LLM models (e.g., GGUF format with `llama.cpp`) on Xinference (`mitambo`) in self-hosted Docker and Dokploy environments.

---

## 1. Root Cause Analysis: The 500 Subactor Crash

### Symptoms
When clicking **Deploy** in the Xinference Web Dashboard or launching via API without explicit engine configuration, the UI displays:
```text
Server error: 500 - [address=0.0.0.0:XXXXX, pid=XX] Remote server unixsocket:///XXXXXXXX closed: 0 bytes read on a total of 11 expected bytes
```

### Why it Happens
1. **Unbounded Context Pre-allocation**: In Xinference, models like `deepseek-coder-instruct` declare a theoretical default context length of `16,384` tokens.
2. **Parallel Slots on Linux**: On Linux CPU hosts, `llama.cpp` defaults `n_parallel` to the available CPU core count (up to 8 slots).
3. **Memory Spike**: Allocating KV cache buffers for $8 \times 16,384 = 131,072$ tokens requires **12.5+ GB of RAM**.
4. **OOM Killer**: When memory exceeds the container or VPS RAM limit (e.g. 4 GB or 8 GB), the Linux kernel immediately terminates the subactor process (`pid`) with `SIGKILL`. The Unix domain socket abruptly closes mid-handshake (`0 bytes read on a total of 11 expected bytes`).

---

## 2. Model Cache Directory Structure

Xinference manages models in `/root/.xinference/cache/v2/`. For GGUF models:

- **Directory naming pattern**:  
  `/root/.xinference/cache/v2/<model_name>-<model_format>-<model_size_in_billions>b-<quantization>/`
  - *Example*: `/root/.xinference/cache/v2/deepseek-coder-instruct-ggufv2-1_3b-Q4_K_M/`

- **Filename pattern**:  
  Must match the template defined in the model spec (e.g. `deepseek-coder-1.3b-instruct.Q4_K_M.gguf`).

### Downloading Directly into the Cache
Inside the container, download the GGUF file directly into the designated cache directory:
```bash
mkdir -p /root/.xinference/cache/v2/deepseek-coder-instruct-ggufv2-1_3b-Q4_K_M

curl -L -o /root/.xinference/cache/v2/deepseek-coder-instruct-ggufv2-1_3b-Q4_K_M/deepseek-coder-1.3b-instruct.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/deepseek-coder-1.3b-instruct-GGUF/resolve/main/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
```

---

## 3. How to Launch Safely

### Method A: Through the Web Dashboard (Recommended for UI users)

1. Open the Xinference Dashboard (`https://mitambo.yourdomain.com`).
2. Navigate to **Launch Model** $\rightarrow$ **Language Models** $\rightarrow$ select the model (e.g. `deepseek-coder-instruct`).
3. Set the base parameters:
   - **Model Engine**: `llama.cpp`
   - **Model Format**: `ggufv2`
   - **Model Size**: `1_3`
   - **Quantization**: `Q4_K_M`
   - **N GPU Layers**: `0`
   - **GPU Count per Replica**: `CPU` (or leave default `auto` with `N GPU Layers: 0`)
   - **Model Path**: Leave **BLANK** (it automatically uses the cached file).
4. **CRITICAL STEP**: Click to expand **`Advanced Configuration`**:
   - Scroll to **Engine Additional Parameters: llama.cpp**
   - Click **+ Add**: Parameter `n_ctx`, Value: `2048`
   - Click **+ Add**: Parameter `n_parallel`, Value: `1`
5. Click **Deploy**.

---

### Method B: Single-Line One-Click Runner (Immune to Web Terminal Bugs)

Web-based terminals (like Dokploy / Portainer console) often drop characters when pasting multi-line text. Use this single-line command inside the container to authenticate and launch in one shot:

```bash
echo "aW1wb3J0IGhhc2hsaWIsIG9zLCBzeXMKZnJvbSB4aW5mZXJlbmNlLmNsaWVudCBpbXBvcnQgUkVTVGZ1bENsaWVudAoKRU5EUE9JTlQgPSAnaHR0cDovLzEyNy4wLjAuMTo5OTk3JwpVU0VSTkFNRSA9ICdhZG1pbicKUEFTU1dPUkQgPSAnV29saUAxMjExJwoKcHJpbnQoZidDb25uZWN0aW5nIHRvIHtFTkRQT0lOVH0uLi4nKQpjbGllbnQgPSBSRVNUZnVsQ2xpZW50KEVORFBPSU5UKQoKcHJpbnQoZidMb2dnaW5nIGluIGFzIHtVU0VSTkFNRX0uLi4nKQpjbGllbnQubG9naW4oVVNFUk5BTUUsIFBBU1NXT1JEKQpwcmludCgn4pyFIExvZ2luIHN1Y2Nlc3NmdWwhJykKCnRva2VuID0gY2xpZW50Ll9nZXRfdG9rZW4oKQpoYXNoZWRfZXAgPSBoYXNobGliLnNoYTI1NihFTkRQT0lOVC5lbmNvZGUoJ3V0Zi04JykpLmhleGRpZ2VzdCgpCmF1dGhfZGlyID0gJy9yb290Ly54aW5mZXJlbmNlL2F1dGgnCm9zLm1ha2VkaXJzKGF1dGhfZGlyLCBleGlzdF9vaz1UcnVlKQp3aXRoIG9wZW4ob3MucGF0aC5qb2luKGF1dGhfZGlyLCBoYXNoZWRfZXApLCAndycpIGFzIGY6CiAgICBmLndyaXRlKHRva2VuKQpwcmludCgn4pyFIFNhdmVkIENMSSB0b2tlbi4nKQoKcHJpbnQoJ0xhdW5jaGluZyBkZWVwc2Vlay1jb2Rlci1pbnN0cnVjdCAoQ1BVLCBuX2N0eD0yMDQ4LCBuX3BhcmFsbGVsPTEpLi4uJykKbW9kZWxfdWlkID0gY2xpZW50LmxhdW5jaF9tb2RlbCgKICAgIG1vZGVsX25hbWU9J2RlZXBzZWVrLWNvZGVyLWluc3RydWN0JywKICAgIG1vZGVsX2VuZ2luZT0nbGxhbWEuY3BwJywKICAgIG1vZGVsX2Zvcm1hdD0nZ2d1ZnYyJywKICAgIG1vZGVsX3NpemVfaW5fYmlsbGlvbnM9JzFfMycsCiAgICBxdWFudGl6YXRpb249J1E0X0tfTScsCiAgICBuX2dwdT1Ob25lLAogICAgbl9ncHVfbGF5ZXJzPTAsCiAgICBuX2N0eD0yMDQ4LAogICAgbl9wYXJhbGxlbD0xLAopCnByaW50KCfwn46JIFNVQ0NFU1MhIE1vZGVsIGlzIHJ1bm5pbmchJykKcHJpbnQoZidNb2RlbCBVSUQ6IHttb2RlbF91aWR9JykK" | base64 -d > /root/launch_model.py && python3 /root/launch_model.py
```

---

### Method C: Official `xinference` CLI Commands

When authentication is enabled (`XINFERENCE_AUTH_ADVANCED: "true"`), you must log in before launching:

```bash
# 1. Authenticate CLI
xinference login --endpoint http://127.0.0.1:9997 --username <USERNAME> --password <PASSWORD>

# 2. Launch with CPU memory limits
xinference launch \
  --endpoint http://127.0.0.1:9997 \
  --model-name deepseek-coder-instruct \
  --model-engine llama.cpp \
  --model-format ggufv2 \
  --size-in-billions 1_3 \
  --quantization Q4_K_M \
  --n-gpu none \
  --n_ctx 2048 \
  --n_parallel 1
```

> [!IMPORTANT]
> Always pass `--n-gpu none` for CPU deployments. Passing `--n-gpu 0` will trigger a validation error (`n_gpu must be greater than 0`).

---

## 4. Verification

Verify the running model from inside the container:

```bash
# List all running models
xinference list

# Test inference
python3 -c "
from xinference.client import RESTfulClient
client = RESTfulClient('http://127.0.0.1:9997')
model = client.get_model('deepseek-coder-instruct')
response = model.chat(messages=[{'role': 'user', 'content': 'Hello, are you ready?'}])
print(response['choices'][0]['message']['content'])
"
```
