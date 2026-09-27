# Models & Declarative Model Registrations

This directory contains declarative model registrations (`registrations/*.json`) configured to pull directly from Hugging Face without requiring manual file downloads or local file paths.

## Structure
```
models/
└── registrations/
    ├── wolinex-coder.json            # Sovereign AI Coding Model (Qwen/Qwen2.5-Coder-3B-Instruct-GGUF)
    ├── qwen2.5-coder-3b.json         # Qwen2.5-Coder 3B GGUF manifest (Hugging Face direct)
    ├── deepseek-coder-1.3b.json      # DeepSeek Coder 1.3B GGUF (TheBloke/deepseek-coder-1.3b-instruct-GGUF)
    ├── qwen2.5-omni-3b.json          # Omni multimodal vision/audio manifest (Qwen/Qwen2.5-Omni-3B)
    ├── qwen-image-2.1.json           # Image diffusion model manifest (0xSojalSec/Qwen-Image-2.1-Uncensored-GGUF)
    ├── bge-small-en-v1.5.json        # Fast sentence embedding manifest (BAAI/bge-small-en-v1.5)
    ├── harrier-oss-v1-0.6b.json      # High-performance 1024d embedding (microsoft/harrier-oss-v1-0.6b)
    ├── bge-reranker-v2-m3.json       # RAG reranker manifest (BAAI/bge-reranker-v2-m3)
    ├── whisper-small.json            # Fast speech-to-text manifest (openai/whisper-small)
    ├── whisper-large-v3-turbo.json   # SOTA speech-to-text (openai/whisper-large-v3-turbo)
    └── magpie-tts.json               # Multilingual 12-language TTS (nvidia/magpie_tts_multilingual_357m)
```

## Direct Hugging Face Model Ingestion
Instead of manual downloads or machine-specific local paths (`file:///...`), all models specify their direct Hugging Face repository and file templates:
1. When launched via `./scripts/start_platform.sh` or the Xinference Web UI, Xinference automatically downloads and caches model weights from Hugging Face into `~/.xinference/cache/`.
2. Model sources and revisions are clearly tracked declaratively without engine source code modifications.
3. Live cloud server deployments work out-of-the-box with zero bottlenecks: simply start the platform with `scripts/start_platform.sh`.

## Model Hub Sources Reference
| Model | Type | Hugging Face Repository | Quantization / Format |
|---|---|---|---|
| `wolinex-coder` | LLM / Code | [`Qwen/Qwen2.5-Coder-3B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF) | `q4_k_m`, `q8_0`, etc. |
| `qwen2.5-coder-3b` | LLM / Code | [`Qwen/Qwen2.5-Coder-3B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF) | `q4_k_m`, `q8_0`, etc. |
| `deepseek-coder-1.3b` | LLM / Code | [`TheBloke/deepseek-coder-1.3b-instruct-GGUF`](https://huggingface.co/TheBloke/deepseek-coder-1.3b-instruct-GGUF) | `q4_k_m`, `q8_0`, etc. |
| `qwen-image-2.1` | Diffusion | [`0xSojalSec/Qwen-Image-2.1-Uncensored-GGUF`](https://huggingface.co/0xSojalSec/Qwen-Image-2.1-Uncensored-GGUF) | `Q4_K_M`, `Q8_0`, etc. |
| `qwen2.5-omni-3b` | Multimodal | [`Qwen/Qwen2.5-Omni-3B`](https://huggingface.co/Qwen/Qwen2.5-Omni-3B) | Official PyTorch / Safetensors |
| `bge-small-en-v1.5` | Embedding | [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) | PyTorch / Safetensors (384d) |
| `harrier-oss-v1-0.6b` | Embedding | [`microsoft/harrier-oss-v1-0.6b`](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) | PyTorch / Safetensors (1024d, 32k ctx) |
| `bge-reranker-v2-m3` | Reranker | [`BAAI/bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) | PyTorch / Safetensors |
| `whisper-small` | Audio ASR | [`openai/whisper-small`](https://huggingface.co/openai/whisper-small) | PyTorch / Safetensors (244M) |
| `whisper-large-v3-turbo` | Audio ASR | [`openai/whisper-large-v3-turbo`](https://huggingface.co/openai/whisper-large-v3-turbo) | PyTorch / Safetensors (809M) |
| `magpie-tts` | Audio TTS | [`nvidia/magpie_tts_multilingual_357m`](https://huggingface.co/nvidia/magpie_tts_multilingual_357m) | PyTorch / Safetensors / GGUF |

## Registering Models
To register all manifests with a running Xinference engine:
```bash
./scripts/register_models.sh
```

---

## Multimodal (Vision & Audio) Integration Guide

### 1. Vision via OpenAI Client
Vision-capable models (e.g., `qwen2.5-omni`, `qwen2.5-vl-instruct`) accept image inputs via the standard OpenAI Chat Completions API. Images can be provided as remote HTTP URLs or base64 data URIs:

```python
import openai
import base64

client = openai.Client(
    base_url="http://127.0.0.1:4000/v1",  # Wolinet AI Unified Gateway
    api_key="sk-wolinet-admin-2026"
)

# Option A: Remote Image URL
response = client.chat.completions.create(
    model="wolinex-omni",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe the architecture shown in this diagram:"},
            {"type": "image_url", "image_url": {"url": "https://example.com/system-architecture.png"}}
        ]
    }]
)
print(response.choices[0].message.content)

# Option B: Local Image Base64
with open("screenshot.png", "rb") as f:
    b64_img = base64.b64encode(f.read()).decode("utf-8")

response = client.chat.completions.create(
    model="wolinex-omni",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze this error screenshot and provide the fix:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
        ]
    }]
)
```

### 2. Controlling Memory with `limit_mm_per_prompt`
When deploying vision models on vLLM backend, pass `limit_mm_per_prompt` at launch to cap the maximum number of images per conversation turn and prevent GPU out-of-memory (OOM):
```bash
xinference launch \
  --model-engine vLLM \
  --model-name qwen2.5-vl-instruct \
  --size-in-billions 3 \
  --model-format pytorch \
  --quantization none \
  --limit_mm_per_prompt '{"image": 4}'
