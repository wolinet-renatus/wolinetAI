#!/usr/bin/env bash
# Build standalone installers for Wolinex Web Portal, Wolinex CLI, and Wolinex Desktop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../lib/build_common.sh
source "${ROOT_DIR}/packaging/lib/build_common.sh"

REBUILD=0
TARGET="all"
COMPONENTS="web,cli"
PYTHON_VERSION="3.12"
UV_VERSION="0.12.19"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild)    REBUILD=1; shift ;;
    --target)     TARGET="${2:-all}"; shift 2 ;;
    --components) COMPONENTS="${2:-web,cli}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: build.sh [--target all|linux|darwin] [--components web,cli,desktop] [--rebuild]
Builds standalone Wolinex installers into dist/installers/wolinex/.
EOF
      exit 0 ;;
    *) build_die "Unknown option: $1" ;;
  esac
done

WEB_OUT_DIR="${ROOT_DIR}/dist/installers/server/wolinex-web"
CLIENT_OUT_DIR="${ROOT_DIR}/dist/downloads/desktop"
mkdir -p "${WEB_OUT_DIR}" "${CLIENT_OUT_DIR}"

has_component() {
  [[ ",${COMPONENTS}," == *",$1,"* || ",${COMPONENTS}," == *",all,"* ]]
}

read_json_version() {
  python3 - "$1" "$2" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
if p.exists():
    print(json.loads(p.read_text(encoding="utf-8")).get("version", sys.argv[2]))
else:
    print(sys.argv[2])
PY
}

stage_web_source() {
  local stage_root="$1"
  mkdir -p "${stage_root}/wolinex" "${stage_root}/packaging"
  tar -C "${ROOT_DIR}/apps/wolinex" \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='build' \
    --exclude='backend/data' \
    --exclude='backend/.webui_secret_key' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    -cf - . | tar -C "${stage_root}/wolinex" -xf -

  cp -R "${ROOT_DIR}/packaging/wolinex" "${stage_root}/packaging/wolinex"
}

stage_cli_source() {
  local stage_root="$1"
  mkdir -p "${stage_root}/WolinexIde"
  tar -C "${ROOT_DIR}/apps/WolinexIde" \
    --exclude='target' \
    --exclude='ui/desktop/node_modules' \
    --exclude='ui/desktop/out' \
    --exclude='ui/desktop/dist' \
    --exclude='.git' \
    -cf - . | tar -C "${stage_root}/WolinexIde" -xf -
}

build_web_linux_deb() {
  local deb_out="${WEB_OUT_DIR}/wolinex-web_amd64.deb"
  if [[ "${REBUILD}" == "0" && -f "${deb_out}" ]]; then
    build_log "Reusing existing ${deb_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${deb_out}"
    return 0
  fi

  local container_cli version stage cid
  container_cli="$(ensure_container_cli)"
  version="$(read_json_version "${ROOT_DIR}/apps/wolinex/package.json" "0.13.2")"
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN

  build_log "Staging clean Wolinex Web source tree for Ubuntu 24.04 .deb build..."
  stage_web_source "${stage}"

  build_log "Building wolinex-web_${version}_amd64.deb in ubuntu:24.04 (${container_cli})..."
  "${container_cli}" build --platform linux/amd64 \
    --target builder \
    --build-arg "WOLINEX_WEB_VERSION=${version}" \
    --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
    --build-arg "UV_VERSION=${UV_VERSION}" \
    -t wolinex-web-deb-builder:local \
    -f "${stage}/packaging/wolinex/Dockerfile.web.deb" \
    "${stage}"

  cid="$("${container_cli}" create wolinex-web-deb-builder:local /bin/true)"
  "${container_cli}" cp "${cid}:/out/wolinex-web_amd64.deb" "${deb_out}"
  "${container_cli}" rm -f "${cid}" >/dev/null
  write_sha256_sidecar "${deb_out}"
  build_log "Ready: ${deb_out}"
}

build_cli_linux_deb() {
  local deb_out="${CLIENT_OUT_DIR}/wolinex-cli_amd64.deb"
  if [[ "${REBUILD}" == "0" && -f "${deb_out}" ]]; then
    build_log "Reusing existing ${deb_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${deb_out}"
    return 0
  fi

  local container_cli version stage cid
  container_cli="$(ensure_container_cli)"
  version="$(read_json_version "${ROOT_DIR}/apps/WolinexIde/ui/desktop/package.json" "1.58.0")"
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN

  build_log "Staging Wolinex CLI Rust workspace for Ubuntu 24.04 .deb build..."
  stage_cli_source "${stage}"

  local extra_vols=()
  if [[ "${container_cli}" == "podman" && -d "${HOME}/.cargo/registry" ]]; then
    extra_vols+=(-v "${HOME}/.cargo/registry:/usr/local/cargo/registry")
    [[ -d "${HOME}/.cargo/git" ]] && extra_vols+=(-v "${HOME}/.cargo/git:/usr/local/cargo/git")
  fi

  build_log "Building wolinex-cli_${version}_amd64.deb in ubuntu:24.04 (${container_cli})..."
  "${container_cli}" build --platform linux/amd64 \
    "${extra_vols[@]}" \
    --target builder \
    --build-arg "WOLINEX_CLI_VERSION=${version}" \
    -t wolinex-cli-deb-builder:local \
    -f "${ROOT_DIR}/packaging/wolinex/Dockerfile.cli.deb" \
    "${stage}"

  cid="$("${container_cli}" create wolinex-cli-deb-builder:local /bin/true)"
  "${container_cli}" cp "${cid}:/out/wolinex-cli_amd64.deb" "${deb_out}"
  "${container_cli}" rm -f "${cid}" >/dev/null
  write_sha256_sidecar "${deb_out}"
  build_log "Ready: ${deb_out}"
}

