#!/usr/bin/env bash
# Build standalone installers for Lango AI Gateway (Linux .deb + macOS binary tarball).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../lib/build_common.sh
source "${ROOT_DIR}/packaging/lib/build_common.sh"

REBUILD=0
TARGET="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=1; shift ;;
    --target)  TARGET="${2:-all}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: build.sh [--target all|linux|darwin] [--rebuild]
Builds Lango binary installers into dist/installers/lango/.
EOF
      exit 0 ;;
    *) build_die "Unknown option: $1" ;;
  esac
done

OUT_DIR="${ROOT_DIR}/dist/installers/server/lango"
mkdir -p "${OUT_DIR}"

sanitize_gateway_config() {
  local src="$1"
  local dst="$2"
  python3 - "$src" "$dst" <<'PY'
import pathlib, re, sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
text = text.replace("http://host.docker.internal:", "http://127.0.0.1:")
text = re.sub(r'(api_key:\s*)"sk-[^"]+"', r'\1"os.environ/XINFERENCE_API_KEY"', text)
text = re.sub(r'(api_key:\s*)"AQ\.[^"]+"', r'\1"os.environ/GEMINI_API_KEY"', text)
text = re.sub(r'(master_key:\s*)"[^"]+"', r'\1"os.environ/LITELLM_MASTER_KEY"', text)
pathlib.Path(sys.argv[2]).write_text(text, encoding="utf-8")
PY
}

build_sanitized_assets() {
  sanitize_gateway_config "${ROOT_DIR}/gateway/config.yaml" "${OUT_DIR}/config.yaml.example"
  sed 's/:5432\/litellm/:5433\/litellm/g' "${ROOT_DIR}/gateway/litellm-rust/deploy/env.example" > "${OUT_DIR}/env.example"
  if [[ -f "${ROOT_DIR}/gateway/model_prices_and_context_window.json" ]]; then
    cp -f "${ROOT_DIR}/gateway/model_prices_and_context_window.json" "${OUT_DIR}/model_prices_and_context_window.json"
  fi
  if [[ -d "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" ]]; then
    rm -rf "${OUT_DIR}/ui"
    cp -R "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" "${OUT_DIR}/ui"
  fi
}

build_linux_deb() {
  local gw_deb="${ROOT_DIR}/gateway/dist/litellm-gateway_amd64.deb"
  if [[ "${REBUILD}" == "1" || ! -f "${gw_deb}" ]]; then
    build_log "Building Lango Ubuntu 24.04 amd64 .deb via gateway/Makefile..."
    make -C "${ROOT_DIR}/gateway" package-deb-linux
  else
    build_log "Reusing existing ${gw_deb} (pass --rebuild to recompile)"
  fi
  cp -f "${gw_deb}" "${OUT_DIR}/litellm-gateway_amd64.deb"
  write_sha256_sidecar "${OUT_DIR}/litellm-gateway_amd64.deb"
  build_log "Ready: ${OUT_DIR}/litellm-gateway_amd64.deb"
}

build_darwin_bundle() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    build_log "Skipping macOS bundle build on $(uname -s)"
    return 0
  fi

  local rust_bin="${ROOT_DIR}/gateway/litellm-rust/target/release/litellm-gateway"
  if [[ "${REBUILD}" == "1" || ! -x "${rust_bin}" ]]; then
    build_log "Compiling release litellm-gateway binary for macOS..."
    (cd "${ROOT_DIR}/gateway/litellm-rust" && cargo build --release --locked -p litellm-gateway)
  else
    build_log "Reusing existing macOS release binary: ${rust_bin}"
  fi

  local arch_tag version stage pkg_dir tarball
  arch_tag="$(darwin_arch_tag)"
  version="$(awk -F'"' '/^version *=/{print $2; exit}' "${ROOT_DIR}/gateway/litellm-rust/crates/gateway/Cargo.toml")"
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN

  pkg_dir="${stage}/lango-${version}-darwin-${arch_tag}"
  mkdir -p "${pkg_dir}/bin" "${pkg_dir}/etc" "${pkg_dir}/share"
  cp -f "${rust_bin}" "${pkg_dir}/bin/litellm-gateway"
  chmod 0755 "${pkg_dir}/bin/litellm-gateway"
  cp -f "${OUT_DIR}/config.yaml.example" "${pkg_dir}/etc/config.yaml.example"
  cp -f "${OUT_DIR}/env.example" "${pkg_dir}/etc/env.example"
  if [[ -f "${OUT_DIR}/model_prices_and_context_window.json" ]]; then
    cp -f "${OUT_DIR}/model_prices_and_context_window.json" "${pkg_dir}/share/model_prices_and_context_window.json"
  fi

  tarball="${OUT_DIR}/lango-darwin-${arch_tag}.tar.gz"
  tar -C "${stage}" -czf "${tarball}" "lango-${version}-darwin-${arch_tag}"
  write_sha256_sidecar "${tarball}"
  build_log "Ready: ${tarball}"
}

build_sanitized_assets

case "${TARGET}" in
  all)
    build_linux_deb
    build_darwin_bundle
    ;;
  linux)  build_linux_deb ;;
  darwin) build_darwin_bundle ;;
  *)      build_die "Unsupported target: ${TARGET} (expected: all|linux|darwin)" ;;
esac
