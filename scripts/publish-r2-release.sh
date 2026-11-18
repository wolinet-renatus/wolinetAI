#!/usr/bin/env bash
# Publish pre-built binary installers (.deb + .sha256 + Lango UI + installer scripts)
# from Mac/CI to Cloudflare R2 (releases/latest/) WITHOUT uploading any source code.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-}"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
R2_ENDPOINT="${R2_ENDPOINT:-}"
R2_BUCKET="${R2_BUCKET:-wolinetai}"
R2_PREFIX="${R2_PREFIX:-releases/latest}"
BUILD_FIRST=0

usage() {
  cat <<'EOF'
Publish Pre-Built Wolinet Server Binary Release to Cloudflare R2 (Zero Source Code)

Usage:
  publish-r2-release.sh [options]

Options:
  --account-id <id>      Cloudflare Account ID
  --access-key <key>     R2 S3 Access Key ID
  --secret-key <secret>  R2 S3 Secret Access Key
  --endpoint <url>       R2 S3 Endpoint (default: https://<account-id>.r2.cloudflarestorage.com)
  --bucket <name>        Target R2 bucket (default: wolinetai)
  --prefix <path>        Object key prefix (default: releases/latest)
  --build                Rebuild Linux amd64 .deb packages locally before publishing
  -h, --help             Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account-id) R2_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --access-key) R2_ACCESS_KEY_ID="${2:-}"; shift 2 ;;
    --secret-key) R2_SECRET_ACCESS_KEY="${2:-}"; shift 2 ;;
    --endpoint)   R2_ENDPOINT="${2:-}"; shift 2 ;;
    --bucket)     R2_BUCKET="${2:-wolinetai}"; shift 2 ;;
    --prefix)     R2_PREFIX="${2:-releases/latest}"; shift 2 ;;
    --build)      BUILD_FIRST=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            die "Unknown option: $1 (try --help)" ;;
  esac
done

if [[ -z "${R2_ENDPOINT}" && -n "${R2_ACCOUNT_ID}" ]]; then
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
fi
[[ -n "${R2_ACCESS_KEY_ID}" && -n "${R2_SECRET_ACCESS_KEY}" && -n "${R2_ENDPOINT}" ]] || \
  die "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT (or R2_ACCOUNT_ID) are required"

if [[ "${BUILD_FIRST}" == "1" ]]; then
  log_header "Rebuilding Linux amd64 server .deb packages locally"
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
  [[ -f "${ROOT_DIR}/dist/installers/server/${rel}" ]] || die "Missing Linux .deb: dist/installers/server/${rel} (pass --build)"
done

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR:-}"' EXIT

log_header "Packing installer-only runtime assets (zero source code)"
mkdir -p "${STAGE_DIR}/bundle/dist/installers/server/lango" "${STAGE_DIR}/bundle/scripts/lib"

cp -f "${ROOT_DIR}/dist/installers/server/lango/config.yaml.example" "${STAGE_DIR}/bundle/dist/installers/server/lango/"
cp -f "${ROOT_DIR}/dist/installers/server/lango/env.example" "${STAGE_DIR}/bundle/dist/installers/server/lango/"
[[ -f "${ROOT_DIR}/dist/installers/server/lango/model_prices_and_context_window.json" ]] && \
  cp -f "${ROOT_DIR}/dist/installers/server/lango/model_prices_and_context_window.json" "${STAGE_DIR}/bundle/dist/installers/server/lango/"
if [[ -d "${ROOT_DIR}/dist/installers/server/lango/ui" ]]; then
  cp -R "${ROOT_DIR}/dist/installers/server/lango/ui" "${STAGE_DIR}/bundle/dist/installers/server/lango/ui"
elif [[ -d "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" ]]; then
  cp -R "${ROOT_DIR}/gateway/ui/litellm-dashboard/out" "${STAGE_DIR}/bundle/dist/installers/server/lango/ui"
elif [[ -d "${ROOT_DIR}/gateway/litellm/proxy/_experimental/out" ]]; then
  cp -R "${ROOT_DIR}/gateway/litellm/proxy/_experimental/out" "${STAGE_DIR}/bundle/dist/installers/server/lango/ui"
fi

cp -f "${ROOT_DIR}/scripts/install-"*.sh "${ROOT_DIR}/scripts/setup-contabo-edge.sh" "${ROOT_DIR}/scripts/setup-r2-backup.sh" "${STAGE_DIR}/bundle/scripts/"
cp -R "${ROOT_DIR}/scripts/lib/." "${STAGE_DIR}/bundle/scripts/lib/"
chmod +x "${STAGE_DIR}/bundle/scripts/"*.sh

