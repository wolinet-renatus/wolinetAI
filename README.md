# Wolinet AI

[![Platform](https://img.shields.io/badge/Platform-Self--Hosted-blue.svg)](https://github.com/wolinet-renatus/inference)
[![Gateway](https://img.shields.io/badge/Gateway-LiteLLM-green.svg)](https://litellm.ai)
[![Engine](https://img.shields.io/badge/Engine-Xinference%20%2B%20xllamacpp-orange.svg)](https://github.com/xorbitsai/inference)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

An enterprise-ready, high-performance self-hosted AI platform featuring intelligent hybrid routing ($0 local GGUF execution + cloud frontier failover) designed for autonomous coding agents and production services.

---

## 📖 Complete Documentation
For the platform architecture, see **[WOLINETAI.md](WOLINETAI.md)**. For the current single-server Compose deployment, CPU/GPU profiles, TLS setup, shared login, and CI rollout, see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

---

## ⚡ 1-Minute Quickstart

```bash
# 1. Clone & enter workspace
git clone https://github.com/wolinet-renatus/inference.git wolinetai
cd wolinetai

# 2. Setup environment
cp .env.example .env

# 3. Start Inference Engine & Gateway
make start

# 4. Verify system health
make health

# 5. Launch interactive coding agent
make agent
```

---

## 🏗️ Architecture at a Glance

```
Clients (Agentic Coding IDE / Apps)
              │
              ▼
   AI Gateway Layer (:4000)
    ├── Enabled models ──► Xinference / configured providers
    ├── Cloud ($)    ──► DeepSeek / Claude / GPT-4o
    └── Media ($$$)  ──► Kling / Runway Video APIs
```

---

## 📂 Project Organization

* **`gateway/`**: LiteLLM Gateway configuration and custom Wolinet integration assets. Lago receives usage events for billing.
* **`inference/`**: Core multi-backend inference engine (Xinference stack) powering local GGUF models.
* **`models/`**: Quantized GGUF model weights and declarative Version 2 JSON manifests (`wolinex-coder`, `qwen2.5-omni`).
* **`apps/web-client/`**: Wolinet AI Studio, backed by the live model catalog exposed by LiteLLM.
* **`apps/agentic-coder/`**: Reference autonomous coding agent with full tool calling capabilities.
* **`scripts/`**: Automation scripts for registration, health checking, and system lifecycle.
* **`docker-compose.yml`**: Production single-command deployment stack with PostgreSQL and Redis.
