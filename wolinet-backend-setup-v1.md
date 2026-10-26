# WOLINET SYSTEM ARCHITECTURE & SOVEREIGN ENGINE SPECIFICATION
## SYSTEM SPECIFICATION: BACKEND ORCHESTRATOR & INFRASTRUCTURE ENGINE (VERIFIED V1.0)
## TARGET RUNTIME: ROOTLESS PODMAN + MACOS APPLEHV / LINUX COMPUTE INSTANCE

---

## 1. STRATEGIC ARCHITECTURAL MANDATES

### OVERVIEW & OBJECTIVE
You are an expert system engineer building the sovereign Wolinet Backend Platform. We are entirely bypassing third-party platform runtimes like Coolify (due to resource latency) and Dokploy (due to multi-node cluster complexity). Instead, we are re-engineering the open-source, high-performance Go-based core engine of 1Panel into a completely sovereign, single-binary container orchestrator named **1apanel**.

This system natively orchestrates our core AI components:
1. **Mitambo (Inference Core):** Powered by Xinference, executing quantized local GGUF models (`Qwen2.5-Coder-3B`, `Qwen2.5-Omni-3B`, `deepseek-coder-1.3b`) completely within memory boundaries with native hardware accelerator mapping and `ShmSize=8g`.
2. **Lango (Gateway Layer):** Powered by LiteLLM, handling API authentication, token usage logging via PostgreSQL `LiteLLM_SpendLogs`, and failover routing to external cloud provider models with a fast 8ms P95 latency response.
3. **WolinEx AI Studio:** The flagship web application and agentic IDE client that connects directly to Lango's gateway variables over in-pod loopback.

---

## 2. PROVISIONED PORT INTERACTION SHEET
All critical processing nodes communicate within a single, isolated **Podman Pod (`wolinetai-core-pod`)** mapped natively to the local network interface (`127.0.0.1`) to ensure absolute zero virtual bridge network NAT overhead.

* `127.0.0.1:4000` &mdash; **Lango Gateway:** Active health status verification (`"I'm alive!"`). Uniform OpenAI specification mapping endpoint.
* `127.0.0.1:5433` (Host) ──► `5432` (Pod) &mdash; **PostgreSQL Cluster:** Host port mapped to `5433` to prevent native PostgreSQL host engine socket collisions.
* `127.0.0.1:6379` &mdash; **Redis 7 Cache Layer:** Persistent cache state utilizing Append-Only File (AOF) block storage for persistent runtime configuration data.
* `127.0.0.1:8080` &mdash; **WolinEx AI Studio:** Open WebUI visual container running local client sessions connected via Lango's core gateway variables.
* `127.0.0.1:9997` &mdash; **Mitambo Engine Node:** Handles compute targets, tracking underlying systems while managing quantized local model weights.
* `127.0.0.1:4004` &mdash; **1apanel Dashboard:** Ultra-lightweight Go application service daemon (idling at ~20MB-50MB RAM) with modern responsive UI.

---

## 3. DATABASE DECOUPLING & RETENTION PROTOCOLS

### A. Lango Persistent Database Layer (PostgreSQL)
* **Applied Schemas:** 189 structural migrations processed successfully via Prisma engine toolings.
* **Tables Present:** 83 operational data tables fully generated (e.g., `LiteLLM_UserTable`, `LiteLLM_ProxyModelTable`, `LiteLLM_SpendLogs`).
* **Default Seed Values:** 
  * Admin Identity: `admin@wolinet.com` (Permission Tier: `proxy_admin`).
  * Active App Virtual Key: `sk-XvKFiwDoOtOe8i4lwbzb8Q` (Alias Mapping: `wolinex`).

