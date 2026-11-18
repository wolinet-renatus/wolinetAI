#!/usr/bin/env bash
# Deploy Wolinet Sovereign 4-Stage Server Stack (.deb installers + edge Nginx/Cloudflare setup)
# from a developer workstation onto a Contabo Ubuntu 24.04 VPS over SSH.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

SSH_HOST=""
SSH_USER="root"
SSH_PORT="22"
SSH_KEY=""
REMOTE_DIR="/opt/wolinet-release"
DOMAIN="${WOLINET_DOMAIN:-wolinet.com}"
PUBLIC_IP="${WOLINET_PUBLIC_IP:-}"
ORIGIN_CERT="${CLOUDFLARE_ORIGIN_CERT:-}"
ORIGIN_KEY="${CLOUDFLARE_ORIGIN_KEY:-}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
EXTRA_PORTS="${EXTRA_OPEN_PORTS:-}"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-}"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
R2_ENDPOINT="${R2_ENDPOINT:-}"
R2_BACKUP_BUCKET="${R2_BACKUP_BUCKET:-wolinetai}"
R2_STORAGE_BUCKET="${R2_STORAGE_BUCKET:-wolinetai}"
BUILD_FIRST=0
ALLOW_DIRECT_HTTP=0
KEEP_REMOTE_STAGE=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Deploy Wolinet Server Stack to Contabo Ubuntu 24.04 over SSH (Binary-Only, Zero Source on Server)

Usage:
  deploy-contabo-ssh.sh --host <contabo-ip> [options]

Options:
  --host <ip|hostname>         Contabo Ubuntu 24.04 SSH host (required)
  --user <user>                SSH username (default: root)
  --port <port>                SSH port (default: 22)
  --identity <key-path>        Optional SSH private key path (-i)
  --remote-dir <dir>           Temporary remote staging directory (default: /opt/wolinet-release)
  --domain <domain>            Cloudflare root domain (default: wolinet.com)
  --public-ip <ipv4>           Server public IPv4 for Cloudflare DNS (default: SSH host if IPv4)
  --origin-cert <local-pem>    Local Cloudflare Origin CA PEM cert to upload
  --origin-key <local-key>     Local Cloudflare Origin CA key to upload
  --cloudflare-token <token>   Cloudflare API token for Origin CA SSL + proxied DNS
  --extra-open-ports <list>    Extra ufw ports (e.g. "9000/tcp,9001/udp")
  --r2-account-id <id>         Cloudflare R2 Account ID
  --r2-access-key <key>        Cloudflare R2 S3 Access Key ID
  --r2-secret-key <secret>     Cloudflare R2 S3 Secret Access Key
  --r2-endpoint <url>          Cloudflare R2 S3 Endpoint
  --r2-backup-bucket <name>    R2 bucket for snapshots (default: wolinetai)
  --r2-storage-bucket <name>   R2 bucket for Wolinex uploads (default: wolinetai)
  --allow-direct-http          Allow 80/443 from any IP (instead of Cloudflare CIDRs)
  --keep-remote-stage          Preserve temporary staging dir on server after install
  --build                      Rebuild Linux .deb artifacts locally before uploading
  --dry-run                    Stage release bundle and print commands without dialing SSH
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)               SSH_HOST="${2:-}"; shift 2 ;;
    --user)               SSH_USER="${2:-root}"; shift 2 ;;
    --port)               SSH_PORT="${2:-22}"; shift 2 ;;
    --identity)           SSH_KEY="${2:-}"; shift 2 ;;
    --remote-dir)         REMOTE_DIR="${2:-/opt/wolinet-release}"; shift 2 ;;
    --domain)             DOMAIN="${2:-wolinet.com}"; shift 2 ;;
    --public-ip)          PUBLIC_IP="${2:-}"; shift 2 ;;
    --origin-cert)        ORIGIN_CERT="${2:-}"; shift 2 ;;
    --origin-key)         ORIGIN_KEY="${2:-}"; shift 2 ;;
    --cloudflare-token)   CF_TOKEN="${2:-}"; shift 2 ;;
    --extra-open-ports)   EXTRA_PORTS="${2:-}"; shift 2 ;;
    --r2-account-id)      R2_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --r2-access-key)      R2_ACCESS_KEY_ID="${2:-}"; shift 2 ;;
    --r2-secret-key)      R2_SECRET_ACCESS_KEY="${2:-}"; shift 2 ;;
    --r2-endpoint)        R2_ENDPOINT="${2:-}"; shift 2 ;;
    --r2-backup-bucket)   R2_BACKUP_BUCKET="${2:-wolinetai}"; shift 2 ;;
    --r2-storage-bucket)  R2_STORAGE_BUCKET="${2:-wolinetai}"; shift 2 ;;
    --allow-direct-http)  ALLOW_DIRECT_HTTP=1; shift ;;
    --keep-remote-stage)  KEEP_REMOTE_STAGE=1; shift ;;
    --build)              BUILD_FIRST=1; shift ;;
    --dry-run)            DRY_RUN=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *)                    die "Unknown option: $1 (try --help)" ;;
  esac
