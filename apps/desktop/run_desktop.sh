#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI Studio - Native Desktop & Browser IDE Launcher
# Powered by Eclipse Theia v1.76.0 with Native AI & Open-VSX Protocol
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${THEIA_PORT:-3090}"
HOST="${THEIA_HOST:-127.0.0.1}"

# Load root .env if present (for WOLINET_GATEWAY_MASTER_KEY and LITELLM_MASTER_KEY)
ROOT_DIR="$(cd "${DIR}/../.." && pwd)"
if [ -f "${ROOT_DIR}/.env" ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
    set +o allexport
fi

# Export environment variables for Wolinet AI Gateway connection
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${LITELLM_MASTER_KEY:-${WOLINET_GATEWAY_MASTER_KEY:-not-needed}}}"
export THEIA_DEFAULT_COLOR_THEME="dark"

MODE="${1:-browser}"
if [ $# -gt 0 ]; then
    shift
fi

echo "=================================================================="
echo "           WOLINET AI STUDIO (Eclipse Theia v1.76.0)              "
echo "=================================================================="
echo " Mode:               $MODE"
echo " Wolinet AI Gateway: $OPENAI_API_BASE_URL"
echo " Open-VSX Registry:  https://open-vsx.org/"
echo " Root:               $DIR"
echo " Workspace:          ${WORKSPACE_DIR:-$ROOT_DIR}"
echo "=================================================================="

# Ensure plugins directory exists
mkdir -p "$DIR/plugins"

# Ensure node_modules exist
if [ ! -d "$DIR/node_modules" ]; then
    echo "[Wolinet Studio] Installing dependencies locally..."
    npm install --legacy-peer-deps --engine-strict=false
fi

TARGET_WORKSPACE="${WORKSPACE_DIR:-$ROOT_DIR}"

case "$MODE" in
    browser)
        echo "[Wolinet Studio] Starting Wolinet AI Studio on http://${HOST}:${PORT}..."
        cd "$DIR/examples/browser"
        exec npx theia start "$TARGET_WORKSPACE" --hostname="$HOST" --port="$PORT" --plugins=local-dir:"$DIR/plugins" "$@"
        ;;
    electron)
        echo "[Wolinet Studio] Starting Wolinet AI Studio (Native Desktop Window)..."
        cd "$DIR/examples/electron"
        exec npx theia start "$TARGET_WORKSPACE" "$@"
        ;;
    build)
        echo "[Wolinet Studio] Building Wolinet AI Studio..."
        npm run compile
        npm run build:browser
        echo "[Wolinet Studio] Build completed successfully."
        ;;
    *)
        echo "Usage: ./run_desktop.sh [browser|electron|build]"
        exit 1
        ;;
esac
