# WOLINET SYSTEM ARCHITECTURE & SOVEREIGN ENGINE SPECIFICATION
## SYSTEM SPECIFICATION: BACKEND ORCHESTRATOR & INFRASTRUCTURE ENGINE (VERIFIED V1.1)
## TARGET RUNTIME: ROOTLESS PODMAN + MACOS APPLEHV / LINUX COMPUTE INSTANCE

---

## 1. STRATEGIC ARCHITECTURAL MANDATES

### OVERVIEW & OBJECTIVE
You are an expert systems engineer building the sovereign Wolinet Backend Platform. We are entirely bypassing third-party platform runtimes like Coolify (due to resource latency) and Dokploy (due to multi-node cluster complexity). Instead, we re-engineer the open-source, high-performance Go-based core engine of 1Panel into a completely sovereign, single-binary container orchestrator and hardware supervisor named **1apanel**.

This system natively orchestrates our core components in a strict **4-Stage Boot Hierarchy**:

1. **Stage 1: DEC Orchestrator & 1Panel Control Plane (Boot First):**
   * Acts as the physical hardware and infrastructure supervisor (CPU cores, RAM limits, NVMe storage mounts, GPU/MPS accelerator allocation, rootless Podman socket).
   * **Data Isolation Mandate:** Uses its own isolated, native SQLite database (`${WORKSPACE_ROOT}/data/1panel/db/` or `/var/lib/wolinet/data/1panel/db/`). It **never** shares schemas with PostgreSQL or any downstream product.
   * Directly provisions and supervises the backing data cluster (PostgreSQL 16 and Redis 7) before any application layer starts.
2. **Stage 2: Mitambo (Inference Core):**
   * Powered by Xinference / llama.cpp / MPS / CUDA, executing quantized local GGUF models (`wolinex-coder`, `qwen2.5-omni-3b`, `deepseek-coder-1.3b`) completely within VRAM/unified memory boundaries with native hardware accelerator mapping and `ShmSize=8g`.
   * Retains its own isolated local SQLite operational pools in `data/mitambo/`.
3. **Stage 3: Lango (Gateway Layer):**
   * Powered by LiteLLM Proxy, providing unified OpenAI-compatible `/v1` endpoints, intelligent hybrid routing ($0 local inference + on-demand cloud failover), virtual keys, and spend logging.
   * Persists to PostgreSQL 16 (`litellm` database) and caches to Redis 7.
4. **Stage 4: Sovereign Workspaces & Edge Applications:**
   * **Sovereign Web Client (Open WebUI Studio):** Modern collaborative chat, agent workspace, and model switching on `:8081`.
   * **Obscura Browser MCP:** Secure sandboxed browser automation engine on `:8080`.
   * **Developer Portal & API Playground:** Interactive API docs and virtual key generator on `:8082`.
   * **Enterprise Homepage:** Public showcase and app distribution landing page on `:3000` / `:80`.
   * **ai-memory Persistence Daemon:** Cross-session memory and context persistence on `:49374`.

### 5. CLIENT PRODUCTS & SDKS (STRICT SERVER DECOUPLING)
* **Wolinet Desktop IDE (`Wolinet-Dkt-Ide`):** An autonomous Tauri desktop IDE that runs on client workstations. It communicates with the server purely over standard REST/WebSocket APIs (`http://<server-ip>:4000/v1`). It is **never** bundled or orchestrated into server Podman Quadlets or containers.
* **Wolinet SDKs (`packages/`):** Python, Go, and TypeScript client libraries for external applications.

---

## 2. PROVISIONED PORT INTERACTION SHEET

All critical server nodes communicate within a single, isolated **Podman Pod (`wolinetai-core-pod`)** mapped natively to the local network interface (`127.0.0.1`) to guarantee absolute zero virtual bridge network NAT overhead.

