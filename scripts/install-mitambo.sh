#!/usr/bin/env bash
# Terminal binary installer for Wolinet Mitambo Inference Engine (Linux .deb + macOS tarball).
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
HOST="${MITAMBO_HOST:-127.0.0.1}"
PORT="${MITAMBO_PORT:-9997}"
DATA_DIR=""
MODELS_DIR=""
API_KEY="${XINFERENCE_API_KEY:-}"
ADMIN_USER="${XINFERENCE_ADMIN_USER:-}"
ADMIN_PASSWORD="${XINFERENCE_ADMIN_PASSWORD:-}"

usage() {
  cat <<'EOF'
Wolinet Mitambo Inference Engine Terminal Installer

Usage:
  install-mitambo.sh [options]

Options:
  --build                   Build installer package from source if missing
  --artifact <path>         Path to .deb (Linux) or .tar.gz (macOS) installer
  --prefix <dir>            Install prefix on macOS (default: ~/.local)
  --host <addr>             Bind address (default: 127.0.0.1)
  --port <port>             Listen port (default: 9997)
  --data-dir <dir>          XINFERENCE_HOME state directory
  --models-dir <dir>        Model weights directory
  --api-key <key>           Optional XINFERENCE_API_KEY
  --admin-user <user>       Optional admin username
  --admin-password <pass>   Optional admin password
  --no-start                Install binaries & config without starting service
  --uninstall               Remove Mitambo service and installed runtime
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)          AUTO_BUILD=1; shift ;;
    --artifact)       ARTIFACT_PATH="${2:-}"; shift 2 ;;
    --prefix)         PREFIX="${2:-}"; shift 2 ;;
    --host)           HOST="${2:-127.0.0.1}"; shift 2 ;;
    --port)           PORT="${2:-9997}"; shift 2 ;;
    --data-dir)       DATA_DIR="${2:-}"; shift 2 ;;
    --models-dir)     MODELS_DIR="${2:-}"; shift 2 ;;
    --api-key)        API_KEY="${2:-}"; shift 2 ;;
    --admin-user)     ADMIN_USER="${2:-}"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="${2:-}"; shift 2 ;;
    --no-start)       NO_START=1; shift ;;
    --uninstall)      UNINSTALL=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *)                die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform
detect_host_resources

configure_mitambo_env() {
  local env_file="$1"
  local template_file="$2"
  local default_data="$3"
  local default_models="$4"
  local use_root="$5"

  local tmp_env
  tmp_env="$(mktemp)"
  if [[ -f "${env_file}" ]]; then
    cp "${env_file}" "${tmp_env}"
  elif [[ -f "${template_file}" ]]; then
    cp "${template_file}" "${tmp_env}"
  else
    touch "${tmp_env}"
  fi

  upsert_env_var "${tmp_env}" "MITAMBO_HOST" "${HOST}"
  upsert_env_var "${tmp_env}" "MITAMBO_PORT" "${PORT}"
  upsert_env_var "${tmp_env}" "XINFERENCE_HOME" "${DATA_DIR:-${default_data}}"
  upsert_env_var "${tmp_env}" "MITAMBO_MODELS_DIR" "${MODELS_DIR:-${default_models}}"
  upsert_env_var "${tmp_env}" "XINFERENCE_THREADS" "${MITAMBO_THREADS}"
  upsert_env_var "${tmp_env}" "OMP_NUM_THREADS" "${MITAMBO_THREADS}"
  upsert_env_var "${tmp_env}" "MKL_NUM_THREADS" "${MITAMBO_THREADS}"
  upsert_env_var "${tmp_env}" "XINFERENCE_AUTH_ADVANCED" "${XINFERENCE_AUTH_ADVANCED:-true}"
  [[ -n "${API_KEY}" ]] && upsert_env_var "${tmp_env}" "XINFERENCE_API_KEY" "${API_KEY}"
  [[ -n "${ADMIN_USER}" ]] && upsert_env_var "${tmp_env}" "XINFERENCE_ADMIN_USER" "${ADMIN_USER}"
  [[ -n "${ADMIN_PASSWORD}" ]] && upsert_env_var "${tmp_env}" "XINFERENCE_ADMIN_PASSWORD" "${ADMIN_PASSWORD}"

  if [[ "${use_root}" == "1" ]]; then
    run_root install -d -m 0750 /etc/wolinet
    run_root install -m 0640 "${tmp_env}" "${env_file}"
    if id -u mitambo >/dev/null 2>&1; then
      run_root chown root:mitambo "${env_file}"
    fi
  else
    mkdir -p "$(dirname "${env_file}")"
    install -m 0600 "${tmp_env}" "${env_file}"
  fi
  rm -f "${tmp_env}"
}

