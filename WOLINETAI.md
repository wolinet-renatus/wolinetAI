# Wolinet AI: Enterprise Self-Hosted AI Platform & Gateway

> **High-Performance Self-Hosted AI Platform with Intelligent Hybrid Routing ($0 Local GGUF Inference + On-Demand Cloud APIs) for Autonomous Coding Agents and Enterprise Services.**

---

## 1. Architecture Overview

Wolinet AI is designed for organizations and developers who want **enterprise-grade autonomy, zero data leakage, and radical cost reduction**. 

Autonomous coding agents typically consume 20–50 turns per task (reading trees, grepping files, running unit tests, linting). Routing 100% of these calls to frontier cloud APIs costs thousands of dollars. Wolinet AI solves this by deploying a **Tiered Hybrid Architecture**:

```mermaid
flowchart TD
    subgraph Clients["Client Applications & Agentic IDEs"]
        Agent["🤖 Agentic Coding Assistant\n(apps/agentic-coder)"]
        IDE["💻 IDE Extensions / Cursor / VS Code"]
        Web["🌐 Web & Mobile Dashboards"]
    end

    subgraph Gateway["Wolinet AI Gateway Layer (LiteLLM Proxy - :4000)"]
        Router["⚡ Unified OpenAI API Gateway (/v1)"]
        Budget["💰 Budget Guardrails & Cost Tracking"]
        Failover["🔄 Latency Routing & Cloud Fallbacks"]
    end

    subgraph Tier1["Tier 1: Local High-Throughput Engine (Xinference - :9997)"]
        LocalEngine["🚀 Native C++ Engine (xllamacpp / llama.cpp)"]
        Coder["wolinex-coder (GGUF 3B)\n• Fast tool calling & code edits"]
        Omni["wolinex-omni (GGUF 3B)\n• Local voice & vision"]
        Embed["bge-embeddings (Local)\n• Semantic Code Search & RAG"]
        Cost1["COST: $0 / token"]
    end

    subgraph Tier2["Tier 2 & 3: Cloud Provider APIs (On-Demand Pay-per-use)"]
        Frontier["🧠 Frontier Reasoning & Deep Architecture\n• Claude 3.5 Sonnet\n• DeepSeek-R1 (671B)\n• OpenAI GPT-4o"]
        Video["🎬 Heavy Compute Multi-Modal\n• Kling AI Video\n• Runway Gen-3 / Luma Dream Machine\n• Fal.ai Flux Pro"]
        Cost2["COST: Pay-as-you-go Credits"]
    end

    Clients -->|Single Endpoint: http://localhost:4000/v1| Router
    Router --> Budget --> Failover
    Failover -->|"80% Volume (Bulk Code/Tools)"| LocalEngine
    LocalEngine --> Coder
    LocalEngine --> Omni
    LocalEngine --> Embed
    Failover -->|"20% Volume (Complex Logic / Video)"| Tier2
    Tier2 --> Frontier
    Tier2 --> Video
```

---

## 2. Directory Structure

```text
wolinetai/
├── WOLINETAI.md                 # Primary Architecture & Contributor Manifesto
├── README.md                    # Quickstart & Repository Overview
├── Makefile                     # Developer Ergonomic CLI (make start, make health, etc.)
├── docker-compose.yml           # Production Docker deployment for Live Server
├── .env                         # Environment variables (DB, Redis, Master Keys, Assets)
│
├── gateway/                     # 🛡️ Cloned Open-Source AI Gateway Layer (LiteLLM Full Source)
│   ├── litellm/                 # Full LiteLLM core Python codebase (Editable live link)
│   │   ├── proxy/               # FastAPI proxy server, routers, auth, DB client
│   │   │   └── payments/        # 🇹🇿 Native Tanzania Payment Gateway Subsystem
│   │   │       └── tanzania/    # M-Pesa, Tigo Pesa, Airtel Money, Selcom & AzamPay integration
│   │   └── ...                  # Provider adapters, router, budget logic
│   ├── assets/                  # 🎨 Wolinet AI Branding Assets (Logos & Favicons)
│   │   ├── wolinet_logo.png     # Custom light logo
│   │   ├── wolinet_logo_dark.png# Custom dark logo
│   │   └── favicon.ico / .png   # Custom Wolinet favicon
│   ├── ui/                      # LiteLLM Next.js Admin Management Dashboard
│   ├── config.yaml              # Multi-tier model routing, fallbacks, & budget rules
│   └── run_gateway.sh           # Local Gateway launcher script (Port 4000)
│
├── inference/                   # 🚀 Core High-Performance Engine (Xinference)
│   ├── xinference/              # Distributed Actor-based model execution engine
│   ├── frontend/                # Next.js Cluster Administration Web UI
│   └── ...                      # Multi-backend runners (llama.cpp, vLLM, SGLang, Diffusers)
│
├── models/                      # 🧠 Local Model Weights & Specs
│   ├── *.gguf                   # Downloaded quantized model weights
│   └── registrations/           # Declarative JSON manifests (Version 2 Specs)
│       ├── wolinex-coder.json   # Wolinet Coder local definition
│       ├── qwen2.5-omni-3b.json # Local voice/vision multi-modal
│       └── qwen-image-2.1.json  # Local diffusion transformer
│
├── apps/                        # 🤖 Client Applications
│   ├── web-client/              # 🌐 Wolinet AI Studio (Hybrid Web Console on Port 8080)
│   │   └── index.html           # Full interactive studio, real-time metrics, & M-Pesa checkout
│   └── agentic-coder/           # Reference Autonomous Coding Agent (CLI + Tools)
│       ├── main.py              # Interactive terminal agent loop
│       └── src/
│           ├── agent.py         # Autonomous multi-turn reasoning engine
│           └── tools.py         # Workspace tools (read, write, list, bash execute)
│
└── scripts/                     # 🛠️ DevOps & Automation Scripts
    ├── register_models.sh       # Persistently registers all models in models/registrations/
    ├── start_platform.sh        # One-command full platform launcher
    └── healthcheck.sh           # End-to-end system health validator
```

