#!/usr/bin/env bash
# Terminal binary installer for Stage 4 Wolinex Web Portal (Server UI on :8081).
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
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8081}"
GATEWAY_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
GATEWAY_KEY="${OPENAI_API_KEY:-}"
DATABASE_URL_ARG="${DATABASE_URL:-}"
REDIS_URL_ARG="${REDIS_URL:-}"
WEBUI_SECRET="${WEBUI_SECRET_KEY:-}"

usage() {
  cat <<'EOF'
Wolinex Web Portal (Stage 4 Server Application) Terminal Installer

Usage:
  install-wolinex-web.sh [options]

Options:
  --build                   Build wolinex-web package from source if missing
  --artifact <path>         Explicit .deb (Linux) or .tar.gz (macOS) path
  --prefix <dir>            Install prefix on macOS (default: ~/.local)
  --host <addr>             Bind address (default: 0.0.0.0)
  --port <port>             Listen port (default: 8081; 8080 is reserved for Obscura Browser MCP)
  --gateway-url <url>       Stage 3 Lango Gateway URL (default: http://127.0.0.1:4000)
  --gateway-key <key>       API key for Lango Gateway (optional)
  --database-url <url>      PostgreSQL connection URL (:5433/webui)
  --redis-url <url>         Redis connection URL (:6379) to unlock multi-worker Uvicorn
  --no-start                Install binaries & config without starting service
  --uninstall               Remove Stage 4 Wolinex Web Portal service and runtime
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)        AUTO_BUILD=1; shift ;;
    --artifact)     ARTIFACT_PATH="${2:-}"; shift 2 ;;
    --prefix)       PREFIX="${2:-}"; shift 2 ;;
    --host)         HOST="${2:-0.0.0.0}"; shift 2 ;;
    --port)         PORT="${2:-8081}"; shift 2 ;;
    --gateway-url)  GATEWAY_URL="${2:-http://127.0.0.1:4000}"; shift 2 ;;
    --gateway-key)  GATEWAY_KEY="${2:-}"; shift 2 ;;
    --database-url) DATABASE_URL_ARG="${2:-}"; shift 2 ;;
    --redis-url)    REDIS_URL_ARG="${2:-}"; shift 2 ;;
    --no-start)     NO_START=1; shift ;;
    --uninstall)    UNINSTALL=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              die "Unknown option: $1 (try --help)" ;;
  esac
done

if [[ "${PORT}" == "8080" ]]; then
  die "Port 8080 is reserved for Wolinet Obscura Browser MCP; use port 8081 (server) or 3080 (local dev)"
fi

detect_platform
detect_host_resources

configure_wolinex_web_env() {
  local env_file="$1"
  local template_file="$2"
  local default_data="$3"
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

  local existing_secret
  existing_secret="$(get_env_var "${tmp_env}" "WEBUI_SECRET_KEY")"
  if [[ -n "${WEBUI_SECRET}" ]]; then
    upsert_env_var "${tmp_env}" "WEBUI_SECRET_KEY" "${WEBUI_SECRET}"
  elif [[ -z "${existing_secret}" || "${existing_secret}" == "replace-with-random-secret" ]]; then
    upsert_env_var "${tmp_env}" "WEBUI_SECRET_KEY" "$(generate_secret "wsec-")"
    log_ok "Generated new WEBUI_SECRET_KEY in ${env_file}"
  fi

  local api_v1="${GATEWAY_URL%/}/v1"
  upsert_env_var "${tmp_env}" "HOST" "${HOST}"
  upsert_env_var "${tmp_env}" "PORT" "${PORT}"
  upsert_env_var "${tmp_env}" "DATA_DIR" "${default_data}"
  upsert_env_var "${tmp_env}" "LITELLM_BASE_URL" "${GATEWAY_URL%/}"
  upsert_env_var "${tmp_env}" "OPENAI_API_BASE_URL" "${api_v1}"
  upsert_env_var "${tmp_env}" "OPENAI_API_BASE_URLS" "${api_v1}"
  upsert_env_var "${tmp_env}" "USE_SLIM_DOCKER" "true"
  upsert_env_var "${tmp_env}" "VECTOR_DB" "pgvector"
  if [[ -n "${GATEWAY_KEY}" ]]; then
    upsert_env_var "${tmp_env}" "OPENAI_API_KEY" "${GATEWAY_KEY}"
    upsert_env_var "${tmp_env}" "LITELLM_MASTER_KEY" "${GATEWAY_KEY}"
  fi
  [[ -n "${DATABASE_URL_ARG}" ]] && upsert_env_var "${tmp_env}" "DATABASE_URL" "${DATABASE_URL_ARG}"
  local web_workers="1"
  if [[ -n "${REDIS_URL_ARG}" ]]; then
    upsert_env_var "${tmp_env}" "REDIS_URL" "${REDIS_URL_ARG}"
    web_workers="${WEB_WORKERS_REDIS}"
  elif [[ -n "$(get_env_var "${tmp_env}" "REDIS_URL")" ]]; then
    web_workers="${WEB_WORKERS_REDIS}"
  fi
  upsert_env_var "${tmp_env}" "UVICORN_WORKERS" "${web_workers}"
  upsert_env_var "${tmp_env}" "WEBUI_NAME" "Wolinet AI"
  upsert_env_var "${tmp_env}" "ENABLE_OPENAI_API" "True"
  upsert_env_var "${tmp_env}" "ENABLE_OLLAMA_API" "False"
  upsert_env_var "${tmp_env}" "OLLAMA_BASE_URL" ""
  upsert_env_var "${tmp_env}" "OLLAMA_BASE_URLS" ""
  upsert_env_var "${tmp_env}" "ENABLE_COMMUNITY_SHARING" "false"
  upsert_env_var "${tmp_env}" "ENABLE_VERSION_UPDATE_CHECK" "false"

  if [[ "${use_root}" == "1" ]]; then
    run_root install -d -m 0750 /etc/wolinet
    run_root install -m 0640 "${tmp_env}" "${env_file}"
    if id -u wolinex >/dev/null 2>&1; then
      run_root chown root:wolinex "${env_file}"
    fi
  else
    mkdir -p "$(dirname "${env_file}")"
    install -m 0600 "${tmp_env}" "${env_file}"
  fi
  rm -f "${tmp_env}"
}

