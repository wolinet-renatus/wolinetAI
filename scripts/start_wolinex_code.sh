#!/usr/bin/env bash
# ==============================================================================
# Wolinex Code - Sovereign Rust Full-Stack IDE Launcher
# Bundles OpenIDEA Rust Engine + Tree-sitter + LSP + Autonomous Agent Pairing
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
IDE_DIR="${ROOT_DIR}/apps/ide"

PROJECT_ARG="${1:-${ROOT_DIR}}"
SESSION_ARG="${2:-}"

echo "=================================================================="
echo " 🚀 Launching Wolinex Code (Sovereign Rust Full-Stack IDE)"
echo " Engine: OpenIDEA Rust Backend + Tree-sitter + LSP Bridge"
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

# 2. Check if installed in /Applications/WolinexCode.app
if [ -d "/Applications/WolinexCode.app" ]; then
    echo "Starting installed /Applications/WolinexCode.app..."
    open -a /Applications/WolinexCode.app --args --project "${PROJECT_ARG}" --session "${SESSION_ARG}"
    exit 0
fi

# 3. Fallback: Launch via workspace runner
ELECTRON_BIN="${ROOT_DIR}/apps/WolinexIde/ui/node_modules/.bin/electron"
if [ -x "${ELECTRON_BIN}" ]; then
    echo "Starting Wolinex Code via workspace runner..."
    cd "${IDE_DIR}/desktop"
    exec "${ELECTRON_BIN}" . --project "${PROJECT_ARG}" --session "${SESSION_ARG}"
else
    echo "Error: Neither /Applications/WolinexCode.app nor Electron runner found." >&2
    exit 1
fi
