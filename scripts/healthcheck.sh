#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Platform Healthcheck
# Validates Xinference, Gateway, and Model Generation
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Wolinet AI Platform Health Check ==="

# Check Xinference
echo -n "1. Checking Xinference Engine (:9997)... "
if curl -s "http://127.0.0.1:9997/v1/models" >/dev/null; then
    echo "✅ HEALTHY"
else
    echo "❌ DOWN"
fi

# Check Running Models
echo "2. Active Local Models:"
"${ROOT_DIR}/.venv/bin/xinference" list || echo "Unable to list models."

# Check LiteLLM Gateway
echo -n "3. Checking AI Gateway (:4000)... "
if curl -s "http://127.0.0.1:4000/health/readiness" >/dev/null 2>&1; then
    echo "✅ HEALTHY"
else
    echo "⚠️  NOT RUNNING (Run: make gateway or ./gateway/run_gateway.sh)"
fi

echo -n "4. Testing Local Inference ('wolinex-coder')... "
RESPONSE=$(curl -s -X POST http://127.0.0.1:9997/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wolinex-coder",
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 10
  }' 2>/dev/null || true)

if [[ "${RESPONSE}" == *"choices"* ]]; then
    echo "✅ INFERENCE WORKING"
else
    echo "❌ INFERENCE FAILED: ${RESPONSE}"
fi

echo "=== Health Check Complete ==="
