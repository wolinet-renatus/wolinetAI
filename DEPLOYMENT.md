# Wolinet AI: Production Deployment & Infrastructure Guide

Complete, highly optimized Docker Compose network architecture, Nginx reverse proxy topology, and CI/CD deployment guide for the **Wolinet Ecosystem** on a single Contabo GPU/CPU Server using raw Docker networking or Dokploy.

---

## 1. Subdomain Topology & Product Matrix

The ecosystem exposes 5 distinct public subdomains terminating TLS on an isolated edge Nginx reverse proxy. All internal inter-service traffic stays private to the Docker bridge network (`wolinet_internal`) with near-zero latency.

```
                    Internet (Client Traffic)
                               │
               ┌───────────────┼───────────────┐
               │ Ports 80, 443 │               │
               ▼               ▼               ▼
        ┌──────────────────────────────────────────────┐
        │  Edge Nginx Reverse Proxy (TLS Terminator)   │
        └──────────────────────┬───────────────────────┘
                               │
       Docker Bridge Network: wolinet_internal (Private 172.x)
        ├── ai.wolinet.com      ──► website:8080    (Bespoke Homepage & App Store Links)
        ├── wolinex.wolinet.com ──► wolinex:8080    (Open WebUI Studio, Replicas: 2)
        ├── lango.wolinet.com   ──► lango:4000      (LiteLLM AI Gateway, Replicas: 2)
        ├── mitambo.wolinet.com ──► mitambo:9997    (Xinference Engine, Basic Auth)
        └── dev.wolinet.com     ──► devportal:8080  (Docs, Key Studio & Live Assistant)
            (docs.wolinet.com)
                               │
        ├── postgres:5432       (Shared DB: 'litellm' & 'webui' databases)
        └── redis:6379          (Session cache & router coordination)
```

| Subdomain | Upstream Target | Description & Responsibilities |
| :--- | :--- | :--- |
| **`ai.wolinet.com`** | `website:8080` | **Marketing Homepage & Showcase:** Custom, fast-loading, branded interface with product matrix mega-menu and App Store / Google Play / Desktop download destinations. |
| **`wolinex.wolinet.com`** | `wolinex:8080` | **Wolinet AI Studio:** User-facing WebUI client with model chat, vision/audio streaming, file RAG, and wildcard session cookie issuance (`.wolinet.com`). |
| **`lango.wolinet.com`** | `lango:4000` | **LiteLLM AI Gateway:** Sovereign routing engine, OpenAI-compatible `/v1` endpoints, budget controls, Postgres spend logging, and CORS preflight handling. |
| **`mitambo.wolinet.com`** | `mitambo:9997` | **Xinference Inference Engine:** High-performance local inference backend (CPU / NVIDIA CUDA). Protected by HTTP Basic Auth (`mitambo.htpasswd`). |
| **`dev.wolinet.com`** / **`docs.wolinet.com`** | `devportal:8080` | **Developer Documentation & Key Studio:** Unified SSO session recognition, dynamic API key generation/rotation, SSE streaming assistant widget, and `/docs` interactive Scalar API specification. |

---

## 2. Docker Compose Network & Service Isolation

All containers attach exclusively to a single user-defined bridge network (`wolinet_internal`). 