| Port | Service Component | Description & Responsibilities |
| :--- | :--- | :--- |
| `127.0.0.1:9999` / `:8888` / `:8089` | **DEC 1Panel Control Plane** | Stage 1 Hardware & Infra Supervisor. Native Go binary on `:9999` (dev/native), `:8888` (control plane), or `:8089` (Quadlet pod ingress). Uses isolated SQLite DB. |
| `127.0.0.1:5433` (Host) ──► `5432` (Pod) | **PostgreSQL 16 Cluster** | Host port mapped to `5433` to prevent native host socket collisions. Houses `litellm` gateway database (189 Prisma migrations). |
| `127.0.0.1:6379` | **Redis 7 Cache Layer** | High-performance Append-Only File (AOF) cache for token rate limiting, router state, and session coordination. |
| `127.0.0.1:9997` | **Mitambo Inference Core** | Local high-throughput compute engine (Xinference/llama.cpp). Exposes `/v1/models` and manages local GGUF models. |
| `127.0.0.1:4000` | **Lango API Gateway** | Central sovereign gateway. Exposes `/v1` routes and `/ui` admin management dashboard. |
| `127.0.0.1:8080` | **Wolinet Obscura / Browser** | Sandboxed browser automation MCP container for agent tool execution. |
| `127.0.0.1:8081` | **Sovereign Web Client** | Open WebUI Studio client container (or `:3080` in local standalone dev). |
| `127.0.0.1:8082` | **Developer Portal** | Interactive developer documentation, key management studio, and Scalar API specs. |
| `127.0.0.1:3000` / `:80` | **Enterprise Homepage** | Fast-loading showcase landing page and download portal. |
| `127.0.0.1:49374` | **ai-memory Daemon** | Cross-session continuity and long-term memory engine. |

---

## 3. DATABASE DECOUPLING & RETENTION PROTOCOLS

