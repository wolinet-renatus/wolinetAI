#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Dynamic Model Auto-Registration Script
# Registers models directly from models/registrations/ with Hugging Face sources
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Registering Wolinet AI Models from Hugging Face Sources ==="

REG_DIR="${ROOT_DIR}/models/registrations"

if [ ! -d "${REG_DIR}" ]; then
    echo "Error: Registrations directory '${REG_DIR}' not found."
    exit 1
fi

for json_file in "${REG_DIR}"/*.json; do
    [ -f "$json_file" ] || continue
    model_name=$(python3 -c "import json; d=json.load(open('${json_file}')); print(d.get('model_name',''))" 2>/dev/null)
    
    # Skip models already built into Xinference to prevent conflict errors
    case "$model_name" in
        wolinex-coder|bge-small-en-v1.5|bge-reranker-v2-m3|whisper-small|whisper-large-v3-turbo)
            echo "[Register] ⏩ ${model_name} is built-in, ready to launch."
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
elif any(a in abilities for a in ['audio2text', 'text2audio', 'speech2text']) or 'tts' in family or family == 'whisper':
    print('audio')
elif 'dimensions' in d:
    print('embedding')
elif 'rerank' in name or 'reranker' in name:
    print('rerank')
else:
    print('LLM')
" 2>/dev/null)

    # Check if already registered
    if curl -s "http://127.0.0.1:9997/v1/model_registrations/${model_type}/${model_name}" | grep -q "\"model_name\"" 2>/dev/null; then
        echo "[Register] ✅ ${model_name} (${model_type}) is registered."
    else
        echo "[Register] 📥 Registering ${model_name} (${model_type})..."
        "${ROOT_DIR}/.venv/bin/xinference" register --model-type "${model_type}" --file "${json_file}" --persist >/dev/null 2>&1 || true
        echo "[Register] ✅ ${model_name} (${model_type}) registered."
    fi
done

echo "=== Model Registration Complete ==="
