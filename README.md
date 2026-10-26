# Wolinet AI

[![Platform](https://img.shields.io/badge/Platform-Sovereign%20Enterprise-blue.svg)](https://github.com/wolinet-renatus/inference)
[![Control Plane](https://img.shields.io/badge/Control%20Plane-DEC%201Panel-purple.svg)](orchestrator/1apanel)
[![Gateway](https://img.shields.io/badge/Gateway-Lango%20LiteLLM-green.svg)](gateway/)
[![Engine](https://img.shields.io/badge/Engine-Mitambo%20Xinference-orange.svg)](inference/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

An enterprise-ready, high-performance self-hosted AI cloud featuring intelligent hybrid routing ($0 local GGUF execution + cloud frontier failover) designed for autonomous coding agents, developer tools, and sovereign enterprise deployments.

---

## 📖 Complete Documentation
* **Architecture & Manifesto:** [WOLINETAI.md](WOLINETAI.md)
* **Backend Specification (V1.1):** [wolinet-backend-setup-v1.md](wolinet-backend-setup-v1.md)
* **Production Deployment & Subdomain Topologies:** [DEPLOYMENT.md](DEPLOYMENT.md)
* **Master Product Catalog:** [products.json](products.json)

---

## ⚡ 1-Minute Master Installation

Deploy the complete sovereign cluster using the master installer:

```bash
# 1. Clone workspace
git clone https://github.com/wolinet-renatus/inference.git wolinetai
cd wolinetai

# 2. Launch hierarchical 4-stage sovereign cluster
./install.sh
```

The installer verifies hardware acceleration (MPS/CUDA), initializes the **DEC 1Panel Control Plane** to manage host resources and container engines, boots backing data clusters, initializes inference and gateway engines, and runs the synthetic **Golden Loop** transaction probe.

---

## 🏗️ Hierarchical 4-Stage Sovereign Architecture

```
Clients (Desktop IDE, CLI Agents, Web & Mobile)
                      │
                      ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Stage 1: DEC 1Panel Control Plane & Hardware Manager        │
 │ • Host Hardware Supervisor (CPU, RAM, GPU/MPS, NVMe Mounts) │
 │ • Isolated Native SQLite DB (data/1panel/db/*.db)           │
 │ • Supervises Rootless Podman Socket & Backing Data Cluster: │
 │   - PostgreSQL 16 (:5433 -> 5432) for Lango Gateway         │
 │   - Redis 7 (:6379) Append-Only Cache                       │
 └────────────────────────────┬────────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────────┐
 │ Stage 2: Mitambo Sovereign Inference Core (:9997)           │
 │ • High-throughput C++ Engine (llama.cpp / MPS / CUDA)       │
 │ • Quantized GGUF Models (wolinex-coder, qwen2.5-omni-3b)    │
 │ • Isolated Local SQLite Pools (data/mitambo/*.db)           │
 └────────────────────────────┬────────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────────┐
 │ Stage 3: Lango Sovereign API Gateway (:4000)                │
 │ • Unified OpenAI-Compatible /v1 REST & Streaming Endpoints  │
 │ • Hybrid Tiered Routing ($0 local + cloud frontier API)     │
 │ • Virtual Keys, Rate Limits, and Postgres Spend Logs        │
 └────────────────────────────┬────────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────────┐
 │ Stage 4: Sovereign Workspaces & Edge Applications           │
 │ • Sovereign Web Client (Open WebUI Studio on :8081)         │
 │ • Obscura Browser MCP Container (Tool Execution on :8080)   │
 │ • Developer Portal & Key Studio (:8082)                     │
 │ • Enterprise Homepage & Showcase (:80 / :3000)              │
 │ • ai-memory Cross-Session Persistence Daemon (:49374)       │
 └─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Strict Database & Data Storage Isolation

| Component | Storage Engine | Location | Isolation Protocol |
| :--- | :--- | :--- | :--- |
| **DEC 1Panel Control Plane** | Native SQLite | `data/1panel/db/*.db` | **100% Isolated.** Pure host metrics, SSL certificates, container states. Zero PostgreSQL dependency. |
| **Lango API Gateway** | PostgreSQL 16 + Redis 7 | `postgres:5432` (host `5433`) | **Relational Auth & Spend.** 189 Prisma migrations, `LiteLLM_SpendLogs`, virtual keys, team quotas. |
| **Mitambo Inference Core** | Local SQLite Pools | `data/mitambo/*.db` | **Model State.** `launch_history.db`, download queues, request counters. |
| **Quantized Weights** | GGUF Files | `models/*.gguf` | **In-Memory Compute.** Zero cloud telemetry or external streaming lag. |

---

## 💻 Client Products & SDKs (Decoupled from Server)

* **Wolinet Desktop IDE (`Wolinet-Dkt-Ide`):** Autonomous Tauri desktop application for developer workstations. Connects via API (`http://<server-ip>:4000/v1`). It is **never** bundled or containerized in server Podman Quadlets.
* **Wolinet SDKs (`packages/`):** Official Python, TypeScript, and Go SDKs for seamless programmatic integration.

---

## 🛠️ Product & Git Subtree Manager (`bin/wolinet-product`)

Manage catalog items, detect changes, and synchronize standalone sub-branches:

```bash
# View product catalog and sub-branch mapping
./bin/wolinet-product list

# Inspect modified files and branch readiness
./bin/wolinet-product status

# Synchronize stack changes bidirectionally with main
./bin/wolinet-product sync lango push
./bin/wolinet-product sync mitambo pull

# Change-aware builder (compiles only targets with unstaged changes)
./bin/wolinet-product build --changed
```

---

## 🌐 Default Core Endpoints

* **DEC 1Panel Control Plane:** `http://localhost:8888` (or `:9999` / `:8089`)
* **Lango API Gateway:** `http://localhost:4000` (`http://localhost:4000/ui`)
* **Mitambo Inference Core:** `http://localhost:9997`
* **Sovereign Web Client:** `http://localhost:8081`
* **Developer Portal:** `http://localhost:8082`
* **Enterprise Homepage:** `http://localhost:80` (or `:3000`)
