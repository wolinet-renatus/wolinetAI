#!/usr/bin/env bash
# Configure Cloudflare R2 S3-compatible object storage (Wolinex Web uploads)
# and automated daily backups (PostgreSQL 16 + 1apanel SQLite + Mitambo state + configs) to R2.
# Credentials are read from runtime env/flags and stored ONLY on-server in /etc/wolinet/r2.env (0600).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-}"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
R2_ENDPOINT="${R2_ENDPOINT:-}"
R2_BACKUP_BUCKET="${R2_BACKUP_BUCKET:-wolinet-backups}"
R2_STORAGE_BUCKET="${R2_STORAGE_BUCKET:-wolinet-storage}"
R2_RETENTION_DAYS="${R2_RETENTION_DAYS:-30}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CONFIGURE_WOLINEX_S3=1
RUN_NOW=0
SKIP_START=0

usage() {
  cat <<'EOF'
Wolinet Cloudflare R2 S3 Storage & Automated Backup Setup

Usage:
  setup-r2-backup.sh [options]

Options:
  --account-id <id>          Cloudflare Account ID
  --access-key <key>         R2 S3 Access Key ID
  --secret-key <secret>      R2 S3 Secret Access Key
  --endpoint <url>           R2 S3 Endpoint (default: https://<account-id>.r2.cloudflarestorage.com)
  --backup-bucket <name>     R2 bucket for daily backups (default: wolinet-backups)
  --storage-bucket <name>    R2 bucket for Wolinex file uploads (default: wolinet-storage)
  --retention-days <days>    Remote R2 backup retention in days (default: 30)
  --cloudflare-token <tok>   Cloudflare API token (used to create buckets if R2 API enabled)
  --no-wolinex-s3            Skip wiring R2 S3 storage into /etc/wolinet/wolinex-web.env
  --run-now                  Execute an immediate backup & R2 upload after setup
  --skip-start               Do not enable/start systemd timer or restart wolinex-web
  -h, --help                 Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account-id)       R2_ACCOUNT_ID="${2:-}"; shift 2 ;;
    --access-key)       R2_ACCESS_KEY_ID="${2:-}"; shift 2 ;;
    --secret-key)       R2_SECRET_ACCESS_KEY="${2:-}"; shift 2 ;;
    --endpoint)         R2_ENDPOINT="${2:-}"; shift 2 ;;
    --backup-bucket)    R2_BACKUP_BUCKET="${2:-wolinet-backups}"; shift 2 ;;
    --storage-bucket)   R2_STORAGE_BUCKET="${2:-wolinet-storage}"; shift 2 ;;
    --retention-days)   R2_RETENTION_DAYS="${2:-30}"; shift 2 ;;
    --cloudflare-token) CF_TOKEN="${2:-}"; shift 2 ;;
    --no-wolinex-s3)    CONFIGURE_WOLINEX_S3=0; shift ;;
    --run-now)          RUN_NOW=1; shift ;;
    --skip-start)       SKIP_START=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    *)                  die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform
[[ "${HOST_OS}" == "linux" ]] || die "setup-r2-backup.sh is intended for the Ubuntu server host"

if [[ -z "${R2_ENDPOINT}" && -n "${R2_ACCOUNT_ID}" ]]; then
  R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
fi

[[ -n "${R2_ACCESS_KEY_ID}" && -n "${R2_SECRET_ACCESS_KEY}" && -n "${R2_ENDPOINT}" ]] || \
  die "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT (or R2_ACCOUNT_ID) are required"

log_header "Writing protected R2 credentials to /etc/wolinet/r2.env (0600)"
run_root install -d -m 0750 /etc/wolinet /var/backups/wolinet

tmp_env="$(mktemp)"
cat > "${tmp_env}" <<EOF
R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
R2_ENDPOINT=${R2_ENDPOINT}
R2_BACKUP_BUCKET=${R2_BACKUP_BUCKET}
R2_STORAGE_BUCKET=${R2_STORAGE_BUCKET}
R2_RETENTION_DAYS=${R2_RETENTION_DAYS}
EOF
run_root install -m 0600 "${tmp_env}" /etc/wolinet/r2.env
rm -f "${tmp_env}"

