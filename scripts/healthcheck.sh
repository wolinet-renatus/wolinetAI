#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI - Platform Healthcheck
# Validates Xinference, Gateway, and Model Generation
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${ROOT_DIR}/.env" ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
    set +o allexport
fi

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

echo -n "4. Testing an enabled gateway model... "
MODEL_ID=$(python3 - <<'PY'
import json
import os
import urllib.request

key = os.getenv("LITELLM_MASTER_KEY") or os.getenv("WOLINET_GATEWAY_MASTER_KEY") or "not-needed"
request = urllib.request.Request(
    "http://127.0.0.1:4000/v1/models",
    headers={"Authorization": f"Bearer {key}"},
)
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        models = json.load(response).get("data", [])
    print(models[0]["id"] if models else "")
except Exception:
    print("")
PY
)

if [ -z "${MODEL_ID}" ]; then
    echo "❌ No enabled model returned by LiteLLM"
else
    RESPONSE=$(curl -s -X POST "http://127.0.0.1:4000/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-${WOLINET_GATEWAY_MASTER_KEY:-not-needed}}" \
      -d "{\"model\":\"${MODEL_ID}\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":10}" 2>/dev/null || true)
    if [[ "${RESPONSE}" == *"choices"* ]]; then
        echo "✅ INFERENCE WORKING (${MODEL_ID})"
    else
        echo "❌ INFERENCE FAILED for ${MODEL_ID}: ${RESPONSE}"
    fi
fi

# Check OrcaCyber AI Defense & Secure Pro (:8088)
echo -n "5. Checking OrcaCyber AI Defense & Secure Pro (:8088)... "
if curl -sf "http://127.0.0.1:8088/health" >/dev/null 2>&1; then
    echo "✅ UP (Secure Pro & Turbo Draft active)"
else
    echo "⚠️  DOWN (Run: python services/defense/orcacyber_defense.py)"
fi

# Check Registered AI Agents (:4000/ui/agents/)
echo -n "6. Registered Sovereign AI Agents: "
AGENTS_COUNT=$(python3 - <<'PY'
import json, os, urllib.request
key = os.getenv("LITELLM_MASTER_KEY") or os.getenv("WOLINET_GATEWAY_MASTER_KEY") or "not-needed"
req = urllib.request.Request("http://127.0.0.1:4000/v1/agents", headers={"Authorization": f"Bearer {key}"})
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        agents = json.load(r)
        names = [a.get("agent_name", "") for a in agents]
        print(f"✅ {len(agents)} Active ({', '.join(names[:3])}...)")
except Exception:
    print("⚠️ Unable to query agents")
PY
)
echo "${AGENTS_COUNT}"

echo "=== Health Check Complete ==="

