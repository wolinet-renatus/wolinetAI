#!/usr/bin/env bash
# Build standalone Stage 1 DEC Orchestrator installers (Linux .deb + macOS tarball).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../lib/build_common.sh
source "${ROOT_DIR}/packaging/lib/build_common.sh"

REBUILD=0
TARGET="all"
ORCH_VERSION="${WOLINET_ORCH_VERSION:-2.0.0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=1; shift ;;
    --target)  TARGET="${2:-all}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: build.sh [--target all|linux|darwin] [--rebuild]
Builds Stage 1 DEC Orchestrator (1apanel + 1panel-agent) into dist/installers/server/orchestrator/.
EOF
      exit 0 ;;
    *) build_die "Unknown option: $1" ;;
  esac
done

OUT_DIR="${ROOT_DIR}/dist/installers/server/orchestrator"
mkdir -p "${OUT_DIR}"

stage_common_assets() {
  local pkg_root="$1"
  mkdir -p "${pkg_root}/bin" "${pkg_root}/scripts" "${pkg_root}/schema" "${pkg_root}/etc" "${pkg_root}/models/registrations"
  cp -f "${ROOT_DIR}/packaging/orchestrator/wolinet-orchestrator" "${pkg_root}/bin/wolinet-orchestrator"
  cp -f "${ROOT_DIR}/packaging/orchestrator/wolinet-migrate-seed" "${pkg_root}/bin/wolinet-migrate-seed"
  chmod 0755 "${pkg_root}/bin/wolinet-orchestrator" "${pkg_root}/bin/wolinet-migrate-seed"
  if [[ -f "${ROOT_DIR}/scripts/db/init-postgres.sh" ]]; then
    cp -f "${ROOT_DIR}/scripts/db/init-postgres.sh" "${pkg_root}/scripts/init-postgres.sh"
    chmod 0755 "${pkg_root}/scripts/init-postgres.sh"
  fi
  if [[ -d "${ROOT_DIR}/packaging/orchestrator/schema" ]]; then
    cp -f "${ROOT_DIR}/packaging/orchestrator/schema/"*.sql "${pkg_root}/schema/" 2>/dev/null || true
  fi
  if [[ -d "${ROOT_DIR}/inference/models/registrations" ]]; then
    cp -f "${ROOT_DIR}/inference/models/registrations/"*.json "${pkg_root}/models/registrations/" 2>/dev/null || true
  fi
  if [[ -f "${ROOT_DIR}/gateway/config.yaml" ]]; then
    python3 - "${ROOT_DIR}/gateway/config.yaml" "${pkg_root}/etc/config.yaml.example" <<'PY'
import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
text = text.replace("http://host.docker.internal:", "http://127.0.0.1:")
text = re.sub(r'(api_key:\s*)"sk-[^"]+"', r'\1"os.environ/XINFERENCE_API_KEY"', text)
text = re.sub(r'(api_key:\s*)"AQ\.[^"]+"', r'\1"os.environ/GEMINI_API_KEY"', text)
text = re.sub(r'(master_key:\s*)"[^"]+"', r'\1"os.environ/LITELLM_MASTER_KEY"', text)
pathlib.Path(sys.argv[2]).write_text(text, encoding="utf-8")
PY
  fi
}

