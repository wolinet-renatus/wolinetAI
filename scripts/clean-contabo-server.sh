#!/usr/bin/env bash
# Production Server Hygiene & Cleanup (Contabo Ubuntu 24.04):
# Removes leftover source checkouts, compilers, downloaded .deb staging files,
# incomplete model/download checkpoints, and Podman builder images/caches
# WITHOUT touching live user data or database volumes under /var/lib/wolinet/data.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "[cleanup:error] Run as root (or via sudo)" >&2
  exit 1
fi

PURGE_DOWNLOADED_MODELS="${PURGE_DOWNLOADED_MODELS:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge-models) PURGE_DOWNLOADED_MODELS=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: clean-contabo-server.sh [--purge-models]
Removes source checkouts (/opt/wolinetai), compilers (Go/Rust/Git/Make),
old .deb staging dirs, Podman build images, and incomplete download checkpoints.
EOF
      exit 0 ;;
    *) echo "[cleanup:error] Unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "[cleanup] Removing leftover source trees, build toolchains, and staging packages..."
rm -rf \
  /opt/wolinetai \
  /opt/wolinet-src \
  /root/wolinetai \
  /opt/wolinet-release \
  /tmp/wolinet-* \
  /tmp/*.deb \
  /tmp/*.deb.sha256 \
  /tmp/wolinet*.tar.gz* \
  /root/*.deb \
  /root/go \
  /usr/local/go \
  /usr/local/bin/go \
  /usr/local/bin/gofmt \
  /root/.cache/go-build \
  /root/.cache/pip \
  /root/.cache/uv \
  /root/.cargo \
  /root/.rustup \
  /root/.npm

echo "[cleanup] Cleaning incomplete download checkpoints and temp files..."
for d in /var/lib/wolinet/models /var/lib/wolinet/mitambo /root/.cache/huggingface /root/.xinference; do
  if [[ -d "${d}" ]]; then
    find "${d}" -type f \( -name '*.incomplete' -o -name '*.part' -o -name '*.tmp' -o -name '*.lock' \) -delete 2>/dev/null || true
    if [[ "${PURGE_DOWNLOADED_MODELS}" == "1" && "${d}" == "/var/lib/wolinet/models" ]]; then
      rm -rf "${d:?}/"*
    fi
  fi
done

if command -v podman >/dev/null 2>&1; then
  echo "[cleanup] Pruning Podman builder containers and build images (preserving runtime datastores)..."
  # Remove exited/dead build containers without touching wolinetai-postgres-1 or wolinetai-redis-1
  while IFS= read -r cid; do
    [[ -n "${cid}" ]] || continue
    cname="$(podman inspect --format '{{.Name}}' "${cid}" 2>/dev/null || true)"
    case "${cname}" in
      wolinetai-postgres-1|wolinetai-redis-1|wolinetai-core-pod*) continue ;;
    esac
    podman rm -f "${cid}" >/dev/null 2>&1 || true
  done < <(podman ps -aq 2>/dev/null || true)

  # Upgrade legacy postgres:16-alpine container definition to pgvector/pgvector:pg16 keeping PGDATA volume
  if podman container exists wolinetai-postgres-1 >/dev/null 2>&1; then
    pg_img="$(podman inspect --format '{{.ImageName}}' wolinetai-postgres-1 2>/dev/null || true)"
    if [[ -n "${pg_img}" && "${pg_img}" != *"pgvector"* ]]; then
      echo "[cleanup] Replacing legacy ${pg_img} container so Stage 1 recreates it with pgvector:pg16 (PGDATA preserved)..."
      podman rm -f wolinetai-postgres-1 >/dev/null 2>&1 || true
    fi
  fi

  # Remove builder images (mitambo-deb-builder, litellm-gateway-deb-builder, node, ubuntu, old postgres)
  while IFS= read -r img; do
    [[ -n "${img}" ]] || continue
    case "${img}" in
      *pgvector*|*redis*) continue ;;
    esac
    podman rmi -f "${img}" >/dev/null 2>&1 || true
  done < <(podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -E '(deb-builder|library/node|library/ubuntu|library/postgres|<none>)' || true)

  podman builder prune -af >/dev/null 2>&1 || true
  podman image prune -af --filter "until=1h" >/dev/null 2>&1 || true
fi

if command -v apt-get >/dev/null 2>&1; then
  echo "[cleanup] Purging server compilers and unused apt build caches..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get purge -y -qq git golang-go rustc cargo make gcc g++ build-essential cmake >/dev/null 2>&1 || true
  apt-get autoremove -y -qq >/dev/null 2>&1 || true
  apt-get clean >/dev/null 2>&1 || true
fi

echo "[cleanup] Server disk space summary after cleanup:"
df -h / | tail -n 1
