#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Web Portal Launcher (Open WebUI)
# Connected directly to Wolinet AI Gateway (LiteLLM) at http://127.0.0.1:4000
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

echo "================================================================="
echo "   WOLINET AI - SOVEREIGN WEB PORTAL (Open WebUI v0.9.6)         "
echo "================================================================="

# Source environment
if [ -f "${SCRIPT_DIR}/.env" ]; then
    set -o allexport
    source "${SCRIPT_DIR}/.env"
    set +o allexport
fi

export PORT="${PORT:-3000}"
export HOST="${HOST:-0.0.0.0}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://127.0.0.1:4000/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-wolinet-admin-2026}"
export ENABLE_FORWARD_USER_INFO_HEADERS="${ENABLE_FORWARD_USER_INFO_HEADERS:-True}"
export WEBUI_NAME="${WEBUI_NAME:-Wolinet AI}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:5433/webui}"
export DATA_DIR="${SCRIPT_DIR}/data"

mkdir -p "${DATA_DIR}"

echo "[Wolinet Portal] Gateway:  ${OPENAI_API_BASE_URL}"
echo "[Wolinet Portal] Web UI:   http://localhost:${PORT}"
echo "[Wolinet Portal] Database: ${DATABASE_URL}"
echo "[Wolinet Portal] User Header Forwarding: ${ENABLE_FORWARD_USER_INFO_HEADERS}"
echo "-----------------------------------------------------------------"

cd "${SCRIPT_DIR}"
export PYTHONPATH="${SCRIPT_DIR}/backend:${PYTHONPATH:-}"

exec "${VENV_DIR}/bin/python3" -m uvicorn open_webui.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --forwarded-allow-ips='*'
