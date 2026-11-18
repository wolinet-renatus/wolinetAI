#!/usr/bin/env bash
# Build standalone installers for Mitambo Inference Engine (Linux .deb + macOS tarball).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../lib/build_common.sh
source "${ROOT_DIR}/packaging/lib/build_common.sh"

REBUILD=0
TARGET="all"
PYTHON_VERSION="3.12"
UV_VERSION="0.12.19"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=1; shift ;;
    --target)  TARGET="${2:-all}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: build.sh [--target all|linux|darwin] [--rebuild]
Builds self-contained Mitambo binary/runtime installers into dist/installers/mitambo/.
EOF
      exit 0 ;;
    *) build_die "Unknown option: $1" ;;
  esac
done

OUT_DIR="${ROOT_DIR}/dist/installers/server/mitambo"
mkdir -p "${OUT_DIR}"

stage_clean_source() {
  local stage_root="$1"
  mkdir -p "${stage_root}/inference" "${stage_root}/packaging"
  tar -C "${ROOT_DIR}/inference" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.gguf' \
    --exclude='*.safetensors' \
    --exclude='*.bin' \
    --exclude='*.pt' \
    --exclude='*.pth' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/.next' \
    --exclude='frontend/.npm-cache' \
    --exclude='frontend/.npm-logs' \
    --exclude='*.egg-info' \
    -cf - . | tar -C "${stage_root}/inference" -xf -

  cp -R "${ROOT_DIR}/packaging/mitambo" "${stage_root}/packaging/mitambo"
}

read_mitambo_version() {
  python3 - "${ROOT_DIR}/inference/xinference/_version.py" <<'PY'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
if p.exists():
    m = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", p.read_text(encoding="utf-8"))
    if m:
        print(m.group(1))
        sys.exit(0)
print("4.2.0")
PY
}

build_linux_deb() {
  local deb_out="${OUT_DIR}/mitambo-inference_amd64.deb"
  if [[ "${REBUILD}" == "0" && -f "${deb_out}" ]]; then
    build_log "Reusing existing ${deb_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${deb_out}"
    return 0
  fi

  local container_cli version stage
  container_cli="$(ensure_container_cli)"
  version="$(read_mitambo_version)"
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN

  build_log "Staging clean inference source tree for Ubuntu 24.04 .deb build..."
  stage_clean_source "${stage}"

  build_log "Building mitambo-inference_${version}_amd64.deb in ubuntu:24.04 (${container_cli})..."
  "${container_cli}" build --platform linux/amd64 \
    --target builder \
    --build-arg "MITAMBO_VERSION=${version}" \
    --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
    --build-arg "UV_VERSION=${UV_VERSION}" \
    -t mitambo-deb-builder:local \
    -f "${stage}/packaging/mitambo/Dockerfile.deb" \
    "${stage}"

  local cid
  cid="$("${container_cli}" create mitambo-deb-builder:local /bin/true)"
  "${container_cli}" cp "${cid}:/out/mitambo-inference_amd64.deb" "${deb_out}"
  "${container_cli}" rm -f "${cid}" >/dev/null
  write_sha256_sidecar "${deb_out}"
  build_log "Ready: ${deb_out}"
}

