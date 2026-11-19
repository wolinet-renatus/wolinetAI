#!/usr/bin/env bash
# Shared terminal installer helpers for Wolinet AI products (lango, mitambo, wolinex).

if [[ -n "${_WOLINET_INSTALLER_COMMON_LOADED:-}" ]]; then
  return 0
fi
_WOLINET_INSTALLER_COMMON_LOADED=1

if [[ -t 1 ]]; then
  _CLR_BOLD='\033[1m'
  _CLR_BLUE='\033[0;34m'
  _CLR_GREEN='\033[0;32m'
  _CLR_YELLOW='\033[0;33m'
  _CLR_RED='\033[0;31m'
  _CLR_DIM='\033[2m'
  _CLR_RESET='\033[0m'
else
  _CLR_BOLD='' _CLR_BLUE='' _CLR_GREEN='' _CLR_YELLOW='' _CLR_RED='' _CLR_DIM='' _CLR_RESET=''
fi

log_header() {
  printf "\n${_CLR_BOLD}${_CLR_BLUE}==> %s${_CLR_RESET}\n" "$*"
}

log_info() {
  printf "${_CLR_DIM}  [info]${_CLR_RESET} %s\n" "$*"
}

log_ok() {
  printf "${_CLR_GREEN}  [ok]${_CLR_RESET} %s\n" "$*"
}

log_warn() {
  printf "${_CLR_YELLOW}  [warn]${_CLR_RESET} %s\n" "$*" >&2
}

log_err() {
  printf "${_CLR_RED}  [error]${_CLR_RESET} %s\n" "$*" >&2
}

die() {
  log_err "$*"
  exit 1
}

detect_platform() {
  local raw_os raw_arch
  raw_os="$(uname -s)"
  raw_arch="$(uname -m)"

  case "${raw_os}" in
    Linux)  HOST_OS="linux" ;;
    Darwin) HOST_OS="darwin" ;;
    *)      die "Unsupported operating system: ${raw_os} (supported: Linux, macOS)" ;;
  esac

  case "${raw_arch}" in
    x86_64|amd64)   HOST_ARCH="amd64"; DARWIN_ARCH="x64" ;;
    aarch64|arm64)  HOST_ARCH="arm64"; DARWIN_ARCH="arm64" ;;
    *)              die "Unsupported CPU architecture: ${raw_arch}" ;;
  esac

  HOST_DISTRO="unknown"
  if [[ "${HOST_OS}" == "linux" && -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    HOST_DISTRO="$(. /etc/os-release && printf '%s' "${ID:-unknown}")"
  fi
}

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "Root privileges required for: $* (re-run with sudo or pass --prefix for user install)"
  fi
}

generate_secret() {
  local prefix="${1:-sk-}"
  local hex=""
  if command -v openssl >/dev/null 2>&1; then
    hex="$(openssl rand -hex 24)"
  elif command -v python3 >/dev/null 2>&1; then
    hex="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
  else
    hex="$(LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 48)"
  fi
  printf '%s%s\n' "${prefix}" "${hex}"
}

sha256_verify() {
  local file_path="$1"
  local sha_file="${file_path}.sha256"
  if [[ ! -f "${sha_file}" ]]; then
    log_warn "No checksum file at ${sha_file}; skipping SHA-256 verification"
    return 0
  fi

  local expected actual
  expected="$(awk '{print $1}' "${sha_file}" | head -n1)"
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "${file_path}" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "${file_path}" | awk '{print $1}')"
  else
    log_warn "Neither sha256sum nor shasum found; skipping checksum verification"
    return 0
  fi

  if [[ "${expected}" != "${actual}" ]]; then
    die "SHA-256 mismatch for ${file_path} (expected ${expected}, got ${actual})"
  fi
  log_ok "Verified SHA-256 checksum for $(basename "${file_path}")"
}

