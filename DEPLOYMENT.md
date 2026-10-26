# Wolinet AI: Production Deployment & Infrastructure Guide

Complete Rootless Podman Quadlet architecture, DEC 1Panel Control Plane hierarchy, Nginx reverse proxy topology, and CI/CD deployment guide for the **Wolinet Ecosystem**.

---

## 1. Subdomain Topology & Product Matrix

The ecosystem exposes public subdomains terminating TLS on an isolated edge reverse proxy (managed via DEC 1Panel or edge Nginx). All internal inter-service traffic stays private to the unified Podman Pod network (`wolinetai-core-pod` / `wolinet_internal`) over local loopback (`127.0.0.1`) with near-zero latency.

```
                    Internet (Client Traffic)
                               │
               ┌───────────────┼───────────────┐
               │ Ports 80, 443 │               │
               ▼               ▼               ▼
        ┌──────────────────────────────────────────────┐
        │  Edge Reverse Proxy / DEC 1Panel Ingress     │
        └──────────────────────┬───────────────────────┘
                               │
       Podman Pod Namespace: wolinetai-core-pod (Loopback 127.0.0.1)
        ├── panel.wolinet.com   ──► 1apanel:8888/:8089 (Stage 1 Control Plane, Native SQLite)
        ├── ai.wolinet.com      ──► website:80/:3000   (Enterprise Homepage & Download Links)
        ├── wolinex.wolinet.com ──► web-client:8081    (Open WebUI Sovereign Workspace)
        ├── lango.wolinet.com   ──► lango:4000         (LiteLLM AI Gateway, /v1 & /ui)
        ├── mitambo.wolinet.com ──► mitambo:9997       (Xinference Engine, GGUF Models)
        └── dev.wolinet.com     ──► devportal:8082     (Docs, Key Studio & Scalar Specs)
            (docs.wolinet.com)
                               │
        ├── postgres:5433->5432 (Lango DB: 'litellm' database, Prisma migrations)
        ├── redis:6379          (Session cache, token rate limits & router state)
        └── obscura:8080        (Sandboxed Browser MCP Container for Agent Tools)
```

| Subdomain | Upstream Target | Description & Responsibilities |
| :--- | :--- | :--- |
| **`panel.wolinet.com`** | `1apanel:8888` / `:8089` | **Stage 1 DEC 1Panel Control Plane:** Hardware supervision (CPU/RAM/GPU), storage mounts, Podman socket management, and isolated native SQLite DB. |
| **`ai.wolinet.com`** | `website:80` / `:3000` | **Marketing Homepage & Showcase:** Custom, fast-loading branded interface with product matrix, documentation links, and client download destinations. |
| **`wolinex.wolinet.com`** | `web-client:8081` | **Wolinet AI Studio (Open WebUI):** Sovereign chat interface, model switching, workspace tools, and session management. |
| **`lango.wolinet.com`** | `lango:4000` | **LiteLLM AI Gateway:** Sovereign routing engine, OpenAI-compatible `/v1` endpoints, budget controls, Postgres spend logging, and CORS preflight handling. |
| **`mitambo.wolinet.com`** | `mitambo:9997` | **Xinference Inference Engine:** High-performance local inference backend (Apple Silicon MPS / NVIDIA CUDA). Protected by HTTP Basic Auth. |
| **`dev.wolinet.com`** / **`docs.wolinet.com`** | `devportal:8082` | **Developer Documentation & Key Studio:** Dynamic API key rotation, interactive Scalar API specifications, and live developer assistants. |

---

## 2. Strict Database & Data Storage Isolation

The Wolinet architecture strictly isolates databases by functional tier to prevent cross-service corruption and security leakage:

1. **DEC 1Panel Control Plane (Native SQLite):**
   * Uses isolated SQLite database files in `${WORKSPACE_ROOT}/data/1panel/db/` (`1panel.db`, `alert.db`).
   * **Strict Isolation Mandate:** Zero connection or schema sharing with PostgreSQL or application databases. Retains pure host hardware metrics, SSL certificates, container switch states, and firewall definitions.
2. **Lango Persistent Database Layer (PostgreSQL 16 & Redis 7):**
   * Dedicated PostgreSQL 16 cluster housing the `litellm` database on port `5433` (host) $\rightarrow$ `5432` (internal).
   * 189 Prisma structural migrations managing `LiteLLM_UserTable`, `LiteLLM_SpendLogs`, and virtual keys.
   * Redis 7 (`:6379`) provides an in-memory Append-Only File (AOF) cache for token rate limiting and routing.
3. **Mitambo Historical Storage (Local SQLite Pools):**
   * Stores model launch history and task queues in `${WORKSPACE_ROOT}/data/mitambo/` (`launch_history.db`, `token_routers.db`, `download_tasks.db`).
4. **Quantized Model Weights (Local Disk):**
   * Quantized GGUF models are stored in `${WORKSPACE_ROOT}/models/` (or `/var/lib/wolinet/models/`). Models execute fully within memory boundaries without cloud dependency.

---

## 3. Client Products & SDKs (Strict Server Decoupling)

