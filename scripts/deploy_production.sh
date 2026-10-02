#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:?Usage: deploy_production.sh sha-<git-sha>}"
STATE_FILE="${ROOT_DIR}/.deployed-image-tag"
COMPOSE=(docker compose --parallel 1 --project-name wolinet --file "${ROOT_DIR}/docker-compose.prod.yml" --file "${ROOT_DIR}/docker-compose.gpu.yml")

if [ ! -f "${ROOT_DIR}/.env" ]; then
    echo "Missing production .env in ${ROOT_DIR}" >&2
    exit 1
fi

set -a
source "${ROOT_DIR}/.env"
set +a

set_release_images() {
    local tag="$1"
    export WOLINET_IMAGE_TAG="${tag}"
    export MITAMBO_IMAGE="ghcr.io/wolinet-renatus/wolinet-mitambo:${tag}"
    export LANGO_IMAGE="ghcr.io/wolinet-renatus/wolinet-lango:${tag}"
    export WOLINEX_IMAGE="ghcr.io/wolinet-renatus/wolinet-wolinex:${tag}"
    export WEBSITE_IMAGE="ghcr.io/wolinet-renatus/wolinet-homepage:${tag}"
}

"${ROOT_DIR}/scripts/setup_mitambo_auth.sh"

PREVIOUS_TAG=""
if [ -f "${STATE_FILE}" ]; then
    PREVIOUS_TAG="$(cat "${STATE_FILE}")"
fi

cd "${ROOT_DIR}"
set_release_images "${IMAGE_TAG}"
"${COMPOSE[@]}" config --quiet

if "${COMPOSE[@]}" ps --status running --quiet nginx | grep -q .; then
    "${COMPOSE[@]}" exec -T nginx nginx -t
fi

echo "==> [deploy] Cleaning bloated logs and stale Docker build caches before pull..."
truncate -s 0 /var/lib/docker/containers/*/*-json.log 2>/dev/null || true
docker builder prune -a -f 2>/dev/null || true
docker container prune -f 2>/dev/null || true
docker image prune -f 2>/dev/null || true

"${COMPOSE[@]}" pull mitambo lango wolinex website nginx

if ! "${COMPOSE[@]}" up -d --no-build --wait --remove-orphans; then
    if [ -n "${PREVIOUS_TAG}" ]; then
        echo "Deployment failed; restoring ${PREVIOUS_TAG}" >&2
        set_release_images "${PREVIOUS_TAG}"
        "${COMPOSE[@]}" pull mitambo lango wolinex website nginx
        "${COMPOSE[@]}" up -d --no-build --wait
    fi
    exit 1
fi
"${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d litellm \
    -f /docker-entrypoint-initdb.d/schema/03_indexes.sql
"${COMPOSE[@]}" exec -T nginx nginx -s reload

printf '%s\n' "${IMAGE_TAG}" > "${STATE_FILE}"
echo "Deployed ${IMAGE_TAG}"
"${COMPOSE[@]}" ps
