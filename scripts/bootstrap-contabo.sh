#!/usr/bin/env bash
# Single-command automatic bootstrap for Contabo Ubuntu 24.04 servers:
# 1. Installs Ubuntu 24.04 OS prerequisites, Podman registry config, and Go 1.26.6 (SHA-256 verified)
# 2. Clones or updates WolinetAI from Git main into /opt/wolinetai
# 3. Builds the 4 Linux amd64 .deb installers (Stages 1 -> 4)
# 4. Runs install-server-stack.sh --with-datastore (auto-secrets, DB migration & seeding, resource tuning)
# 5. Configures Cloudflare Origin TLS, Host Nginx (*.wolinet.com), UFW, systemd-resolved, and optional DNS
# 6. Verifies all 4 loopback & Nginx HTTPS endpoints
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E bash "$0" "$@"
  fi
  echo "[bootstrap:error] Must run as root or via sudo" >&2
  exit 1
fi

REPO_URL="${WOLINET_REPO_URL:-https://github.com/wolinet-renatus/wolinetAI.git}"
REPO_BRANCH="${WOLINET_REPO_BRANCH:-main}"
REPO_DIR="${WOLINET_REPO_DIR:-/opt/wolinetai}"
DOMAIN="${WOLINET_DOMAIN:-wolinet.com}"
ORIGIN_CERT="${CLOUDFLARE_ORIGIN_CERT:-}"
ORIGIN_KEY="${CLOUDFLARE_ORIGIN_KEY:-}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
ALLOW_DIRECT_HTTP="${ALLOW_DIRECT_HTTP:-0}"
EXTRA_PORTS="${EXTRA_OPEN_PORTS:-}"
GO_VERSION="1.26.6"
SKIP_BUILD=0

usage() {
  cat <<'EOF'
Wolinet AI Contabo Ubuntu 24.04 Zero-Config Bootstrap

Usage:
  git clone --branch main --depth 1 https://github.com/wolinet-renatus/wolinetAI.git /opt/wolinetai
  sudo bash /opt/wolinetai/scripts/bootstrap-contabo.sh --domain wolinet.com

  # Or pass Cloudflare credentials to auto-upsert *.wolinet.com DNS records:
  sudo CLOUDFLARE_API_TOKEN="..." bash /opt/wolinetai/scripts/bootstrap-contabo.sh --domain wolinet.com

Options:
  --domain <domain>            Root Cloudflare domain (default: wolinet.com)
  --repo-url <git-url>         Git repository URL
  --branch <branch>            Git branch to deploy (default: main)
  --repo-dir <dir>             Target clone directory (default: /opt/wolinetai)
  --origin-cert <path>         Cloudflare Origin CA PEM cert path on server
  --origin-key <path>          Cloudflare Origin CA key path on server
  --cloudflare-token <token>   Cloudflare API token for automatic proxied A record upsert
  --allow-direct-http          Allow ports 80/443 from any IP (instead of Cloudflare CIDRs only)
  --extra-open-ports <list>    Comma-separated extra ufw ports (e.g. "9000/tcp,9001/udp")
  --skip-build                 Reuse existing .deb artifacts if already present in dist/
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)             DOMAIN="${2:-wolinet.com}"; shift 2 ;;
    --repo-url)           REPO_URL="${2:-}"; shift 2 ;;
    --branch)             REPO_BRANCH="${2:-main}"; shift 2 ;;
    --repo-dir)           REPO_DIR="${2:-/opt/wolinetai}"; shift 2 ;;
    --origin-cert)        ORIGIN_CERT="${2:-}"; shift 2 ;;
    --origin-key)         ORIGIN_KEY="${2:-}"; shift 2 ;;
    --cloudflare-token)   CF_TOKEN="${2:-}"; shift 2 ;;
    --allow-direct-http)  ALLOW_DIRECT_HTTP=1; shift ;;
    --extra-open-ports)   EXTRA_PORTS="${2:-}"; shift 2 ;;
    --skip-build)         SKIP_BUILD=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *)                    echo "[bootstrap:error] Unknown option: $1" >&2; exit 1 ;;
  esac
done