The Wolinet architecture strictly enforces **three isolated database storage domains**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STRICT DATA STORAGE ISOLATION                         │
├──────────────────────────────┬──────────────────────────────┬───────────────┤
│ 1. 1Panel Control Plane      │ 2. Lango Gateway Cluster     │ 3. Mitambo    │
│    Native SQLite             │    PostgreSQL 16 + Redis 7   │    SQLite     │
│    (data/1panel/db/*.db)     │    (litellm @ :5433->5432)   │    (data/     │
│                              │                              │    mitambo/)  │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ • alert.db                   │ • LiteLLM_UserTable          │ • launch_     │
│ • 1panel.db (settings/hosts) │ • LiteLLM_SpendLogs          │   history.db  │
│ • Zero PostgreSQL dependency │ • LiteLLM_ProxyModelTable    │ • token_      │
│ • Pure host hardware &       │ • Virtual Keys & Spend Caps  │   routers.db  │
│   container state            │ • Redis session tokens       │ • download_   │
│                              │                              │   tasks.db    │
└──────────────────────────────┴──────────────────────────────┴───────────────┘
```

### A. 1Panel Control Plane (Native SQLite)
* Completely decoupled from PostgreSQL.
* Stores host hardware metrics, SSL certificates, container switch states, and firewall definitions inside `${WORKSPACE_ROOT}/data/1panel/db/` (`1panel.db`, `alert.db`).

### B. Lango Persistent Database Layer (PostgreSQL 16)
* **Target Database:** `litellm` (initialized via `scripts/db/init-postgres.sh`).
* **Applied Schemas:** 189 structural migrations processed successfully via Prisma engine toolings.
* **Tables Present:** 83 operational data tables fully generated (e.g., `LiteLLM_UserTable`, `LiteLLM_ProxyModelTable`, `LiteLLM_SpendLogs`).
* **Active Administrative Key:** Resolves dynamically from `.env` (`LITELLM_MASTER_KEY=sk-wolinet-admin-2026`).

### C. Mitambo Historical Preservation Pools (Local SQLite)
Mounted at `${WORKSPACE_ROOT}/data/mitambo/` (or `/var/lib/wolinet/data/mitambo`):
* `launch_history.db` &mdash; Tracks historical quantized weight deployments (e.g., `deepseek-coder-1.3b-tZIwEoUf`).
* `token_routers.db` &mdash; Retains metric weights and internal request counts.
* `download_tasks.db` &mdash; Logs automated download queue operations for local GGUF models.

### D. Quantized Local Memory Storage
All model execution weights are stored inside `${WORKSPACE_ROOT}/models/` (or `/var/lib/wolinet/models/` in production Linux):
* `wolinex-coder` (`Qwen2.5-Coder-3B-Instruct-GGUF`) &mdash; Core structural programming and fast agent tool calls.
* `qwen2.5-omni-3b` &mdash; Real-time multimodal voice and vision operations.
* `deepseek-coder-1.3b` &mdash; High-speed code execution mapping routines.

---

## 4. INSTRUCTIONS AND BEHAVIORAL PROMPTS FOR CODING AGENTS

### 🤖 AGENT OPERATION RULES

#### 🟢 MANDATORY SYSTEMS EXECUTION ACTIONS (WHAT TO DO)
1. **Respect Stage 1 Boot Hierarchy:** Always ensure DEC 1Panel Control Plane and its backing data stores (PostgreSQL & Redis) are active before initiating Lango Gateway or Mitambo Inference requests.
2. **Maintain Strict DB Isolation:** Never query or write 1Panel control plane settings to PostgreSQL. 1Panel must only read/write its native SQLite database files in `data/1panel/db/`.
3. **Preserve Host Port Mapping:** When modifying internal network controllers within Go code or Podman deployment Quadlets, preserve the `5433:5432` map for PostgreSQL to protect development machines from socket collisions.
4. **Isolate Desktop IDE & SDKs:** Never attempt to package or run `Wolinet-Dkt-Ide` inside server container pods or compose stacks. Treat it strictly as an external API client connecting to `http://<server-ip>:4000/v1`.
5. **Decouple Host Paths Dynamically:** Use dynamic host path resolution (`${WORKSPACE_ROOT}`, `.`, or `$PWD` in development; `/var/lib/wolinet` in production Linux environments) across all Makefiles, shell scripts, and Go service controllers.
6. **Use Unified Master Installer:** Deploy and verify the full sovereign cluster with `./install.sh` (or `./bin/wolinet-install`).

#### 🔴 ABSOLUTE ARCHITECTURAL PROHIBITIONS (WHAT NOT TO DO)
1. **DO NOT Mix Panel Configuration States with App DBs:** Never force the 1apanel core engine to log structural interface views onto the production PostgreSQL database. 1apanel must strictly retain its internal, isolated SQLite file state.
2. **DO NOT Use Port 4004 for 1Panel:** 1Panel operates on `:9999` (native/dev), `:8888` (standard control plane), and `:8089` (Quadlet pod ingress). Never configure or probe port 4004.
3. **DO NOT Confuse Port 8080 with Web Client:** Port `8080` is reserved for the Wolinet Obscura / Browser MCP container. The Sovereign Web Client runs on port `8081` (server) / `3080` (dev).
4. **DO NOT Reset Pod Namespaces on Service Updates:** When pushing code modifications or system fixes to a specific application layer (e.g., updating the WebUI front-end), do not execute a global pod cycle command. You must cycle the isolated target container instance cleanly.
5. **DO NOT Hardcode Machine User Directory Paths:** Never embed explicit paths like `/Users/apple/...` or `/home/ubuntu/...` into Go source code files, configurations, or container templates. All directory structures must resolve dynamically using relative anchors (`.`), current path variables (`$PWD`), or structured environment tokens (`${WORKSPACE_ROOT}`).
6. **DO NOT Use Docker Commands Natively in Production Scripts:** Production automation must target rootless `podman` Quadlets (`orchestrator/podman/quadlets/`) and `podman compose`.
7. **DO NOT Invoke Ollama Services:** Never generate templates, routes, or UI components linked to Ollama execution states. All local inference processes belong exclusively to Mitambo.
8. **DO NOT Hardcode Credentials:** Absolutely zero plain-text database hashes, Cloudflare tokens, encryption keys, or local loop passwords may exist inside code files or configurations. Bind every secret dynamically to local environment parameters (`.env`).

---

## 5. RESOURCE DEDUPLICATION & ARCHITECTURAL BOUNDARIES

To prevent duplicate background processes, memory fragmentation, and massive VRAM/RAM waste, responsibilities are strictly partitioned across three distinct layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                STRICT TASK DEDICATION & RESOURCE DEDUPLICATION              │
├──────────────────────────────┬──────────────────────────────┬───────────────┤
│ 1. 1Panel Control Plane      │ 2. Mitambo (Compute Core)    │ 3. Lango      │
│    (Host Hardware & Watchdog)│    (Sole GGUF Matrix Engine) │    (Gateway)  │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ • Physical CPU/RAM metrics   │ • GGUF model execution       │ • Public /v1  │
│ • Podman socket supervisor   │ • Memory-locked VRAM/RAM     │ • API Keys &  │
│ • Reverse proxy & ACME SSL   │ • CUDA / Metal Tensor Ops    │   Spend logs  │
│ • Isolated Native SQLite DB  │ • Internal :9997 only        │ • Cloud Fall- │
│ ❌ ZERO AI Inferences        │ ❌ NO API Key Management     │   back & Mesh │
│ ❌ ZERO Model Weight Loading │ ❌ NO Public Internet Ports  │ ❌ NO Tensors │
└──────────────────────────────┴──────────────────────────────┴───────────────┘
```

### A. Why Upstream 1Panel App Store AI Must Never Run
Standard 1Panel includes an app store with optional AI runners (Ollama, vLLM). In the Wolinet architecture:
* **Conflict:** If 1Panel installs Ollama or vLLM, it allocates another 8GB–32GB of VRAM and loads duplicate GGUF models into memory, crashing the system due to Out-Of-Memory (OOM) kernel panics.
* **Enforcement:** 1Panel's AI app installer is strictly disabled. 1Panel only monitors the **container status and hardware usage** of `mitambo-inference`. It never runs its own inference daemons.

### B. Boundary Matrix: Who Does What?

| Operational Task | Assigned Subsystem | Prohibited Subsystems | Rationale & Resource Impact |
| :--- | :--- | :--- | :--- |
| **Host Resource Monitoring** (CPU, RAM, GPU temp, Disk) | **1Panel** (`:9999`/`:8888`) | Mitambo, Lango | 1Panel has bare-metal host privileges and systemd access; services inside containers only see virtual limits. |
| **Container Auto-Healing & Lifecycle** | **1Panel** (via Podman socket) | Mitambo, Lango | Prevents nested container socket exposure; 1Panel controls the Podman daemon from the host. |
| **Inference & Tensor Computation** (GGUF, MPS, CUDA) | **Mitambo** (`:9997`) | 1Panel, Lango, Web Client | Concentrates 100% of GPU VRAM into a single memory-locked pool (`LimitMEMLOCK=-1`, `ShmSize=8g`). |
| **API Routing & Key Authentication** | **Lango** (`:4000`) | 1Panel, Mitambo | Single source of truth for spend tracking, rate-limiting, and PostgreSQL auditing. Mitambo has zero auth overhead. |
| **Edge SSL & Reverse Proxy** | **1Panel** (OpenResty/Nginx) | Lango, Mitambo | 1Panel handles ACME certificates and edge routing on ports `:80`/`:443` without container network overhead. |
| **Agent Chat & MCP Workspaces** | **Web Client** (`:8081`) / **IDE** | 1Panel | UI state and MCP client tools are strictly isolated to client frontends. |

