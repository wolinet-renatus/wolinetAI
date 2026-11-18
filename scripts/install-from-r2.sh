#!/usr/bin/env bash
# Binary-Only Zero-Source Server Installer from Cloudflare R2:
# Downloads pre-compiled amd64 .deb packages + .sha256 checksums + installer scripts from R2,
# verifies SHA-256 checksums, removes any leftover /opt/wolinetai source checkout,
# installs Stages 1->4, configures Cloudflare Origin SSL/DNS/Nginx/UFW + R2 auto-backup, and cleans up.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    exec sudo -E bash "$0" "$@"
  fi
  echo "[r2-install:error] Must run as root or via sudo" >&2
  exit 1
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
    *) echo "[r2-install:error] Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${R2_ENDPOINT}" && -n "${R2_ACCOUNT_ID}" ]]; then
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
fi
[[ -n "${R2_ACCESS_KEY_ID}" && -n "${R2_SECRET_ACCESS_KEY}" && -n "${R2_ENDPOINT}" ]] || {
  echo "[r2-install:error] R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT are required" >&2
  exit 1
}

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq podman uidmap slirp4netns nginx ufw curl ca-certificates openssl postgresql-client python3 >/dev/null

install -d -m 0755 /etc/containers/registries.conf.d
cat > /etc/containers/registries.conf.d/99-wolinet-dockerhub.conf <<'EOF'
unqualified-search-registries = ["docker.io"]
short-name-mode = "permissive"
EOF
systemctl enable --now podman.socket >/dev/null 2>&1 || true

# Remove any prior source checkout so zero source code stays on production server
rm -rf /opt/wolinetai

WORK_DIR="$(mktemp -d /tmp/wolinet-bin-XXXXXX)"
trap 'rm -rf "${WORK_DIR:-}"' EXIT

mkdir -p \
  "${WORK_DIR}/dist/installers/server/orchestrator" \
  "${WORK_DIR}/dist/installers/server/mitambo" \
  "${WORK_DIR}/dist/installers/server/lango" \
  "${WORK_DIR}/dist/installers/server/wolinex-web"

echo "[r2-install] Downloading pre-built binary packages from s3://${R2_BUCKET}/${R2_PREFIX}/..."
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

tar -C "${WORK_DIR}" -xzf "${WORK_DIR}/wolinet-deploy-assets.tar.gz"
chmod +x "${WORK_DIR}/scripts/"*.sh

bash "${WORK_DIR}/scripts/install-server-stack.sh" --with-datastore

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

echo "[r2-install] Verifying running services (zero source code stored on server)..."
curl -fsS --max-time 10 http://127.0.0.1:8888/ >/dev/null && echo "  [OK] 1apanel :8888"
curl -fsS --max-time 10 http://127.0.0.1:9997/status >/dev/null && echo "  [OK] Mitambo :9997"
curl -fsS --max-time 10 http://127.0.0.1:4000/health/liveliness >/dev/null && echo "  [OK] Lango :4000"
curl -fsS --max-time 10 http://127.0.0.1:8081/health >/dev/null && echo "  [OK] Wolinex Web :8081"