---

## 3. The 3-Tier Cost Optimization Strategy

| Tier | Workload Focus | Model Engine | Cost Impact |
| :--- | :--- | :--- | :--- |
| **Tier 1: Local Heavy-Duty**<br>*(~80% of total tokens)* | • Autonomous agent loops<br>• Reading files & code search<br>• Syntax linting & basic bug fixes<br>• Autocomplete & inline suggestions | **Local Engine (Xinference)**<br>`wolinex-coder` (3B Q4_K_M GGUF)<br>`qwen2.5-omni` (3B iq2_m GGUF) | **$0.00 / token**<br>Unlimited local tokens 24/7 without credit depletion. |
| **Tier 2: Frontier Reasoning**<br>*(~15% of total tokens)* | • Multi-file architectural refactoring<br>• Intricate algorithmic puzzles<br>• System design verification | **Cloud Provider APIs**<br>• DeepSeek-R1 (Full 671B)<br>• Claude 3.5 Sonnet<br>• OpenAI GPT-4o | **Low Cost**<br>Called surgically only when local models trigger uncertainty or fallbacks. |
| **Tier 3: Extreme Multi-Modal**<br>*(~5% of workloads)* | • Text-to-Video generation<br>• Ultra high-resolution image rendering | **Cloud Specialized APIs**<br>• Kling AI / Runway Gen-3<br>• Fal.ai / Replicate Flux Pro | **Pay-per-video**<br>Avoids renting $2,000/mo 80GB VRAM GPUs on server. |

---

## 4. Quick Start (Local Development)

### Prerequisites
* macOS (Apple Silicon or Intel) or Linux (x86_64 / aarch64).
* Python 3.10+ and `uv` package manager.

### 1. Initialize Platform
```bash
# Clone the repository
git clone https://github.com/wolinet-renatus/inference.git wolinetai
cd wolinetai

# Splay the environment
cp .env.example .env
```

### 2. Start Services
```bash
# Start both Inference Engine (:9997) and AI Gateway (:4000)
make start
```

### 3. Verify Health
```bash
make health
```

---

## 5. Working with Models