### Direct Microservice Cross-References
* **WebUI (`wolinex`)** connects directly to LiteLLM via `http://lango:4000/v1` and database `postgresql://postgres:...@postgres:5432/webui`.
* **LiteLLM (`lango`)** bridges to the inference engine via `http://mitambo:9997` and database `postgresql://postgres:...@postgres:5432/litellm`.
* **Developer Portal (`devportal`)** proxies auth and session checks directly to `http://wolinex:8080/api/wolinet/auth` and streaming chat to `http://lango:4000/v1`.
* **PostgreSQL (`postgres`)** initializes both `litellm` and `webui` databases and indexes via [`scripts/db/init-postgres.sh`](file:///Users/apple/Documents/wolinetai/scripts/db/init-postgres.sh). SQLite file creation is completely disabled.

### Model Storage & Strict Isolation Policy
No model weights or GGUF files are bundled into container images or manually copied to the server disk.
* Xinference runs with `xinference_data` volume mounted to `/root/.xinference`.
* Models are launched dynamically on-demand from **Hugging Face** or **ModelScope** via Xinference's native Model Launch API or Web UI.
* Models persist across container restarts in the Docker named volume without host filesystem contamination.

---

## 3. Hardware Allocations: CPU VPS vs. NVIDIA GPU Server

Wolinet AI supports dual deployment topologies through Docker Compose layer composability:

### Pure CPU Profile (Default: `docker-compose.prod.yml`)
Enforces compute limits to prevent CPU starvation on general-purpose VPS nodes:
```yaml
services:
  mitambo:
    deploy:
      resources:
        limits:
          cpus: "12.0"
          memory: 28G
```

### NVIDIA GPU Profile (Override: `docker-compose.gpu.yml`)
Pins GGUF model layers and tensor computations directly into GPU VRAM using NVIDIA Container Toolkit:
```yaml
services:
  mitambo:
    deploy:
      resources:
        limits:
          cpus: "16.0"
          memory: 28G
        reservations:
          memory: 8G
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,utility
```

To run on a Contabo NVIDIA GPU server:
```bash
docker compose --project-name wolinet \
  -f docker-compose.prod.yml \
  -f docker-compose.gpu.yml \
  up -d --wait
```

---

## 4. Nginx Reverse Proxy & Streaming Configuration

The Nginx topology in [`nginx/conf.d/wolinet.conf`](file:///Users/apple/Documents/wolinetai/nginx/conf.d/wolinet.conf) enforces:

### Real-Time SSE Streaming Optimization
Buffer artifacts during token generation are strictly suppressed on `lango.wolinet.com` and `wolinex.wolinet.com`:
```nginx
proxy_buffering off;
proxy_cache off;
chunked_transfer_encoding on;
proxy_read_timeout 600s;
add_header X-Accel-Buffering no;
```

### Wildcard SSO Cookie Security
Cookies set by Wolinex are scoped to the root `.wolinet.com` domain with strict transport attributes:
```nginx
proxy_cookie_domain wolinex.wolinet.com .wolinet.com;
proxy_cookie_path / "/; Domain=.wolinet.com; Secure; SameSite=Lax";
proxy_cookie_flags ~ secure httponly samesite=lax;
```
This enables authenticated users on `wolinex.wolinet.com` to navigate seamlessly to `dev.wolinet.com` without re-authenticating.

### CORS Preflight & External Application Access
`lango.wolinet.com` safely handles preflight `OPTIONS` requests and sets dynamic origin reflection:
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

## 5. Deployment Options: Raw Docker vs. Dokploy

### Option A: Raw Docker & Docker Compose (Standard Contabo Setup)

1. **DNS Setup:** Direct A records for `ai`, `wolinex`, `lango`, `mitambo`, and `dev` pointing to server IP.
2. **Server Initialization:**
   ```bash
   sudo mkdir -p /opt/wolinetai && sudo chown "$USER" /opt/wolinetai
   git clone --branch production https://github.com/wolinet-renatus/wolinetAI.git /opt/wolinetai
   cd /opt/wolinetai
   cp .env.prod.example .env
   chmod 600 .env
   # Populate secrets (POSTGRES_PASSWORD, REDIS_PASSWORD, LITELLM_MASTER_KEY, etc.)
   ```
3. **Provision TLS & Passwords:**
   ```bash
   ./scripts/setup-tls.sh
   ./scripts/setup_mitambo_auth.sh
   ```
4. **Launch Stack:**
   * **CPU:** `WOLINET_IMAGE_TAG=latest ./scripts/deploy_production.sh latest`
   * **GPU:** Append `-f docker-compose.gpu.yml` to compose commands.

### Option B: Dokploy Deployment

Dokploy can orchestrate the Wolinet stack as a native Compose project:

1. **Create Compose Service in Dokploy:**
   - In the Dokploy Dashboard, click **Create Application** ➔ select **Compose**.
   - Set Name to `wolinet`.
2. **Repository Configuration:**
   - Provider: **GitHub**
   - Repository: `wolinet-renatus/wolinetAI`
   - Branch: `production`
   - Compose File Path: `docker-compose.prod.yml` (or upload merged `docker-compose.prod.yml` + `docker-compose.gpu.yml`)
3. **Environment Variables:**
   - Copy the contents of `.env.prod.example` into Dokploy's **Environment** tab.
   - Replace all `CHANGE_ME` tokens with cryptographically secure random values.
4. **Port Binding / Reverse Proxy Mode:**
   - If using Dokploy's integrated Traefik proxy, you can map domains directly to services or let the bundled `nginx` service bind host ports `80` and `443` directly.
5. **Volume Persistence:**
   - Named volumes `postgres_data`, `redis_data`, `xinference_data`, and `webui_data` will be automatically preserved across rebuilds.

---

## 6. Automated CI/CD Rolling Deployment Pipeline

The workflow defined in [`.github/workflows/deploy.yml`](file:///Users/apple/Documents/wolinetai/.github/workflows/deploy.yml) provides an automated delivery pipeline:

1. **Validate Stage:**
   - Executes deployment contract tests: `python -m unittest discover -s tests/deployment -v`.
   - Lints browser JavaScript: `node --check apps/homepage/app.js` and `apps/dev-portal/app.js`.
   - Validates Compose syntax: `docker compose -f docker-compose.prod.yml config`.
   - Tests Nginx syntax in an isolated container with temporary certificates: `nginx -t`.
2. **Build Stage:**
   - Builds isolated multi-stage images for `wolinet-homepage`, `wolinet-devportal`, `wolinet-lango`, and `wolinet-wolinex`.
   - Pushes SHA-tagged artifacts to GitHub Container Registry (`ghcr.io`).
3. **Deploy Stage (Push to `production` branch):**
   - Establishes secure SSH tunnel to the Contabo server.
   - Syncs Compose configurations and deployment scripts via `rsync`.
   - Invokes [`scripts/deploy_production.sh`](file:///Users/apple/Documents/wolinetai/scripts/deploy_production.sh).
   - Performs zero-downtime rolling restart (`replicas: 2` on stateless services).
   - Reloads Nginx gracefully (`nginx -s reload`).
   - Automatically rolls back to the previous tag if health checks fail.
   - Performs public endpoint verification across all 4 services.
