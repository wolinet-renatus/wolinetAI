# Wolinet AI — Comprehensive Platform Architecture & Topology

> **Status:** Production-Ready Sovereign Cluster  
> **Classification:** Enterprise-Grade AI Infrastructure & Self-Hosted Automation Plane  
> **Last Updated:** October 2026

---

## 1. Executive Summary & Architectural Vision

**Wolinet AI** is an enterprise-grade, sovereign AI platform engineered for total data privacy, $0 marginal-cost local execution, and intelligent cloud fallback resilience. By fusing bare-metal hardware execution (Apple Silicon MPS / NVIDIA CUDA) with zero-trust AI cyber defense, sovereign memory hubs, and headless browser automation, Wolinet delivers an end-to-end environment for autonomous coding agents, system administration copilots, and enterprise developer tools.

### Key Pillars

1. **Sovereign Local Hardware Core:** Zero API billing, zero data leakage, and low latency through the Mitambo C++ inference runtime and OrcaCyber Rust defense core.
2. **Resilient Hybrid Fallback Fabric:** Upstream Lango AI Gateway routes requests with latency-based load balancing, 90-second execution deadlines, and automatic cascading fallbacks across Moonshot Kimi K3.1, Google Gemini 3.8, and DeepSeek clusters.
3. **Embedded Control Plane Automation:** DEC 1Panel acts as both the bare-metal supervisor and the host for the embedded **Wolinet DevOps Copilot** (`/ai/chat`), orchestrating Docker containers, cron jobs, and database engines over high-performance Unix domain sockets.
4. **Sub-Microsecond Zero-Trust Defense:** Every inference call entering local or speculative tiers passes through the OrcaCyber Nano 1.0 Rust core for real-time prompt injection mitigation and threat telemetry.

---

## 2. Complete Service Topology & Port Matrix

| Service | Port | Protocol | Binding / Target | Purpose & Responsibility |
| :--- | :---: | :---: | :--- | :--- |
| **Lango AI Gateway** | `4000` | HTTP / SSE | `0.0.0.0:4000` (Docker `wolinetai-lango-1`) | Master OpenAI-compatible reverse proxy, rate limiting, and fallback routing |
| **OrcaCyber AI Defense** | `8088` | HTTP | Host `127.0.0.1:8088` (Rust Core Binary) | Sub-microsecond prompt injection guardrail, threat telemetry, and safety pass-through |
| **Mitambo Inference Core**| `9997` | HTTP | Host `127.0.0.1:9997` (Xinference / llama.cpp) | Bare-metal GGUF execution engine for sovereign models (`wolinex-coder`) |
| **DEC 1Panel Control Plane**| `9999`| HTTP / WS | Host `0.0.0.0:9999` (`bin/1apanel`) | Host supervisor, container orchestration, file management, and system monitoring |
| **1Panel Agent Bridge** | Socket | Unix Domain | `/tmp/1panel/agent.sock` (`bin/1panel-agent`) | Master IPC daemon handling 1Panel AI Chat completions and telemetry |
| **OpenWebUI Studio** | `8081` | HTTP / WS | Host `127.0.0.1:8081` (Python / Svelte) | Rich collaborative chat workspace, model comparison, and MCP tooling |
| **Wolinet Memory Hub** | `8000` | HTTP | Host `127.0.0.1:8000` (`litellm_memory`) | Cross-session semantic memory, vector storage, and Slack/agent persistence |
| **Obscura Browser Bridge**| `8080`| HTTP | `0.0.0.0:8080` (Docker `wolinet-browser`) | Headless Chromium sandbox, web crawler, and clean Markdown scraper |
| **PostgreSQL 16** | `5433` | TCP | Host `127.0.0.1:5433` -> Container `5432` | Backing transactional storage for gateway keys, audit logs, and metrics |
| **Redis 7** | `6379` | TCP | Host `127.0.0.1:6379` -> Container `6379` | Append-only cache for route caching, token counts, and cooldown timers |

---

## 3. Layer-by-Layer Architectural Decomposition

