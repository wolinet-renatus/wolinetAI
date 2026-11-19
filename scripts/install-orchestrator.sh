#!/usr/bin/env bash
# Terminal binary installer for Stage 1 DEC Orchestrator (1apanel + 1panel-agent + Podman datastores).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

ARTIFACT_PATH=""
AUTO_BUILD=0
NO_START=0
WITH_DATASTORE=0
UNINSTALL=0
PREFIX=""
PORT="${ORIGINAL_PORT:-8888}"
ADMIN_USER="${ORIGINAL_USERNAME:-admin}"
ADMIN_PASSWORD="${ORIGINAL_PASSWORD:-}"
POSTGRES_PASSWORD_ARG="${POSTGRES_PASSWORD:-}"
POSTGRES_PORT_ARG="${POSTGRES_PORT:-5433}"

usage() {
  cat <<'EOF'
Wolinet Stage 1 DEC Orchestrator Installer (Install & Boot First)

Usage:
  install-orchestrator.sh [options]

Options:
  --build                   Build Stage 1 package from source if missing
  --artifact <path>         Path to .deb (Linux) or .tar.gz (macOS) installer
  --prefix <dir>            Install prefix on macOS (default: ~/.local)
  --port <port>             1apanel port: 8888 (prod), 9999 (dev), or 8089 (pod); port 4004 is forbidden
  --admin-user <user>       Control plane admin username (default: admin)
  --admin-password <pass>   Control plane password (auto-generated if omitted)
  --postgres-password <pw>  PostgreSQL password for Stage 1 backing DB (auto-generated if omitted)
  --with-datastore          Also provision Podman PostgreSQL (:5433->5432) & Redis (:6379)
  --no-start                Install binaries, dirs & config without starting daemons
  --uninstall               Remove Stage 1 orchestrator services and binaries
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)             AUTO_BUILD=1; shift ;;
    --artifact)          ARTIFACT_PATH="${2:-}"; shift 2 ;;
    --prefix)            PREFIX="${2:-}"; shift 2 ;;
    --port)              PORT="${2:-8888}"; shift 2 ;;
    --admin-user)        ADMIN_USER="${2:-admin}"; shift 2 ;;
    --admin-password)    ADMIN_PASSWORD="${2:-}"; shift 2 ;;
    --postgres-password) POSTGRES_PASSWORD_ARG="${2:-}"; shift 2 ;;
    --with-datastore)    WITH_DATASTORE=1; shift ;;
    --no-start)          NO_START=1; shift ;;
    --uninstall)         UNINSTALL=1; shift ;;
    -h|--help)           usage; exit 0 ;;
    *)                   die "Unknown option: $1 (try --help)" ;;
  esac
done

if [[ "${PORT}" == "4004" ]]; then
  die "Port 4004 is prohibited for 1apanel; use 8888 (control plane), 9999 (dev), or 8089 (pod ingress)"
fi

detect_platform
detect_host_resources

configure_orchestrator_env() {
  local env_file="$1"
  local template_file="$2"
  local panel_base="$3"
  local use_root="$4"

  local tmp_env
  tmp_env="$(mktemp)"
  if [[ -f "${env_file}" ]]; then
    cp "${env_file}" "${tmp_env}"
  elif [[ -f "${template_file}" ]]; then
    cp "${template_file}" "${tmp_env}"
  else
    touch "${tmp_env}"
  fi

  local existing_pw existing_pg_pw
  existing_pw="$(get_env_var "${tmp_env}" "ORIGINAL_PASSWORD")"
  existing_pg_pw="$(get_env_var "${tmp_env}" "POSTGRES_PASSWORD")"

  if [[ -n "${ADMIN_PASSWORD}" ]]; then
    upsert_env_var "${tmp_env}" "ORIGINAL_PASSWORD" "${ADMIN_PASSWORD}"
  elif [[ -z "${existing_pw}" || "${existing_pw}" == "replace-with-strong-password" ]]; then
    upsert_env_var "${tmp_env}" "ORIGINAL_PASSWORD" "$(generate_secret "woli-")"
    log_ok "Generated random ORIGINAL_PASSWORD in ${env_file}"
  fi

  if [[ -n "${POSTGRES_PASSWORD_ARG}" ]]; then
    upsert_env_var "${tmp_env}" "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD_ARG}"
  elif [[ -z "${existing_pg_pw}" || "${existing_pg_pw}" == "replace-with-strong-postgres-password" ]]; then
    upsert_env_var "${tmp_env}" "POSTGRES_PASSWORD" "$(generate_secret "pg-")"
    log_ok "Generated random POSTGRES_PASSWORD in ${env_file}"
  fi

  upsert_env_var "${tmp_env}" "PANEL_BASE_DIR" "${panel_base}"
  upsert_env_var "${tmp_env}" "BASE_DIR" "${panel_base}/1panel"
  upsert_env_var "${tmp_env}" "ORIGINAL_PORT" "${PORT}"
  upsert_env_var "${tmp_env}" "ORIGINAL_USERNAME" "${ADMIN_USER}"
  upsert_env_var "${tmp_env}" "POSTGRES_PORT" "${POSTGRES_PORT_ARG}"
  upsert_env_var "${tmp_env}" "GOMAXPROCS" "${ORCH_GOMAXPROCS}"
  upsert_env_var "${tmp_env}" "PG_MEM_MB" "${PG_MEM_MB}"
  upsert_env_var "${tmp_env}" "PG_SHM_MB" "${PG_SHM_MB}"
  upsert_env_var "${tmp_env}" "PG_SHARED_BUFFERS_MB" "${PG_SHARED_BUFFERS_MB}"
  upsert_env_var "${tmp_env}" "REDIS_MEM_MB" "${REDIS_MEM_MB}"
  upsert_env_var "${tmp_env}" "REDIS_MAXMEM_MB" "${REDIS_MAXMEM_MB}"

  if [[ "${use_root}" == "1" ]]; then
    run_root install -d -m 0700 /etc/wolinet
    run_root install -m 0600 "${tmp_env}" "${env_file}"
  else
    mkdir -p "$(dirname "${env_file}")"
    install -m 0600 "${tmp_env}" "${env_file}"
  fi
  rm -f "${tmp_env}"
}

