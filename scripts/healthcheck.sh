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
if curl -sf "http://127.0.0.1:9997/status" >/dev/null; then
    echo "✅ HEALTHY"
else
    echo "❌ DOWN"
fi

# Check Running Models
echo "2. Active Local Models:"
if [[ -n "${XINFERENCE_API_KEY:-}" ]]; then
    "${ROOT_DIR}/.venv/bin/xinference" list \
        --endpoint "http://127.0.0.1:9997" \
        --api-key "${XINFERENCE_API_KEY}" || echo "Unable to list models."
else
    echo "Set XINFERENCE_API_KEY to list authenticated models."
fi

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
  -H "Authorization: Bearer ${XINFERENCE_API_KEY:-}" \
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
