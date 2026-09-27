#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI Web Client & Agent Server Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-3210}"
WORKSPACE="${WORKSPACE:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

echo "[Wolinet Web Client] Starting server on http://127.0.0.1:${PORT}"
echo "[Wolinet Web Client] Workspace: ${WORKSPACE}"

exec node "${SCRIPT_DIR}/bin/litespeed.mjs" serve --port "${PORT}" --workspace "${WORKSPACE}"
