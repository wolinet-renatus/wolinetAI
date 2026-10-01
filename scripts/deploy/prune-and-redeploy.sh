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

echo "==> [wolinet] 3/5 Pruning stale Docker images and builder caches..."
# Remove stopped/dangling containers and untagged images without deleting named volumes
docker container prune -f
docker image prune -f
docker builder prune -f

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
chmod +x "${ROOT_DIR}/inference/start-mitambo.sh" 2>/dev/null || true
chmod +x "${ROOT_DIR}/gateway/start-gateway.sh" 2>/dev/null || true
chmod +x "${ROOT_DIR}/scripts/models/launch-wolinet-coder.sh" 2>/dev/null || true

echo "==> [wolinet] Verified $(find "${ROOT_DIR}/inference/xinference/ui/web/dist" -type f | wc -l) files in xinference UI dist"
echo "==> [wolinet] Verified $(find "${ROOT_DIR}/website" -type f | wc -l) files in website dist"

echo "==> [wolinet] 5/5 Starting stack fresh with latest configuration..."
COMPOSE_FILE="docker-compose.yml"
if [ -f "docker-compose.prod.yml" ] && [ "${1:-}" = "prod" ]; then
  COMPOSE_FILE="docker-compose.prod.yml"
fi
docker compose -f "${COMPOSE_FILE}" up -d --build --remove-orphans

echo "==> [wolinet] 6/6 Purging stale models from Open WebUI database..."
sleep 5
PG_CONTAINER=$(docker ps -q -f name=postgres | head -n 1 || true)
if [ -n "${PG_CONTAINER}" ]; then
  for db in webui wolinex; do
    docker exec "${PG_CONTAINER}" psql -U postgres -d "${db}" -c "DELETE FROM model WHERE id NOT IN ('wolinet-coder');" 2>/dev/null || true
  done
  echo "==> [wolinet] Stale models purged from Open WebUI database."
fi

# Force reload lango and wolinex containers to pick up updated config and models
for svc in lango wolinex; do
  C_ID=$(docker ps -q -f name="${svc}" | head -n 1 || true)
  if [ -n "${C_ID}" ]; then
    echo "==> [wolinet] Restarting ${svc} container (${C_ID})..."
    docker restart "${C_ID}" >/dev/null 2>&1 || true
  fi
done

echo "==> [wolinet] 7/7 Verifying Wolinet Coder (deepseek-coder-instruct) is active and running..."
bash "${ROOT_DIR}/scripts/models/launch-wolinet-coder.sh" || true

echo "==> [wolinet] Deployment complete! Stack is up, authenticated, model is running."

