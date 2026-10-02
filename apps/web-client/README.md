# Wolinet AI Studio (Web Client)

A sovereign, high-performance browser console for **Wolinet AI** connected directly to the LiteLLM Gateway layer (`http://127.0.0.1:4000/v1`).

---

## ⚡ Architectural Principles

1. **Zero Local Database Bloat**:
   - Completely eliminated local SQLite / Open WebUI databases (`webui.db`).
   - Model discovery, users, virtual keys, chat completions, and usage billing are routed through the **LiteLLM Gateway** (:4000).
   - Session conversations are stored securely in browser `localStorage` and can be exported as JSON or Markdown.

2. **Gateway-Managed Routing**:
   - Chat and media models are available after their provider routes are enabled in LiteLLM.
   - The WebUI model picker reads the models allowed by the gateway key.

   - Built-in developer simulation endpoint for rapid local testing.

4. **Real-Time Telemetry**:
   - Live cluster health indicators (:4000 Gateway & :9997 Xinference).
   - Per-message Time-To-First-Token (TTFT), duration, throughput, and gateway cost estimates.
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
| **Key Generation** | `POST /key/generate` | Issues LiteLLM virtual keys with custom spend budgets |
| **Key Inspection** | `GET /key/info` | Monitors spend, max budget, and token activity |
