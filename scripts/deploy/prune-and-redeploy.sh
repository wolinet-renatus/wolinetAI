#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Clean Prune & Fresh Stack Redeployment
# ==============================================================================
# Safely prunes stale/dangling Docker build artifacts, wipes temporary caches,
# pulls the latest git commit with all static UI assets, and restarts the stack fresh.
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo "==> [wolinet] 1/5 Pulling latest changes from git..."
git fetch origin main
git reset --hard origin/main

echo "==> [wolinet] 2/5 Stopping existing stack containers..."
docker compose down --remove-orphans || true

echo "==> [wolinet] 3/5 Pruning stale Docker logs, builder caches, and unused images..."
# 1. Truncate bloated container log files if accessible
truncate -s 0 /var/lib/docker/containers/*/*-json.log 2>/dev/null || true

# 2. Prune stopped containers
docker container prune -f

# 3. Aggressively prune BuildKit build cache (frees tens of gigabytes)
docker builder prune -a -f

# 4. Prune unused images not used by running containers
docker image prune -f

echo "==> [wolinet] 4/5 Verifying UI and website distribution files..."
test -f "${ROOT_DIR}/inference/xinference/ui/web/dist/index.html" || {
  echo "ERROR: inference/xinference/ui/web/dist/index.html is missing!" >&2
  exit 1
}
test -f "${ROOT_DIR}/website/index.html" || {
  echo "ERROR: website/index.html is missing!" >&2
  exit 1
}

# Harden host permissions so container workers (nginx, xinference, litellm) can read files
chmod -R a+rX "${ROOT_DIR}/website" 2>/dev/null || true
chmod -R a+rX "${ROOT_DIR}/inference/xinference/ui/web/dist" 2>/dev/null || true
chmod -R a+rX "${ROOT_DIR}/inference/frontend/out" 2>/dev/null || true
chmod -R a+rX "${ROOT_DIR}/apps/dev-portal" 2>/dev/null || true
chmod -R a+rX "${ROOT_DIR}/apps/web-client/backend/open_webui" 2>/dev/null || true
chmod +x "${ROOT_DIR}/inference/start-mitambo.sh" 2>/dev/null || true
chmod +x "${ROOT_DIR}/gateway/start-gateway.sh" 2>/dev/null || true
sysctl -w vm.overcommit_memory=1 2>/dev/null || true

echo "==> [wolinet] Verified $(find "${ROOT_DIR}/inference/xinference/ui/web/dist" -type f | wc -l) files in xinference UI dist"
echo "==> [wolinet] Verified $(find "${ROOT_DIR}/website" -type f | wc -l) files in website dist"

echo "==> [wolinet] 5/5 Pulling pre-built images and starting stack fresh..."
COMPOSE_FILE="docker-compose.yml"
if [ -f "docker-compose.prod.yml" ] && [ "${1:-}" = "prod" ]; then
  COMPOSE_FILE="docker-compose.prod.yml"
fi

# Pull latest pre-built images from GHCR — NEVER build directly on host
docker compose -f "${COMPOSE_FILE}" pull --quiet || docker compose -f "${COMPOSE_FILE}" pull
docker compose -f "${COMPOSE_FILE}" up -d --no-build --remove-orphans

# Force reload lango and wolinex containers to pick up updated config and models
for svc in lango wolinex; do
  C_ID=$(docker ps -q -f name="${svc}" | head -n 1 || true)
  if [ -n "${C_ID}" ]; then
    echo "==> [wolinet] Restarting ${svc} container (${C_ID})..."
    docker restart "${C_ID}" >/dev/null 2>&1 || true
  fi
done

echo "==> [wolinet] Deployment complete! The model-sync service will publish running Xinference models to LiteLLM."
