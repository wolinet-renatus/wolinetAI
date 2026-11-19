#!/usr/bin/env bash
# Terminal binary installer for Lango AI Gateway (Linux .deb + macOS tarball).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

ARTIFACT_PATH=""
AUTO_BUILD=0
NO_START=0
UNINSTALL=0
PREFIX=""
PORT="${PORT:-4000}"
HOST="${HOST:-0.0.0.0}"
MASTER_KEY="${LITELLM_MASTER_KEY:-}"
UI_USER_ARG="${UI_USERNAME:-}"
UI_PASS_ARG="${UI_PASSWORD:-}"
DATABASE_URL_ARG="${DATABASE_URL:-}"
REDIS_URL_ARG="${REDIS_URL:-}"
XINFERENCE_API_KEY_ARG="${XINFERENCE_API_KEY:-}"

usage() {
  cat <<'EOF'
Lango AI Gateway Terminal Installer

Usage:
  install-lango.sh [options]

Options:
  --build                   Build installer package from source if missing
  --artifact <path>         Path to .deb (Linux) or .tar.gz (macOS) installer
  --prefix <dir>            Install prefix on macOS (default: ~/.local)
  --port <port>             Listen port (default: 4000)
  --host <addr>             Bind address (default: 0.0.0.0)
  --master-key <key>        Set LITELLM_MASTER_KEY (auto-generated if omitted)
  --database-url <url>      PostgreSQL connection string
  --redis-url <url>         Redis connection string
  --xinference-key <key>    Stage 2 Mitambo XINFERENCE_API_KEY
  --no-start                Install binaries & config without starting service
  --uninstall               Remove Lango service and installed binaries
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)           AUTO_BUILD=1; shift ;;
    --artifact)        ARTIFACT_PATH="${2:-}"; shift 2 ;;
    --prefix)          PREFIX="${2:-}"; shift 2 ;;
    --port)            PORT="${2:-4000}"; shift 2 ;;
    --host)            HOST="${2:-0.0.0.0}"; shift 2 ;;
    --master-key)      MASTER_KEY="${2:-}"; shift 2 ;;
    --ui-username)     UI_USER_ARG="${2:-}"; shift 2 ;;
    --ui-password)     UI_PASS_ARG="${2:-}"; shift 2 ;;
    --database-url)    DATABASE_URL_ARG="${2:-}"; shift 2 ;;
    --redis-url)       REDIS_URL_ARG="${2:-}"; shift 2 ;;
    --xinference-key)  XINFERENCE_API_KEY_ARG="${2:-}"; shift 2 ;;
    --no-start)        NO_START=1; shift ;;
    --uninstall)       UNINSTALL=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)                 die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform
detect_host_resources

write_lango_cli_wrapper() {
  local wrapper_path="$1"
  local bin_path="$2"
  local env_file="$3"
  local is_linux="$4"

  cat <<EOF > "${wrapper_path}"
#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="${env_file}"
BIN_PATH="${bin_path}"

load_env() {
  if [[ -f "\${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "\${ENV_FILE}"
    set +a
  fi
}

case "\${1:-help}" in
  start)
    if [[ "${is_linux}" == "1" ]] && command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
      exec systemctl start litellm-gateway
    fi
    load_env
    exec "\${BIN_PATH}"
    ;;
  stop)
    if [[ "${is_linux}" == "1" ]] && command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
      exec systemctl stop litellm-gateway
    fi
    pkill -f "\${BIN_PATH}" || true
    ;;
  status)
    if [[ "${is_linux}" == "1" ]] && command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
      systemctl status litellm-gateway --no-pager
    else
      load_env
      curl -fsS "http://127.0.0.1:\${PORT:-4000}/health/liveliness" && echo ""
    fi
    ;;
  logs)
    if [[ "${is_linux}" == "1" ]] && command -v journalctl >/dev/null 2>&1; then
      exec journalctl -u litellm-gateway -n 100 -f
    fi
    tail -n 100 -f "\${HOME}/Library/Logs/wolinet/lango/stderr.log"
    ;;
  version|--version|-V)
    exec "\${BIN_PATH}" --version
    ;;
  help|--help|-h)
    cat <<'USAGE'
Lango AI Gateway CLI
Usage: lango <command>
  start     Start gateway (systemd or foreground)
  stop      Stop gateway
  status    Check gateway service / liveliness
  logs      Tail gateway logs
  run       Run binary directly with loaded env
  --help    Show upstream binary flags
USAGE
    "\${BIN_PATH}" --help
    ;;
  run)
    shift
    load_env
    exec "\${BIN_PATH}" "\$@"
    ;;
  *)
    load_env
    exec "\${BIN_PATH}" "\$@"
    ;;
esac
EOF
  chmod 0755 "${wrapper_path}"
}