ASSETS_TGZ="${STAGE_DIR}/wolinet-deploy-assets.tar.gz"
tar -C "${STAGE_DIR}/bundle" -czf "${ASSETS_TGZ}" .
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${STAGE_DIR}" && sha256sum "wolinet-deploy-assets.tar.gz" > "wolinet-deploy-assets.tar.gz.sha256")
else
  (cd "${STAGE_DIR}" && shasum -a 256 "wolinet-deploy-assets.tar.gz" > "wolinet-deploy-assets.tar.gz.sha256")
fi

log_header "Uploading binary artifacts to s3://${R2_BUCKET}/${R2_PREFIX}/"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
R2_ENDPOINT="${R2_ENDPOINT}" \
python3 - "${R2_BUCKET}" "${R2_PREFIX}" \
  "${ASSETS_TGZ}" \
  "${ASSETS_TGZ}.sha256" \
  "${ROOT_DIR}/dist/installers/server/orchestrator/wolinet-orchestrator_amd64.deb" \
  "${ROOT_DIR}/dist/installers/server/orchestrator/wolinet-orchestrator_amd64.deb.sha256" \
  "${ROOT_DIR}/dist/installers/server/mitambo/mitambo-inference_amd64.deb" \
  "${ROOT_DIR}/dist/installers/server/mitambo/mitambo-inference_amd64.deb.sha256" \
  "${ROOT_DIR}/dist/installers/server/lango/litellm-gateway_amd64.deb" \
  "${ROOT_DIR}/dist/installers/server/lango/litellm-gateway_amd64.deb.sha256" \
  "${ROOT_DIR}/dist/installers/server/wolinex-web/wolinex-web_amd64.deb" \
  "${ROOT_DIR}/dist/installers/server/wolinex-web/wolinex-web_amd64.deb.sha256" <<'PY'
import datetime, hashlib, hmac, http.client, os, pathlib, sys, urllib.parse

bucket, prefix, *files = sys.argv[1:]
endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
ak = os.environ["R2_ACCESS_KEY_ID"]
sk = os.environ["R2_SECRET_ACCESS_KEY"]
parsed = urllib.parse.urlsplit(endpoint)
host = parsed.netloc

def sign(k: bytes, m: str) -> bytes:
    return hmac.new(k, m.encode("utf-8"), hashlib.sha256).digest()

def signing_key(secret: str, ds: str) -> bytes:
    return sign(sign(sign(sign(("AWS4" + secret).encode("utf-8"), ds), "auto"), "s3"), "aws4_request")

def upload(local_path: pathlib.Path) -> None:
    key = f"{prefix.strip('/')}/{local_path.name}"
    uri = f"/{bucket}/{urllib.parse.quote(key, safe='/-_.~')}"
    h = hashlib.sha256()
    size = local_path.stat().st_size
    with local_path.open("rb") as fh:
        while chunk := fh.read(4 * 1024 * 1024):
            h.update(chunk)
    payload_hash = h.hexdigest()

    now = datetime.datetime.now(datetime.timezone.utc)
    amz, ds = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    ch = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz}\n"
    sh = "host;x-amz-content-sha256;x-amz-date"
    cr = "\n".join(["PUT", uri, "", ch, sh, payload_hash])
    scope = f"{ds}/auto/s3/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(cr.encode("utf-8")).hexdigest()])
    sig = hmac.new(signing_key(sk, ds), sts.encode("utf-8"), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={sh}, Signature={sig}"

    conn = http.client.HTTPSConnection(host, timeout=600)
    conn.putrequest("PUT", uri)
    conn.putheader("Host", host)
    conn.putheader("Content-Length", str(size))
    conn.putheader("x-amz-date", amz)
    conn.putheader("x-amz-content-sha256", payload_hash)
    conn.putheader("Authorization", auth)
    conn.endheaders()

    with local_path.open("rb") as fh:
        while chunk := fh.read(4 * 1024 * 1024):
            conn.send(chunk)

    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    if resp.status not in (200, 201, 204):
        raise RuntimeError(f"Upload failed for {key}: http={resp.status} {body.decode('utf-8', 'ignore')}")
    print(f"  uploaded s3://{bucket}/{key} ({size / (1024 * 1024):.2f} MiB)")

for fp in files:
    p = pathlib.Path(fp)
    if p.exists():
        upload(p)
PY

log_ok "Binary release published to s3://${R2_BUCKET}/${R2_PREFIX}/ (zero source code included)"