upsert_env_var() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  local formatted_value tmp_file

  if [[ "${value}" =~ ^\".*\"$ ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi

  if [[ "${value}" == *$'\n'* || "${value}" =~ [[:space:]\;\&\|\$\`\<\>\(\)] ]]; then
    formatted_value="\"${value//\"/\\\"}\""
  else
    formatted_value="${value}"
  fi

  tmp_file="$(mktemp)"
  awk -v k="${key}" -v v="${formatted_value}" '
    BEGIN { found = 0 }
    $0 ~ ("^[# ]*" k "=") {
      if (!found) {
        print k "=" v
        found = 1
      }
      next
    }
    { print }
    END {
      if (!found) {
        print k "=" v
      }
    }
  ' "${env_file}" > "${tmp_file}"

  cat "${tmp_file}" > "${env_file}"
  rm -f "${tmp_file}"
}

get_env_var() {
  local env_file="$1"
  local key="$2"
  if [[ ! -f "${env_file}" ]]; then
    return 0
  fi
  local raw
  raw="$(awk -F= -v k="${key}" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "${env_file}")"
  if [[ "${raw}" =~ ^\".*\"$ || "${raw}" =~ ^\'.*\'$ ]]; then
    raw="${raw:1:${#raw}-2}"
  fi
  printf '%s\n' "${raw}"
}

resolve_product_artifact() {
  local product="$1"
  local filename="$2"
  local explicit_path="${3:-}"
  local auto_build="${4:-0}"
  local release_base="${WOLINET_RELEASE_BASE_URL:-}"
  local repo_root="$5"

  if [[ -n "${explicit_path}" ]]; then
    [[ -f "${explicit_path}" ]] || die "Artifact not found: ${explicit_path}"
    printf '%s\n' "${explicit_path}"
    return 0
  fi

  local candidate
  for candidate in \
    "${repo_root}/dist/installers/server/${product}/${filename}" \
    "${repo_root}/dist/downloads/desktop/${filename}" \
    "${repo_root}/gateway/dist/${filename}"
  do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  if [[ "${auto_build}" == "1" ]]; then
    local builder="${repo_root}/packaging/${product}/build.sh"
    [[ -x "${builder}" ]] || die "Builder script not found: ${builder}"
    log_info "Artifact ${filename} missing locally; running ${builder}..." >&2
    "${builder}" >&2
    for candidate in \
      "${repo_root}/dist/installers/server/${product}/${filename}" \
      "${repo_root}/dist/downloads/desktop/${filename}"; do
      if [[ -f "${candidate}" ]]; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    done
    die "Build completed but ${filename} was not produced under dist/"
  fi

  if [[ -n "${release_base}" ]]; then
    local dl_dir url target
    dl_dir="$(mktemp -d)"
    target="${dl_dir}/${filename}"
    url="${release_base%/}/${product}/${filename}"
    log_info "Downloading ${url}..." >&2
    curl -fsSL -o "${target}" "${url}" || die "Failed to download ${url}"
    curl -fsSL -o "${target}.sha256" "${url}.sha256" 2>/dev/null || true
    printf '%s\n' "${target}"
    return 0
  fi

  die "Artifact ${filename} not found under dist/installers/${product}/. Pass --build to build locally or --artifact <path>."
}

has_systemd() {
  [[ "${HOST_OS:-}" == "linux" && -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1
}

detect_host_resources() {
  local cpus=4 mem_mb=8192 accel="cpu"
  if [[ "${HOST_OS:-}" == "darwin" ]]; then
    cpus="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
    local bytes
    bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 8589934592)"
    mem_mb="$((bytes / 1048576))"
    [[ "${HOST_ARCH:-}" == "arm64" ]] && accel="mps"
  else
    cpus="$(nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo 4)"
    if [[ -r /proc/meminfo ]]; then
      local kb
      kb="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo 2>/dev/null || echo 8388608)"
      mem_mb="$((kb / 1024))"
    fi
    command -v nvidia-smi >/dev/null 2>&1 && accel="cuda"
  fi
  (( cpus < 1 )) && cpus=2
  (( mem_mb < 1024 )) && mem_mb=2048

  HOST_CPUS="${cpus}"
  HOST_MEM_MB="${mem_mb}"
  HOST_ACCEL="${accel}"

  clamp_int() {
    local val="$1" lo="$2" hi="$3"
    (( val < lo )) && val="${lo}"
    (( val > hi )) && val="${hi}"
    printf '%s\n' "${val}"
  }

  # Stage 1: Orchestrator + Postgres + Redis
  ORCH_GOMAXPROCS="$(clamp_int "$((cpus / 4))" 2 8)"
  ORCH_MEM_HIGH_MB="$(clamp_int "$((mem_mb * 5 / 100))" 512 1536)"
  ORCH_MEM_MAX_MB="$(clamp_int "$((mem_mb * 10 / 100))" 1024 3072)"
  PG_MEM_MB="$(clamp_int "$((mem_mb * 15 / 100))" 512 4096)"
  PG_SHM_MB="$(clamp_int "$((PG_MEM_MB / 4))" 256 1024)"
  PG_SHARED_BUFFERS_MB="$(clamp_int "$((PG_MEM_MB / 4))" 128 1024)"
  REDIS_MEM_MB="$(clamp_int "$((mem_mb * 5 / 100))" 256 1024)"
  REDIS_MAXMEM_MB="$((REDIS_MEM_MB * 80 / 100))"

  # Stage 2: Mitambo Inference Core (largest RAM budget + memlock)
  MITAMBO_THREADS="$(clamp_int "$((cpus - 2))" 2 16)"
  MITAMBO_MEM_LOW_MB="$(clamp_int "$((mem_mb * 20 / 100))" 1024 8192)"
  MITAMBO_MEM_HIGH_MB="$(clamp_int "$((mem_mb * 50 / 100))" 2048 32768)"
  MITAMBO_MEM_MAX_MB="$(clamp_int "$((mem_mb * 65 / 100))" 3072 49152)"

  # Stage 3: Lango Gateway (high CPU scheduling weight, lean Rust footprint)
  LANGO_TOKIO_THREADS="$(clamp_int "${cpus}" 2 8)"
  LANGO_MEM_LOW_MB=256
  LANGO_MEM_HIGH_MB="$(clamp_int "$((mem_mb * 8 / 100))" 512 2048)"
  LANGO_MEM_MAX_MB="$(clamp_int "$((mem_mb * 15 / 100))" 1024 4096)"

  # Stage 4: Wolinex Web Portal
  WEB_MEM_LOW_MB=512
  WEB_MEM_HIGH_MB="$(clamp_int "$((mem_mb * 12 / 100))" 1024 3072)"
  WEB_MEM_MAX_MB="$(clamp_int "$((mem_mb * 22 / 100))" 2048 6144)"
  WEB_WORKERS_REDIS="$(clamp_int "$((cpus / 4))" 2 4)"

  export HOST_CPUS HOST_MEM_MB HOST_ACCEL \
    ORCH_GOMAXPROCS ORCH_MEM_HIGH_MB ORCH_MEM_MAX_MB \
    PG_MEM_MB PG_SHM_MB PG_SHARED_BUFFERS_MB REDIS_MEM_MB REDIS_MAXMEM_MB \
    MITAMBO_THREADS MITAMBO_MEM_LOW_MB MITAMBO_MEM_HIGH_MB MITAMBO_MEM_MAX_MB \
    LANGO_TOKIO_THREADS LANGO_MEM_LOW_MB LANGO_MEM_HIGH_MB LANGO_MEM_MAX_MB \
    WEB_MEM_LOW_MB WEB_MEM_HIGH_MB WEB_MEM_MAX_MB WEB_WORKERS_REDIS
}

write_systemd_stage_override() {
  local service_name="$1"
  local after_units="$2"
  local mem_low_mb="$3"
  local mem_high_mb="$4"
  local mem_max_mb="$5"
  local cpu_weight="$6"
  local extra_service_lines="${7:-}"

  local dropin_dir="/etc/systemd/system/${service_name}.service.d"
  run_root install -d -m 0755 "${dropin_dir}"
  {
    printf '[Unit]\n'
    printf 'After=%s\n\n' "${after_units}"
    printf '[Service]\n'
    [[ -n "${mem_low_mb}" && "${mem_low_mb}" != "0" ]] && printf 'MemoryLow=%sM\n' "${mem_low_mb}"
    [[ -n "${mem_high_mb}" && "${mem_high_mb}" != "0" ]] && printf 'MemoryHigh=%sM\n' "${mem_high_mb}"
    [[ -n "${mem_max_mb}" && "${mem_max_mb}" != "0" ]] && printf 'MemoryMax=%sM\n' "${mem_max_mb}"
    [[ -n "${cpu_weight}" && "${cpu_weight}" != "0" ]] && printf 'CPUWeight=%s\n' "${cpu_weight}"
    printf 'LimitNOFILE=65535\n'
    if [[ -n "${extra_service_lines}" ]]; then
      printf '%s\n' "${extra_service_lines}"
    fi
  } | run_root tee "${dropin_dir}/wolinet-stage.conf" >/dev/null
}

install_deb_file() {
  local deb_path="$1"
  if run_root dpkg -i "${deb_path}"; then
    return 0
  fi
  log_info "Resolving missing Debian dependencies via apt..."
  run_root env DEBIAN_FRONTEND=noninteractive apt-get update -o Acquire::Retries=4 -o Acquire::ForceIPv4=true -qq
  run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -o Acquire::Retries=4 -o Acquire::ForceIPv4=true --fix-missing -f
  run_root dpkg -i "${deb_path}"
}

wait_http_ok() {
  local url="$1"
  local timeout_secs="${2:-30}"
  local i
  for ((i = 1; i <= timeout_secs; i++)); do
    if curl -fsS --max-time 2 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

write_launchagent_plist() {
  local label="$1"
  local bin_path="$2"
  local log_dir="$3"
  local env_file="$4"
  shift 4
  local extra_args=("$@")

  local plist_dir="${HOME}/Library/LaunchAgents"
  local plist_path="${plist_dir}/${label}.plist"
  mkdir -p "${plist_dir}" "${log_dir}"

  {
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>set -a; [ -f '${env_file}' ] && source '${env_file}'; set +a; exec '${bin_path}' ${extra_args[*]:-}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log_dir}/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${log_dir}/stderr.log</string>
</dict>
</plist>
EOF
  } > "${plist_path}"
  printf '%s\n' "${plist_path}"
}

start_launchagent() {
  local label="$1"
  local plist_path="$2"
  local domain="gui/$(id -u)"
  launchctl bootout "${domain}/${label}" >/dev/null 2>&1 || true
  launchctl bootstrap "${domain}" "${plist_path}"
  launchctl kickstart -k "${domain}/${label}" >/dev/null 2>&1 || true
}

stop_launchagent() {
  local label="$1"
  local plist_path="${HOME}/Library/LaunchAgents/${label}.plist"
  local domain="gui/$(id -u)"
  launchctl bootout "${domain}/${label}" >/dev/null 2>&1 || true
  rm -f "${plist_path}"
}