### Model Manifests ([models/registrations/](file:///Users/apple/Documents/wolinetai/models/registrations))
Custom models are defined declaratively without touching engine source code. For example, [models/registrations/wolinex-coder.json](file:///Users/apple/Documents/wolinetai/models/registrations/wolinex-coder.json):

```json
{
  "version": 2,
  "context_length": 32768,
  "model_name": "wolinex-coder",
  "model_family": "qwen2.5-coder-instruct",
  "model_specs": [
    {
      "model_format": "ggufv2",
      "model_size_in_billions": 3,
      "quantization": "q4_k_m",
      "model_id": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
      "model_hub": "huggingface",
      "model_file_name_template": "qwen2.5-coder-3b-instruct-{quantization}.gguf"
    }
  ],
  "chat_template": "{%- if messages[0]['role'] == 'system' -%}{{- '<|im_start|>system\\n' + messages[0]['content'] + '<|im_end|>\\n' -}}{%- else -%}{{- '<|im_start|>system\\nYou are Wolinex Coder, an advanced AI coding assistant developed by Wolinet Tech. You are a helpful assistant.<|im_end|>\\n' -}}{%- endif -%}{% for message in messages %}...{% endfor %}"
}
```

### Auto-Registration
To register or update local models:
```bash
make register
```

### Active Model Status
```bash
make list
```

---

## 6. Live Server Deployment (Enterprise Production)

To deploy Wolinet AI on a production cloud server (AWS, GCP, Hetzner, Lambda Labs, RunPod):

### Step 1: Configure `.env`
```bash
UI_USERNAME=admin
UI_PASSWORD=sk-wolinet-admin-2026
LITELLM_MASTER_KEY=sk-wolinet-admin-2026
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/litellm
DEEPSEEK_API_KEY=sk-your-deepseek-key
ANTHROPIC_API_KEY=sk-your-anthropic-key
OPENAI_API_KEY=sk-your-openai-key
```

### LiteLLM Admin UI Credentials
* **URL**: `http://localhost:4000/ui`
* **Username**: `admin`
* **Password**: `sk-wolinet-admin-2026`

### Step 2: Launch with Docker Compose
```bash
make docker-up
```

### Server Sizing Guide
* **CPU-Only Node (Cost-Optimized)**: 8–16 vCPU, 32GB RAM. Comfortably runs 3B–7B models (`wolinex-coder`) at ~20 tokens/sec.
* **GPU Node (High-Throughput)**: 1x NVIDIA RTX 3090/4090 or A10G (24GB VRAM). Runs 14B–32B models at 60–100+ tokens/sec.

---

## 7. Building Autonomous Coding Clients

All client applications (CLI, VS Code extension, web agent) interact with the **single Unified Gateway endpoint**:

```python
from openai import OpenAI

# Connect to Wolinet AI Gateway
client = OpenAI(
    base_url="http://localhost:4000/v1",  # Or https://api.wolinet.tech/v1
    api_key="sk-wolinet-master-key"
)

# Call local $0 model for routine coding:
response = client.chat.completions.create(
    model="wolinex-coder",
    messages=[{"role": "user", "content": "Refactor this function..."}]
)

# Or call frontier model for complex architectural planning:
response = client.chat.completions.create(
    model="deepseek-r1",
    messages=[{"role": "user", "content": "Design a distributed raft consensus..."}]
)
```

### Reference Agent Implementation
We have included a full reference autonomous agent in `apps/agentic-coder`:
```bash
# Run the interactive agentic coder
make agent

# Or pass a direct task:
.venv/bin/python3 apps/agentic-coder/main.py --prompt "Analyze the git status and write unit tests for tools.py"
```

---

## 8. 🇹🇿 Tanzania Mobile Money Payment Rails & Credit Architecture

To serve developers and enterprises across Tanzania and East Africa, Wolinet AI includes a native mobile money billing subsystem built directly into the LiteLLM gateway (`gateway/litellm/proxy/payments/tanzania/`).

### Supported Rails & Auto-Carrier Detection
* **Vodacom M-Pesa** (`074x`, `075x`, `076x`)
* **Tigo Pesa / Airtel Money** (`065x`, `067x`, `071x`, `068x`, `069x`, `078x`)
* **HaloPesa** (`062x`)
* **Selcom & AzamPay Aggregation** (Direct USSD Push & Web Checkout)

### Payment API Surface

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/v1/payments/tanzania/packages` | `GET` | List available TZS token packages with USD credit values |
| `/v1/payments/tanzania/checkout` | `POST` | Initiate USSD Push prompt to customer mobile number |
| `/v1/payments/tanzania/status/{order_id}` | `GET` | Poll real-time order confirmation status |
| `/v1/payments/tanzania/simulate-success/{order_id}` | `POST` | Dev sandbox: simulates customer USSD PIN approval & credit grant |

### Automated Credit & Key Allocation
Upon successful USSD PIN approval:
1. An order record in the payment store transition to `SUCCESS`.
2. A dedicated LiteLLM virtual key (`sk-wolinet-...`) is generated or topped up.
3. The dollar equivalent budget is credited to LiteLLM's `LiteLLM_VerificationToken` table in PostgreSQL.
4. Clients receive instantaneous access to cloud reasoning models while local models stay permanently $0.00.

---

## 9. 🎨 Open-Source Source Code & Custom Branding

The gateway codebase located in `gateway/` is 100% open source and fully customizable:

* **Live Editable Source**: The python runtime links directly to `gateway/litellm`, so any changes made to gateway routing, middleware, auth, or custom routes take effect immediately.
* **Wolinet AI Brand Identity**:
  * Light Brand Logo: `gateway/assets/wolinet_logo.png`
  * Dark Brand Logo: `gateway/assets/wolinet_logo_dark.png`
  * Favicon: `gateway/assets/favicon.ico` & `favicon.png`
  * Configured via `.env` (`UI_LOGO_PATH`, `UI_LOGO_PATH_DARK`, `LITELLM_FAVICON_URL`)
* **Serving Endpoints**:
  * `GET /get_image` $\rightarrow$ Serves branded logo
  * `GET /get_favicon` $\rightarrow$ Serves branded favicon
* **Wolinet AI Studio Web Client**:
  * Located at `apps/web-client/index.html` (served on port `8080`).
  * Features real-time token telemetry, model switching, API key configuration, and integrated Tanzania Mobile Money checkout modal.

---

## 10. Contributor Guidelines

1. **Never Hardcode Model Identifiers in Engine Code**: All model identities, templates, and quantization profiles belong in [models/registrations/](file:///Users/apple/Documents/wolinetai/models/registrations/).
2. **Gateway-First Routing**: New models (local or cloud) must be added to [gateway/config.yaml](file:///Users/apple/Documents/wolinetai/gateway/config.yaml) with defined fallback chains.
3. **OpenAI Standard Compliance**: All endpoints must conform to the standard OpenAI REST schemas to ensure zero friction with Cursor, Open WebUI, and standard SDKs.
4. **Editable Gateway Development**: Modify code inside `gateway/litellm` and test with `make gateway` or `./gateway/run_gateway.sh`.

---

## 11. Multi-Modal, Diffusion & Performance Tuning Playbook

### 1. Vision & Multimodal API
Vision-capable models (such as `wolinex-omni`, `qwen2.5-vl-instruct`) are accessed using the standard OpenAI Chat Completions endpoint (`/v1/chat/completions`) with image URLs or Base64 data URIs:

```python
import openai

client = openai.Client(
    base_url="http://127.0.0.1:4000/v1",
    api_key="sk-wolinet-admin-2026"
)

# Vision Chat Completion with Image URL
response = client.chat.completions.create(
    model="wolinex-omni",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What components are in this architecture diagram?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/system.png"}}
        ]
    }]
)
```

> **Memory Guardrail (`limit_mm_per_prompt`)**:
> On vLLM deployments, pass `limit_mm_per_prompt='{"image": 4}'` to throttle image count per conversation turn, preventing GPU memory overflows during long multi-image sessions.

### 2. High-Performance Image Generation & OCR
The LiteLLM gateway proxies all image endpoints directly:
* **Text-to-Image** (`POST /v1/images/generations`)
* **Image-to-Image** (`POST /v1/images/variations`)
* **OCR & Document Structure** (`POST /v1/images/ocr`)

```bash
# Generate Image with Qwen-Image-2.1
curl -X POST http://127.0.0.1:4000/v1/images/generations \
  -H "Authorization: Bearer sk-wolinet-admin-2026" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-image-2.1", "prompt": "Futuristic neon cloud workstation, 8k resolution"}'
