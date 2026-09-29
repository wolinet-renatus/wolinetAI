# Wolinet AI Studio (Web Client)

A sovereign, high-performance browser console for **Wolinet AI** connected directly to the LiteLLM Gateway layer (`http://127.0.0.1:4000/v1`).

---

## ⚡ Architectural Principles

1. **Zero Local Database Bloat**:
   - Completely eliminated local SQLite / Open WebUI databases (`webui.db`).
   - All models, users, virtual keys, chat completions, and payments are routed directly through the **LiteLLM Gateway** (:4000).
   - Session conversations are stored securely in browser `localStorage` and can be exported as JSON or Markdown.

2. **Intelligent 3-Tier Hybrid Routing**:
   - **Tier 1 (Local - $0.00 / token)**: `wolinex-coder` & `wolinex-omni` running on high-throughput local engine (Xinference :9997).
   - **Tier 2 (Cloud Frontier)**: `deepseek-r1`, `claude-3-5-sonnet`, `gpt-4o` via Gateway fallback.
   - **Tier 3 (Multi-Modal)**: Kling AI and Runway video pipelines.

3. **🇹🇿 Native Tanzania Mobile Money Top-Up**:
   - Direct integration with Gateway's `/v1/payments/tanzania/*` subsystem.
   - Instant USSD push checkout for **Vodacom M-Pesa**, **Tigo Pesa**, **Airtel Money**, and **HaloPesa**.
   - Built-in developer simulation endpoint for rapid local testing.

4. **Real-Time Telemetry**:
   - Live cluster health indicators (:4000 Gateway & :9997 Xinference).
   - Per-message Time-To-First-Token (TTFT), duration, tokens/sec throughput, and cost estimation ($0 for local models).
   - Collapsible reasoning chain `<think>` blocks for DeepSeek-R1.

---

## 🚀 Quickstart

```bash
# Launch Wolinet AI Studio on port 8080
./run_studio.sh

# Or from workspace root:
make web
```

Then visit: **`http://localhost:8080`**

---

## 🔌 Gateway Route Summary

| Studio Feature | Target Gateway Endpoint | Description |
| :--- | :--- | :--- |
| **Cluster Health** | `GET /health/readiness` & `GET /health` | Health check and round-trip latency ping |
| **Model Catalog** | `GET /v1/models` & `GET /model/info` | Dynamic model enumeration, context windows & pricing |
| **Streaming Chat** | `POST /v1/chat/completions` | SSE streaming with reasoning content and tool inspection |
| **Mobile Money** | `GET /v1/payments/tanzania/packages` | TZS package catalog with USD credit equivalencies |
| **USSD Checkout** | `POST /v1/payments/tanzania/checkout` | Triggers USSD PIN push to customer mobile handset |
| **Order Status** | `GET /v1/payments/tanzania/status/{id}` | Live payment polling |
| **Dev Simulation** | `POST /v1/payments/tanzania/simulate-success/{id}` | Sandbox instant PIN approval and virtual key allocation |
| **Key Generation** | `POST /key/generate` | Issues LiteLLM virtual keys with custom spend budgets |
| **Key Inspection** | `GET /key/info` | Monitors spend, max budget, and token activity |