configure_lango_env() {
  local env_file="$1"
  local config_path="$2"
  local use_root="$3"

  local tmp_env
  tmp_env="$(mktemp)"
  if [[ -f "${env_file}" ]]; then
    cp "${env_file}" "${tmp_env}"
  elif [[ -f "${ROOT_DIR}/dist/installers/server/lango/env.example" ]]; then
    cp "${ROOT_DIR}/dist/installers/server/lango/env.example" "${tmp_env}"
  elif [[ -f "${ROOT_DIR}/gateway/litellm-rust/deploy/env.example" ]]; then
    sed 's/:5432\/litellm/:5433\/litellm/g' "${ROOT_DIR}/gateway/litellm-rust/deploy/env.example" > "${tmp_env}"
  else
    touch "${tmp_env}"
  fi

  local existing_master
  existing_master="$(get_env_var "${tmp_env}" "LITELLM_MASTER_KEY")"
  if [[ -n "${MASTER_KEY}" ]]; then
    upsert_env_var "${tmp_env}" "LITELLM_MASTER_KEY" "${MASTER_KEY}"
  elif [[ -z "${existing_master}" || "${existing_master}" == "sk-replace-with-strong-master-key" ]]; then
    upsert_env_var "${tmp_env}" "LITELLM_MASTER_KEY" "$(generate_secret "sk-lango-")"
    log_ok "Generated new LITELLM_MASTER_KEY in ${env_file}"
  fi

  upsert_env_var "${tmp_env}" "UI_USERNAME" "${UI_USER_ARG:-$(get_env_var "${tmp_env}" "UI_USERNAME" | grep -E '.+' || echo 'admin')}"
  if [[ -n "${UI_PASS_ARG}" ]]; then
    upsert_env_var "${tmp_env}" "UI_PASSWORD" "${UI_PASS_ARG}"
  fi
  upsert_env_var "${tmp_env}" "HOST" "${HOST}"
  upsert_env_var "${tmp_env}" "PORT" "${PORT}"
  upsert_env_var "${tmp_env}" "LITELLM_CONFIG" "${config_path}"
  upsert_env_var "${tmp_env}" "TOKIO_WORKER_THREADS" "${LANGO_TOKIO_THREADS}"
  [[ -n "${DATABASE_URL_ARG}" ]] && upsert_env_var "${tmp_env}" "DATABASE_URL" "${DATABASE_URL_ARG}"
  [[ -n "${REDIS_URL_ARG}" ]] && upsert_env_var "${tmp_env}" "REDIS_URL" "${REDIS_URL_ARG}"
  [[ -n "${XINFERENCE_API_KEY_ARG}" ]] && upsert_env_var "${tmp_env}" "XINFERENCE_API_KEY" "${XINFERENCE_API_KEY_ARG}"

  if [[ "${use_root}" == "1" ]]; then
    run_root install -d -m 0750 /etc/litellm
    run_root install -m 0640 "${tmp_env}" "${env_file}"
    if id -u litellm >/dev/null 2>&1; then
      run_root chown root:litellm "${env_file}"
    fi
  else
    mkdir -p "$(dirname "${env_file}")"
    install -m 0600 "${tmp_env}" "${env_file}"
  fi
  rm -f "${tmp_env}"
}

install_linux() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Lango AI Gateway (Linux)"
    if has_systemd; then
      run_root systemctl disable --now litellm-gateway >/dev/null 2>&1 || true
    fi
    run_root dpkg -r litellm-gateway >/dev/null 2>&1 || true
    run_root rm -f /usr/local/bin/lango /usr/bin/lango
    log_ok "Lango uninstalled (config preserved in /etc/litellm)"
    return 0
  fi

  log_header "Installing Lango AI Gateway (Linux ${HOST_ARCH})"
  local deb_name="litellm-gateway_${HOST_ARCH}.deb"
  local deb_path
  deb_path="$(resolve_product_artifact "lango" "${deb_name}" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${deb_path}"

  install_deb_file "${deb_path}"

  local cfg_dst="/etc/litellm/config.yaml"
  if [[ ! -f "${cfg_dst}" ]]; then
    local cfg_src="${ROOT_DIR}/dist/installers/server/lango/config.yaml.example"
    if [[ -f "${cfg_src}" ]]; then
      run_root install -m 0644 "${cfg_src}" "${cfg_dst}"
      if id -u litellm >/dev/null 2>&1; then
        run_root chown root:litellm "${cfg_dst}"
      fi
      log_ok "Installed default config at ${cfg_dst}"
    fi
  elif grep -q 'disable_env_credential_login:[[:space:]]*true' "${cfg_dst}" && \
       ! grep -qE '^(MICROSOFT|GOOGLE|GENERIC)_CLIENT_ID=' /etc/litellm/env 2>/dev/null; then
    run_root sed -i 's/disable_env_credential_login:[[:space:]]*true/disable_env_credential_login: false/g' "${cfg_dst}"
    log_ok "Enabled admin UI credential login in ${cfg_dst} (no SSO configured)"
  fi

  configure_lango_env "/etc/litellm/env" "${cfg_dst}" 1

  # Enforce Stage 3 systemd ordering & hardware budget after Stage 1 orchestrator & Stage 2 Mitambo
  local lango_extra_lines=""
  if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt -c >/dev/null 2>&1; then
    lango_extra_lines=$'PrivateDevices=no\nLockPersonality=no\nRestrictRealtime=no\nRestrictSUIDSGID=no'
  fi
  write_systemd_stage_override "litellm-gateway" "network-online.target 1apanel.service mitambo.service postgresql.service redis-server.service" "${LANGO_MEM_LOW_MB}" "${LANGO_MEM_HIGH_MB}" "${LANGO_MEM_MAX_MB}" 150 "${lango_extra_lines}"

  local tmp_cli
  tmp_cli="$(mktemp)"
  write_lango_cli_wrapper "${tmp_cli}" "/usr/bin/litellm-gateway" "/etc/litellm/env" 1
  run_root install -m 0755 "${tmp_cli}" /usr/bin/lango
  rm -f "${tmp_cli}"
  log_ok "Installed CLI commands: /usr/bin/litellm-gateway and /usr/bin/lango (Tokio=${LANGO_TOKIO_THREADS}, MemoryMax=${LANGO_MEM_MAX_MB}M)"

  if [[ "${NO_START}" == "0" ]] && has_systemd; then
    run_root systemctl daemon-reload
    run_root systemctl enable litellm-gateway >/dev/null 2>&1 || true
    run_root systemctl restart litellm-gateway
    if wait_http_ok "http://127.0.0.1:${PORT}/health/liveliness" 20; then
      log_ok "Lango Gateway healthy at http://127.0.0.1:${PORT}/health/liveliness"
    else
      log_warn "Service started; check 'journalctl -u litellm-gateway -n 50' if health probe timed out"
    fi
  else
    log_info "Skipping systemd startup (--no-start or systemd inactive). Run 'lango run' to launch manually."
  fi
}