build_linux_deb() {
  local deb_out="${OUT_DIR}/wolinet-orchestrator_amd64.deb"
  if [[ "${REBUILD}" == "0" && -f "${deb_out}" ]]; then
    build_log "Reusing existing ${deb_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${deb_out}"
    return 0
  fi

  command -v go >/dev/null 2>&1 || build_die "Go toolchain is required to cross-compile 1apanel Linux binaries"
  local container_cli stage pkg_root
  container_cli="$(ensure_container_cli)"
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN

  pkg_root="${stage}/pkg/opt/wolinet/orchestrator"
  mkdir -p \
    "${stage}/pkg/DEBIAN" \
    "${stage}/pkg/usr/bin" \
    "${stage}/pkg/lib/systemd/system" \
    "${stage}/pkg/etc/wolinet" \
    "${stage}/pkg/etc/security/limits.d" \
    "${stage}/pkg/etc/sysctl.d"

  build_log "Cross-compiling Stage 1 1apanel & 1panel-agent for linux/amd64..."
  (cd "${ROOT_DIR}/orchestrator/1apanel/core" && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags '-s -w' -o "${pkg_root}/bin/1apanel" ./cmd/server/main.go)
  (cd "${ROOT_DIR}/orchestrator/1apanel/agent" && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags '-s -w' -o "${pkg_root}/bin/1panel-agent" ./cmd/server/main.go)
  chmod 0755 "${pkg_root}/bin/1apanel" "${pkg_root}/bin/1panel-agent"

  stage_common_assets "${pkg_root}"
  ln -sf /opt/wolinet/orchestrator/bin/wolinet-orchestrator "${stage}/pkg/usr/bin/wolinet-orchestrator"
  ln -sf /opt/wolinet/orchestrator/bin/wolinet-migrate-seed "${stage}/pkg/usr/bin/wolinet-migrate-seed"
  ln -sf /opt/wolinet/orchestrator/bin/1apanel "${stage}/pkg/usr/bin/1apanel"
  ln -sf /opt/wolinet/orchestrator/bin/1panel-agent "${stage}/pkg/usr/bin/1panel-agent"

  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/1apanel.service" "${stage}/pkg/lib/systemd/system/1apanel.service"
  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/1panel-agent.service" "${stage}/pkg/lib/systemd/system/1panel-agent.service"
  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/env.example" "${stage}/pkg/etc/wolinet/1apanel.env.example"
  chmod 0600 "${stage}/pkg/etc/wolinet/1apanel.env.example"

  printf '* soft memlock unlimited\n* hard memlock unlimited\n* soft nofile 65535\n* hard nofile 65535\n' > "${stage}/pkg/etc/security/limits.d/99-wolinet.conf"
  printf 'vm.max_map_count=262144\nfs.file-max=2097152\n' > "${stage}/pkg/etc/sysctl.d/99-wolinet.conf"

  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/debian/postinst" "${stage}/pkg/DEBIAN/postinst"
  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/debian/prerm" "${stage}/pkg/DEBIAN/prerm"
  chmod 0755 "${stage}/pkg/DEBIAN/postinst" "${stage}/pkg/DEBIAN/prerm"

  local installed_kb
  installed_kb="$(du -sk "${stage}/pkg/opt" | awk '{print $1}')"
  cat > "${stage}/pkg/DEBIAN/control" <<EOF
Package: wolinet-orchestrator
Version: ${ORCH_VERSION}-1
Section: admin
Priority: optional
Architecture: amd64
Installed-Size: ${installed_kb}
Depends: ca-certificates
Recommends: podman, curl
Maintainer: Wolinet AI <engineering@wolinet.com>
Description: Wolinet Stage 1 DEC Orchestrator (1apanel & 1panel-agent)
 Sovereign single-binary infrastructure supervisor, native SQLite state store, and Podman orchestrator.
EOF
  printf '/etc/wolinet/1apanel.env.example\n' > "${stage}/pkg/DEBIAN/conffiles"

  build_log "Packaging wolinet-orchestrator_${ORCH_VERSION}_amd64.deb via ubuntu:24.04 (${container_cli})..."
  "${container_cli}" run --rm --platform linux/amd64 \
    -v "${stage}:/work" \
    docker.io/library/ubuntu:24.04 \
    dpkg-deb --root-owner-group --build /work/pkg /work/wolinet-orchestrator_amd64.deb

  cp -f "${stage}/wolinet-orchestrator_amd64.deb" "${deb_out}"
  write_sha256_sidecar "${deb_out}"
  build_log "Ready: ${deb_out}"
}

build_darwin_bundle() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    build_log "Skipping macOS Orchestrator bundle build on $(uname -s)"
    return 0
  fi

  local arch_tag goarch tar_out
  arch_tag="$(darwin_arch_tag)"
  case "${arch_tag}" in
    x64)   goarch="amd64" ;;
    arm64) goarch="arm64" ;;
    *)     build_die "Unsupported arch tag: ${arch_tag}" ;;
  esac

  tar_out="${OUT_DIR}/orchestrator-darwin-${arch_tag}.tar.gz"
  if [[ "${REBUILD}" == "0" && -f "${tar_out}" ]]; then
    build_log "Reusing existing ${tar_out} (pass --rebuild to rebuild)"
    write_sha256_sidecar "${tar_out}"
    return 0
  fi

  local stage pkg_dir
  stage="$(mktemp -d)"
  trap 'rm -rf "${stage:-}"' RETURN
  pkg_dir="${stage}/wolinet-orchestrator-${ORCH_VERSION}-darwin-${arch_tag}"
  mkdir -p "${pkg_dir}/bin" "${pkg_dir}/etc"

  if command -v go >/dev/null 2>&1; then
    build_log "Compiling Stage 1 1apanel & 1panel-agent for darwin/${goarch}..."
    (cd "${ROOT_DIR}/orchestrator/1apanel/core" && CGO_ENABLED=0 GOOS=darwin GOARCH="${goarch}" go build -trimpath -ldflags '-s -w' -o "${pkg_dir}/bin/1apanel" ./cmd/server/main.go)
    (cd "${ROOT_DIR}/orchestrator/1apanel/agent" && CGO_ENABLED=0 GOOS=darwin GOARCH="${goarch}" go build -trimpath -ldflags '-s -w' -o "${pkg_dir}/bin/1panel-agent" ./cmd/server/main.go)
  elif [[ -x "${ROOT_DIR}/bin/1apanel" && -x "${ROOT_DIR}/bin/1panel-agent" ]]; then
    build_log "Copying prebuilt macOS 1apanel & 1panel-agent binaries from bin/..."
    cp -f "${ROOT_DIR}/bin/1apanel" "${pkg_dir}/bin/1apanel"
    cp -f "${ROOT_DIR}/bin/1panel-agent" "${pkg_dir}/bin/1panel-agent"
  else
    build_die "Neither go toolchain nor prebuilt bin/1apanel binaries found"
  fi
  chmod 0755 "${pkg_dir}/bin/1apanel" "${pkg_dir}/bin/1panel-agent"

  stage_common_assets "${pkg_dir}"
  cp -f "${ROOT_DIR}/packaging/orchestrator/deploy/env.example" "${pkg_dir}/etc/1apanel.env.example"

  tar -C "${stage}" -czf "${tar_out}" "wolinet-orchestrator-${ORCH_VERSION}-darwin-${arch_tag}"
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