```
                       ┌────────────────────────────────────────────────────────┐
                       │     Clients (Desktop IDE, CLI, OpenWebUI, 1Panel)      │
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                                                   ▼
                       ┌────────────────────────────────────────────────────────┐
                       │    Stage 1: Lango AI Gateway (Port 4000 / LiteLLM)     │
                       │  - Auth: Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q               │
                       │  - Latency-Based Router (90s Timeout, 2 Retries)       │
                       │  - Router Fallbacks & Context Window Fallbacks          │
                       └─────────────┬────────────────────────────┬─────────────┘
                                     │                            │
                     Local Sovereign │ Request                    │ Cloud Fallback
                                     ▼                            ▼
        ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────┐
        │ Stage 2: OrcaCyber Nano 1.0 AI Defense       │  │ Cloud Frontier Tier              │
        │ - Port 8088 (High-Speed Rust Core / Axum)    │  │ - Wolinet Max (Gemini 3.8 Flash) │
        │ - Latency: < 0.001 ms (Threat Telemetry)     │  │ - Wolinet Max Pro (Kimi K3.1)    │
        │ - Pass-Through Inspection Filter             │  │ - Scorpio / Pro (DeepSeek V4.1)  │
        └──────────────────────┬───────────────────────┘  └──────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │ Stage 3: Mitambo Inference Cluster           │
        │ - Port 9997 (Xinference / llama.cpp / MPS)   │
        │ - Models: wolinex-coder (131,072 context)    │
        │ - Speculative Acceleration (qwen-dflash)     │
        └──────────────────────────────────────────────┘
```

