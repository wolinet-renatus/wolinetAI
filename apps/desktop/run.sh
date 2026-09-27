#!/usr/bin/env bash
# ==============================================================================
# Launch Wolinet AI Desktop (Native Intel macOS App)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APP_PATH="${SCRIPT_DIR}/WolinetAI.app"

# Source environment if present
if [ -f "${ROOT_DIR}/apps/web-client/.env" ]; then
    set -o allexport
    source "${ROOT_DIR}/apps/web-client/.env"
    set +o allexport
elif [ -f "${ROOT_DIR}/.env" ]; then
    set -o allexport
    source "${ROOT_DIR}/.env"
    set +o allexport
fi

# Pre-set Gateway defaults
export LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}"
export LITELLM_API_KEY="${LITELLM_API_KEY:-sk-wolinet-admin-2026}"
export LITESPEED_MODEL="${LITESPEED_MODEL:-wolinex-coder}"

echo "[Wolinet Desktop] Launching native Intel macOS app: ${APP_PATH}"
echo "[Wolinet Desktop] Connected to Gateway: ${LITELLM_BASE_URL}"
open "${APP_PATH}"