done

[[ -n "${SSH_HOST}" ]] || { usage >&2; die "--host <contabo-ip> is required"; }

if [[ "${BUILD_FIRST}" == "1" ]]; then
  log_header "Building Linux amd64 server packages locally"
  "${ROOT_DIR}/packaging/orchestrator/build.sh" --target linux --rebuild
  "${ROOT_DIR}/packaging/mitambo/build.sh" --target linux --rebuild
  "${ROOT_DIR}/packaging/lango/build.sh" --target linux --rebuild
  "${ROOT_DIR}/packaging/wolinex/build.sh" --components web --target linux --rebuild
fi

REQUIRED_DEBS=(
  "orchestrator/wolinet-orchestrator_amd64.deb"
  "mitambo/mitambo-inference_amd64.deb"
  "lango/litellm-gateway_amd64.deb"
  "wolinex-web/wolinex-web_amd64.deb"
)
for rel in "${REQUIRED_DEBS[@]}"; do
  [[ -f "${ROOT_DIR}/dist/installers/server/${rel}" ]] || die "Missing Linux package: dist/installers/server/${rel} (pass --build)"
done

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR:-}"' EXIT

log_header "Staging Contabo deployment payload"
mkdir -p \
  "${STAGE_DIR}/dist/installers/server/orchestrator" \
  "${STAGE_DIR}/dist/installers/server/mitambo" \
  "${STAGE_DIR}/dist/installers/server/lango" \
  "${STAGE_DIR}/dist/installers/server/wolinex-web" \
  "${STAGE_DIR}/scripts/lib"

cp -f "${ROOT_DIR}/dist/installers/server/orchestrator/wolinet-orchestrator_amd64.deb"* "${STAGE_DIR}/dist/installers/server/orchestrator/"
cp -f "${ROOT_DIR}/dist/installers/server/mitambo/mitambo-inference_amd64.deb"* "${STAGE_DIR}/dist/installers/server/mitambo/"
cp -f "${ROOT_DIR}/dist/installers/server/lango/litellm-gateway_amd64.deb"* "${STAGE_DIR}/dist/installers/server/lango/"
cp -f "${ROOT_DIR}/dist/installers/server/lango/config.yaml.example" "${STAGE_DIR}/dist/installers/server/lango/"
cp -f "${ROOT_DIR}/dist/installers/server/lango/env.example" "${STAGE_DIR}/dist/installers/server/lango/"
[[ -f "${ROOT_DIR}/dist/installers/server/lango/model_prices_and_context_window.json" ]] && \
  cp -f "${ROOT_DIR}/dist/installers/server/lango/model_prices_and_context_window.json" "${STAGE_DIR}/dist/installers/server/lango/"
if [[ -d "${ROOT_DIR}/dist/installers/server/lango/ui" ]]; then
  cp -R "${ROOT_DIR}/dist/installers/server/lango/ui" "${STAGE_DIR}/dist/installers/server/lango/ui"
elif [[ -d "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" ]]; then
  cp -R "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" "${STAGE_DIR}/dist/installers/server/lango/ui"
elif [[ -d "${ROOT_DIR}/gateway/litellm/proxy/_experimental/out" ]]; then
  cp -R "${ROOT_DIR}/gateway/litellm/proxy/_experimental/out" "${STAGE_DIR}/dist/installers/server/lango/ui"
fi
cp -f "${ROOT_DIR}/dist/installers/server/wolinex-web/wolinex-web_amd64.deb"* "${STAGE_DIR}/dist/installers/server/wolinex-web/"

cp -f "${ROOT_DIR}/scripts/install-"*.sh "${ROOT_DIR}/scripts/setup-contabo-edge.sh" "${ROOT_DIR}/scripts/setup-r2-backup.sh" "${ROOT_DIR}/scripts/clean-contabo-server.sh" "${STAGE_DIR}/scripts/"
cp -R "${ROOT_DIR}/scripts/lib/." "${STAGE_DIR}/scripts/lib/"
chmod +x "${STAGE_DIR}/scripts/"*.sh

if [[ -n "${ORIGIN_CERT}" || -n "${ORIGIN_KEY}" ]]; then
  [[ -f "${ORIGIN_CERT}" && -f "${ORIGIN_KEY}" ]] || die "Both --origin-cert and --origin-key must exist on disk"
  mkdir -p "${STAGE_DIR}/certs"
  cp -f "${ORIGIN_CERT}" "${STAGE_DIR}/certs/origin.crt"
  cp -f "${ORIGIN_KEY}" "${STAGE_DIR}/certs/origin.key"
fi

SSH_OPTS=(-p "${SSH_PORT}" -o StrictHostKeyChecking=accept-new)
[[ -n "${SSH_KEY}" ]] && SSH_OPTS+=(-i "${SSH_KEY}")
TARGET="${SSH_USER}@${SSH_HOST}"

