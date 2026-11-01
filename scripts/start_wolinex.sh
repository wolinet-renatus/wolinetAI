#!/usr/bin/env bash
# ==============================================================================
# Wolinex Autonomous IDE & Workstation - Sovereign Desktop Launcher
# Bundles Wolinex Neural Core + Rust Code Engine + Autonomous Multi-Agent Swarms
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${ROOT_DIR}/apps/WolinexIde/ui/desktop"

echo "=================================================================="
echo " 🚀 Launching Wolinex Autonomous IDE & Sovereign Workstation"
echo " Native Engine: Wolinex Core + OpenIDEA Rust Engine + Neural Swarms"
echo " Sovereign AI Gateway: http://127.0.0.1:4000"
echo " Workstation Directory: ${APP_DIR}"
echo "=================================================================="

# 1. Kill any dangling processes that might hold ports
pkill -f "goose serve" 2>/dev/null || true

# 2. Check & start Wolinex Sovereign Gateway if not running
if ! curl -s http://127.0.0.1:4000/health/liveliness >/dev/null 2>&1; then
    echo "⚡ Initializing Wolinex Sovereign AI Gateway on port 4000..."
    if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' | grep -q 'wolinetai-lango-1'; then
        docker start wolinetai-postgres-1 wolinet-postgres-bridge wolinetai-redis-1 wolinetai-lango-1 2>/dev/null || true
    else
        nohup "${ROOT_DIR}/gateway/run_gateway.sh" > "${ROOT_DIR}/gateway/gateway.log" 2>&1 &
    fi
    for i in {1..15}; do
        if curl -s http://127.0.0.1:4000/health/liveliness >/dev/null 2>&1; then
            echo "✓ Wolinex Sovereign Gateway online at http://127.0.0.1:4000"
            break
        fi
        sleep 1
    done
fi

# 3. Ensure sidecar binaries are executable
chmod +x "${ROOT_DIR}/apps/WolinexIde/bin/openidea-server" 2>/dev/null || true
chmod +x "${ROOT_DIR}/apps/WolinexIde/bin/gtwall" 2>/dev/null || true
chmod +x "${APP_DIR}/src/bin/goose" 2>/dev/null || true
chmod +x "${APP_DIR}/src/bin/openidea-server" 2>/dev/null || true

# 4. Enter desktop directory and start GUI
cd "${APP_DIR}"
export ELECTRON_IS_DEV=1
export NODE_ENV=development
export GOOSE_ALLOWLIST_BYPASS=true
export LITELLM_HOST="${LITELLM_HOST:-http://127.0.0.1:4000}"
export LITELLM_API_KEY="${LITELLM_API_KEY:-sk-XvKFiwDoOtOe8i4lwbzb8Q}"
export WOLINEX_PORTAL_URL="${WOLINEX_PORTAL_URL:-http://127.0.0.1:8081}"
export GOOSE_DEFAULT_PROVIDER="litellm"
export GOOSE_PROVIDER="litellm"
export GOOSE_DEFAULT_MODEL="Wolinex Coder"
export GOOSE_MODEL="Wolinex Coder"

echo "Starting Wolinex Workstation..."
pnpm run start-gui

