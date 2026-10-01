#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "${ROOT_DIR}/.env"
set +a
EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL before requesting certificates}"
CERTS_DIR="${ROOT_DIR}/nginx/certs"

mkdir -p "${CERTS_DIR}"
mkdir -p "${ROOT_DIR}/nginx/certbot"

for domain in ai wolinex lango mitambo dev docs; do
    host="${domain}.wolinet.com"
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "${EMAIL}" \
        --domains "${host}"
    mkdir -p "${CERTS_DIR}/${host}"
    install -m 644 "/etc/letsencrypt/live/${host}/fullchain.pem" "${CERTS_DIR}/${host}/fullchain.pem"
    install -m 600 "/etc/letsencrypt/live/${host}/privkey.pem" "${CERTS_DIR}/${host}/privkey.pem"
done

echo "Certificates copied to nginx/certs. Run docker compose up after port 80 is released."
