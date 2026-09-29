#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — TLS Certificate Setup Script
# Run ONCE on the Contabo server before starting the nginx container.
# Requires: certbot installed on the host (apt install certbot)
# ==============================================================================
set -euo pipefail

DOMAINS=(
    "ai.wolinet.com"
    "wolinex.wolinet.com"
    "lango.wolinet.com"
    "mitambo.wolinet.com"
    "dev.wolinet.com"
)

EMAIL="devops@wolinet.com"   # ← Change to your admin email
NGINX_CERTS_DIR="./nginx/certs"
WEBROOT="/var/www/certbot"

mkdir -p "$WEBROOT" "$NGINX_CERTS_DIR"

echo "==> Generating DH parameters (this takes ~2min, runs once)..."
if [ ! -f "./nginx/dhparam.pem" ]; then
    openssl dhparam -out ./nginx/dhparam.pem 2048
    echo "    dhparam.pem generated."
else
    echo "    dhparam.pem already exists, skipping."
fi

for DOMAIN in "${DOMAINS[@]}"; do
    echo "==> Issuing certificate for ${DOMAIN}..."
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --domains "$DOMAIN" \
        --expand

    CERT_DIR="$NGINX_CERTS_DIR/$DOMAIN"
    mkdir -p "$CERT_DIR"
    ln -sf "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
    ln -sf "/etc/letsencrypt/live/$DOMAIN/privkey.pem"   "$CERT_DIR/privkey.pem"
    echo "    Certificate linked to $CERT_DIR"
done

echo ""
echo "==> All certificates provisioned!"
echo "    Add this cron to auto-renew (certbot renew + nginx reload):"
echo "    0 3 * * 1 certbot renew --quiet && docker exec wolinet-nginx nginx -s reload"
