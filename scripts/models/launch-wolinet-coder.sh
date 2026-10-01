#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Launch Wolinet Coder (DeepSeek Coder 1.3B) & Purge Stale Models
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/launch-wolinet-coder.py"

echo "=== [Wolinet AI] Launching Wolinet Coder Engine ==="

# Check if running inside container or on host with docker
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q "mitambo"; then
    CONTAINER=$(docker ps --format '{{.Names}}' | grep "mitambo" | head -n 1)
    echo "Found running mitambo container: ${CONTAINER}"
    echo "Copying script into container..."
    docker cp "${PYTHON_SCRIPT}" "${CONTAINER}:/root/launch-wolinet-coder.py"
    echo "Executing launch script inside ${CONTAINER}..."
    docker exec -it "${CONTAINER}" python3 /root/launch-wolinet-coder.py
elif command -v python3 >/dev/null 2>&1; then
    echo "Executing launch script locally against http://127.0.0.1:9997..."
    python3 "${PYTHON_SCRIPT}"
else
    echo "Error: Neither docker nor python3 found."
    exit 1
fi

echo "=== [Wolinet AI] Wolinet Coder Launched Successfully ==="