log()  { printf '[bootstrap] %s\n' "$*"; }
warn() { printf '[bootstrap:warn] %s\n' "$*" >&2; }
die()  { printf '[bootstrap:error] %s\n' "$*" >&2; exit 1; }

ARCH="$(uname -m)"
[[ "${ARCH}" == "x86_64" || "${ARCH}" == "amd64" ]] || die "Expected x86_64/amd64 Ubuntu server; got ${ARCH}"

wait_for_apt() {
  local tries=0
  while fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock /var/cache/apt/archives/lock >/dev/null 2>&1; do
    tries=$((tries + 1))
    [[ "${tries}" -lt 60 ]] || die "Timed out waiting for apt/dpkg lock"
    sleep 2
  done
}

log "1/6 Installing Ubuntu 24.04 system prerequisites..."
export DEBIAN_FRONTEND=noninteractive
wait_for_apt
apt-get update -qq
wait_for_apt
apt-get install -y -qq \
  git curl ca-certificates openssl gnupg \
  podman uidmap slirp4netns \
  nginx ufw postgresql-client \
  make python3 tar xz-utils jq >/dev/null

install_go_toolchain() {
  local current_ver=""
  if command -v go >/dev/null 2>&1; then
    current_ver="$(go version | awk '{print $3}' | sed 's/^go//')"
  fi
  if [[ -n "${current_ver}" ]] && python3 -c "import sys; v=lambda s: tuple(int(x) for x in s.split('.')[:3]); sys.exit(0 if v('${current_ver}') >= v('${GO_VERSION}') else 1)" 2>/dev/null; then
    log "Using existing Go ${current_ver}"
    return 0
  fi

  log "Installing Go ${GO_VERSION} for linux/amd64..."
  local tmp_dir tarball sha_file expected_sha
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir:-}"' RETURN
  tarball="${tmp_dir}/go${GO_VERSION}.linux-amd64.tar.gz"
  sha_file="${tarball}.sha256"

  curl -fsSL -o "${tarball}" "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
  curl -fsSL -o "${sha_file}" "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz.sha256"
  expected_sha="$(tr -d '[:space:]' < "${sha_file}")"
  printf '%s  %s\n' "${expected_sha}" "${tarball}" | sha256sum -c -

  rm -rf /usr/local/go
  tar -C /usr/local -xzf "${tarball}"
  ln -sf /usr/local/go/bin/go /usr/local/bin/go
  ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
}

install_go_toolchain
export PATH="/usr/local/go/bin:${PATH}"

configure_podman_registries() {
  install -d -m 0755 /etc/containers/registries.conf.d
  cat > /etc/containers/registries.conf.d/99-wolinet-dockerhub.conf <<'EOF'
unqualified-search-registries = ["docker.io"]
short-name-mode = "permissive"
EOF
}

configure_podman_registries

log "2/6 Syncing WolinetAI repository (${REPO_BRANCH}) into ${REPO_DIR}..."
if [[ -d "${REPO_DIR}/.git" ]]; then
  git -C "${REPO_DIR}" fetch --depth 1 origin "${REPO_BRANCH}"
  git -C "${REPO_DIR}" checkout -f -B "${REPO_BRANCH}" "origin/${REPO_BRANCH}"
else
  mkdir -p "$(dirname "${REPO_DIR}")"
  git clone --branch "${REPO_BRANCH}" --depth 1 "${REPO_URL}" "${REPO_DIR}"
fi
cd "${REPO_DIR}"

if [[ "${SKIP_BUILD}" == "0" ]]; then
  log "3/6 Building 4-stage Linux amd64 .deb installers (Orchestrator, Mitambo, Lango, Wolinex Web)..."
  ./packaging/orchestrator/build.sh --target linux --rebuild
  ./packaging/mitambo/build.sh --target linux --rebuild
  ./packaging/lango/build.sh --target linux --rebuild
  ./packaging/wolinex/build.sh --components web --target linux --rebuild
else
  log "3/6 Skipping package rebuild (--skip-build)"
fi

log "4/6 Installing 4-stage stack, Podman Postgres/Redis, resource tuning & DB seeding..."
bash "${REPO_DIR}/scripts/install-server-stack.sh" --with-datastore

