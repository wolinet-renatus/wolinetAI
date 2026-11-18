#!/usr/bin/env bash
# Compatibility wrapper routing server Web Portal vs decoupled Client Workstation installs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPONENT="web"
FORWARD_ARGS=()
HAS_EXPLICIT_COMPONENT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --component|--components)
      COMPONENT="${2:-web}"
      HAS_EXPLICIT_COMPONENT=1
      shift 2
      ;;
    *)
      FORWARD_ARGS+=("$1")
      shift
      ;;
  esac
done

case "${COMPONENT}" in
  web)
    exec "${SCRIPT_DIR}/install-wolinex-web.sh" "${FORWARD_ARGS[@]}"
    ;;
  cli|desktop|cli,desktop|desktop,cli)
    exec "${SCRIPT_DIR}/install-wolinex-client.sh" --component "${COMPONENT}" "${FORWARD_ARGS[@]}"
    ;;
  all|web,cli|web,cli,desktop)
    "${SCRIPT_DIR}/install-wolinex-web.sh" "${FORWARD_ARGS[@]}"
    echo ""
    echo "[note] Installing decoupled client workstation components separately via install-wolinex-client.sh..."
    if [[ "${COMPONENT}" == "all" ]]; then
      exec "${SCRIPT_DIR}/install-wolinex-client.sh" --component cli,desktop "${FORWARD_ARGS[@]}"
    else
      exec "${SCRIPT_DIR}/install-wolinex-client.sh" --component "${COMPONENT#web,}" "${FORWARD_ARGS[@]}"
    fi
    ;;
  *)
    if [[ "${HAS_EXPLICIT_COMPONENT}" == "0" ]]; then
      exec "${SCRIPT_DIR}/install-wolinex-web.sh" "${FORWARD_ARGS[@]}"
    fi
    echo "Unsupported --component '${COMPONENT}' (expected: web, cli, desktop, or all)" >&2
    exit 1
    ;;
esac