build_web_darwin_bundle() {
  local arch_tag version tar_out
  arch_tag="$(darwin_arch_tag)"
  version="$(read_json_version "${ROOT_DIR}/apps/wolinex/package.json" "0.13.2")"
  tar_out="${WEB_OUT_DIR}/wolinex-web-darwin-${arch_tag}.tar.gz"

  if [[ "${REBUILD}" == "0" && -f "${tar_out}" ]]; then
    build_log "Reusing existing ${tar_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${tar_out}"
    return 0
  fi

  command -v uv >/dev/null 2>&1 || build_die "uv is required on macOS to build Wolinex Web bundle"
  command -v npm >/dev/null 2>&1 || build_die "npm is required on macOS to build Wolinex Web frontend"

  local stage pkg_dir py_bin
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN
  pkg_dir="${stage}/wolinex-web-${version}-darwin-${arch_tag}"
  mkdir -p "${pkg_dir}/bin" "${pkg_dir}/etc"

  build_log "Building Wolinex Web frontend assets..."
  if [[ ! -d "${ROOT_DIR}/apps/wolinex/build" || "${REBUILD}" == "1" ]]; then
    (
      cd "${ROOT_DIR}/apps/wolinex"
      ONNXRUNTIME_NODE_INSTALL_CUDA=skip npm ci --force
      npm run build
    )
  fi

  build_log "Provisioning standalone Python ${PYTHON_VERSION} for Wolinex Web..."
  UV_PYTHON_BIN_DIR="${stage}/pybin" UV_PYTHON_INSTALL_DIR="${pkg_dir}/python" uv python install "${PYTHON_VERSION}"
  py_bin="$(find "${pkg_dir}/python" -path '*/bin/python3' | head -n1)"
  [[ -x "${py_bin}" ]] || build_die "Failed to locate standalone python3 inside ${pkg_dir}/python"

  uv venv --relocatable "${pkg_dir}/venv" --python "${py_bin}"
  uv pip install --python "${pkg_dir}/venv/bin/python" -r "${ROOT_DIR}/apps/wolinex/backend/requirements-slim.txt"

  tar -C "${ROOT_DIR}/apps/wolinex/backend" --exclude='data' --exclude='__pycache__' --exclude='*.pyc' -cf - . \
    | { mkdir -p "${pkg_dir}/backend" && tar -C "${pkg_dir}/backend" -xf -; }
  cp -R "${ROOT_DIR}/apps/wolinex/build" "${pkg_dir}/frontend"
  cp -f "${ROOT_DIR}/apps/wolinex/package.json" "${pkg_dir}/package.json"
  cp -f "${ROOT_DIR}/apps/wolinex/CHANGELOG.md" "${pkg_dir}/CHANGELOG.md"
  cp -f "${ROOT_DIR}/packaging/wolinex/wolinex-web" "${pkg_dir}/bin/wolinex-web"
  chmod 0755 "${pkg_dir}/bin/wolinex-web"
  cp -f "${ROOT_DIR}/packaging/wolinex/deploy/env.example" "${pkg_dir}/etc/wolinex-web.env.example"
  find "${pkg_dir}" -type d -name '__pycache__' -prune -exec rm -rf {} +

  tar -C "${stage}" -czf "${tar_out}" "wolinex-web-${version}-darwin-${arch_tag}"
  write_sha256_sidecar "${tar_out}"
  build_log "Ready: ${tar_out}"
}

