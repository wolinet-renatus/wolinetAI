#!/usr/bin/env bash
# Binary-Only Zero-Source Server Installer from Cloudflare R2:
# 1. Configures reliable systemd-resolved DNS (1.1.1.1 / 9.9.9.9) up front
# 2. Cleans up any prior source clones, compilers, Podman build images, checkpoints & .deb caches
# 3. Downloads pre-compiled amd64 .deb packages + .sha256 sidecars + installer assets from R2
# 4. Verifies SHA-256 checksums, installs Stages 1->4, runs DB migrations/seeding,
#    configures Cloudflare Origin CA SSL/DNS/Nginx/UFW + 6-hourly R2 backups, and wipes /tmp staging.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E bash "$0" "$@"
  fi
  echo "[r2-install:error] Must run as root or via sudo" >&2
  exit 1
fi

exec 9>/run/wolinet-install.lock
if ! flock -n 9; then
  echo "[r2-install] Waiting for existing installer instance to finish (up to 30s)..." >&2
  flock -w 30 9 || { echo "[r2-install:error] Another installer run holds /run/wolinet-install.lock" >&2; exit 1; }
fi

DOMAIN="${WOLINET_DOMAIN:-wolinet.com}"
PUBLIC_IP="${WOLINET_PUBLIC_IP:-}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
ORIGIN_CERT="${CLOUDFLARE_ORIGIN_CERT:-}"
ORIGIN_KEY="${CLOUDFLARE_ORIGIN_KEY:-}"
ALLOW_DIRECT_HTTP="${ALLOW_DIRECT_HTTP:-0}"
EXTRA_PORTS="${EXTRA_OPEN_PORTS:-}"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-}"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
R2_ENDPOINT="${R2_ENDPOINT:-}"
R2_BUCKET="${R2_BUCKET:-wolinetai}"
R2_PREFIX="${R2_PREFIX:-releases/latest}"
SKIP_PRE_CLEAN="${SKIP_PRE_CLEAN:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)            DOMAIN="${2:-wolinet.com}"; shift 2 ;;
    --public-ip)         PUBLIC_IP="${2:-}"; shift 2 ;;
    --cloudflare-token)  CF_TOKEN="${2:-}"; shift 2 ;;
    --origin-cert)       ORIGIN_CERT="${2:-}"; shift 2 ;;
    --origin-key)        ORIGIN_KEY="${2:-}"; shift 2 ;;
    --allow-direct-http) ALLOW_DIRECT_HTTP=1; shift ;;
    --extra-open-ports)  EXTRA_PORTS="${2:-}"; shift 2 ;;
    --r2-account-id)     R2_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --r2-access-key)     R2_ACCESS_KEY_ID="${2:-}"; shift 2 ;;
    --r2-secret-key)     R2_SECRET_ACCESS_KEY="${2:-}"; shift 2 ;;
    --r2-endpoint)       R2_ENDPOINT="${2:-}"; shift 2 ;;
    --r2-bucket)         R2_BUCKET="${2:-wolinetai}"; shift 2 ;;
    --r2-prefix)         R2_PREFIX="${2:-releases/latest}"; shift 2 ;;
    --skip-clean)        SKIP_PRE_CLEAN=1; shift ;;
    *) echo "[r2-install:error] Unknown option: $1" >&2; exit 1 ;;
  esac
done

reject_placeholder() {
  local name="$1" val="$2"
  local upper="${val^^}"
  if [[ -n "${val}" && ( "${val}" == \<*\> || "${val}" == *"<your-"* || "${upper}" == PASTE_* || "${upper}" == YOUR_* || "${upper}" == CHANGE_ME* || "${upper}" == REPLACE_WITH* ) ]]; then
    echo "[r2-install:error] ${name} is set to a placeholder (${val}). Pass the real value or unset R2_* to reuse /etc/wolinet/r2.env." >&2
    exit 1
  fi
}