log "5/6 Configuring Host Nginx, TLS, UFW, systemd-resolved & Cloudflare edge..."
EDGE_ARGS=(--domain "${DOMAIN}")
[[ -n "${ORIGIN_CERT}" && -n "${ORIGIN_KEY}" ]] && EDGE_ARGS+=(--origin-cert "${ORIGIN_CERT}" --origin-key "${ORIGIN_KEY}")
[[ "${ALLOW_DIRECT_HTTP}" == "1" ]] && EDGE_ARGS+=(--allow-direct-http)
[[ -n "${EXTRA_PORTS}" ]] && EDGE_ARGS+=(--extra-open-ports "${EXTRA_PORTS}")

CLOUDFLARE_API_TOKEN="${CF_TOKEN}" bash "${REPO_DIR}/scripts/setup-contabo-edge.sh" "${EDGE_ARGS[@]}"

log "6/6 Verifying deployed services on loopback and Nginx HTTPS..."
check_local() {
  local name="$1" url="$2" host_hdr="${3:-}"
  local rc=1
  if [[ -n "${host_hdr}" ]]; then
    curl -fsSk --max-time 10 -H "Host: ${host_hdr}" "${url}" >/dev/null 2>&1 && rc=0
  else
    curl -fsS --max-time 10 "${url}" >/dev/null 2>&1 && rc=0
  fi
  if [[ "${rc}" == "0" ]]; then
    printf '  [OK] %-14s -> %s\n' "${name}" "${url}"
  else
    printf '  [WARN] %-12s -> %s (still warming up; inspect journalctl)\n' "${name}" "${url}"
  fi
}

check_local "1apanel" "http://127.0.0.1:8888/"
check_local "mitambo" "http://127.0.0.1:9997/status"
check_local "lango" "http://127.0.0.1:4000/health/liveliness"
check_local "wolinex-web" "http://127.0.0.1:8081/health"
check_local "nginx-panel" "https://127.0.0.1/" "panel.${DOMAIN}"
check_local "nginx-mitambo" "https://127.0.0.1/status" "mitambo.${DOMAIN}"
check_local "nginx-lango-ui" "https://127.0.0.1/ui/" "lango.${DOMAIN}"
check_local "nginx-wolinex" "https://127.0.0.1/health" "wolinex.${DOMAIN}"
nginx -t >/dev/null && printf '  [OK] %-14s -> nginx -t passed\n' "nginx"

ORCH_USER="$(awk -F= '/^ORIGINAL_USERNAME=/{print $2; exit}' /etc/wolinet/1apanel.env 2>/dev/null || echo admin)"
ORCH_PASS="$(awk -F= '/^ORIGINAL_PASSWORD=/{print $2; exit}' /etc/wolinet/1apanel.env 2>/dev/null || echo '')"
MASTER_KEY="$(awk -F= '/^LITELLM_MASTER_KEY=/{print $2; exit}' /etc/litellm/env 2>/dev/null || echo '')"

cat <<EOF

========================================================================
Wolinet AI Contabo Deployment Complete
========================================================================
Admin GUIs & Endpoints:
  1apanel Admin GUI   : https://panel.${DOMAIN}
  Mitambo Admin GUI   : https://mitambo.${DOMAIN}
  Lango Admin UI/API  : https://lango.${DOMAIN}/ui  &  https://lango.${DOMAIN}/v1
  Wolinex Web Portal  : https://wolinex.${DOMAIN}

Auto-Generated Credentials (stored on server with 0600/0640 permissions):
  1apanel & Mitambo Admin User : ${ORCH_USER}
  Env files                    : /etc/wolinet/1apanel.env
                                 /etc/wolinet/mitambo.env
                                 /etc/litellm/env
                                 /etc/wolinet/wolinex-web.env
  Credentials status           : 1apanel=${ORCH_PASS:+configured} LangoMasterKey=${MASTER_KEY:+configured}

Inspect generated keys locally on the server when needed:
  sudo grep -E '^(ORIGINAL_|LITELLM_MASTER_KEY|XINFERENCE_)' /etc/wolinet/1apanel.env /etc/wolinet/mitambo.env /etc/litellm/env
========================================================================
EOF