### B. Mitambo Historical Preservation Pools (SQLite Storage)
To protect model selection history and user validation settings, the control logic handles syncing directly with local SQLite structural instances mounted at `/var/lib/wolinet/data/mitambo/` (or `${WORKSPACE_ROOT}/data/mitambo`):
* `launch_history.db` &mdash; Tracks historical quantized weight deployments (e.g., `deepseek-coder-1.3b-tZIwEoUf`).
* `token_routers.db` &mdash; Retains metric weights and internal request counts.
* `auth.db` &mdash; Stores internal user metadata maps and system access keys.
* `download_tasks.db` &mdash; Logs automated download queue operations for local GGUF models.

### C. Quantized Local Memory Storage
All model execution weights are stored inside the local storage path: `${WORKSPACE_ROOT}/models/` (or `/var/lib/wolinet/models/` in production). The system targets three localized packages:
* `Qwen2.5-Coder-3B` &mdash; Core structural programming support.
* `Qwen2.5-Omni-3B` &mdash; Real-time multimodal operations.
* `deepseek-coder-1.3b` &mdash; High-speed code execution mapping routines.

---

## 4. INSTRUCTIONS AND BEHAVIORAL PROMPTS FOR CODING AGENTS

### 🤖 AGENT OPERATION RULES

#### 🟢 MANDATORY SYSTEMS EXECUTION ACTIONS (WHAT TO DO)
1. **Maintain Shared Host Port Mapping:** When modifying internal network controllers within Go code or Podman deployment Quadlets, preserve the `5433:5432` map for PostgreSQL to protect development machines from socket collisions.
2. **Execute Clean Container Controls:** Bind all visual container switch toggles inside the **1apanel Orchestrator Dashboard (`:4004`)** to interact directly via local execution calls (`podman stop/start <container_name>`), keeping sister processing containers fully operational. Never stop or restart the entire pod when modifying a single service.
3. **Route Metrics via Lango DB Maps:** Ensure that the usage statistics dashboard (Requests, Token usage counters) fetches its data loops by reading directly from the `LiteLLM_SpendLogs` tables on the local PostgreSQL service rather than executing slow system logs queries.
4. **Enforce Password Cache Access:** Ensure every Go data fetch routine connecting to Redis passes the standard password authentication parameter (`redis`) along with active tracking loops.
5. **Decouple Host Paths Dynamically:** Use dynamic host path resolution (`${WORKSPACE_ROOT}`, `.`, or `$PWD` in development; `/var/lib/wolinet` in production Linux environments) across all Makefiles, shell scripts, and Go service controllers.

#### 🔴 ABSOLUTE ARCHITECTURAL PROHIBITIONS (WHAT NOT TO DO)
1. **DO NOT Mix Panel Configuration States:** Never force your 1apanel core engine to log structural interface views onto the production PostgreSQL database. 1apanel must strictly retain its internal, isolated SQLite file state tracker (`core.db`).
2. **DO NOT Reset Pod Namespaces on Service Updates:** When pushing code modifications or system fixes to a specific application layer (e.g., updating the WolinEx front-end), do not execute a global pod cycle command. You must cycle the isolated target container instance cleanly.
3. **DO NOT Hardcode Machine User Directory Paths:** Never embed explicit paths like `/Users/apple/...` or `/home/ubuntu/...` into Go source code files, configurations, or container templates. All directory structures must resolve dynamically using relative anchors (`.`), current path variables (`$PWD`), or structured environment tokens (`${WORKSPACE_ROOT}`).
4. **DO NOT Use Docker Commands Natively:** Do not write any code blocks, endpoints, or scripts that invoke the traditional `docker` background system daemon. Every container interaction pattern must call rootless `podman` utilities directly.
5. **DO NOT Invoke Ollama Services:** Never generate templates, routes, or UI components linked to Ollama execution states. All local inference processes belong exclusively to Mitambo.
6. **DO NOT Hardcode Credentials:** Absolutely zero plain-text database hashes, Cloudflare tokens, encryption keys, or local loop passwords may exist inside code files or configurations. Bind every secret dynamically to local environment parameters (`.env`).
