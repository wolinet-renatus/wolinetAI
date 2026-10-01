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

echo "==> [wolinet] 4/5 Verifying UI distribution files..."
test -f "${ROOT_DIR}/inference/xinference/ui/web/dist/index.html" || {
  echo "ERROR: inference/xinference/ui/web/dist/index.html is missing!" >&2
  exit 1
}
echo "==> [wolinet] Verified $(find "${ROOT_DIR}/inference/xinference/ui/web/dist" -type f | wc -l) static files in UI dist"

echo "==> [wolinet] 5/5 Starting stack fresh with latest configuration..."
docker compose up -d --remove-orphans

echo "==> [wolinet] Deployment complete! Run scripts/deploy/verify-stack.sh to check health."
