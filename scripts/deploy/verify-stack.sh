#!/usr/bin/env bash
set -euo pipefail

compose=(docker compose)
if [[ -z "${COMPOSE_FILE:-}" ]]; then
  compose+=(--file docker-compose.yml)
fi

"${compose[@]}" config --quiet

for attempt in $(seq 1 60); do
  container_id=$("${compose[@]}" ps -q mitambo)
  if [[ -n "${container_id}" ]]; then
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")
    if [[ "${health}" == healthy ]]; then
      break
    fi
  fi
  if [[ "${attempt}" -eq 60 ]]; then
    echo "mitambo did not become healthy within 5 minutes" >&2
    exit 1
  fi
  sleep 5
done

"${compose[@]}" exec -T postgres sh -ec '
  for database in litellm webui; do
    result=$(psql -U "$POSTGRES_USER" -d "$database" -Atqc "SELECT current_database()")
    test "$result" = "$database"
    printf "database %s: ready\n" "$database"
  done
'

"${compose[@]}" exec -T lango python -c '
import os
import urllib.request

request = urllib.request.Request(
    "http://mitambo:9997/status",
    headers={"Authorization": "Bearer " + os.environ["XINFERENCE_API_KEY"]},
)
with urllib.request.urlopen(request, timeout=10) as response:
    if response.status != 200:
        raise SystemExit(f"mitambo /status returned HTTP {response.status}")
print("mitambo /status: ready")
'