```

### 3. VRAM Optimization Strategies for Large Models
| Technique | CLI Parameter | Impact |
|---|---|---|
| **CPU Offloading** | `--cpu_offload True` | Dynamically moves idle model blocks to RAM; enables 12B+ diffusion models to run on 8GB VRAM GPUs. |
| **GGUF Transformer Quantization** | `--gguf_quantization Q4_K_M` | Compresses diffusion model weights (e.g., FLUX.1 or Qwen-Image-2.1) down to ~5–8 GB VRAM. |
| **Lightning LoRA Acceleration** | `--lightning_version 4steps-V1.0` | Distills sampling down to 4 or 8 inference steps, dropping generation time from ~34s to ~3s. |
| **Text Encoder 8-bit Quantization** | `--quantize_text_encoder text_encoder_2` | Uses bitsandbytes to quantize heavy T5-XXL text encoders to 8-bit. |

### 4. Production Environment Tuning (Live Servers)
In cloud deployments, ensure the following environment variables are set in `.env`:
* `XINFERENCE_MODEL_SRC=huggingface`: Directly pulls from Hugging Face repositories.
* `XINFERENCE_DOWNLOAD_MAX_ATTEMPTS=3`: Automatic retry on network flakiness.
* `XINFERENCE_HUB_DETECT_TIMEOUT=3`: Prevents launch delays if hub reachability checks stall.
* `XINFERENCE_MODEL_DOWNLOAD_WORKERS=4` & `HF_HUB_DOWNLOAD_WORKERS=4`: Parallelized chunk downloads.
* `XINFERENCE_MEDIA_ALLOW_LOCAL_PATH=true`: Permissive file path loading for local agent tools.
* `XINFERENCE_MEDIA_BLOCK_PRIVATE_ADDRESS=false`: Enables multimodal fetch from internal network IPs.