install_darwin() {
  local install_prefix="${PREFIX:-${HOME}/.local}"
  local app_dir="${install_prefix}/opt/lango"
  local bin_dir="${install_prefix}/bin"
  local etc_dir="${install_prefix}/etc/lango"
  local label="com.wolinet.lango"

  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Lango AI Gateway (macOS)"
    stop_launchagent "${label}"
    rm -f "${bin_dir}/litellm-gateway" "${bin_dir}/lango"
    rm -rf "${app_dir}"
    log_ok "Lango uninstalled from ${install_prefix} (config preserved in ${etc_dir})"
    return 0
  fi

  log_header "Installing Lango AI Gateway (macOS ${DARWIN_ARCH})"
  local tar_name="lango-darwin-${DARWIN_ARCH}.tar.gz"
  local tar_path
  tar_path="$(resolve_product_artifact "lango" "${tar_name}" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${tar_path}"

  local unpack_dir
  unpack_dir="$(mktemp -d)"
  trap 'rm -rf "${unpack_dir:-}"' RETURN
  tar -C "${unpack_dir}" -xzf "${tar_path}"
  local extracted
  extracted="$(find "${unpack_dir}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [[ -n "${extracted}" ]] || die "Empty archive: ${tar_path}"

  mkdir -p "${app_dir}" "${bin_dir}" "${etc_dir}"
  cp -f "${extracted}/bin/litellm-gateway" "${bin_dir}/litellm-gateway"
  chmod 0755 "${bin_dir}/litellm-gateway"

  if [[ -f "${extracted}/share/model_prices_and_context_window.json" ]]; then
    cp -f "${extracted}/share/model_prices_and_context_window.json" "${app_dir}/model_prices_and_context_window.json"
  fi
  if [[ ! -f "${etc_dir}/config.yaml" && -f "${extracted}/etc/config.yaml.example" ]]; then
    cp -f "${extracted}/etc/config.yaml.example" "${etc_dir}/config.yaml"
  fi

  configure_lango_env "${etc_dir}/env" "${etc_dir}/config.yaml" 0
  write_lango_cli_wrapper "${bin_dir}/lango" "${bin_dir}/litellm-gateway" "${etc_dir}/env" 0
  log_ok "Installed binaries in ${bin_dir}/litellm-gateway and ${bin_dir}/lango"

  if [[ "${NO_START}" == "0" ]]; then
    local plist_path
    plist_path="$(write_launchagent_plist "${label}" "${bin_dir}/litellm-gateway" "${HOME}/Library/Logs/wolinet/lango" "${etc_dir}/env")"
    start_launchagent "${label}" "${plist_path}"
    if wait_http_ok "http://127.0.0.1:${PORT}/health/liveliness" 20; then
      log_ok "Lango Gateway healthy at http://127.0.0.1:${PORT}/health/liveliness"
    else
      log_warn "LaunchAgent loaded (${plist_path}); check ${HOME}/Library/Logs/wolinet/lango/stderr.log"
    fi
  else
    log_info "Skipping LaunchAgent startup (--no-start). Run '${bin_dir}/lango run' to start."
  fi
}

case "${HOST_OS}" in
  linux)  install_linux ;;
  darwin) install_darwin ;;
esac