```

---

## Image Generation, Variation & OCR Guide

Wolinet AI routes all image endpoints (`/v1/images/*`) through the unified gateway on port 4000 directly to Xinference.

### 1. Text-to-Image Generation (`/v1/images/generations`)
```bash
curl -X POST http://127.0.0.1:4000/v1/images/generations \
  -H "Authorization: Bearer sk-wolinet-admin-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-image-2.1",
    "prompt": "Futuristic cloud server rack glowing in cyan and purple, cinematic lighting, 8k"
  }'
```

### 2. Image-to-Image Variation (`/v1/images/variations`)
```bash
curl -X POST http://127.0.0.1:4000/v1/images/variations \
  -H "Authorization: Bearer sk-wolinet-admin-2026" \
  -F model=qwen-image-2.1 \
  -F image=@input_reference.jpg \
  -F prompt="Convert this sketch into a photorealistic corporate logo"
```

### 3. OCR & Whole-Document Parsing (`/v1/images/ocr`)
Extract raw text or run whole-document layout analysis on images and PDFs:
```bash
# Per-page OCR on Image or PDF
curl -X POST http://127.0.0.1:4000/v1/images/ocr \
  -H "Authorization: Bearer sk-wolinet-admin-2026" \
  -F model=whisper-large-v3-turbo \
  -F image=@document.pdf \
  -F 'kwargs={"pages": [1, 2], "dpi": 300}'

# Whole-Document Parsing (DeepDoc layout, table extraction, reading order)
curl -X POST http://127.0.0.1:4000/v1/images/ocr \
  -H "Authorization: Bearer sk-wolinet-admin-2026" \
  -F model=whisper-large-v3-turbo \
  -F image=@contract.pdf \
  -F 'kwargs={"task": "parse", "zoomin": 3, "image_scope": "table_figure"}'
```

---

## Memory Optimization for Large Image & Diffusion Models

Running modern diffusion models (Flux.1, SD3.5, Qwen-Image) on consumer GPUs or cost-effective cloud nodes requires deliberate memory management:

| Flag / Parameter | Description | Recommended Usage |
|---|---|---|
| `--cpu_offload True` | Dynamically offloads idle pipeline components to CPU RAM during execution. | **Essential for < 16GB GPUs**. Reduces VRAM requirement dramatically with negligible latency impact. |
| `--gguf_quantization Q4_K_M` | Uses GGUF quantized weights for diffusion transformers (Q2_K through Q8_0). | Drops FLUX.1 VRAM to ~5 GiB (Q2_K) or ~8 GiB (Q4_K_M). |
| `--quantize_text_encoder <layer>` | Quantizes the heavy T5-XXL text encoder to 8-bit precision via bitsandbytes. | Enabled by default in Xinference v0.16.1+ for Flux.1 and SD3.5. |
| `--transformer_nf4 True` | Applies NF4 quantization to transformer blocks. | Default on SD3.5 Large models. |
| `--lightning_version 4steps-V1.0` | Uses distilled Lightning LoRA weights to reduce inference steps to 4 or 8. | Cuts image generation time from ~34s to ~3s! |

**Example Launch Command**:
```bash
xinference launch \
  --model-name qwen-image-2.1 \
  --model-type image \
  --model-engine diffusers \
  --gguf_quantization Q4_K_M \
  --cpu_offload True
```