install_linux() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Mitambo Inference Engine (Linux)"
    if has_systemd; then
      run_root systemctl disable --now mitambo.service >/dev/null 2>&1 || true
    fi
    run_root dpkg -r mitambo-inference >/dev/null 2>&1 || true
    log_ok "Mitambo uninstalled (models & env preserved under /var/lib/wolinet and /etc/wolinet)"
    return 0
  fi

  log_header "Installing Mitambo Inference Engine (Linux ${HOST_ARCH})"
  local deb_name="mitambo-inference_${HOST_ARCH}.deb"
  local deb_path
  deb_path="$(resolve_product_artifact "mitambo" "${deb_name}" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${deb_path}"

  install_deb_file "${deb_path}"
  run_root install -d -m 0750 -o mitambo -g mitambo /var/lib/wolinet/data/mitambo
  configure_mitambo_env "/etc/wolinet/mitambo.env" "/etc/wolinet/mitambo.env.example" "/var/lib/wolinet/data/mitambo" "/var/lib/wolinet/models" 1

  write_systemd_stage_override "mitambo" "network-online.target 1apanel.service" "${MITAMBO_MEM_LOW_MB}" "${MITAMBO_MEM_HIGH_MB}" "${MITAMBO_MEM_MAX_MB}" 200 $'LimitMEMLOCK=infinity\nReadWritePaths=/var/lib/wolinet/mitambo /var/lib/wolinet/data/mitambo /var/lib/wolinet/models'

  log_ok "Installed CLI command: /usr/bin/mitambo (threads=${MITAMBO_THREADS}, MemoryMax=${MITAMBO_MEM_MAX_MB}M)"
  if [[ "${NO_START}" == "0" ]] && has_systemd; then
    run_root systemctl daemon-reload
    run_root systemctl enable --now mitambo.service
    if wait_http_ok "http://127.0.0.1:${PORT}/status" 30; then
      log_ok "Mitambo healthy at http://127.0.0.1:${PORT}/status"
    else
      log_warn "Service started; check 'journalctl -u mitambo -n 50' while inference initializes"
    fi
  else
    log_info "Skipping systemd startup (--no-start or systemd inactive). Run 'mitambo serve' to start manually."
  fi
}

install_darwin() {
  local install_prefix="${PREFIX:-${HOME}/.local}"
  local app_dir="${install_prefix}/opt/mitambo"
  local bin_dir="${install_prefix}/bin"
  local etc_dir="${install_prefix}/etc/mitambo"
  local state_dir="${DATA_DIR:-${install_prefix}/var/mitambo}"
  local label="com.wolinet.mitambo"

  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Mitambo Inference Engine (macOS)"
    stop_launchagent "${label}"
    rm -f "${bin_dir}/mitambo"
    rm -rf "${app_dir}"
    log_ok "Mitambo uninstalled from ${install_prefix} (data preserved in ${state_dir})"
    return 0
  fi

  log_header "Installing Mitambo Inference Engine (macOS ${DARWIN_ARCH})"
  local tar_name="mitambo-darwin-${DARWIN_ARCH}.tar.gz"
  local tar_path
  tar_path="$(resolve_product_artifact "mitambo" "${tar_name}" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${tar_path}"

  local unpack_dir
  unpack_dir="$(mktemp -d)"
  trap 'rm -rf "${unpack_dir:-}"' RETURN
  tar -C "${unpack_dir}" -xzf "${tar_path}"
  local extracted
  extracted="$(find "${unpack_dir}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [[ -n "${extracted}" ]] || die "Empty archive: ${tar_path}"

  rm -rf "${app_dir}"
  mkdir -p "$(dirname "${app_dir}")" "${bin_dir}" "${etc_dir}" "${state_dir}/models"
  cp -R "${extracted}" "${app_dir}"

  # Repoint python symlinks in venv cleanly for the chosen install prefix
  local py_bin
  py_bin="$(find "${app_dir}/python" -path '*/bin/python3' | head -n1)"
  [[ -x "${py_bin}" ]] && ln -sf "${py_bin}" "${app_dir}/venv/bin/python" && ln -sf "${py_bin}" "${app_dir}/venv/bin/python3"

  ln -sf "${app_dir}/bin/mitambo" "${bin_dir}/mitambo"
  configure_mitambo_env "${etc_dir}/env" "${app_dir}/etc/mitambo.env.example" "${state_dir}" "${state_dir}/models" 0
  ln -sf "${etc_dir}/env" "${app_dir}/etc/mitambo.env"

  log_ok "Installed Mitambo runtime to ${app_dir} and CLI to ${bin_dir}/mitambo"
  if [[ "${NO_START}" == "0" ]]; then
    local plist_path
    plist_path="$(write_launchagent_plist "${label}" "${bin_dir}/mitambo" "${HOME}/Library/Logs/wolinet/mitambo" "${etc_dir}/env" "serve")"
    start_launchagent "${label}" "${plist_path}"
    if wait_http_ok "http://127.0.0.1:${PORT}/status" 30; then
      log_ok "Mitambo healthy at http://127.0.0.1:${PORT}/status"
    else
      log_warn "LaunchAgent loaded (${plist_path}); check ${HOME}/Library/Logs/wolinet/mitambo/stderr.log"
    fi
  else
    log_info "Skipping LaunchAgent startup (--no-start). Run '${bin_dir}/mitambo serve' to start manually."
  fi
}

case "${HOST_OS}" in
  linux)  install_linux ;;
  darwin) install_darwin ;;
esac
