#!/usr/bin/env bash
# Stage-ordered Server Installer: Stage 1 (Orchestrator) -> Stage 2 (Mitambo) -> Stage 3 (Lango) -> Stage 4 (Wolinex Web).
# Client workstation apps (Wolinex Desktop / Goose CLI) are strictly excluded per architectural mandate.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

PASS_ARGS=()
ORCH_ARGS=()
WEB_ONLY_ARGS=()
INSTALL_STAGES="1,2,3,4"
INSTALL_PREFIX="${HOME}/.local"
WITH_DATASTORE=0

usage() {
  cat <<'EOF'
Wolinet AI Sovereign Server Stack Installer (4-Stage Boot Hierarchy)

Stages installed in order:
  Stage 1: orchestrator  (1apanel + 1panel-agent on :8888, isolated SQLite, Podman datastores)
  Stage 2: mitambo       (Local inference engine on :9997)
  Stage 3: lango         (Sovereign AI Gateway on :4000, PostgreSQL :5433/litellm + Redis :6379)
  Stage 4: wolinex-web   (Sovereign Web Client on :8081; :8080 reserved for Obscura Browser MCP)

Note: Client tools (wolinex-cli / Wolinex Desktop) are never installed on servers;
use ./scripts/install-wolinex-client.sh on developer workstations.

Usage:
  install-server-stack.sh [options]

Options:
  --stages <1,2,3,4>   Subset of server stages to run (default: 1,2,3,4)
  --build              Build any missing server packages locally before installing
  --prefix <dir>       Install prefix on macOS
  --with-datastore     Also provision Stage 1 Podman PostgreSQL (:5433) & Redis (:6379)
  --no-start           Install all binaries & configs without starting daemons
  --uninstall          Uninstall selected server stages (reverse order 4 -> 3 -> 2 -> 1)
  -h, --help           Show this help
EOF
}

UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stages)         INSTALL_STAGES="${2:-1,2,3,4}"; shift 2 ;;
    --build)          PASS_ARGS+=("--build"); shift ;;
    --prefix)         INSTALL_PREFIX="${2:-${HOME}/.local}"; PASS_ARGS+=("--prefix" "${INSTALL_PREFIX}"); shift 2 ;;
    --no-start)       PASS_ARGS+=("--no-start"); shift ;;
    --with-datastore) WITH_DATASTORE=1; ORCH_ARGS+=("--with-datastore"); shift ;;
    --uninstall)      UNINSTALL=1; PASS_ARGS+=("--uninstall"); shift ;;
    -h|--help)        usage; exit 0 ;;
    *)                die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform

has_stage() {
  [[ ",${INSTALL_STAGES}," == *",$1,"* ]]
}

if [[ "${UNINSTALL}" == "1" ]]; then
  log_header "Uninstalling Wolinet Server Stack (Stages 4 -> 1)"
  has_stage 4 && "${SCRIPT_DIR}/install-wolinex-web.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
  has_stage 3 && "${SCRIPT_DIR}/install-lango.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
  has_stage 2 && "${SCRIPT_DIR}/install-mitambo.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
  has_stage 1 && "${SCRIPT_DIR}/install-orchestrator.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
  log_ok "Selected server stages uninstalled"
  exit 0
fi

if [[ "${HOST_OS}" == "linux" ]]; then
  ORCH_ENV="/etc/wolinet/1apanel.env"
  MITAMBO_ENV="/etc/wolinet/mitambo.env"
  LANGO_ENV="/etc/litellm/env"
  WEB_ENV="/etc/wolinet/wolinex-web.env"
  ORCH_BIN="/usr/bin/wolinet-orchestrator"
  IS_ROOT_ENV=1
else
  ORCH_ENV="${INSTALL_PREFIX}/etc/orchestrator/env"
  MITAMBO_ENV="${INSTALL_PREFIX}/etc/mitambo/env"
  LANGO_ENV="${INSTALL_PREFIX}/etc/lango/env"
  WEB_ENV="${INSTALL_PREFIX}/etc/wolinex-web/env"
  ORCH_BIN="${INSTALL_PREFIX}/bin/wolinet-orchestrator"
  IS_ROOT_ENV=0
fi