build_cli_darwin_bundle() {
  local arch_tag version tar_out rust_bin
  arch_tag="$(darwin_arch_tag)"
  version="$(read_json_version "${ROOT_DIR}/apps/WolinexIde/ui/desktop/package.json" "1.58.0")"
  tar_out="${CLIENT_OUT_DIR}/wolinex-cli-darwin-${arch_tag}.tar.gz"

  if [[ "${REBUILD}" == "0" && -f "${tar_out}" ]]; then
    build_log "Reusing existing ${tar_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${tar_out}"
    return 0
  fi

  rust_bin="${ROOT_DIR}/apps/WolinexIde/target/release/goose"
  if [[ "${REBUILD}" == "1" || ! -x "${rust_bin}" ]]; then
    build_log "Compiling release Wolinex CLI binary for macOS..."
    (cd "${ROOT_DIR}/apps/WolinexIde" && cargo build --release --locked --no-default-features --features portable-default -p goose-cli --bin goose)
  fi

  local stage pkg_dir
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN
  pkg_dir="${stage}/wolinex-cli-${version}-darwin-${arch_tag}"
  mkdir -p "${pkg_dir}/bin"
  install -m 0755 "${rust_bin}" "${pkg_dir}/bin/wolinex"
  ln -sf wolinex "${pkg_dir}/bin/wolinex-cli"

  tar -C "${stage}" -czf "${tar_out}" "wolinex-cli-${version}-darwin-${arch_tag}"
  write_sha256_sidecar "${tar_out}"
  build_log "Ready: ${tar_out}"
}

build_desktop_bundle() {
  local desktop_dir="${ROOT_DIR}/apps/WolinexIde/ui/desktop"
  local rust_bin="${ROOT_DIR}/apps/WolinexIde/target/release/goose"
  if [[ ! -x "${rust_bin}" && "${REBUILD}" == "1" ]]; then
    build_log "Compiling Wolinex Rust backend for Desktop..."
    (cd "${ROOT_DIR}/apps/WolinexIde" && cargo build --release --locked --no-default-features --features portable-default -p goose-cli --bin goose)
  fi
  if [[ -x "${rust_bin}" ]]; then
    mkdir -p "${desktop_dir}/src/bin"
    install -m 0755 "${rust_bin}" "${desktop_dir}/src/bin/goose"
  fi
  build_log "Packaging Wolinex Desktop via Electron Forge in ${desktop_dir}..."
  mkdir -p "${desktop_dir}/.electron-cache"
  find "${HOME}/Library/Caches/electron" "${HOME}/.cache/electron" -name 'electron-*.zip' 2>/dev/null \
    -exec cp -n {} "${desktop_dir}/.electron-cache/" \; || true
  if [[ "$(uname -s)" == "Darwin" ]]; then
    local arch_tag app_dir zip_out node_major make_shim=""
    arch_tag="$(darwin_arch_tag)"
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 24)"
    if (( node_major >= 25 )); then
      # Node 26 deadlocks yauzl/extract-zip on larger Electron zip entries; delegate extract-zip to macOS unzip
      make_shim="$(mktemp /tmp/wolinet-extract-shim-XXXXXX.cjs)"
      cat > "${make_shim}" <<'JS'
const Module = require('node:module');
const { execFileSync } = require('node:child_process');
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'extract-zip') {
    return async function (zipPath, opts) {
      execFileSync('/usr/bin/unzip', ['-q', '-o', zipPath, '-d', opts.dir], { stdio: 'inherit' });
    };
  }
  return origLoad.apply(this, arguments);
};
JS
    fi
    (
      cd "${desktop_dir}"
      export ELECTRON_ARCH="${arch_tag}"
      [[ -n "${make_shim}" ]] && export NODE_OPTIONS="--require=${make_shim} ${NODE_OPTIONS:-}"
      pnpm install && pnpm run make
    )
    [[ -n "${make_shim}" ]] && rm -f "${make_shim}"
    app_dir="$(find "${desktop_dir}/out" -maxdepth 2 -name '*.app' -type d | head -n1 || true)"
    if [[ -n "${app_dir}" ]]; then
      zip_out="${CLIENT_OUT_DIR}/Wolinex-darwin-${arch_tag}.zip"
      (cd "$(dirname "${app_dir}")" && ditto -c -k --sequesterRsrc --keepParent "$(basename "${app_dir}")" "${zip_out}")
      write_sha256_sidecar "${zip_out}"
      build_log "Ready: ${zip_out}"
    fi
  else
    (cd "${desktop_dir}" && pnpm install && pnpm run make)
    find "${desktop_dir}/out/make/deb" -name '*.deb' -exec cp -f {} "${CLIENT_OUT_DIR}/" \; 2>/dev/null || true
  fi
}

case "${TARGET}" in
  all)
    if has_component web; then build_web_linux_deb; fi
    if has_component cli; then build_cli_linux_deb; fi
    if [[ "$(uname -s)" == "Darwin" ]]; then
      if has_component web; then build_web_darwin_bundle; fi
      if has_component cli; then build_cli_darwin_bundle; fi
    fi
    if has_component desktop; then build_desktop_bundle; fi
    ;;
  linux)
    if has_component web; then build_web_linux_deb; fi
    if has_component cli; then build_cli_linux_deb; fi
    if has_component desktop; then build_desktop_bundle; fi
    ;;
  darwin)
    [[ "$(uname -s)" == "Darwin" ]] || build_die "macOS builds must run on Darwin"
    if has_component web; then build_web_darwin_bundle; fi
    if has_component cli; then build_cli_darwin_bundle; fi
    if has_component desktop; then build_desktop_bundle; fi
    ;;
  *) build_die "Unsupported target: ${TARGET} (expected: all|linux|darwin)" ;;
esac
