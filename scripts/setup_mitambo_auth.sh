#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [ ! -f "${ENV_FILE}" ]; then
    echo "Missing production .env in ${ROOT_DIR}" >&2
    exit 1
fi

set -a
source "${ENV_FILE}"
set +a

: "${MITAMBO_ADMIN_USER:?Set MITAMBO_ADMIN_USER in .env}"
: "${MITAMBO_ADMIN_PASSWORD:?Set MITAMBO_ADMIN_PASSWORD in .env}"

case "${MITAMBO_ADMIN_PASSWORD}" in
    CHANGE_ME*|password|admin)
        echo "MITAMBO_ADMIN_PASSWORD must be replaced with a unique password" >&2
        exit 1
        ;;
esac

if [ "${#MITAMBO_ADMIN_PASSWORD}" -lt 20 ] || [[ "${MITAMBO_ADMIN_USER}" == *:* ]]; then
    echo "Use a password of at least 20 characters and a username without colons" >&2
    exit 1
fi

SECRET_DIR="${ROOT_DIR}/nginx/secrets"
mkdir -p "${SECRET_DIR}"
umask 077
HASH="$(printf '%s' "${MITAMBO_ADMIN_PASSWORD}" | openssl passwd -6 -stdin)"
printf '%s:%s\n' "${MITAMBO_ADMIN_USER}" "${HASH}" > "${SECRET_DIR}/mitambo.htpasswd"
chmod 600 "${SECRET_DIR}/mitambo.htpasswd"
echo "Mitambo Nginx credentials written to nginx/secrets/mitambo.htpasswd"