resolve_or_generate_secret() {
  local current="$1" env_file="$2" var_name="$3" prefix="$4"
  if [[ -n "${current}" ]]; then
    printf '%s\n' "${current}"
    return 0
  fi
  local existing=""
  if [[ -r "${env_file}" ]]; then
    existing="$(get_env_var "${env_file}" "${var_name}")"
  fi
  if [[ -n "${existing}" && "${existing}" != replace-* && "${existing}" != sk-replace* ]]; then
    printf '%s\n' "${existing}"
  else
    generate_secret "${prefix}"
  fi
}

SHARED_PG_PASS="$(resolve_or_generate_secret "${POSTGRES_PASSWORD:-}" "${ORCH_ENV}" "POSTGRES_PASSWORD" "pg-")"
SHARED_ADMIN_PASS="$(resolve_or_generate_secret "${ORIGINAL_PASSWORD:-}" "${ORCH_ENV}" "ORIGINAL_PASSWORD" "woli-")"
SHARED_XINF_KEY="$(resolve_or_generate_secret "${XINFERENCE_API_KEY:-}" "${MITAMBO_ENV}" "XINFERENCE_API_KEY" "sk-xinf-")"
SHARED_MASTER_KEY="$(resolve_or_generate_secret "${LITELLM_MASTER_KEY:-}" "${LANGO_ENV}" "LITELLM_MASTER_KEY" "sk-lango-")"
SHARED_PORTAL_KEY="$(resolve_or_generate_secret "${WOLINEX_PORTAL_API_KEY:-}" "${WEB_ENV}" "OPENAI_API_KEY" "sk-portal-")"
SHARED_COPILOT_KEY="$(resolve_or_generate_secret "${AI_GATEWAY_KEY:-}" "${ORCH_ENV}" "AI_GATEWAY_KEY" "sk-copilot-")"

LITELLM_DB_URL="postgresql://postgres:${SHARED_PG_PASS}@127.0.0.1:5433/litellm"
WEBUI_DB_URL="postgresql://postgres:${SHARED_PG_PASS}@127.0.0.1:5433/webui"
SHARED_REDIS_URL="redis://127.0.0.1:6379"

sync_orchestrator_copilot_env() {
  [[ -f "${ORCH_ENV}" ]] || return 0
  local tmp_env
  tmp_env="$(mktemp)"
  cp "${ORCH_ENV}" "${tmp_env}"
  upsert_env_var "${tmp_env}" "AI_GATEWAY_URL" "http://127.0.0.1:4000"
  upsert_env_var "${tmp_env}" "AI_GATEWAY_KEY" "${SHARED_COPILOT_KEY}"
  upsert_env_var "${tmp_env}" "WOLINEX_PORTAL_API_KEY" "${SHARED_PORTAL_KEY}"
  if [[ "${IS_ROOT_ENV}" == "1" ]]; then
    run_root install -m 0600 "${tmp_env}" "${ORCH_ENV}"
  else
    install -m 0600 "${tmp_env}" "${ORCH_ENV}"
  fi
  rm -f "${tmp_env}"
}

log_header "Installing Wolinet Sovereign Server Stack (4-Stage Boot Order)"
STAGE_INSTALL_ARGS=()
[[ "${#PASS_ARGS[@]}" -gt 0 ]] && STAGE_INSTALL_ARGS=("${PASS_ARGS[@]}")
DEFER_START=0
if [[ " ${PASS_ARGS[*]:-} " != *" --no-start "* ]] && has_systemd; then
  DEFER_START=1
  STAGE_INSTALL_ARGS+=("--no-start")
fi

if has_stage 1; then
  log_header "[Stage 1/4] DEC Orchestrator (1apanel + backing datastores)"
  "${SCRIPT_DIR}/install-orchestrator.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} ${ORCH_ARGS[@]+"${ORCH_ARGS[@]}"} \
    --admin-password "${SHARED_ADMIN_PASS}" \
    --postgres-password "${SHARED_PG_PASS}"
  sync_orchestrator_copilot_env
fi
if has_stage 2; then
  log_header "[Stage 2/4] Mitambo Local Inference Engine (:9997)"
  "${SCRIPT_DIR}/install-mitambo.sh" ${STAGE_INSTALL_ARGS[@]+"${STAGE_INSTALL_ARGS[@]}"} \
    --api-key "${SHARED_XINF_KEY}" \
    --admin-user "admin" \
    --admin-password "${SHARED_ADMIN_PASS}"
