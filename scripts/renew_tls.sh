#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="${ROOT_DIR}/nginx/certs"
CHALLENGE_DIR="${ROOT_DIR}/nginx/certbot"

mkdir -p "${CHALLENGE_DIR}"
certbot renew --quiet --authenticator webroot --webroot-path "${CHALLENGE_DIR}"

for domain in ai wolinex lango mitambo dev; do
    host="${domain}.wolinet.com"
    install -m 644 "/etc/letsencrypt/live/${host}/fullchain.pem" "${CERTS_DIR}/${host}/fullchain.pem"
    install -m 600 "/etc/letsencrypt/live/${host}/privkey.pem" "${CERTS_DIR}/${host}/privkey.pem"
done

docker compose --project-name wolinet --file "${ROOT_DIR}/docker-compose.prod.yml" exec -T nginx nginx -t
docker compose --project-name wolinet --file "${ROOT_DIR}/docker-compose.prod.yml" exec -T nginx nginx -s reload
