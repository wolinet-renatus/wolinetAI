#!/usr/bin/env bash
# Shared packaging helpers for Wolinet AI product builders.

if [[ -n "${_WOLINET_BUILD_COMMON_LOADED:-}" ]]; then
  return 0
fi
_WOLINET_BUILD_COMMON_LOADED=1

build_log() {
  printf '[build] %s\n' "$*"
}

build_warn() {
  printf '[build:warn] %s\n' "$*" >&2
}

build_die() {
  printf '[build:error] %s\n' "$*" >&2
  exit 1
}

ensure_container_cli() {
  if command -v podman >/dev/null 2>&1; then
    printf 'podman\n'
    return 0
  fi
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    printf 'docker\n'
    return 0
  fi
  build_die "Neither podman nor a running docker daemon was found for Linux packaging"
}

write_sha256_sidecar() {
  local file_path="$1"
  local dir_name base_name
  dir_name="$(dirname "${file_path}")"
  base_name="$(basename "${file_path}")"

  (
    cd "${dir_name}"
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum "${base_name}" > "${base_name}.sha256"
    else
      shasum -a 256 "${base_name}" > "${base_name}.sha256"
    fi
  )
}

darwin_arch_tag() {
  case "$(uname -m)" in
    x86_64|amd64)  printf 'x64\n' ;;
    aarch64|arm64) printf 'arm64\n' ;;
    *)             build_die "Unsupported macOS arch: $(uname -m)" ;;
  esac
}
