#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Web Portal Launcher (Open WebUI)
# Connected directly to Wolinet AI Gateway (LiteLLM) at http://127.0.0.1:4000
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [ -d "${ROOT_DIR}/inference/.venv" ]; then
    VENV_DIR="${ROOT_DIR}/inference/.venv"
else
    VENV_DIR="${ROOT_DIR}/.venv"
fi

echo "================================================================="
echo "   WOLINET AI - SOVEREIGN WEB PORTAL (Open WebUI v0.9.6)         "
echo "================================================================="

# Source environment
if [ -f "${SCRIPT_DIR}/.env" ]; then
    set -o allexport
    source "${SCRIPT_DIR}/.env"
    set +o allexport
fi

export PORT="${PORT:-8081}"
export HOST="${HOST:-0.0.0.0}"
export LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-wolinet-admin-2026}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://127.0.0.1:4000/v1}"
export OPENAI_API_BASE_URLS="${OPENAI_API_BASE_URLS:-http://127.0.0.1:4000/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${LITELLM_MASTER_KEY}}"
export OPENAI_API_KEYS="${OPENAI_API_KEYS:-${OPENAI_API_KEY}}"
export AUDIO_TTS_ENGINE="${AUDIO_TTS_ENGINE:-openai}"
export AUDIO_TTS_OPENAI_API_BASE_URL="${AUDIO_TTS_OPENAI_API_BASE_URL:-http://127.0.0.1:4000/v1}"
export AUDIO_TTS_OPENAI_API_KEY="${AUDIO_TTS_OPENAI_API_KEY:-sk-wolinet-admin-2026}"
export AUDIO_TTS_MODEL="${AUDIO_TTS_MODEL:-Wolinet Voice}"
export AUDIO_TTS_VOICE="${AUDIO_TTS_VOICE:-Renatus}"
export AUDIO_TTS_SPLIT_ON="${AUDIO_TTS_SPLIT_ON:-punctuation}"
export ENABLE_OPENAI_API="${ENABLE_OPENAI_API:-True}"
export ENABLE_OLLAMA_API="${ENABLE_OLLAMA_API:-False}"
export DEFAULT_MODELS="${DEFAULT_MODELS:-Wolinet Pro}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-AQ.Ab8RN6I6jDTRMgx2zJbueLK2_s7DMq6-Ec3Y4BUJuA8khozfYA}"
export IMAGES_GEMINI_API_KEY="${IMAGES_GEMINI_API_KEY:-${GEMINI_API_KEY}}"
export ENABLE_EVALUATION_ARENA_MODELS="${ENABLE_EVALUATION_ARENA_MODELS:-False}"
export USER_PERMISSIONS_CHAT_CONTROLS="${USER_PERMISSIONS_CHAT_CONTROLS:-False}"
export USER_PERMISSIONS_CHAT_VALVES="${USER_PERMISSIONS_CHAT_VALVES:-False}"
export USER_PERMISSIONS_CHAT_SYSTEM_PROMPT="${USER_PERMISSIONS_CHAT_SYSTEM_PROMPT:-False}"
export USER_PERMISSIONS_CHAT_PARAMS="${USER_PERMISSIONS_CHAT_PARAMS:-False}"
export ENABLE_FORWARD_USER_INFO_HEADERS="${ENABLE_FORWARD_USER_INFO_HEADERS:-True}"
export WEBUI_NAME="${WEBUI_NAME:-Wolinet AI}"
export ENABLE_WEB_SEARCH="${ENABLE_WEB_SEARCH:-True}"
export WEB_SEARCH_ENGINE="${WEB_SEARCH_ENGINE:-obscura}"
export WEB_LOADER_ENGINE="${WEB_LOADER_ENGINE:-obscura}"
export BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL="${BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL:-True}"
export BYPASS_WEB_SEARCH_WEB_LOADER="${BYPASS_WEB_SEARCH_WEB_LOADER:-False}"
export RAG_SYSTEM_CONTEXT="${RAG_SYSTEM_CONTEXT:-True}"
export OBSCURA_URL="${OBSCURA_URL:-http://127.0.0.1:8080/mcp}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:CHANGE_ME_STRONG_PG_PASSWORD@127.0.0.1:5433/webui}"
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