build_darwin_bundle() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    build_log "Skipping macOS Mitambo bundle build on $(uname -s)"
    return 0
  fi

  local arch_tag version tar_out
  arch_tag="$(darwin_arch_tag)"
  version="$(read_mitambo_version)"
  tar_out="${OUT_DIR}/mitambo-darwin-${arch_tag}.tar.gz"

  if [[ "${REBUILD}" == "0" && -f "${tar_out}" ]]; then
    build_log "Reusing existing ${tar_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${tar_out}"
    return 0
  fi

  command -v uv >/dev/null 2>&1 || build_die "uv is required on macOS to build standalone Mitambo runtime"

  local stage pkg_dir py_bin
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN
  pkg_dir="${stage}/mitambo-${version}-darwin-${arch_tag}"
  mkdir -p "${pkg_dir}/bin" "${pkg_dir}/etc" "${pkg_dir}/models/registrations"

  build_log "Staging clean inference source for macOS ${arch_tag} bundle..."
  stage_clean_source "${stage}/src"

  build_log "Provisioning standalone relocatable Python ${PYTHON_VERSION}..."
  UV_PYTHON_BIN_DIR="${stage}/pybin" UV_PYTHON_INSTALL_DIR="${pkg_dir}/python" uv python install "${PYTHON_VERSION}"
  py_bin="$(find "${pkg_dir}/python" -path '*/bin/python3' | head -n1)"
  [[ -x "${py_bin}" ]] || build_die "Failed to locate standalone python3 inside ${pkg_dir}/python"

  local extra_pins=()
  if [[ "${arch_tag}" == "x64" ]]; then
    # PyTorch 2.2.2 (last Intel macOS x86_64 wheel) was compiled against NumPy 1.x C ABI
    extra_pins+=("numpy<2")
  fi

  uv venv --relocatable "${pkg_dir}/venv" --python "${py_bin}"
  NO_WEB_UI=1 XINFERENCE_SKIP_MODEL_SPEC_VALIDATION=1 uv pip install \
    --python "${pkg_dir}/venv/bin/python" \
    torch \
    "${extra_pins[@]}" \
    "xoscar>=0.10.0" \
    "psutil>=5.9.0" \
    "pillow" \
    "click<8.2.0" \
    "tqdm>=4.27" \
    "tabulate" \
    "requests" \
    "aiohttp" \
    "pydantic>2" \
    "anyio" \
    "fastapi>=0.110.3,<0.137" \
    "python-multipart>=0.0.18" \
    "orjson" \
    "uvicorn" \
    "PyYAML" \
    "huggingface-hub>=0.19.4" \
    "filelock>=3.30.0" \
    "typing_extensions" \
    "modelscope>=1.21.0" \
    "sse_starlette>=1.6.5" \
    "openai>=1.40.0" \
    "anthropic>=0.25.0" \
    "python-jose[cryptography]" \
    "bcrypt>=4.0.0" \
    "aioprometheus[starlette]>=23.12.0" \
    "httpx" \
    "async-timeout" \
    "setproctitle" \
    "transformers" \
    "peft>=0.18.0" \
    "timm" \
    "packaging>=24.2" \
    "gguf"

  # Install xllamacpp when a binary wheel is available for the host arch
  uv pip install --python "${pkg_dir}/venv/bin/python" --only-binary :all: "xllamacpp>=0.2.0" >/dev/null 2>&1 || true

  NO_WEB_UI=1 XINFERENCE_SKIP_MODEL_SPEC_VALIDATION=1 uv pip install \
    --python "${pkg_dir}/venv/bin/python" \
    --no-build-isolation \
    --no-deps \
    "${stage}/src/inference"

  find "${pkg_dir}" -type d -name '__pycache__' -prune -exec rm -rf {} +

  cp -f "${ROOT_DIR}/packaging/mitambo/mitambo" "${pkg_dir}/bin/mitambo"
  chmod 0755 "${pkg_dir}/bin/mitambo"
  cp -f "${ROOT_DIR}/packaging/mitambo/deploy/env.example" "${pkg_dir}/etc/mitambo.env.example"
  if [[ -d "${ROOT_DIR}/inference/models/registrations" ]]; then
    cp -R "${ROOT_DIR}/inference/models/registrations/." "${pkg_dir}/models/registrations/"
  fi
  if [[ -d "${stage}/src/inference/frontend/out" ]]; then
    cp -R "${stage}/src/inference/frontend/out" "${pkg_dir}/frontend"
  fi

  tar -C "${stage}" -czf "${tar_out}" "mitambo-${version}-darwin-${arch_tag}"
  write_sha256_sidecar "${tar_out}"
  build_log "Ready: ${tar_out}"
}

case "${TARGET}" in
  all)
    build_linux_deb
    build_darwin_bundle
    ;;
  linux)  build_linux_deb ;;
  darwin) build_darwin_bundle ;;
  *)      build_die "Unsupported target: ${TARGET} (expected: all|linux|darwin)" ;;
esac
