#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — Sovereign Podman Deployment Engine
# Deploys Mitambo, Lango, WolinEx, Home Website, and Dev Portal in a unified Pod.
# Host networking loopback ensures 0-latency inter-container communication.
# ==============================================================================
set -euo pipefail

POD_NAME="wolinetai-core-pod"
BASE_DIR="${WORKSPACE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DATA_DIR="${BASE_DIR}/data"

echo "============================================================"
echo "Wolinet AI — Sovereign Podman Orchestration"
echo "============================================================"

# 1. Ensure Podman VM is active
if ! podman machine info >/dev/null 2>&1; then
    echo "==> Starting Podman Machine..."
    podman machine start || true
fi

# 2. Create or Update the unified Pod
RECREATE_POD=false
if [[ "${1:-}" == "--recreate" ]]; then
    RECREATE_POD=true
elif podman pod exists "${POD_NAME}"; then
    # Check if existing pod has port 3000 and 8082 mapped
    if ! podman pod inspect "${POD_NAME}" | grep -q '"3000"'; then
        echo "==> Detected legacy port configuration on '${POD_NAME}'. Re-provisioning pod with ports 3000 & 8082..."
        RECREATE_POD=true
    fi
fi

if [[ "${RECREATE_POD}" == "true" ]] && podman pod exists "${POD_NAME}"; then
    echo "==> Stopping and recreating Pod '${POD_NAME}'..."
    podman pod rm -f "${POD_NAME}"
fi

if podman pod exists "${POD_NAME}"; then
    echo "==> Pod '${POD_NAME}' already exists and is configured."
else
    echo "==> Creating unified Pod '${POD_NAME}' with exposed ports..."
    podman pod create \
        --name "${POD_NAME}" \
        -p 3000:3000 \
        -p 8080:8080 \
        -p 8082:8082 \
        -p 4000:4000 \
        -p 5433:5432 \
        -p 6379:6379 \
        -p 8089:8089 \
        -p 9997:9997
fi

# 3. PostgreSQL Database Cluster
echo "==> Deploying wolinet-postgres..."
if podman container exists wolinet-postgres; then
    podman start wolinet-postgres
else
    podman run -d \
        --name wolinet-postgres \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${DATA_DIR}/postgres:/var/lib/postgresql/data:Z" \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=litellm \
        docker.io/library/postgres:16-alpine \
        postgres -c tcp_keepalives_idle=60 -c tcp_keepalives_interval=10 -c tcp_keepalives_count=5
fi

# 4. Redis Cache Store
echo "==> Deploying wolinet-redis..."
if podman container exists wolinet-redis; then
    podman start wolinet-redis
else
    podman run -d \
        --name wolinet-redis \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${DATA_DIR}/redis:/data:Z" \
        docker.io/library/redis:7-alpine \
        redis-server --requirepass redis --appendonly yes
fi

# 5. Mitambo Inference Core (Xinference)
echo "==> Deploying wolinet-mitambo..."
if podman container exists wolinet-mitambo; then
    podman start wolinet-mitambo
elif podman image exists ghcr.io/wolinet-renatus/wolinet-mitambo-cpu:latest; then
    podman run -d \
        --name wolinet-mitambo \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${BASE_DIR}/models:/models:ro" \
        -v "${DATA_DIR}/mitambo:/root/.xinference:Z" \
        -e XINFERENCE_HOME=/root/.xinference \
        -e XINFERENCE_AUTH_DB_PATH=/root/.xinference/auth/auth.db \
        -e XINFERENCE_MODEL_SRC=huggingface \
        -e XINFERENCE_ENABLE_VIRTUAL_ENV=0 \
        -e XINFERENCE_AUTH_ADVANCED=true \
        -e XINFERENCE_ADMIN_USER=admin \
        -e XINFERENCE_ADMIN_PASSWORD=Woli@1211 \
        -e XINFERENCE_API_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e OMP_NUM_THREADS=8 \
        -e VECLIB_MAXIMUM_THREADS=8 \
        ghcr.io/wolinet-renatus/wolinet-mitambo-cpu:latest \
        xinference-local -H 0.0.0.0 -p 9997 --log-level info
else
    echo "==> Deploying Mitambo inference host bridge (host:9998 -> loopback:9997)..."
    podman run -d \
        --name wolinet-mitambo \
        --pod "${POD_NAME}" \
        --restart always \
        docker.io/library/alpine:latest \
        sh -c "apk add --no-cache socat && exec socat TCP-LISTEN:9997,fork,reuseaddr TCP:host.containers.internal:9998"
fi

# 6. Lango AI Gateway (LiteLLM)
echo "==> Deploying wolinet-lango..."
if podman container exists wolinet-lango; then
    podman start wolinet-lango