install_linux() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Stage 1 DEC Orchestrator (Linux)"
    if has_systemd; then
      run_root systemctl disable --now 1apanel.service 1panel-agent.service >/dev/null 2>&1 || true
    fi
    run_root dpkg -r wolinet-orchestrator >/dev/null 2>&1 || true
    log_ok "Stage 1 DEC Orchestrator uninstalled (isolated SQLite state preserved under /var/lib/wolinet/data/1panel/db)"
    return 0
  fi

  log_header "Installing Stage 1 DEC Orchestrator (Linux ${HOST_ARCH})"
  local deb_path
  deb_path="$(resolve_product_artifact "orchestrator" "wolinet-orchestrator_${HOST_ARCH}.deb" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${deb_path}"

  install_deb_file "${deb_path}"
  configure_orchestrator_env "/etc/wolinet/1apanel.env" "/etc/wolinet/1apanel.env.example" "/var/lib/wolinet/data" 1
  run_root sysctl -p /etc/sysctl.d/99-wolinet.conf >/dev/null 2>&1 || true

  write_systemd_stage_override "1panel-agent" "network-online.target" "0" "${ORCH_MEM_HIGH_MB}" "${ORCH_MEM_MAX_MB}" 120 "LimitMEMLOCK=infinity"
  write_systemd_stage_override "1apanel" "network-online.target 1panel-agent.service" "0" "${ORCH_MEM_HIGH_MB}" "${ORCH_MEM_MAX_MB}" 120 "LimitMEMLOCK=infinity"

  log_ok "Installed Stage 1 commands: /usr/bin/wolinet-orchestrator, /usr/bin/wolinet-migrate-seed, /usr/bin/1apanel, /usr/bin/1panel-agent (CPU=${HOST_CPUS}, RAM=${HOST_MEM_MB}MB)"

  if [[ "${NO_START}" == "0" ]] && has_systemd; then
    run_root systemctl enable --now podman.socket >/dev/null 2>&1 || true
    run_root install -d -m 0755 /etc/containers /etc/tmpfiles.d
    run_root touch /etc/containers/nodocker
    if ! command -v docker >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
      tmp_docker="$(mktemp)"
      printf '#!/bin/sh\nexec /usr/bin/podman "$@"\n' > "${tmp_docker}"
      run_root install -m 0755 "${tmp_docker}" /usr/local/bin/docker
      rm -f "${tmp_docker}"
    fi
    if [[ -S /run/podman/podman.sock && ! -e /var/run/docker.sock ]]; then
      run_root ln -sfn /run/podman/podman.sock /var/run/docker.sock
    fi
    run_root systemctl daemon-reload
    run_root systemctl enable --now 1panel-agent.service 1apanel.service
    if wait_http_ok "http://127.0.0.1:${PORT}/" 20; then
      log_ok "Stage 1 1apanel healthy at http://127.0.0.1:${PORT}"
    else
      log_warn "Services started; inspect 'journalctl -u 1apanel -n 50' if UI takes longer to initialize"
    fi
  else
    log_info "Skipping systemd startup (--no-start or systemd inactive). Run 'wolinet-orchestrator serve-core' manually."
  fi

  if [[ "${WITH_DATASTORE}" == "1" ]]; then
    WOLINET_ORCH_ENV_FILE="/etc/wolinet/1apanel.env" /usr/bin/wolinet-orchestrator datastore-up
    WOLINET_ORCH_ENV_FILE="/etc/wolinet/1apanel.env" /usr/bin/wolinet-orchestrator migrate-seed
  fi
}