load_saved_r2_var() {
  local key="$1"
  [[ -r /etc/wolinet/r2.env ]] || return 0
  awk -F= -v k="${key}" '$1 == k {sub(/^[^=]*=/, ""); print; exit}' /etc/wolinet/r2.env
}

reject_placeholder "CLOUDFLARE_API_TOKEN" "${CF_TOKEN}"
reject_placeholder "R2_ACCOUNT_ID" "${R2_ACCOUNT_ID}"
reject_placeholder "R2_ACCESS_KEY_ID" "${R2_ACCESS_KEY_ID}"
reject_placeholder "R2_SECRET_ACCESS_KEY" "${R2_SECRET_ACCESS_KEY}"
reject_placeholder "R2_ENDPOINT" "${R2_ENDPOINT}"

if [[ -r /etc/wolinet/r2.env ]]; then
  [[ -n "${R2_ACCOUNT_ID}" ]] || R2_ACCOUNT_ID="$(load_saved_r2_var R2_ACCOUNT_ID)"
  [[ -n "${R2_ACCESS_KEY_ID}" ]] || R2_ACCESS_KEY_ID="$(load_saved_r2_var R2_ACCESS_KEY_ID)"
  [[ -n "${R2_SECRET_ACCESS_KEY}" ]] || R2_SECRET_ACCESS_KEY="$(load_saved_r2_var R2_SECRET_ACCESS_KEY)"
  [[ -n "${R2_ENDPOINT}" ]] || R2_ENDPOINT="$(load_saved_r2_var R2_ENDPOINT)"
fi

if [[ -z "${R2_ENDPOINT}" && -n "${R2_ACCOUNT_ID}" ]]; then
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
fi
[[ -n "${R2_ACCESS_KEY_ID}" && -n "${R2_SECRET_ACCESS_KEY}" && -n "${R2_ENDPOINT}" ]] || {
  echo "[r2-install:error] R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT are required (pass them or ensure /etc/wolinet/r2.env exists)" >&2
  exit 1
}

echo "[r2-install] 1/5 Configuring reliable DNS (1.1.1.1 / 9.9.9.9)..."
if [[ -d /run/systemd/system ]]; then
  install -d -m 0755 /etc/systemd/resolved.conf.d
  cat > /etc/systemd/resolved.conf.d/99-wolinet-dns.conf <<'EOF'
[Resolve]
DNS=1.1.1.1 9.9.9.9
FallbackDNS=8.8.8.8 1.0.0.1
DNSStubListener=yes
EOF
  systemctl reload-or-restart systemd-resolved >/dev/null 2>&1 || true
fi

if [[ "${SKIP_PRE_CLEAN}" == "0" ]]; then
  echo "[r2-install] 2/5 Cleaning old source trees, compilers, Podman build images & checkpoints..."
  dpkg --configure -a >/dev/null 2>&1 || true
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

  for d in /var/lib/wolinet/models /var/lib/wolinet/mitambo /root/.cache/huggingface /root/.xinference; do
    [[ -d "${d}" ]] && find "${d}" -type f \( -name '*.incomplete' -o -name '*.part' -o -name '*.tmp' -o -name '*.lock' \) -delete 2>/dev/null || true
  done

  if command -v podman >/dev/null 2>&1; then
    while IFS= read -r cid; do
      [[ -n "${cid}" ]] || continue
      cname="$(podman inspect --format '{{.Name}}' "${cid}" 2>/dev/null || true)"
      case "${cname}" in
        wolinetai-postgres-1|wolinetai-redis-1|wolinetai-core-pod*) continue ;;
      esac
      podman rm -f "${cid}" >/dev/null 2>&1 || true
    done < <(podman ps -aq 2>/dev/null || true)

    if podman container exists wolinetai-postgres-1 >/dev/null 2>&1; then
      pg_img="$(podman inspect --format '{{.ImageName}}' wolinetai-postgres-1 2>/dev/null || true)"
      if [[ -n "${pg_img}" && "${pg_img}" != *"pgvector"* ]]; then
        podman rm -f wolinetai-postgres-1 >/dev/null 2>&1 || true
      fi
    fi

    while IFS= read -r img; do
      [[ -n "${img}" ]] || continue
      case "${img}" in
        *pgvector*|*redis*) continue ;;
      esac
      podman rmi -f "${img}" >/dev/null 2>&1 || true
    done < <(podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -E '(deb-builder|library/node|library/ubuntu|library/postgres|<none>)' || true)

    podman builder prune -af >/dev/null 2>&1 || true
  fi

  export DEBIAN_FRONTEND=noninteractive
  apt-get purge -y -qq git golang-go rustc cargo make gcc g++ build-essential cmake >/dev/null 2>&1 || true
  apt-get autoremove -y -qq >/dev/null 2>&1 || true
