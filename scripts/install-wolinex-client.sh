#!/usr/bin/env bash
# Terminal installer for Wolinex Client Workstation Downloads (CLI + Desktop App).
# Strictly decoupled from server deployments; connects over REST to Lango Gateway (:4000).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

COMPONENT="cli"
ARTIFACT_PATH=""
AUTO_BUILD=0
UNINSTALL=0
PREFIX=""
GATEWAY_URL="${LITELLM_HOST:-http://127.0.0.1:4000}"

usage() {
  cat <<'EOF'
Wolinex Workstation Client Installer (Decoupled from Server Deployments)

Usage:
  install-wolinex-client.sh [options]

Options:
  --component <list>   Client artifact(s): cli, desktop, all (default: cli)
  --build              Build client artifact if missing locally
  --artifact <path>    Explicit client package (.deb, .tar.gz, .zip)
  --prefix <dir>       Install prefix on macOS (default: ~/.local)
  --gateway-url <url>  Remote/local Lango Gateway URL (default: http://127.0.0.1:4000)
  --uninstall          Remove Wolinex client downloads from this workstation
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --component|--components) COMPONENT="${2:-cli}"; shift 2 ;;
    --build)                  AUTO_BUILD=1; shift ;;
    --artifact)               ARTIFACT_PATH="${2:-}"; shift 2 ;;
    --prefix)                 PREFIX="${2:-}"; shift 2 ;;
    --gateway-url)            GATEWAY_URL="${2:-http://127.0.0.1:4000}"; shift 2 ;;
    --uninstall)              UNINSTALL=1; shift ;;
    -h|--help)                usage; exit 0 ;;
    *)                        die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform

if [[ -n "${ARTIFACT_PATH}" && "${COMPONENT}" == *,* ]]; then
  die "--artifact cannot be combined with multiple components (${COMPONENT})"
fi

has_component() {
  [[ ",${COMPONENT}," == *",$1,"* || ",${COMPONENT}," == *",all,"* ]]
}

configure_client_profile() {
  local profile_dir="${HOME}/.config/wolinex"
  mkdir -p "${profile_dir}"
  cat > "${profile_dir}/client.env" <<EOF
# Workstation connection profile for Wolinex Client -> Lango Gateway REST API
LITELLM_HOST=${GATEWAY_URL%/}
OPENAI_API_BASE=${GATEWAY_URL%/}/v1
GOOSE_PROVIDER=litellm
GOOSE_MODEL="Wolinet Pro"
EOF
  log_ok "Configured client gateway endpoint (${GATEWAY_URL%/}/v1) in ${profile_dir}/client.env"
}

install_cli_linux() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Wolinex Client CLI (Linux Workstation)"
    run_root dpkg -r wolinex-cli >/dev/null 2>&1 || true
    log_ok "Wolinex Client CLI removed"
    return 0
  fi

  log_header "Installing Wolinex Client CLI (Linux Workstation ${HOST_ARCH})"
  local deb_path
  deb_path="$(resolve_product_artifact "wolinex" "wolinex-cli_${HOST_ARCH}.deb" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${deb_path}"
  install_deb_file "${deb_path}"
  configure_client_profile
  log_ok "Installed client commands: /usr/bin/wolinex and /usr/bin/wolinex-cli"
}

install_cli_darwin() {
  local install_prefix="${PREFIX:-${HOME}/.local}"
  local bin_dir="${install_prefix}/bin"

  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Wolinex Client CLI (macOS Workstation)"
    rm -f "${bin_dir}/wolinex" "${bin_dir}/wolinex-cli"
    log_ok "Wolinex Client CLI removed from ${bin_dir}"
    return 0
  fi

  log_header "Installing Wolinex Client CLI (macOS Workstation ${DARWIN_ARCH})"
  local tar_path
  tar_path="$(resolve_product_artifact "wolinex" "wolinex-cli-darwin-${DARWIN_ARCH}.tar.gz" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
  sha256_verify "${tar_path}"

  local unpack_dir
  unpack_dir="$(mktemp -d)"
  trap 'rm -rf "${unpack_dir:-}"' RETURN
  tar -C "${unpack_dir}" -xzf "${tar_path}"
  local extracted
  extracted="$(find "${unpack_dir}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  [[ -n "${extracted}" ]] || die "Empty archive: ${tar_path}"

  mkdir -p "${bin_dir}"
  install -m 0755 "${extracted}/bin/wolinex" "${bin_dir}/wolinex"
  ln -sf wolinex "${bin_dir}/wolinex-cli"
  configure_client_profile
  log_ok "Installed client commands: ${bin_dir}/wolinex and ${bin_dir}/wolinex-cli"
}

install_desktop() {
  if [[ "${UNINSTALL}" == "1" ]]; then
    log_header "Uninstalling Wolinex Desktop App"
    if [[ "${HOST_OS}" == "darwin" ]]; then
      rm -rf "/Applications/Wolinex.app" "${HOME}/Applications/Wolinex.app"
    else
      run_root dpkg -r Goose Wolinex >/dev/null 2>&1 || true
    fi
    log_ok "Wolinex Desktop App removed"
    return 0
  fi

  log_header "Installing Wolinex Desktop App (${HOST_OS})"
  if [[ "${HOST_OS}" == "darwin" ]]; then
    local zip_path
    zip_path="$(resolve_product_artifact "wolinex" "Wolinex-darwin-${DARWIN_ARCH}.zip" "${ARTIFACT_PATH}" "${AUTO_BUILD}" "${ROOT_DIR}")"
    sha256_verify "${zip_path}"
    local apps_dir="/Applications"
    [[ -w "${apps_dir}" ]] || apps_dir="${HOME}/Applications"
    mkdir -p "${apps_dir}"
    ditto -x -k "${zip_path}" "${apps_dir}"
    configure_client_profile
    log_ok "Installed Wolinex.app into ${apps_dir}/Wolinex.app"
  else
    local deb_path
    deb_path="${ARTIFACT_PATH:-$(find "${ROOT_DIR}/dist/downloads/desktop" -maxdepth 1 \( -name '*Wolinex*.deb' -o -name '*Goose*.deb' \) 2>/dev/null | head -n1 || true)}"
    [[ -f "${deb_path}" ]] || die "No Linux desktop .deb found in dist/downloads/desktop/; build desktop first via packaging/wolinex/build.sh --components desktop"
    sha256_verify "${deb_path}"
    install_deb_file "${deb_path}"
    configure_client_profile
    log_ok "Installed Wolinex Desktop App from ${deb_path}"
  fi
}

case "${HOST_OS}" in
  linux)
    if has_component cli; then install_cli_linux; fi
    if has_component desktop; then install_desktop; fi
    ;;
  darwin)
    if has_component cli; then install_cli_darwin; fi
    if has_component desktop; then install_desktop; fi
    ;;
esac
