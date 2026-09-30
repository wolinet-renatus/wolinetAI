#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/backups}"
if [[ "${BACKUP_DIR}" != /* ]]; then
  BACKUP_DIR="${REPO_ROOT}/${BACKUP_DIR}"
fi

mkdir -p -- "${BACKUP_DIR}"
cd -- "${REPO_ROOT}"

if ! command -v docker >/dev/null 2>&1 || ! command -v gzip >/dev/null 2>&1 || ! command -v flock >/dev/null 2>&1; then
  echo "docker, gzip, and flock must be installed on the host" >&2
  exit 1
fi

exec 9>"${BACKUP_DIR}/.postgres-backup.lock"
if ! flock -n 9; then
  echo "Another PostgreSQL backup is already running" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%d_%H%M%S)"
backup_file="${BACKUP_DIR}/wolinet_db_${timestamp}.sql.gz"
tmp_file="$(mktemp "${BACKUP_DIR}/.wolinet_db_${timestamp}.sql.gz.tmp.XXXXXX")"
cleanup() {
  if [[ -n "${tmp_file:-}" ]]; then
    rm -f -- "${tmp_file}"
  fi
}
trap cleanup EXIT

# -T prevents a pseudo-TTY from altering the binary-safe pg_dumpall stream.
# Read POSTGRES_USER inside the container so customized Compose credentials work.
docker compose exec -T postgres sh -ec 'exec pg_dumpall -U "${POSTGRES_USER:-postgres}"' \
  | gzip -c > "${tmp_file}"

if [[ ! -s "${tmp_file}" ]]; then
  echo "PostgreSQL dump produced an empty archive" >&2
  exit 1
fi
gzip -t -- "${tmp_file}"
mv -- "${tmp_file}" "${backup_file}"
tmp_file=""

# Keep only this script's generated database archives; leave unrelated files alone.
find "${BACKUP_DIR}" -type f -name 'wolinet_db_*.sql.gz' -mtime +7 -delete

echo "PostgreSQL backup created: ${backup_file}"