fi

echo "[r2-install] 3/5 Installing lightweight runtime dependencies..."
export DEBIAN_FRONTEND=noninteractive
dpkg --configure -a >/dev/null 2>&1 || true
RUNTIME_PKGS=(
  podman uidmap slirp4netns nginx ufw curl ca-certificates openssl postgresql-client python3
  libgomp1 libglib2.0-0 libgl1 libpq5
)
MISSING_PKGS=()
for pkg in "${RUNTIME_PKGS[@]}"; do
  if [[ "${pkg}" == "nginx" ]] && command -v nginx >/dev/null 2>&1; then
    continue
  fi
  if ! dpkg-query -W -f='${Status}\n' "${pkg}" 2>/dev/null | grep -q '^install ok installed$'; then
    MISSING_PKGS+=("${pkg}")
  fi
done
if (( ${#MISSING_PKGS[@]} > 0 )); then
  mkdir -p /var/lib/apt/lists/partial
  chmod 755 /var/lib/apt/lists/partial
  APT_OPTS=(
    -o DPkg::Lock::Timeout=120
    -o Acquire::Retries=4
    -o Acquire::ForceIPv4=true
    -o Acquire::http::No-Cache=true
  )
  if ! apt-get install -y -qq "${APT_OPTS[@]}" --no-upgrade "${MISSING_PKGS[@]}" >/dev/null 2>&1; then
    find /var/lib/apt/lists -maxdepth 1 -type f -delete 2>/dev/null || true
    rm -rf /var/lib/apt/lists/partial/* 2>/dev/null || true
    mkdir -p /var/lib/apt/lists/partial
    if apt-get update "${APT_OPTS[@]}" -qq && \
       apt-get install -y -qq "${APT_OPTS[@]}" --fix-missing --no-upgrade "${MISSING_PKGS[@]}" >/dev/null; then
      :
    else
      echo "[r2-install] Retrying missing packages against archive.ubuntu.com (bypassing stale security mirror)..."
      tmp_sources="$(mktemp /tmp/wolinet-apt-XXXXXX.list)"
      cat > "${tmp_sources}" <<'APTEOF'
deb http://archive.ubuntu.com/ubuntu noble main universe
deb http://archive.ubuntu.com/ubuntu noble-updates main universe
APTEOF
      APT_ARCHIVE_OPTS=("${APT_OPTS[@]}" -o "Dir::Etc::sourcelist=${tmp_sources}" -o "Dir::Etc::sourceparts=-")
      apt-get update "${APT_ARCHIVE_OPTS[@]}" -qq
      apt-get install -y -qq "${APT_ARCHIVE_OPTS[@]}" --fix-missing --no-upgrade "${MISSING_PKGS[@]}" >/dev/null
      rm -f "${tmp_sources}"
    fi
  fi
fi

install -d -m 0755 /etc/containers/registries.conf.d
cat > /etc/containers/registries.conf.d/99-wolinet-dockerhub.conf <<'EOF'
unqualified-search-registries = ["docker.io"]
short-name-mode = "permissive"
EOF
systemctl enable --now podman.socket >/dev/null 2>&1 || true

WORK_DIR="$(mktemp -d /tmp/wolinet-bin-XXXXXX)"
trap 'rm -rf "${WORK_DIR:-}"' EXIT

mkdir -p \
  "${WORK_DIR}/dist/installers/server/orchestrator" \
  "${WORK_DIR}/dist/installers/server/mitambo" \
  "${WORK_DIR}/dist/installers/server/lango" \
  "${WORK_DIR}/dist/installers/server/wolinex-web"

echo "[r2-install] 4/5 Downloading verified binary packages from s3://${R2_BUCKET}/${R2_PREFIX}/..."
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
R2_ENDPOINT="${R2_ENDPOINT}" \
python3 - "${R2_BUCKET}" "${R2_PREFIX}" "${WORK_DIR}" <<'PY'
import datetime, hashlib, hmac, http.client, os, pathlib, sys, urllib.parse

bucket, prefix, work_dir = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
ak = os.environ["R2_ACCESS_KEY_ID"]
sk = os.environ["R2_SECRET_ACCESS_KEY"]
parsed = urllib.parse.urlsplit(endpoint)
host = parsed.netloc

targets = [
    ("wolinet-deploy-assets.tar.gz", work_dir / "wolinet-deploy-assets.tar.gz"),
    ("wolinet-deploy-assets.tar.gz.sha256", work_dir / "wolinet-deploy-assets.tar.gz.sha256"),
    ("wolinet-orchestrator_amd64.deb", work_dir / "dist/installers/server/orchestrator/wolinet-orchestrator_amd64.deb"),
    ("wolinet-orchestrator_amd64.deb.sha256", work_dir / "dist/installers/server/orchestrator/wolinet-orchestrator_amd64.deb.sha256"),
    ("mitambo-inference_amd64.deb", work_dir / "dist/installers/server/mitambo/mitambo-inference_amd64.deb"),
    ("mitambo-inference_amd64.deb.sha256", work_dir / "dist/installers/server/mitambo/mitambo-inference_amd64.deb.sha256"),
    ("litellm-gateway_amd64.deb", work_dir / "dist/installers/server/lango/litellm-gateway_amd64.deb"),
    ("litellm-gateway_amd64.deb.sha256", work_dir / "dist/installers/server/lango/litellm-gateway_amd64.deb.sha256"),
    ("wolinex-web_amd64.deb", work_dir / "dist/installers/server/wolinex-web/wolinex-web_amd64.deb"),
    ("wolinex-web_amd64.deb.sha256", work_dir / "dist/installers/server/wolinex-web/wolinex-web_amd64.deb.sha256"),
]

def sign(k: bytes, m: str) -> bytes:
    return hmac.new(k, m.encode("utf-8"), hashlib.sha256).digest()

def signing_key(secret: str, ds: str) -> bytes:
    return sign(sign(sign(sign(("AWS4" + secret).encode("utf-8"), ds), "auto"), "s3"), "aws4_request")

def download(name: str, dst: pathlib.Path) -> None:
    key = f"{prefix.strip('/')}/{name}"
    uri = f"/{bucket}/{urllib.parse.quote(key, safe='/-_.~')}"
    now = datetime.datetime.now(datetime.timezone.utc)
    amz, ds = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    ph = hashlib.sha256(b"").hexdigest()
    ch = f"host:{host}\nx-amz-content-sha256:{ph}\nx-amz-date:{amz}\n"
    sh = "host;x-amz-content-sha256;x-amz-date"
    cr = "\n".join(["GET", uri, "", ch, sh, ph])
    scope = f"{ds}/auto/s3/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(cr.encode("utf-8")).hexdigest()])
    sig = hmac.new(signing_key(sk, ds), sts.encode("utf-8"), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={sh}, Signature={sig}"

    conn = http.client.HTTPSConnection(host, timeout=600)
    conn.request("GET", uri, headers={"Host": host, "x-amz-date": amz, "x-amz-content-sha256": ph, "Authorization": auth})
    resp = conn.getresponse()
    if resp.status != 200:
        err = resp.read().decode("utf-8", "ignore")
        conn.close()
        raise RuntimeError(f"Failed downloading s3://{bucket}/{key}: http={resp.status} {err}")
    total = 0
    with dst.open("wb") as fh:
        while chunk := resp.read(4 * 1024 * 1024):
            fh.write(chunk)
            total += len(chunk)
    conn.close()
    print(f"  downloaded {name} ({total / (1024 * 1024):.2f} MiB)")

for name, dst in targets:
    download(name, dst)
PY

echo "[r2-install] Verifying SHA-256 checksums..."
(cd "${WORK_DIR}" && sha256sum -c "wolinet-deploy-assets.tar.gz.sha256")
for d in orchestrator mitambo lango wolinex-web; do
  (cd "${WORK_DIR}/dist/installers/server/${d}" && sha256sum -c *.deb.sha256)
done

tar --warning=no-unknown-keyword -C "${WORK_DIR}" -xzf "${WORK_DIR}/wolinet-deploy-assets.tar.gz"
chmod +x "${WORK_DIR}/scripts/"*.sh

echo "[r2-install] 5/5 Installing Stages 1->4, DB migrations/seeding, Cloudflare edge & R2 backup..."
WOLINET_DOMAIN="${DOMAIN}" bash "${WORK_DIR}/scripts/install-server-stack.sh" --with-datastore

EDGE_ARGS=(--domain "${DOMAIN}")
[[ -n "${PUBLIC_IP}" ]] && EDGE_ARGS+=(--public-ip "${PUBLIC_IP}")
[[ -n "${ORIGIN_CERT}" && -n "${ORIGIN_KEY}" ]] && EDGE_ARGS+=(--origin-cert "${ORIGIN_CERT}" --origin-key "${ORIGIN_KEY}")
[[ "${ALLOW_DIRECT_HTTP}" == "1" ]] && EDGE_ARGS+=(--allow-direct-http)
[[ -n "${EXTRA_PORTS}" ]] && EDGE_ARGS+=(--extra-open-ports "${EXTRA_PORTS}")
CLOUDFLARE_API_TOKEN="${CF_TOKEN}" bash "${WORK_DIR}/scripts/setup-contabo-edge.sh" "${EDGE_ARGS[@]}"

R2_ACCOUNT_ID="${R2_ACCOUNT_ID}" \
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
R2_ENDPOINT="${R2_ENDPOINT}" \
R2_BACKUP_BUCKET="${R2_BUCKET}" \
R2_STORAGE_BUCKET="${R2_BUCKET}" \
CLOUDFLARE_API_TOKEN="${CF_TOKEN}" \
  bash "${WORK_DIR}/scripts/setup-r2-backup.sh" --run-now

apt-get clean >/dev/null 2>&1 || true

echo "[r2-install] Verifying running services, PostgreSQL & cleanup status..."
verify_svc() {
  local name="$1" url="$2" unit="$3" max_wait="$4"
  local i=0
  while (( i < max_wait )); do
    if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
      echo "  [OK] ${name} (${url})"
      return 0
    fi
    sleep 2
    i=$((i + 2))
  done
  echo "  [WARN] ${name} not yet reachable at ${url} after ${max_wait}s; recent logs:" >&2
  journalctl -u "${unit}" -n 25 --no-pager >&2 || true
  return 0
}
verify_svc "1apanel :8888" "http://127.0.0.1:8888/" "1apanel" 20
verify_svc "Lango :4000" "http://127.0.0.1:4000/health/liveliness" "litellm-gateway" 45
verify_svc "Wolinex Web :8081" "http://127.0.0.1:8081/health" "wolinex-web" 90
verify_svc "Mitambo :9997" "http://127.0.0.1:9997/status" "mitambo" 90
PG_PASS="$(awk -F= '/^POSTGRES_PASSWORD=/{print $2; exit}' /etc/wolinet/1apanel.env 2>/dev/null || echo '')"
if [[ -n "${PG_PASS}" ]] && command -v psql >/dev/null 2>&1; then
  MC="$(PGPASSWORD="${PG_PASS}" psql -h 127.0.0.1 -p 5433 -U postgres -d litellm -tAc 'SELECT count(*) FROM "LiteLLM_ProxyModelTable";' 2>/dev/null || echo '0')"
  AV="$(PGPASSWORD="${PG_PASS}" psql -h 127.0.0.1 -p 5433 -U postgres -d webui -tAc 'SELECT version_num FROM alembic_version LIMIT 1;' 2>/dev/null || echo 'none')"
  echo "  [OK] PostgreSQL litellm_models=${MC} webui_alembic=${AV}"
fi
df -h / | tail -n 1
echo "[r2-install] Domain endpoints:"
echo "  https://ai.${DOMAIN}      -> Product showcase"
echo "  https://wolinex.${DOMAIN} -> Web chat UI (:8081 -> Lango :4000, shared PG :5433)"
echo "  https://lango.${DOMAIN}   -> Gateway API & /ui Admin Dashboard (:4000)"
echo "  https://mitambo.${DOMAIN} -> Inference engine (:9997)"
echo "  https://wcp.${DOMAIN}     -> Wolinet Control Panel (:8888)"
echo "  https://docs.${DOMAIN}    -> Developer documentation & Scalar API Ref"
echo "  https://dev.${DOMAIN}     -> Developer studio, key gen & AI assistant"
read_saved_env() {
  local fp="$1" key="$2" raw=""
  [[ -r "${fp}" ]] || return 0
  raw="$(awk -F= -v k="${key}" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "${fp}")"
  if [[ "${raw}" =~ ^\".*\"$ || "${raw}" =~ ^\'.*\'$ ]]; then
    raw="${raw:1:${#raw}-2}"
  fi
  printf '%s' "${raw}"
}
WCP_USER="$(read_saved_env /etc/wolinet/1apanel.env ORIGINAL_USERNAME)"
WCP_PASS="$(read_saved_env /etc/wolinet/1apanel.env ORIGINAL_PASSWORD)"
MIT_USER="$(read_saved_env /etc/wolinet/mitambo.env XINFERENCE_ADMIN_USER)"
MIT_PASS="$(read_saved_env /etc/wolinet/mitambo.env XINFERENCE_ADMIN_PASSWORD)"
LANGO_USER="$(read_saved_env /etc/litellm/env UI_USERNAME)"
LANGO_PASS="$(read_saved_env /etc/litellm/env UI_PASSWORD)"
LANGO_MASTER="$(read_saved_env /etc/litellm/env LITELLM_MASTER_KEY)"
WEB_EMAIL="$(read_saved_env /etc/wolinet/wolinex-web.env WEBUI_ADMIN_EMAIL)"
WEB_PASS="$(read_saved_env /etc/wolinet/wolinex-web.env WEBUI_ADMIN_PASSWORD)"
echo "[r2-install] Portal login credentials (saved in /etc/wolinet/* & /etc/litellm/env):"
echo "  https://wcp.${DOMAIN}        username=${WCP_USER:-admin}  password=${WCP_PASS:-<see /etc/wolinet/1apanel.env>}"
echo "  https://mitambo.${DOMAIN}    username=${MIT_USER:-admin}  password=${MIT_PASS:-${WCP_PASS:-<see /etc/wolinet/mitambo.env>}}"
echo "  https://lango.${DOMAIN}/ui/  username=${LANGO_USER:-admin}  password=${LANGO_PASS:-${LANGO_MASTER:-<see /etc/litellm/env>}}"
echo "  https://wolinex.${DOMAIN}    email=${WEB_EMAIL:-admin@${DOMAIN}}  password=${WEB_PASS:-${WCP_PASS:-<see /etc/wolinet/wolinex-web.env>}}"
echo "  https://dev.${DOMAIN}        (signs in via wolinex.${DOMAIN} SSO cookie on .${DOMAIN})"