fi
if has_stage 3; then
  log_header "[Stage 3/4] Lango AI Gateway (:4000)"
  "${SCRIPT_DIR}/install-lango.sh" ${STAGE_INSTALL_ARGS[@]+"${STAGE_INSTALL_ARGS[@]}"} \
    --master-key "${SHARED_MASTER_KEY}" \
    --xinference-key "${SHARED_XINF_KEY}" \
    --database-url "${LITELLM_DB_URL}" \
    --redis-url "${SHARED_REDIS_URL}"
fi
if has_stage 4; then
  log_header "[Stage 4/4] Wolinex Web Portal (:8081)"
  "${SCRIPT_DIR}/install-wolinex-web.sh" ${STAGE_INSTALL_ARGS[@]+"${STAGE_INSTALL_ARGS[@]}"} ${WEB_ONLY_ARGS[@]+"${WEB_ONLY_ARGS[@]}"} \
    --gateway-url "http://127.0.0.1:4000" \
    --gateway-key "${SHARED_PORTAL_KEY}" \
    --database-url "${WEBUI_DB_URL}" \
    --redis-url "${SHARED_REDIS_URL}"
fi

if [[ -x "${ORCH_BIN}" ]]; then
  log_header "[Finalize] Running canonical DB migrations & data seeding"
  XINF_HOME_ENV="$([[ -r "${MITAMBO_ENV}" ]] && get_env_var "${MITAMBO_ENV}" "XINFERENCE_HOME" || true)"
  MIT_MOD_ENV="$([[ -r "${MITAMBO_ENV}" ]] && get_env_var "${MITAMBO_ENV}" "MITAMBO_MODELS_DIR" || true)"
  POSTGRES_PASSWORD="${SHARED_PG_PASS}" \
  ORIGINAL_PASSWORD="${SHARED_ADMIN_PASS}" \
  XINFERENCE_API_KEY="${SHARED_XINF_KEY}" \
  XINFERENCE_ADMIN_USER="admin" \
  XINFERENCE_ADMIN_PASSWORD="${SHARED_ADMIN_PASS}" \
  LITELLM_MASTER_KEY="${SHARED_MASTER_KEY}" \
  WOLINEX_PORTAL_API_KEY="${SHARED_PORTAL_KEY}" \
  AI_GATEWAY_KEY="${SHARED_COPILOT_KEY}" \
  XINFERENCE_HOME="${XINF_HOME_ENV:-/var/lib/wolinet/data/mitambo}" \
  MITAMBO_MODELS_DIR="${MIT_MOD_ENV:-/var/lib/wolinet/models}" \
  WOLINET_ORCH_ENV_FILE="${ORCH_ENV}" \
    "${ORCH_BIN}" migrate-seed
fi

if [[ "${DEFER_START}" == "1" ]]; then
  log_header "[Boot] Starting Stage 1 -> Stage 2 -> Stage 3 -> Stage 4 systemd services"
  run_root systemctl daemon-reload
  if has_stage 1; then
    run_root systemctl restart 1panel-agent.service 1apanel.service >/dev/null 2>&1 || true
  fi
  if has_stage 2; then
    run_root systemctl enable --now mitambo.service
    wait_http_ok "http://127.0.0.1:9997/status" 60 \
      && log_ok "Stage 2 Mitambo healthy at http://127.0.0.1:9997/status" \
      || log_warn "Mitambo started; check 'journalctl -u mitambo -n 50' if still warming up"
  fi
  if has_stage 3; then
    run_root systemctl enable --now litellm-gateway.service
    wait_http_ok "http://127.0.0.1:4000/health/liveliness" 30 \
      && log_ok "Stage 3 Lango Gateway healthy at http://127.0.0.1:4000/health/liveliness" \
      || log_warn "Lango Gateway started; check 'journalctl -u litellm-gateway -n 50'"
  fi
  if has_stage 4; then
    run_root systemctl enable --now wolinex-web.service
    wait_http_ok "http://127.0.0.1:8081/health" 75 \
      && log_ok "Stage 4 Wolinex Web Portal healthy at http://127.0.0.1:8081/health" \
      || log_warn "Wolinex Web started; check 'journalctl -u wolinex-web -n 50'"
  fi
fi

log_ok "Server stack installation complete. For workstation clients run: ./scripts/install-wolinex-client.sh"