if [[ -z "${PUBLIC_IP}" && "${SSH_HOST}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  PUBLIC_IP="${SSH_HOST}"
fi

EDGE_FLAGS="--domain '${DOMAIN}'"
[[ -n "${PUBLIC_IP}" ]] && EDGE_FLAGS="${EDGE_FLAGS} --public-ip '${PUBLIC_IP}'"
[[ "${ALLOW_DIRECT_HTTP}" == "1" ]] && EDGE_FLAGS="${EDGE_FLAGS} --allow-direct-http"
[[ -n "${EXTRA_PORTS}" ]] && EDGE_FLAGS="${EDGE_FLAGS} --extra-open-ports '${EXTRA_PORTS}'"
[[ -f "${STAGE_DIR}/certs/origin.crt" ]] && EDGE_FLAGS="${EDGE_FLAGS} --origin-cert '${REMOTE_DIR}/certs/origin.crt' --origin-key '${REMOTE_DIR}/certs/origin.key'"

if [[ "${DRY_RUN}" == "1" ]]; then
  log_ok "Dry run complete; staged bundle size: $(du -sh "${STAGE_DIR}" | awk '{print $1}')"
  log_info "Would deploy to: ssh ${SSH_OPTS[*]} ${TARGET} -> ${REMOTE_DIR}"
  log_info "Would run edge setup flags: ${EDGE_FLAGS}"
  exit 0
fi

log_header "Pre-cleaning old compile artifacts, checkpoints & configuring reliable DNS on ${TARGET}"
ssh "${SSH_OPTS[@]}" "${TARGET}" sudo bash -s < "${ROOT_DIR}/scripts/clean-contabo-server.sh"

log_header "Uploading binary-only server stack bundle to ${TARGET}:${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "${TARGET}" "sudo mkdir -p '${REMOTE_DIR}' && sudo chown -R \"\$(id -u):\$(id -g)\" '${REMOTE_DIR}'"
tar -C "${STAGE_DIR}" -czf - . | ssh "${SSH_OPTS[@]}" "${TARGET}" "tar -C '${REMOTE_DIR}' -xzf -"

log_header "Provisioning Ubuntu 24.04 runtime, 4-stage stack, Cloudflare edge & R2 backup (zero source on server)"
# Pass secrets cleanly via remote stdin env rather than CLI process args
ssh "${SSH_OPTS[@]}" "${TARGET}" bash -s <<EOF
set -euo pipefail
if [[ -d /run/systemd/system ]]; then
  sudo install -d -m 0755 /etc/systemd/resolved.conf.d
  printf '[Resolve]\nDNS=1.1.1.1 9.9.9.9\nFallbackDNS=8.8.8.8 1.0.0.1\nDNSStubListener=yes\n' | sudo tee /etc/systemd/resolved.conf.d/99-wolinet-dns.conf >/dev/null
  sudo systemctl reload-or-restart systemd-resolved >/dev/null 2>&1 || true
fi
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq podman uidmap slirp4netns nginx ufw curl ca-certificates openssl postgresql-client >/dev/null
sudo mkdir -p /etc/containers/registries.conf.d
printf 'unqualified-search-registries = ["docker.io"]\nshort-name-mode = "permissive"\n' | sudo tee /etc/containers/registries.conf.d/99-wolinet-dockerhub.conf >/dev/null
sudo systemctl enable --now podman.socket >/dev/null 2>&1 || true

sudo bash "${REMOTE_DIR}/scripts/install-server-stack.sh" --with-datastore

export CLOUDFLARE_API_TOKEN="${CF_TOKEN}"
sudo -E bash "${REMOTE_DIR}/scripts/setup-contabo-edge.sh" ${EDGE_FLAGS}

if [[ -n "${R2_ACCESS_KEY_ID}" && -n "${R2_SECRET_ACCESS_KEY}" ]]; then
  export R2_ACCOUNT_ID="${R2_ACCOUNT_ID}"
  export R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}"
  export R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}"
  export R2_ENDPOINT="${R2_ENDPOINT}"
  export R2_BACKUP_BUCKET="${R2_BACKUP_BUCKET}"
  export R2_STORAGE_BUCKET="${R2_STORAGE_BUCKET}"
  sudo -E bash "${REMOTE_DIR}/scripts/setup-r2-backup.sh" --run-now
fi

if [[ "${KEEP_REMOTE_STAGE}" == "0" ]]; then
  sudo rm -rf "${REMOTE_DIR}"
fi
EOF

log_ok "Contabo deployment complete!"
log_info "GUI Endpoints:"
log_info "  1apanel Admin GUI   : https://panel.${DOMAIN}"
log_info "  Mitambo Admin GUI   : https://mitambo.${DOMAIN}"
log_info "  Lango Admin UI/API  : https://lango.${DOMAIN}/ui  &  https://lango.${DOMAIN}/v1"
log_info "  Wolinex Web Portal  : https://wolinex.${DOMAIN}"
log_info "Workstation Desktop/CLI setup:"
log_info "  ./scripts/install-wolinex-client.sh --component all --gateway-url https://lango.${DOMAIN}"