install_darwin() {
  local install_prefix="${PREFIX:-${HOME}/.local}"
  local app_dir="${install_prefix}/opt/orchestrator"
  local bin_dir="${install_prefix}/bin"
  local etc_dir="${install_prefix}/etc/orchestrator"
  local data_dir="${install_prefix}/var/wolinet/data"

  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Stage 1 DEC Orchestrator (macOS)"
    stop_launchagent "com.wolinet.1apanel"
    stop_launchagent "com.wolinet.1panel-agent"
    rm -f "${bin_dir}/wolinet-orchestrator" "${bin_dir}/1apanel" "${bin_dir}/1panel-agent"
    rm -rf "${app_dir}"
    log_ok "Stage 1 DEC Orchestrator uninstalled from ${install_prefix} (isolated SQLite state preserved)"
    return 0
  fi

  log_header "Installing Stage 1 DEC Orchestrator (macOS ${DARWIN_ARCH})"
  local tar_path
  tar_path="$(resolve_product_artifact "orchestrator" "orchestrator-darwin-${DARWIN_ARCH}.tar.gz" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${tar_path}"

  local unpack_dir
  unpack_dir="$(mktemp -d)"
  trap 'rm -rf "${unpack_dir:-}"' RETURN
  tar -C "${unpack_dir}" -xzf "${tar_path}"
  local extracted
  extracted="$(find "${unpack_dir}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [[ -n "${extracted}" ]] || die "Empty archive: ${tar_path}"

  rm -rf "${app_dir}"
  mkdir -p "$(dirname "${app_dir}")" "${bin_dir}" "${etc_dir}" \
    "${data_dir}/1panel/db" "${data_dir}/postgres" "${data_dir}/redis" "${data_dir}/mitambo" "${install_prefix}/var/wolinet/models"
  cp -R "${extracted}" "${app_dir}"

  ln -sf "${app_dir}/bin/wolinet-orchestrator" "${bin_dir}/wolinet-orchestrator"
  ln -sf "${app_dir}/bin/1apanel" "${bin_dir}/1apanel"
  ln -sf "${app_dir}/bin/1panel-agent" "${bin_dir}/1panel-agent"

  configure_orchestrator_env "${etc_dir}/env" "${app_dir}/etc/1apanel.env.example" "${data_dir}" 0
  ln -sf "${etc_dir}/env" "${app_dir}/etc/1apanel.env"

  log_ok "Installed Stage 1 commands in ${bin_dir}/{wolinet-orchestrator,1apanel,1panel-agent}"
  if [[ "${NO_START}" == "0" ]]; then
    local agent_plist core_plist
    agent_plist="$(write_launchagent_plist "com.wolinet.1panel-agent" "${bin_dir}/wolinet-orchestrator" "${HOME}/Library/Logs/wolinet/1panel-agent" "${etc_dir}/env" "serve-agent")"
    start_launchagent "com.wolinet.1panel-agent" "${agent_plist}"
    core_plist="$(write_launchagent_plist "com.wolinet.1apanel" "${bin_dir}/wolinet-orchestrator" "${HOME}/Library/Logs/wolinet/1apanel" "${etc_dir}/env" "serve-core")"
    start_launchagent "com.wolinet.1apanel" "${core_plist}"
    if wait_http_ok "http://127.0.0.1:${PORT}/" 20; then
      log_ok "Stage 1 1apanel healthy at http://127.0.0.1:${PORT}"
    else
      log_warn "LaunchAgents loaded; check ${HOME}/Library/Logs/wolinet/1apanel/stderr.log"
    fi
  else
    log_info "Skipping LaunchAgent startup (--no-start). Run '${bin_dir}/wolinet-orchestrator serve-core' manually."
  fi

  if [[ "${WITH_DATASTORE}" == "1" ]]; then
    WOLINET_ORCH_ENV_FILE="${etc_dir}/env" "${bin_dir}/wolinet-orchestrator" datastore-up
  fi
}

case "${HOST_OS}" in
  linux)  install_linux ;;
  darwin) install_darwin ;;
esac
