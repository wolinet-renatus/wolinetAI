#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI Gateway Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [ -f "${ROOT_DIR}/.env" ]; then
    echo "[Gateway] Sourcing ${ROOT_DIR}/.env"
    set -o allexport
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
    set +o allexport
fi

# Normalize branding asset paths if relative for environment portability
if [ -n "${UI_LOGO_PATH:-}" ] && [[ "${UI_LOGO_PATH}" != /* ]] && [[ "${UI_LOGO_PATH}" != http* ]]; then
    export UI_LOGO_PATH="${ROOT_DIR}/${UI_LOGO_PATH}"
fi
if [ -n "${UI_LOGO_PATH_DARK:-}" ] && [[ "${UI_LOGO_PATH_DARK}" != /* ]] && [[ "${UI_LOGO_PATH_DARK}" != http* ]]; then
    export UI_LOGO_PATH_DARK="${ROOT_DIR}/${UI_LOGO_PATH_DARK}"
fi
if [ -n "${LITELLM_FAVICON_URL:-}" ] && [[ "${LITELLM_FAVICON_URL}" != /* ]] && [[ "${LITELLM_FAVICON_URL}" != http* ]]; then
    export LITELLM_FAVICON_URL="${ROOT_DIR}/${LITELLM_FAVICON_URL}"
fi

PORT="${WOLINET_GATEWAY_PORT:-4000}"
HOST="${WOLINET_GATEWAY_HOST:-0.0.0.0}"
CONFIG="${SCRIPT_DIR}/config.yaml"

echo "[Gateway] Starting Wolinet AI Gateway on http://${HOST}:${PORT}"
echo "[Gateway] Unified API Endpoint: http://${HOST}:${PORT}/v1"
echo "[Gateway] Model Routing Table: ${CONFIG}"

exec "${ROOT_DIR}/.venv/bin/litellm" \
    --config "${CONFIG}" \
    --port "${PORT}" \
    --host "${HOST}"