install_web_linux() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Stage 4 Wolinex Web Portal (Linux)"
    if has_systemd; then
      run_root systemctl disable --now wolinex-web.service >/dev/null 2>&1 || true
    fi
    run_root dpkg -r wolinex-web >/dev/null 2>&1 || true
    log_ok "Wolinex Web Portal uninstalled"
    return 0
  fi

  log_header "Installing Stage 4 Wolinex Web Portal (Linux ${HOST_ARCH})"
  local deb_path
  deb_path="$(resolve_product_artifact "wolinex-web" "wolinex-web_${HOST_ARCH}.deb" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${deb_path}"
  install_deb_file "${deb_path}"
  configure_wolinex_web_env "/etc/wolinet/wolinex-web.env" "/etc/wolinet/wolinex-web.env.example" "/var/lib/wolinet/wolinex" 1

  write_systemd_stage_override "wolinex-web" "network-online.target 1apanel.service litellm-gateway.service postgresql.service redis-server.service" "${WEB_MEM_LOW_MB}" "${WEB_MEM_HIGH_MB}" "${WEB_MEM_MAX_MB}" 100

  log_ok "Installed CLI command: /usr/bin/wolinex-web (MemoryMax=${WEB_MEM_MAX_MB}M)"
  if [[ "${NO_START}" == "0" ]] && has_systemd; then
    run_root systemctl daemon-reload
    run_root systemctl enable wolinex-web.service >/dev/null 2>&1 || true
    run_root systemctl restart wolinex-web.service
    if wait_http_ok "http://127.0.0.1:${PORT}/health" 30; then
      log_ok "Stage 4 Wolinex Web Portal healthy at http://127.0.0.1:${PORT}/health"
    else
      log_warn "Service started; inspect 'journalctl -u wolinex-web -n 50' while WebUI initializes"
    fi
  else
    log_info "Skipping systemd startup (--no-start or systemd inactive). Run 'wolinex-web serve' to start manually."
  fi
}

install_web_darwin() {
  local install_prefix="${PREFIX:-${HOME}/.local}"
  local app_dir="${install_prefix}/opt/wolinex-web"
  local bin_dir="${install_prefix}/bin"
  local etc_dir="${install_prefix}/etc/wolinex-web"
  local state_dir="${install_prefix}/var/wolinex-web"
  local label="com.wolinet.wolinex-web"

  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Stage 4 Wolinex Web Portal (macOS)"
    stop_launchagent "${label}"
    rm -f "${bin_dir}/wolinex-web"
    rm -rf "${app_dir}"
    log_ok "Wolinex Web Portal uninstalled from ${install_prefix}"
    return 0
  fi

  log_header "Installing Stage 4 Wolinex Web Portal (macOS ${DARWIN_ARCH})"
  local tar_path
  tar_path="$(resolve_product_artifact "wolinex-web" "wolinex-web-darwin-${DARWIN_ARCH}.tar.gz" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${tar_path}"

  local unpack_dir
  unpack_dir="$(mktemp -d)"
  trap 'rm -rf "${unpack_dir:-}"' RETURN
  tar -C "${unpack_dir}" -xzf "${tar_path}"
  local extracted
  extracted="$(find "${unpack_dir}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [[ -n "${extracted}" ]] || die "Empty archive: ${tar_path}"

  rm -rf "${app_dir}"
  mkdir -p "$(dirname "${app_dir}")" "${bin_dir}" "${etc_dir}" "${state_dir}"
  cp -R "${extracted}" "${app_dir}"

  local py_bin
  py_bin="$(find "${app_dir}/python" -path '*/bin/python3' | head -n1)"
  [[ -x "${py_bin}" ]] && ln -sf "${py_bin}" "${app_dir}/venv/bin/python" && ln -sf "${py_bin}" "${app_dir}/venv/bin/python3"

  ln -sf "${app_dir}/bin/wolinex-web" "${bin_dir}/wolinex-web"
  configure_wolinex_web_env "${etc_dir}/env" "${app_dir}/etc/wolinex-web.env.example" "${state_dir}" 0
  ln -sf "${etc_dir}/env" "${app_dir}/etc/wolinex-web.env"

  log_ok "Installed Wolinex Web Portal to ${app_dir} and CLI to ${bin_dir}/wolinex-web"
  if [[ "${NO_START}" == "0" ]]; then
    local plist_path
    plist_path="$(write_launchagent_plist "${label}" "${bin_dir}/wolinex-web" "${HOME}/Library/Logs/wolinet/wolinex-web" "${etc_dir}/env" "serve")"
    start_launchagent "${label}" "${plist_path}"
    if wait_http_ok "http://127.0.0.1:${PORT}/health" 30; then
      log_ok "Stage 4 Wolinex Web Portal healthy at http://127.0.0.1:${PORT}/health"
    else
      log_warn "LaunchAgent loaded (${plist_path}); check ${HOME}/Library/Logs/wolinet/wolinex-web/stderr.log"
    fi
  else
    log_info "Skipping LaunchAgent startup (--no-start). Run '${bin_dir}/wolinex-web serve' to start manually."
  fi
}

case "${HOST_OS}" in
  linux)  install_web_linux ;;
  darwin) install_web_darwin ;;
esac