else
    podman run -d \
        --name wolinet-lango \
        --pod "${POD_NAME}" \
        --restart always \
        --entrypoint /usr/local/bin/start-gateway.sh \
        -v "${BASE_DIR}/gateway/start-gateway.sh:/usr/local/bin/start-gateway.sh:ro" \
        -v "${BASE_DIR}/gateway/config.yaml:/app/config.yaml:ro" \
        -v "${BASE_DIR}/gateway/assets:/app/assets:ro" \
        -v "${BASE_DIR}/gateway/litellm/router.py:/app/.venv/lib/python3.13/site-packages/litellm/router.py:ro" \
        -e LITELLM_MASTER_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e WOLINET_GATEWAY_MASTER_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e UI_USERNAME=admin \
        -e UI_PASSWORD=Wolinet@2026! \
        -e LITELLM_CONFIG_PATH=/app/config.yaml \
        -e DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/litellm \
        -e REDIS_HOST=127.0.0.1 \
        -e REDIS_PORT=6379 \
        -e REDIS_PASSWORD=redis \
        -e REDIS_URL=redis://:redis@127.0.0.1:6379 \
        -e WOLINET_API_BASE=http://127.0.0.1:9997/v1 \
        -e WOLINET_INFERENCE_URL=http://127.0.0.1:9997 \
        -e XINFERENCE_API_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e OPENAI_API_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e STORE_MODEL_IN_DB=true \
        -e DOCS_URL=/docs \
        -e ROOT_REDIRECT_URL=/ui \
        ghcr.io/wolinet-renatus/wolinet-lango:latest
fi

# 7. WolinEx Coder Studio (WebUI)
echo "==> Deploying wolinet-wolinex..."
if podman container exists wolinet-wolinex; then
    podman start wolinet-wolinex
elif podman image exists ghcr.io/wolinet-renatus/wolinet-wolinex:latest; then
    podman run -d \
        --name wolinet-wolinex \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${DATA_DIR}/wolinex:/app/backend/data:Z" \
        -e PORT=8080 \
        -e HOST=0.0.0.0 \
        -e WEBUI_NAME="Wolinet AI" \
        -e WEBUI_SECRET_KEY=dev-secret-key-32-chars-minimum-length-change-in-prod \
        -e OPENAI_API_BASE_URL=http://127.0.0.1:4000/v1 \
        -e OPENAI_API_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e LITELLM_BASE_URL=http://127.0.0.1:4000 \
        -e LITELLM_MASTER_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/webui \
        -e WEBUI_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/webui \
        -e REDIS_URL=redis://:redis@127.0.0.1:6379 \
        -e ENABLE_OLLAMA_API=False \
        -e ENABLE_OPENAI_API=True \
        -e ENABLE_FORWARD_USER_INFO_HEADERS=True \
        -e DEFAULT_MODELS="Wolinet Pro" \
        -e BYPASS_MODEL_ACCESS_CONTROL=True \
        -e RAG_EMBEDDING_ENGINE=openai \
        -e RAG_EMBEDDING_MODEL="wolinex-embed" \
        -e RAG_OPENAI_API_BASE_URL=http://127.0.0.1:4000/v1 \
        -e RAG_OPENAI_API_KEY=sk-XvKFiwDoOtOe8i4lwbzb8Q \
        -e SCARF_NO_ANALYTICS=true \
        -e DO_NOT_TRACK=true \
        -e ANONYMIZED_TELEMETRY=false \
        ghcr.io/wolinet-renatus/wolinet-wolinex:latest
else
    echo "==> Deploying WolinEx Studio host bridge (host:8081 -> loopback:8080)..."
    podman run -d \
        --name wolinet-wolinex \
        --pod "${POD_NAME}" \
        --restart always \
        docker.io/library/alpine:latest \
        sh -c "apk add --no-cache socat && exec socat TCP-LISTEN:8080,fork,reuseaddr TCP:host.containers.internal:8081"
fi

# 8. Wolinet AI Home / Marketing Website
echo "==> Deploying wolinet-website..."
if podman container exists wolinet-website; then
    podman start wolinet-website
else
    podman run -d \
        --name wolinet-website \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${BASE_DIR}/apps/website:/usr/share/nginx/html:ro" \
        -v "${BASE_DIR}/apps/website/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
        docker.io/library/nginx:1.27-alpine
fi

# 9. Wolinet AI Developer Portal & Docs
echo "==> Deploying wolinet-devportal..."
if podman container exists wolinet-devportal; then
    podman start wolinet-devportal
else
    podman run -d \
        --name wolinet-devportal \
        --pod "${POD_NAME}" \
        --restart always \
        -v "${BASE_DIR}/apps/dev-portal:/usr/share/nginx/html:ro" \
        -v "${BASE_DIR}/apps/dev-portal/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
        docker.io/library/nginx:1.27-alpine
fi

echo "============================================================"
echo "Sovereign Podman Deployment initiated successfully!"
echo "Services active in '${POD_NAME}':"
echo " - Home Website:        http://localhost:3000"
echo " - WolinEx Studio:       http://localhost:8080"
echo " - Developer Portal:     http://localhost:8082"
echo " - Interactive API Docs: http://localhost:4000/docs & http://localhost:8082/docs"
echo " - Lango AI Gateway:     http://localhost:4000"
echo " - Mitambo Inference:    loopback:9997 (internal to pod)"
echo " - PostgreSQL Cluster:   localhost:5433 -> 5432"
echo " - Redis Cache:          loopback:6379 (internal to pod)"
echo " - 1apanel Ingress:      http://localhost:8089"
echo "============================================================"
