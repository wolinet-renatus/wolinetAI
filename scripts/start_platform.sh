#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Full Platform Launcher
# Starts Xinference Local Engine (port 9997) + LiteLLM AI Gateway (port 4000)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

XINFERENCE_PORT="${XINFERENCE_PORT:-9997}"
GATEWAY_PORT="${WOLINET_GATEWAY_PORT:-4000}"

# Load .env if present (picks up HF_TOKEN, API keys, etc.)
if [ -f "${ROOT_DIR}/.env" ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
    set +o allexport
fi

# Ensure HF token and download policy are available for fast direct downloads
export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
export XINFERENCE_MODEL_SRC="${XINFERENCE_MODEL_SRC:-modelscope}"
export XINFERENCE_DOWNLOAD_MAX_ATTEMPTS="${XINFERENCE_DOWNLOAD_MAX_ATTEMPTS:-3}"
export XINFERENCE_HUB_DETECT_TIMEOUT="${XINFERENCE_HUB_DETECT_TIMEOUT:-3}"
export XINFERENCE_MODEL_DOWNLOAD_WORKERS="${XINFERENCE_MODEL_DOWNLOAD_WORKERS:-4}"
export HF_HUB_DOWNLOAD_WORKERS="${HF_HUB_DOWNLOAD_WORKERS:-4}"
export XINFERENCE_MEDIA_ALLOW_LOCAL_PATH="${XINFERENCE_MEDIA_ALLOW_LOCAL_PATH:-true}"
export XINFERENCE_MEDIA_BLOCK_PRIVATE_ADDRESS="${XINFERENCE_MEDIA_BLOCK_PRIVATE_ADDRESS:-false}"
export XINFERENCE_HTTP_REQUEST_TIMEOUT="${XINFERENCE_HTTP_REQUEST_TIMEOUT:-600}"

echo "=================================================================="
echo " 🚀 Starting Wolinet AI Enterprise Platform"
echo " Local Inference Engine: http://127.0.0.1:${XINFERENCE_PORT}"
echo " Unified AI Gateway:     http://0.0.0.0:${GATEWAY_PORT}"
echo "=================================================================="

# ---------------------------------------------------------------------------
# 0. Auto-register all models from models/registrations/ into xinference home
# ---------------------------------------------------------------------------
REGISTRATIONS_DIR="${ROOT_DIR}/models/registrations"
XINFERENCE_V2_DIR="${HOME}/.xinference/model/v2"

if [ -d "${REGISTRATIONS_DIR}" ]; then
    echo "[Registry] Syncing custom models from ${REGISTRATIONS_DIR}..."
    for json_file in "${REGISTRATIONS_DIR}"/*.json; do
        [ -f "$json_file" ] || continue
        model_name=$(python3 -c "import json; d=json.load(open('${json_file}')); print(d.get('model_name',''))" 2>/dev/null)
        case "$model_name" in
            wolinex-coder|bge-small-en-v1.5|bge-reranker-v2-m3|whisper-small)
                continue
                ;;
        esac
        model_type=$(python3 -c "
import json
d = json.load(open('${json_file}'))
name = d.get('model_name', '')
abilities = d.get('model_ability', [])
family = d.get('model_family', '')
if any(a in abilities for a in ['text2image', 'image2image', 'inpainting', 'ocr', 'docanalyze']) or family == 'ocr':
    print('image')
elif any(a in abilities for a in ['audio2text', 'text2audio', 'speech2text']) or family == 'whisper':
    print('audio')
elif 'dimensions' in d:
    print('embedding')
elif 'rerank' in name or 'reranker' in name:
    print('rerank')
else:
    print('llm')
" 2>/dev/null)
        target_dir="${XINFERENCE_V2_DIR}/${model_type}"
        mkdir -p "${target_dir}"
        cp "${json_file}" "${target_dir}/${model_name}.json"
        echo "[Registry] ✅ ${model_name} → ${model_type}"
    done
    echo "[Registry] Model sync complete."
fi


if curl -sf "http://127.0.0.1:${XINFERENCE_PORT}/status" >/dev/null 2>&1; then
    echo "[Engine] Xinference is already running on port ${XINFERENCE_PORT}."
else
    echo "[Engine] Starting Xinference daemon on port ${XINFERENCE_PORT}..."
    "${ROOT_DIR}/.venv/bin/xinference-local" \
        -H 127.0.0.1 \
        -p "${XINFERENCE_PORT}" > "${ROOT_DIR}/xinference.log" 2>&1 &
    
    echo "[Engine] Waiting for Xinference to become healthy..."
    for i in {1..30}; do
        if curl -sf "http://127.0.0.1:${XINFERENCE_PORT}/status" >/dev/null 2>&1; then
            echo "[Engine] Xinference is UP!"
            break
        fi
        sleep 1
    done
fi

# 2. Launch local models when an authenticated Xinference API key is configured
xinference_cli() {
    "${ROOT_DIR}/.venv/bin/xinference" "$@" \
        --endpoint "http://127.0.0.1:${XINFERENCE_PORT}" \
        --api-key "${XINFERENCE_API_KEY}"
}

if [[ -z "${XINFERENCE_API_KEY:-}" ]]; then
    echo "[Engine] Auth is enabled. Set XINFERENCE_API_KEY after Xinference setup to launch models."
else
RUNNING_MODELS=$(xinference_cli list 2>/dev/null || true)
if [[ "${RUNNING_MODELS}" != *"wolinex-coder"* ]]; then
    echo "[Engine] Launching default model 'wolinex-coder'..."
    MODEL_PATH_ARGS=()
    if [ -n "${WOLINET_CODER_MODEL_PATH:-}" ] && [ -f "${WOLINET_CODER_MODEL_PATH}" ]; then
        MODEL_PATH_ARGS=(--model-path "${WOLINET_CODER_MODEL_PATH}")
    elif [ -f "${ROOT_DIR}/models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf" ]; then
        MODEL_PATH_ARGS=(--model-path "${ROOT_DIR}/models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf")
    fi
    xinference_cli launch \
        -n wolinex-coder \
        -u wolinex-coder \
        --model-engine llama.cpp \
        --size-in-billions 3 \
        --model-format ggufv2 \
        -q q4_k_m \
        ${MODEL_PATH_ARGS[@]+"${MODEL_PATH_ARGS[@]}"} \
        --disable-virtual-env || true
fi

if [[ "${RUNNING_MODELS}" != *"qwen2.5-omni-3b-local"* ]]; then
    echo "[Engine] Launching multimodal model 'qwen2.5-omni-3b-local'..."
    OMNI_PATH_ARGS=()
    if [ -f "${ROOT_DIR}/models/Qwen2.5-Omni-3B-iq2_m.gguf" ]; then
        OMNI_PATH_ARGS=(--model-path "${ROOT_DIR}/models/Qwen2.5-Omni-3B-iq2_m.gguf")
    fi
    xinference_cli launch \
        -n qwen2.5-omni-3b-local \
        -u qwen2.5-omni-3b-local \
        --model-engine llama.cpp \
        --size-in-billions 3 \
        --model-format ggufv2 \
        -q iq2_m \
        ${OMNI_PATH_ARGS[@]+"${OMNI_PATH_ARGS[@]}"} \
        --disable-virtual-env || true
fi

if [[ "${RUNNING_MODELS}" != *"deepseek-coder-1.3b"* ]]; then
    echo "[Engine] Launching code model 'deepseek-coder-1.3b'..."
    DEEPSEEK_PATH_ARGS=()
    if [ -f "${ROOT_DIR}/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf" ]; then
        DEEPSEEK_PATH_ARGS=(--model-path "${ROOT_DIR}/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf")
    fi
    xinference_cli launch \
        -n deepseek-coder-1.3b \
        -u deepseek-coder-1.3b \
        --model-engine llama.cpp \
        --size-in-billions 1_3 \
        --model-format ggufv2 \
        -q q4_k_m \
        ${DEEPSEEK_PATH_ARGS[@]+"${DEEPSEEK_PATH_ARGS[@]}"} \
        --disable-virtual-env || true
fi

if [[ "${RUNNING_MODELS}" != *"bge-small-en-v1.5"* ]]; then
    echo "[Engine] Launching default embedding model 'bge-small-en-v1.5'..."
    xinference_cli launch \
        -u bge-small-en-v1.5 \
        --model-name bge-small-en-v1.5 \
        --model-type embedding || true
fi

if [[ "${RUNNING_MODELS}" != *"bge-reranker-v2-m3"* ]]; then
    echo "[Engine] Launching default reranker model 'bge-reranker-v2-m3'..."
    xinference_cli launch \
        -u bge-reranker-v2-m3 \
        --model-name bge-reranker-v2-m3 \
        --model-type rerank || true
fi
fi

# 3. Start AI Gateway (LiteLLM)
echo "[Gateway] Starting LiteLLM Gateway on port ${GATEWAY_PORT}..."
exec "${ROOT_DIR}/gateway/run_gateway.sh"
