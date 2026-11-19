#!/usr/bin/env bash
# ==============================================================================
# Wolinex IDE - Sovereign AI Workstation & Desktop IDE
# Goose AI Core + Autonomous Swarm + ACP + Sovereign Local LLM Gateway
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DESKTOP_DIR="${ROOT_DIR}/apps/WolinexIde/ui/desktop"

PROJECT_ARG="${1:-${ROOT_DIR}}"
SESSION_ARG="${2:-}"

echo "=================================================================="
echo " 🚀 Launching Wolinex IDE (Sovereign AI Workstation & IDE)"
echo " Engine: Goose AI Agent + ACP + Swarm Orchestrator"
echo " Gateway: http://127.0.0.1:4000"
echo " Target Project: ${PROJECT_ARG}"
echo "=================================================================="

# 1. Update active state in ~/.wolinex
mkdir -p "${HOME}/.wolinex/sessions"
python3 -c "
import json, os, datetime
state_file = os.path.expanduser('~/.wolinex/active_state.json')
current = {}
if os.path.exists(state_file):
    try:
        with open(state_file, 'r') as f:
            current = json.load(f)
    except:
        pass
current.update({
    'active_project': '''${PROJECT_ARG}''',
    'active_session': '''${SESSION_ARG}''',
    'gateway_url': os.environ.get('LITELLM_HOST', 'http://127.0.0.1:4000'),
    'updated_at': datetime.datetime.now().isoformat()
})
with open(state_file, 'w') as f:
    json.dump(current, f, indent=2)
"

# 2. Check if installed in /Applications/Wolinex.app
if [ -d "/Applications/Wolinex.app" ]; then
    echo "Starting installed /Applications/Wolinex.app..."
    open -a /Applications/Wolinex.app --args --project "${PROJECT_ARG}"
    exit 0
fi

# 3. Launch via desktop UI runner
if [ -d "${DESKTOP_DIR}" ]; then
    echo "Starting Wolinex IDE via desktop UI..."
    cd "${DESKTOP_DIR}"
    exec pnpm run start-gui
else
    echo "Error: ${DESKTOP_DIR} not found." >&2
    exit 1
fi