### Stage 1: Lango AI Gateway (`gateway/`)
- **Engine:** LiteLLM Proxy packaged inside `ghcr.io/wolinet-renatus/wolinet-lango:latest`.
- **Config:** [`gateway/config.yaml`](file:///Users/apple/Documents/wolinetai/gateway/config.yaml) directly bind-mounted into the container.
- **Failover Logic:** Automatically routes from primary models to fallbacks if timeouts or provider rate limits occur.
- **Timeouts:** Configured to `90` seconds across all tier models with `allowed_fails: 1` and `cooldown_time: 30s`.

### Stage 2: OrcaCyber AI Cyber Defense Core (`services/defense-rs/`)
- **Engine:** Native Rust Axum microservice running as a lightweight daemon.
- **Role:** Analyzes incoming prompts and completions for structural injections, jailbreaks, and delimiter tampering.
- **Telemetry:** Injects metadata directly into chat completion payloads:
  ```json
  "defense_telemetry": {
    "action": "PASS_THROUGH",
    "is_safe": true,
    "latency_ms": 0.00072,
    "model": "OrcaCyber-Nano-1.0-AI-Defense-DFlash2-Q8_0",
    "threat_score": 0.0,
    "verdict": "CLEAN"
  }
  ```

### Stage 3: Mitambo Local Inference Cluster (`inference/`)
- **Engine:** Xinference cluster orchestrating C++ llama.cpp backends.
- **Hardware Acceleration:** Native Apple Silicon Metal Performance Shaders (MPS) and NVIDIA CUDA support.
- **Models Loaded:** `wolinex-coder` (DeepSeek-R1 Distill Qwen 1.5B, Q4_K_M GGUF, 131k context length).

### Stage 4: DEC 1Panel Control Plane & DevOps Copilot (`orchestrator/1apanel/`)
- **Core Binary:** [`bin/1apanel`](file:///Users/apple/Documents/wolinetai/bin/1apanel) listening on port `9999`.
- **Daemon Binary:** [`bin/1panel-agent`](file:///Users/apple/Documents/wolinetai/bin/1panel-agent) communicating via `/tmp/1panel/agent.sock`.
- **Embedded AI Chat Copilot:** Located at `http://localhost:9999/ai/chat` ([`index.vue`](file:///Users/apple/Documents/wolinetai/orchestrator/1apanel/frontend/src/views/ai/chat/index.vue)).
- **Database:** Native SQLite at [`data/1panel/db/agent.db`](file:///Users/apple/Documents/wolinetai/data/1panel/db/agent.db), storing model metadata in `agent_account_models`.

---

## 4. Model Roster & Dropdown Hierarchy

The 1Panel AI Chat drop list and Lango Gateway support the following 10 unified models:

| # | Model Identifier | Display Name | Underlying Provider | Optimal Use Case |
| :-: | :--- | :--- | :--- | :--- |
| **1** | `wolinet-max` | **Wolinet Max** | Google Vertex Gemini 3.8 Flash | Complex system reasoning, multi-step architecture planning |
| **2** | `wolinet-pro` | **Wolinet Pro** | Sovereign Local Engine (Port 8088) | Sovereign conversational engine, $0 cost, zero data leakage |
| **3** | `wolinex-coder` | **Wolinex Coder** | Mitambo Local Engine (Port 9997) | High-speed code generation, refactoring, bash automation |
| **4** | `wolinet-coder` | **Wolinet Coder** | Mitambo / Sovereign Coder | Systems & DevOps shell script generation |
| **5** | `wolinet-turbo` | **Wolinet Turbo** | Google Gemini 3.8 Flash Cloud | Sub-second ultra fast generation, rapid diagnostics |
| **6** | `wolinet-max-pro` | **Wolinet Max Pro** | Moonshot Kimi K3.1 Pro MoE | 1-Million context token analysis, massive log parsing |
| **7** | `scorpio-pro` | **Scorpio Pro** | DeepSeek V4 Pro | Frontier deep reasoning, mathematical and logic analysis |
| **8** | `scorpio` | **Scorpio** | DeepSeek V4.1 Flash | Fast reasoning and coding with vision capability |
| **9** | `secure-pro` | **Secure Pro** | OrcaCyber Nano 1.0 (Port 8088) | AI cybersecurity, firewall rules, vulnerability auditing |
| **10**| `wolinet-turbo-draft` | **Wolinet Turbo Draft** | DFlash2 Speculative Engine | Accelerated speculative decoding draft model |

---

## 5. Fallback Routing Architecture

LiteLLM Router in [`gateway/config.yaml`](file:///Users/apple/Documents/wolinetai/gateway/config.yaml#L516-L565) guarantees high availability through automated fallback chains:

```yaml
fallbacks:
  - "Wolinet Turbo": ["Wolinet Max", "Wolinet Pro", "Wolinex Coder", "Wolinet Max Pro"]
  - "wolinet-turbo": ["Wolinet Max", "Wolinet Pro", "Wolinex Coder", "Wolinet Max Pro"]
  - "Wolinet Max": ["Scorpio", "Wolinet Max Pro", "Wolinex Coder", "Wolinet Pro"]
  - "Wolinet Pro": ["Wolinex Coder", "Wolinet Max"]
  - "Wolinex Coder": ["Wolinet Pro", "Wolinet Max"]
  - "Wolinet Max Pro": ["Scorpio", "Wolinet Max", "Wolinex Coder", "Wolinet Pro"]
  - "Scorpio Pro": ["Scorpio", "Wolinet Max Pro", "Wolinet Max", "Wolinet Pro"]
  - "Secure Pro": ["Wolinet Pro", "Wolinet Max"]
```

If an upstream provider exceeds 90 seconds or returns an HTTP 408/502/503 error, LiteLLM automatically retries the prompt against the designated fallback group without breaking the client connection.

---

## 6. Quick Action Prompts in 1Panel AI Chat

The 1Panel AI Chat UI provides one-click operational diagnostics built into the frontend:

1. **⚡ Server Resource Audit:** Audits hardware specs, CPU load averages, memory allocation, and top resource consumers.
2. **🐳 Docker & Sandbox Health:** Audits container status across Obscura Browser (`:8080`), Lango Gateway (`:4000`), Postgres (`:5433`), and Redis (`:6379`).
3. **🧠 AI Mesh Diagnostics:** Benchmarks real-time TTFB, connection latency, and route readiness across Mitambo (`:9997`), OrcaCyber (`:8088`), and Lango (`:4000`).
4. **🛠️ Automation Script Generator:** Crafts defensive bash scripts for maintenance, disk trimming, and daemon monitoring.
5. **🔍 Error Log Investigation:** Diagnoses systemd `journalctl` signals and Docker container logs with standard recovery steps.

---

## 7. Verification & Health Probing Quick Reference

Execute these commands from any host terminal:

```bash
# 1. Probe OrcaCyber Defense Core
curl -s http://127.0.0.1:8088/health | jq .

# 2. Probe Lango AI Gateway Health
curl -s http://127.0.0.1:4000/health/liveliness

# 3. Probe Mitambo Local Inference Models
curl -s -H "Authorization: Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q" http://127.0.0.1:9997/v1/models | jq .

# 4. Probe 1Panel AI Options via Socket
curl -s -X POST --unix-socket /tmp/1panel/agent.sock http://localhost/api/v2/ai/agents/chat/options | jq .

# 5. Execute Minimal Token Inference Test
curl -s -X POST http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q" \
  -H "Content-Type: application/json" \
  -d '{"model":"wolinet-turbo","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' | jq .
```