* **Wolinet Desktop IDE (`Wolinet-Dkt-Ide`):** An autonomous Tauri desktop client application that runs on developer workstations (macOS/Linux/Windows). It connects to the server purely over standard REST/WebSocket APIs (`http://<server-ip>:4000/v1`). It is **never** bundled or orchestrated into server Podman Quadlets or container images.
* **Wolinet SDKs (`packages/`):** Python, Go, and TypeScript client libraries for integrating external applications with the Lango Gateway.

---

## 4. Hardware Profiles: CPU Nodes vs. Apple Silicon vs. NVIDIA GPU

Wolinet AI dynamically optimizes hardware usage through native accelerator detection:

### Apple Silicon Profile (macOS M-Series)
* Utilizes **Metal Performance Shaders (MPS)** for accelerated matrix multiplication.
* Mitambo runs with native unified memory allocation, delivering 15–35+ tokens/second on 3B–7B quantized models (`wolinex-coder`).

### NVIDIA GPU Profile (Linux CUDA Server)
* Pins GGUF model layers and tensor computations directly into GPU VRAM using NVIDIA Container Toolkit (`--gpus all` or CDI device mapping):
```ini
# Quadlet: mitambo-inference.container
AddDevice=nvidia.com/gpu=all
Environment=NVIDIA_VISIBLE_DEVICES=all
Environment=NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### Pure CPU Profile (General-Purpose Cloud VPS)
* Enforces compute thread ceilings to prevent host starvation on 8–16 vCPU nodes:
```yaml
services:
  mitambo:
    deploy:
      resources:
        limits:
          cpus: "12.0"
          memory: 28G
```

---

## 5. Deployment Methods

### Option A: Master Sovereign Installer (Recommended)

Execute the 1-command installer on any Linux or macOS server:
```bash
./install.sh
```
This triggers the hierarchical 4-stage boot:
1. Preflight hardware diagnostics & container engine detection (Podman/Docker).
2. Stage 1: Boots DEC 1Panel Control Plane (`bin/1apanel`) and backing PostgreSQL 16 & Redis 7.
3. Stage 2: Boots Mitambo Local Inference Core (:9997) with GPU/MPS accelerator.
4. Stage 3: Boots Lango Sovereign API Gateway (:4000).
5. Stage 4: Boots Web Client (:8081), Dev Portal (:8082), Homepage (:80), and ai-memory (:49374).
6. Runs the synthetic Golden Loop probe to verify end-to-end transaction integrity.

### Option B: Rootless Podman Quadlets (`orchestrator/podman/quadlets/`)

For production systemd-managed Linux environments:
1. Copy quadlet definitions from `orchestrator/podman/quadlets/` to `~/.config/containers/systemd/`:
   * `wolinetai.pod` (Master Pod definition and port mappings)
   * `postgres-cluster.container`
   * `redis-cache.container`
   * `mitambo-inference.container`
   * `lango-gateway.container`
   * `wolinet-browser.container`
   * `wolinet-website.container`
   * `wolinet-devportal.container`
2. Reload systemd and start:
   ```bash
   systemctl --user daemon-reload
   systemctl --user start wolinetai-pod.service
   ```

### Option C: Docker Compose / Dokploy

For existing environments running Docker or Dokploy:
```bash
docker compose -f docker-compose.yml up -d
```
All services attach to the `wolinet_internal` overlay network with healthcheck dependency gates.

---

## 6. Nginx Reverse Proxy & Streaming Configuration

The Nginx topology enforces:

### Real-Time SSE Streaming Optimization
Buffer artifacts during token generation are strictly suppressed on `lango.wolinet.com` and `wolinex.wolinet.com`:
```nginx
proxy_buffering off;
proxy_cache off;
chunked_transfer_encoding on;
proxy_read_timeout 600s;
add_header X-Accel-Buffering no;
```

### CORS Preflight & External Application Access
`lango.wolinet.com` safely handles preflight `OPTIONS` requests:
```nginx
if ($request_method = 'OPTIONS') {
    add_header 'Access-Control-Allow-Origin' '$http_origin' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS, PATCH' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Requested-With, Accept, Origin, User-Agent, Cache-Control, X-OpenWebUI-User-Id, X-OpenWebUI-User-Email, X-OpenWebUI-User-Name' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;
    add_header 'Access-Control-Max-Age' 86400;
    add_header 'Content-Type' 'text/plain charset=UTF-8';
    add_header 'Content-Length' 0;
    return 204;
}
```

---

## 7. Automated CI/CD Rolling Deployment Pipeline

The workflow defined in [`.github/workflows/deploy.yml`](file:///Users/apple/Documents/wolinetai/.github/workflows/deploy.yml) provides an automated delivery pipeline:
1. **Validate Stage:** Tests deployment contracts, JavaScript syntax, and Compose syntax.
2. **Build Stage:** Builds multi-stage images for `wolinet-lango`, `wolinet-wolinex`, `wolinet-homepage`, and `wolinet-devportal`.
3. **Deploy Stage:** Syncs configuration, triggers rolling restarts, reloads reverse proxy configurations, and verifies the Golden Loop synthetic transaction.