log_header "Installing pure-Python AWS SigV4 R2 client (/usr/local/bin/wolinet-r2-client)"
run_root tee /usr/local/bin/wolinet-r2-client >/dev/null <<'PY'
#!/usr/bin/env python3
"""Minimal AWS SigV4 S3 client for Cloudflare R2 (stdlib only)."""
import datetime
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def signing_key(secret: str, date_stamp: str, region: str = "auto", service: str = "s3") -> bytes:
    k_date = sign(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    return sign(k_service, "aws4_request")


def s3_request(method: str, bucket: str, key: str = "", query: str = "", body: bytes = b""):
    endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
    access_key = os.environ["R2_ACCESS_KEY_ID"]
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"]

    parsed = urllib.parse.urlsplit(endpoint)
    host = parsed.netloc
    clean_key = key.lstrip("/")
    canonical_uri = f"/{bucket}" + (f"/{urllib.parse.quote(clean_key, safe='/-_.~')}" if clean_key else "")
    url = f"{parsed.scheme}://{host}{canonical_uri}" + (f"?{query}" if query else "")

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([
        method,
        canonical_uri,
        query,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    scope = f"{date_stamp}/auto/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        signing_key(secret_key, date_stamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(
        url,
        data=body if method in ("PUT", "POST") else None,
        method=method,
        headers={
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": auth_header,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def ensure_bucket(bucket: str) -> int:
    st, body = s3_request("HEAD", bucket)
    if st in (200, 204):
        print(f"R2 bucket ready: {bucket}")
        return 0
    st_put, put_body = s3_request("PUT", bucket)
    if st_put in (200, 204, 409):
        print(f"R2 bucket created/ready: {bucket}")
        return 0
    acct = os.environ.get("R2_ACCOUNT_ID", "")
    cf_tok = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if acct and cf_tok:
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/r2/buckets",
            data=json.dumps({"name": bucket}).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {cf_tok}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res.get("success"):
                    print(f"R2 bucket created via API: {bucket}")
                    return 0
        except urllib.error.HTTPError as exc:
            err = exc.read().decode("utf-8", "ignore")
            print(f"[r2:warn] Cloudflare R2 bucket API returned {exc.code}: {err}", file=sys.stderr)
            return 2
    print(f"[r2:warn] S3 HEAD/PUT failed for bucket {bucket}: http={st_put} {put_body.decode('utf-8', 'ignore')}", file=sys.stderr)
    return 2


def put_file(bucket: str, remote_key: str, local_path: str) -> int:
    with open(local_path, "rb") as fh:
        data = fh.read()
    st, body = s3_request("PUT", bucket, key=remote_key, body=data)
    if st in (200, 201, 204):
        print(f"Uploaded s3://{bucket}/{remote_key} ({len(data)} bytes)")
        return 0
    print(f"[r2:error] Upload failed for {remote_key}: http={st} {body.decode('utf-8', 'ignore')}", file=sys.stderr)
    return 1


def get_file(bucket: str, remote_key: str, local_path: str) -> int:
    st, body = s3_request("GET", bucket, key=remote_key)
    if st == 200:
        with open(local_path, "wb") as fh:
            fh.write(body)
        print(f"Downloaded s3://{bucket}/{remote_key} -> {local_path} ({len(body)} bytes)")
        return 0
    print(f"[r2:error] Download failed for {remote_key}: http={st} {body.decode('utf-8', 'ignore')}", file=sys.stderr)
    return 1


def list_objects(bucket: str, prefix: str, latest_only: bool = False) -> int:
    q = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    st, body = s3_request("GET", bucket, query=q)
    if st != 200:
        print(f"[r2:error] List failed for {bucket}/{prefix}: http={st}", file=sys.stderr)
        return 1
    root = ET.fromstring(body)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    rows = []
    for item in root.findall("s3:Contents", ns):
        key_el = item.find("s3:Key", ns)
        sz_el = item.find("s3:Size", ns)
        lm_el = item.find("s3:LastModified", ns)
        if key_el is None or not key_el.text:
            continue
        rows.append((key_el.text, int(sz_el.text or 0) if sz_el is not None else 0, lm_el.text if lm_el is not None else ""))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return 2
    if latest_only:
        print(rows[-1][0])
        return 0
    for k, sz, lm in rows:
        print(f"{lm}\t{sz}\t{k}")
    return 0


def prune_older(bucket: str, prefix: str, days: int) -> int:
    q = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    st, body = s3_request("GET", bucket, query=q)
    if st != 200:
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    root = ET.fromstring(body)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    for item in root.findall("s3:Contents", ns):
        key_el = item.find("s3:Key", ns)
        lm_el = item.find("s3:LastModified", ns)
        if key_el is None or lm_el is None or not key_el.text or not lm_el.text:
            continue
        ts = datetime.datetime.fromisoformat(lm_el.text.replace("Z", "+00:00"))
        if ts < cutoff:
            s3_request("DELETE", bucket, key=key_el.text)
            print(f"Pruned expired R2 object: s3://{bucket}/{key_el.text}")
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: wolinet-r2-client <ensure-bucket|put|get|list|latest|prune> ...", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "ensure-bucket":
        return ensure_bucket(sys.argv[2])
    if cmd == "put":
        return put_file(sys.argv[2], sys.argv[3], sys.argv[4])
    if cmd == "get":
        return get_file(sys.argv[2], sys.argv[3], sys.argv[4])
    if cmd == "list":
        return list_objects(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    if cmd == "latest":
        return list_objects(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "", latest_only=True)
    if cmd == "prune":
        return prune_older(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
PY
run_root chmod 0755 /usr/local/bin/wolinet-r2-client

log_header "Installing scheduled backup runner (/usr/local/bin/wolinet-backup-r2)"
run_root tee /usr/local/bin/wolinet-backup-r2 >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ -f /etc/wolinet/r2.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/wolinet/r2.env
  set +a
fi

BACKUP_ROOT="/var/backups/wolinet"
mkdir -p "${BACKUP_ROOT}"
exec 9>"${BACKUP_ROOT}/.backup.lock"
flock -n 9 || { echo "Backup already running" >&2; exit 0; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAY="$(date -u +%Y-%m-%d)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR:-}"' EXIT

# 1. Stage 1 Podman PostgreSQL 16 (Wolinex chat history in webui + Lango keys/logs in litellm)
PG_CONTAINER="$(podman ps --format '{{.Names}}' 2>/dev/null | grep -E 'wolinet.*postgres|postgres.*1' | head -n1 || true)"
if [[ -n "${PG_CONTAINER}" ]]; then
  podman exec "${PG_CONTAINER}" sh -ec 'exec pg_dumpall --clean --if-exists -U "${POSTGRES_USER:-postgres}"' \
    | gzip -c > "${WORK_DIR}/postgres_all.sql.gz"
  gzip -t "${WORK_DIR}/postgres_all.sql.gz"
fi

# 2. Stage 1 1apanel SQLite + Stage 2 Mitambo + Stage 4 Wolinex state + configs
TAR_PATHS=()
[[ -d /var/lib/wolinet/data/1panel ]] && TAR_PATHS+=(/var/lib/wolinet/data/1panel)
[[ -d /var/lib/wolinet/mitambo ]] && TAR_PATHS+=(/var/lib/wolinet/mitambo)
[[ -d /var/lib/wolinet/wolinex-web ]] && TAR_PATHS+=(/var/lib/wolinet/wolinex-web)
[[ -d /etc/wolinet ]] && TAR_PATHS+=(/etc/wolinet)
[[ -d /etc/litellm ]] && TAR_PATHS+=(/etc/litellm)
[[ -f /etc/nginx/sites-available/wolinet-edge.conf ]] && TAR_PATHS+=(/etc/nginx/sites-available/wolinet-edge.conf)

if [[ "${#TAR_PATHS[@]}" -gt 0 ]]; then
  tar --ignore-failed-read -czf "${WORK_DIR}/state_and_configs.tar.gz" "${TAR_PATHS[@]}"
fi

BUNDLE="${BACKUP_ROOT}/wolinet_backup_${STAMP}.tar.gz"
tar -C "${WORK_DIR}" -czf "${BUNDLE}" .
chmod 0600 "${BUNDLE}"

# Keep 7 days locally
find "${BACKUP_ROOT}" -type f -name 'wolinet_backup_*.tar.gz' -mtime +7 -delete

if [[ -n "${R2_ACCESS_KEY_ID:-}" && -n "${R2_SECRET_ACCESS_KEY:-}" && -n "${R2_ENDPOINT:-}" ]]; then
  BUCKET="${R2_BACKUP_BUCKET:-wolinet-backups}"
  if /usr/local/bin/wolinet-r2-client ensure-bucket "${BUCKET}"; then
    /usr/local/bin/wolinet-r2-client put "${BUCKET}" "snapshots/${DAY}/wolinet_backup_${STAMP}.tar.gz" "${BUNDLE}"
    /usr/local/bin/wolinet-r2-client prune "${BUCKET}" "snapshots/" "${R2_RETENTION_DAYS:-30}"
  else
    echo "[backup:warn] Local backup saved to ${BUNDLE}; R2 upload deferred until R2 is enabled on Cloudflare Dashboard" >&2
  fi
fi
EOF
run_root chmod 0755 /usr/local/bin/wolinet-backup-r2

log_header "Installing disaster-recovery restore tool (/usr/local/bin/wolinet-restore-r2)"
run_root tee /usr/local/bin/wolinet-restore-r2 >/dev/null <<'EOF'
#!/usr/bin/env bash
# Restore Wolinet chat history (Postgres webui + litellm), 1apanel SQLite, Mitambo, and configs from R2 or local backup.
set -euo pipefail

if [[ -f /etc/wolinet/r2.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/wolinet/r2.env
  set +a
fi

REMOTE_KEY=""
LOCAL_FILE=""
LIST_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) LIST_ONLY=1; shift ;;
    --key)  REMOTE_KEY="${2:-}"; shift 2 ;;
    --file) LOCAL_FILE="${2:-}"; shift 2 ;;
    -h|--help)
      cat <<'USAGE'
Usage:
  wolinet-restore-r2 --list                  List backups available in Cloudflare R2
  wolinet-restore-r2                         Restore latest backup snapshot from R2
  wolinet-restore-r2 --key <s3-key>          Restore a specific backup key from R2
  wolinet-restore-r2 --file <local.tar.gz>   Restore from a local backup archive
USAGE
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

BUCKET="${R2_BACKUP_BUCKET:-wolinet-backups}"
if [[ "${LIST_ONLY}" == "1" ]]; then
  exec /usr/local/bin/wolinet-r2-client list "${BUCKET}" "snapshots/"
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR:-}"' EXIT

if [[ -n "${LOCAL_FILE}" ]]; then
  ARCHIVE="${LOCAL_FILE}"
else
  if [[ -z "${REMOTE_KEY}" ]]; then
    REMOTE_KEY="$(/usr/local/bin/wolinet-r2-client latest "${BUCKET}" "snapshots/")"
  fi
  ARCHIVE="${WORK_DIR}/restore_bundle.tar.gz"
  /usr/local/bin/wolinet-r2-client get "${BUCKET}" "${REMOTE_KEY}" "${ARCHIVE}"
fi

tar -C "${WORK_DIR}" -xzf "${ARCHIVE}"

echo "[restore] Stopping application services before state restore..."
systemctl stop wolinex-web litellm-gateway mitambo 1apanel 1panel-agent >/dev/null 2>&1 || true

if [[ -f "${WORK_DIR}/state_and_configs.tar.gz" ]]; then
  echo "[restore] Restoring /var/lib/wolinet, /etc/wolinet, /etc/litellm & Nginx site config..."
  tar -C / -xzf "${WORK_DIR}/state_and_configs.tar.gz"
fi

PG_CONTAINER="$(podman ps -a --format '{{.Names}}' 2>/dev/null | grep -E 'wolinet.*postgres|postgres.*1' | head -n1 || true)"
if [[ -n "${PG_CONTAINER}" && -f "${WORK_DIR}/postgres_all.sql.gz" ]]; then
  podman start "${PG_CONTAINER}" >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do
    podman exec "${PG_CONTAINER}" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
  done
  echo "[restore] Restoring PostgreSQL databases (webui chat history + litellm)..."
  gunzip -c "${WORK_DIR}/postgres_all.sql.gz" | podman exec -i "${PG_CONTAINER}" psql -U postgres -v ON_ERROR_STOP=0 >/dev/null
fi

echo "[restore] Restarting services in 4-stage boot order..."
systemctl start 1panel-agent 1apanel mitambo litellm-gateway wolinex-web nginx || true
echo "[restore] Disaster-recovery restore completed from ${REMOTE_KEY:-${LOCAL_FILE}}"
EOF
run_root chmod 0755 /usr/local/bin/wolinet-restore-r2

if [[ "${CONFIGURE_WOLINEX_S3}" == "1" ]] && [[ -f /etc/wolinet/wolinex-web.env ]]; then
  log_header "Wiring Cloudflare R2 S3 storage into /etc/wolinet/wolinex-web.env"
  tmp_web="$(mktemp)"
  cp /etc/wolinet/wolinex-web.env "${tmp_web}"
  upsert_env_var "${tmp_web}" "STORAGE_PROVIDER" "s3"
  upsert_env_var "${tmp_web}" "STORAGE_LOCAL_CACHE" "true"
  upsert_env_var "${tmp_web}" "S3_ACCESS_KEY_ID" "${R2_ACCESS_KEY_ID}"
  upsert_env_var "${tmp_web}" "S3_SECRET_ACCESS_KEY" "${R2_SECRET_ACCESS_KEY}"
  upsert_env_var "${tmp_web}" "S3_ENDPOINT_URL" "${R2_ENDPOINT}"
  upsert_env_var "${tmp_web}" "S3_BUCKET_NAME" "${R2_STORAGE_BUCKET}"
  upsert_env_var "${tmp_web}" "S3_REGION_NAME" "auto"
  upsert_env_var "${tmp_web}" "S3_ADDRESSING_STYLE" "path"
  upsert_env_var "${tmp_web}" "S3_KEY_PREFIX" "wolinex-uploads/"
  run_root install -m 0640 "${tmp_web}" /etc/wolinet/wolinex-web.env
  id -u wolinex >/dev/null 2>&1 && run_root chown root:wolinex /etc/wolinet/wolinex-web.env || true
  rm -f "${tmp_web}"
fi

log_header "Installing systemd daily backup timer (02:30 UTC)"
run_root tee /etc/systemd/system/wolinet-backup.service >/dev/null <<'EOF'
[Unit]
Description=Wolinet AI Daily Sovereign Backup to Cloudflare R2
After=network-online.target 1apanel.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/wolinet-backup-r2
Nice=10
IOSchedulingClass=best-effort
EOF

run_root tee /etc/systemd/system/wolinet-backup.timer >/dev/null <<'EOF'
[Unit]
Description=6-Hourly Wolinet AI Sovereign Backup Timer

[Timer]
OnCalendar=*-*-* 00/6:15:00 UTC
RandomizedDelaySec=600
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Verify bucket creation cleanly (non-fatal if user has not activated R2 in Dashboard yet)
set +e
R2_ACCOUNT_ID="${R2_ACCOUNT_ID}" R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
  R2_ENDPOINT="${R2_ENDPOINT}" CLOUDFLARE_API_TOKEN="${CF_TOKEN}" \
  /usr/local/bin/wolinet-r2-client ensure-bucket "${R2_BACKUP_BUCKET}"
rc_b="$?"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID}" R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
  R2_ENDPOINT="${R2_ENDPOINT}" CLOUDFLARE_API_TOKEN="${CF_TOKEN}" \
  /usr/local/bin/wolinet-r2-client ensure-bucket "${R2_STORAGE_BUCKET}"
rc_s="$?"
set -e

if [[ "${rc_b}" != "0" || "${rc_s}" != "0" ]]; then
  log_warn "Cloudflare R2 is not activated yet on account ${R2_ACCOUNT_ID:-unknown} (Cloudflare Dashboard -> R2 Object Storage -> Enable R2)."
  log_warn "Once R2 is enabled, run: sudo /usr/local/bin/wolinet-backup-r2"
fi

if [[ "${SKIP_START}" == "0" ]] && has_systemd; then
  run_root systemctl daemon-reload
  run_root systemctl enable --now wolinet-backup.timer
  if [[ "${CONFIGURE_WOLINEX_S3}" == "1" ]] && systemctl is-enabled wolinex-web.service >/dev/null 2>&1; then
    run_root systemctl restart wolinex-web.service
    wait_http_ok "http://127.0.0.1:8081/health" 60 >/dev/null 2>&1 || true
  fi
  if [[ "${RUN_NOW}" == "1" ]]; then
    /usr/local/bin/wolinet-backup-r2 || true
  fi
fi

log_ok "R2 backup timer and storage configuration installed (/etc/wolinet/r2.env, wolinet-backup.timer)"
