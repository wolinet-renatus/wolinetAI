#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}"
export LITELLM_API_KEY="${LITELLM_API_KEY:-sk-XvKFiwDoOtOe8i4lwbzb8Q}"
export LITELLM_MODEL="${LITELLM_MODEL:-Wolinet Pro}"
export BACKGROUND_MODEL="${BACKGROUND_MODEL:-Wolinet Pro}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:CHANGE_ME_STRONG_PG_PASSWORD@127.0.0.1:5432/litellm_memory?sslmode=disable}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://127.0.0.1:8000}"
export PORT="${PORT:-8000}"
export STATE_DIR="${STATE_DIR:-${SCRIPT_DIR}/.state}"
export SHARING_ENABLED="${SHARING_ENABLED:-true}"
export SEARCH_CACHE_MB="${SEARCH_CACHE_MB:-128}"
export ALLOWED_EMAIL_DOMAIN="${ALLOWED_EMAIL_DOMAIN:-wolinet.com}"

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

cd "${SCRIPT_DIR}"
echo "[litellm-memory] Starting Sovereign LiteLLM Memory Service on http://0.0.0.0:${PORT}..."
exec uv run python -m uvicorn litellm_memory.application:app --host 0.0.0.0 --port "${PORT}" --no-access-log
