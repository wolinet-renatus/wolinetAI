#!/usr/bin/env bash
# Configure Host Nginx + Cloudflare Origin TLS + UFW + systemd-resolved + optional Cloudflare DNS
# on a single Contabo Ubuntu 24.04 server while keeping all inter-product hops on 127.0.0.1.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/installer_common.sh
source "${ROOT_DIR}/scripts/lib/installer_common.sh"

DOMAIN="${WOLINET_DOMAIN:-wolinet.com}"
PANEL_HOST=""
MITAMBO_HOST_FQDN=""
LANGO_HOST_FQDN=""
WOLINEX_HOST_FQDN=""
ORIGIN_CERT="${CLOUDFLARE_ORIGIN_CERT:-}"
ORIGIN_KEY="${CLOUDFLARE_ORIGIN_KEY:-}"
LANGO_UI_DIR="${WOLINET_LANGO_UI_DIR:-}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
CF_ZONE_ID="${CLOUDFLARE_ZONE_ID:-}"
PUBLIC_IP="${WOLINET_PUBLIC_IP:-}"
CF_PROXIED="${CLOUDFLARE_PROXIED:-true}"
EXTRA_PORTS="${EXTRA_OPEN_PORTS:-}"
SKIP_UFW=0
ALLOW_DIRECT_HTTP=0
SKIP_RESTART=0

usage() {
  cat <<'EOF'
Wolinet Contabo Ubuntu 24.04 Edge & Cloudflare Setup

Routes external HTTPS (*.wolinet.com) via Host Nginx -> 127.0.0.1:<port> so all 4
products have full browser Admin GUI & API access while internal hops stay on loopback.

Usage:
  setup-contabo-edge.sh [options]

Options:
  --domain <domain>            Root Cloudflare domain (default: wolinet.com)
  --panel-host <fqdn>          1apanel FQDN (default: panel.<domain>)
  --mitambo-host <fqdn>        Mitambo FQDN (default: mitambo.<domain>)
  --lango-host <fqdn>          Lango Gateway + /ui FQDN (default: lango.<domain>)
  --wolinex-host <fqdn>        Wolinex Web FQDN (default: wolinex.<domain>)
  --origin-cert <path>         Cloudflare Origin CA PEM certificate path
  --origin-key <path>          Cloudflare Origin CA private key path
  --lango-ui-dir <dir>         Static Next.js export dir for Lango /ui
  --cloudflare-token <token>   Cloudflare API token to upsert proxied A records
  --cloudflare-zone-id <id>    Optional explicit Cloudflare Zone ID
  --public-ip <ipv4>           Server public IPv4 (auto-detected if omitted)
  --extra-open-ports <list>    Comma-separated extra ufw ports (e.g. "9000/tcp,9001/udp")
  --allow-direct-http          Allow 80/443 from any IP instead of Cloudflare CIDRs only
  --skip-ufw                   Do not modify ufw rules
  --skip-restart               Write configs & test 'nginx -t' without restarting daemons
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)             DOMAIN="${2:-wolinet.com}"; shift 2 ;;
    --panel-host)         PANEL_HOST="${2:-}"; shift 2 ;;
    --mitambo-host)       MITAMBO_HOST_FQDN="${2:-}"; shift 2 ;;
    --lango-host)         LANGO_HOST_FQDN="${2:-}"; shift 2 ;;
    --wolinex-host)       WOLINEX_HOST_FQDN="${2:-}"; shift 2 ;;
    --origin-cert)        ORIGIN_CERT="${2:-}"; shift 2 ;;
    --origin-key)         ORIGIN_KEY="${2:-}"; shift 2 ;;
    --lango-ui-dir)       LANGO_UI_DIR="${2:-}"; shift 2 ;;
    --cloudflare-token)   CF_TOKEN="${2:-}"; shift 2 ;;
    --cloudflare-zone-id) CF_ZONE_ID="${2:-}"; shift 2 ;;
    --public-ip)          PUBLIC_IP="${2:-}"; shift 2 ;;
    --extra-open-ports)   EXTRA_PORTS="${2:-}"; shift 2 ;;
    --allow-direct-http)  ALLOW_DIRECT_HTTP=1; shift ;;
    --skip-ufw)           SKIP_UFW=1; shift ;;
    --skip-restart)       SKIP_RESTART=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *)                    die "Unknown option: $1 (try --help)" ;;
  esac
done

detect_platform
[[ "${HOST_OS}" == "linux" ]] || die "setup-contabo-edge.sh must run on the Linux server host"

PANEL_HOST="${PANEL_HOST:-panel.${DOMAIN}}"
MITAMBO_HOST_FQDN="${MITAMBO_HOST_FQDN:-mitambo.${DOMAIN}}"
LANGO_HOST_FQDN="${LANGO_HOST_FQDN:-lango.${DOMAIN}}"
WOLINEX_HOST_FQDN="${WOLINEX_HOST_FQDN:-wolinex.${DOMAIN}}"

CERT_DIR="/etc/nginx/certs/${DOMAIN}"
CERT_PEM="${CERT_DIR}/origin.crt"
KEY_PEM="${CERT_DIR}/origin.key"
TARGET_UI_DIR="/opt/wolinet/lango/ui"

configure_resolved_dns() {
  log_header "Configuring systemd-resolved reliable upstream DNS"
  run_root install -d -m 0755 /etc/systemd/resolved.conf.d
  run_root tee /etc/systemd/resolved.conf.d/99-wolinet-dns.conf >/dev/null <<'EOF'
[Resolve]
DNS=1.1.1.1 9.9.9.9
FallbackDNS=8.8.8.8 1.0.0.1
DNSStubListener=yes
EOF
  if [[ "${SKIP_RESTART}" == "0" ]] && has_systemd; then
    run_root systemctl reload-or-restart systemd-resolved >/dev/null 2>&1 || true
  fi
  log_ok "Configured DNS resolvers (1.1.1.1, 9.9.9.9) in /etc/systemd/resolved.conf.d/99-wolinet-dns.conf"
}

ensure_loopback_bindings() {
  log_header "Pinning inter-product upstreams strictly to 127.0.0.1"
  update_env_file() {
    local fpath="$1" owner="$2" mode="$3"
    shift 3
    [[ -f "${fpath}" ]] || return 0
    local tmp
    tmp="$(mktemp)"
    cp "${fpath}" "${tmp}"
    while [[ $# -ge 2 ]]; do
      upsert_env_var "${tmp}" "$1" "$2"
      shift 2
    done
    run_root install -m "${mode}" "${tmp}" "${fpath}"
    [[ -n "${owner}" ]] && run_root chown "${owner}" "${fpath}" || true
    rm -f "${tmp}"
  }

  local mit_owner="root:root"
  id -u mitambo >/dev/null 2>&1 && mit_owner="root:mitambo"
  update_env_file "/etc/wolinet/mitambo.env" "${mit_owner}" 0640 \
    "MITAMBO_HOST" "127.0.0.1" \
    "XINFERENCE_AUTH_ADVANCED" "true"

  local lango_owner="root:root"
  id -u litellm >/dev/null 2>&1 && lango_owner="root:litellm"
  update_env_file "/etc/litellm/env" "${lango_owner}" 0640 \
    "HOST" "127.0.0.1" \
    "PORT" "4000"

  local web_owner="root:root"
  id -u wolinex >/dev/null 2>&1 && web_owner="root:wolinex"
  update_env_file "/etc/wolinet/wolinex-web.env" "${web_owner}" 0640 \
    "HOST" "127.0.0.1" \
    "PORT" "8081" \
    "LITELLM_BASE_URL" "http://127.0.0.1:4000" \
    "OPENAI_API_BASE_URL" "http://127.0.0.1:4000/v1" \
    "OPENAI_API_BASE_URLS" "http://127.0.0.1:4000/v1"

  log_ok "Service listeners pinned to loopback (127.0.0.1:8888, 9997, 4000, 8081)"
}

stage_lango_static_ui() {
  local src="${LANGO_UI_DIR}"
  if [[ -z "${src}" ]]; then
    for cand in \
      "${TARGET_UI_DIR}" \
      "${ROOT_DIR}/dist/installers/server/lango/ui" \
      "${ROOT_DIR}/gateway/ui/litellm-dashboard/out"; do
      if [[ -d "${cand}" && -f "${cand}/index.html" ]]; then
        src="${cand}"
        break
      fi
    done
  fi
  run_root install -d -m 0755 "${TARGET_UI_DIR}"
  if [[ -n "${src}" && -d "${src}" && "${src}" != "${TARGET_UI_DIR}" ]]; then
    run_root rm -rf "${TARGET_UI_DIR:?}/"*
    run_root cp -R "${src}/." "${TARGET_UI_DIR}/"
    log_ok "Staged Lango static /ui export into ${TARGET_UI_DIR}"
  elif [[ -f "${TARGET_UI_DIR}/index.html" ]]; then
    log_ok "Using existing Lango static /ui export at ${TARGET_UI_DIR}"
  else
    log_warn "No Lango dashboard static export found; ${LANGO_HOST_FQDN}/ui will return 404 until populated in ${TARGET_UI_DIR}"
  fi
}

stage_tls_certificates() {
  run_root install -d -m 0700 "${CERT_DIR}"
  if [[ -n "${ORIGIN_CERT}" && -n "${ORIGIN_KEY}" ]]; then
    [[ -f "${ORIGIN_CERT}" && -f "${ORIGIN_KEY}" ]] || die "Origin cert/key not found: ${ORIGIN_CERT}, ${ORIGIN_KEY}"
    run_root install -m 0644 "${ORIGIN_CERT}" "${CERT_PEM}"
    run_root install -m 0600 "${ORIGIN_KEY}" "${KEY_PEM}"
    log_ok "Installed Cloudflare Origin CA certificate in ${CERT_DIR}"
    return 0
  fi

  if [[ -f "${CERT_PEM}" && -f "${KEY_PEM}" ]]; then
    log_ok "Preserving existing TLS certificate in ${CERT_DIR}"
    return 0
  fi

  command -v openssl >/dev/null 2>&1 || die "openssl is required to generate fallback origin cert when --origin-cert is omitted"
  log_warn "Generating temporary self-signed origin cert in ${CERT_DIR} (replace with 15-year Cloudflare Origin CA PEM for Full Strict)"
  run_root openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -keyout "${KEY_PEM}" \
    -out "${CERT_PEM}" \
    -subj "/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN}" >/dev/null 2>&1
  run_root chmod 0600 "${KEY_PEM}"
  run_root chmod 0644 "${CERT_PEM}"
}

write_nginx_config() {
  log_header "Configuring Host Nginx edge reverse proxy for *.${DOMAIN}"
  command -v nginx >/dev/null 2>&1 || die "nginx is not installed (run: apt-get install -y nginx)"

  run_root install -d -m 0755 /etc/nginx/conf.d /etc/nginx/snippets /etc/nginx/sites-available /etc/nginx/sites-enabled

  run_root tee /etc/nginx/conf.d/00-wolinet-ws.conf >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
EOF

  run_root tee /etc/nginx/snippets/wolinet-cloudflare.conf >/dev/null <<'EOF'
# Restore true client IP from Cloudflare Edge
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
real_ip_header CF-Connecting-IP;
real_ip_recursive on;

proxy_http_version 1.1;
proxy_socket_keepalive on;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
EOF

  run_root tee /etc/nginx/sites-available/wolinet-edge.conf >/dev/null <<EOF
# Wolinet Sovereign Single-Server Edge Proxy (${DOMAIN})
# External HTTPS terminates at Nginx -> internal loopback services on 127.0.0.1.

server {
    listen 80;
    listen [::]:80;
    server_name ${PANEL_HOST} ${MITAMBO_HOST_FQDN} ${LANGO_HOST_FQDN} ${WOLINEX_HOST_FQDN};
    return 301 https://\$host\$request_uri;
}

# 1. Stage 1: DEC 1apanel Admin GUI & WebSocket Terminal (:8888)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${PANEL_HOST};

    ssl_certificate     ${CERT_PEM};
    ssl_certificate_key ${KEY_PEM};
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 512m;

    location / {
        include /etc/nginx/snippets/wolinet-cloudflare.conf;
        proxy_pass http://127.0.0.1:8888;
        proxy_buffering off;
        proxy_cache off;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}

# 2. Stage 2: Mitambo Admin GUI & Inference API (:9997)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${MITAMBO_HOST_FQDN};

    ssl_certificate     ${CERT_PEM};
    ssl_certificate_key ${KEY_PEM};
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 1024m;

    location / {
        include /etc/nginx/snippets/wolinet-cloudflare.conf;
        proxy_pass http://127.0.0.1:9997;
        proxy_buffering off;
        proxy_cache off;
        add_header X-Accel-Buffering no always;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}

# 3. Stage 3: Lango Admin Dashboard (/ui static SPA) + AI Gateway API (:4000)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${LANGO_HOST_FQDN};

    ssl_certificate     ${CERT_PEM};
    ssl_certificate_key ${KEY_PEM};
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 100m;

    location = /ui {
        return 301 /ui/;
    }

    location ^~ /litellm-asset-prefix/ {
        rewrite ^/litellm-asset-prefix/(.*)\$ /\$1 break;
        root ${TARGET_UI_DIR};
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location ^~ /_next/ {
        root ${TARGET_UI_DIR};
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location ^~ /ui/ {
        rewrite ^/ui/?(.*)\$ /\$1 break;
        root ${TARGET_UI_DIR};
        try_files \$uri \$uri/index.html \$uri.html /index.html =404;
    }

    location / {
        include /etc/nginx/snippets/wolinet-cloudflare.conf;
        proxy_pass http://127.0.0.1:4000;
        proxy_buffering off;
        proxy_cache off;
        add_header X-Accel-Buffering no always;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}

# 4. Stage 4: Wolinex Web Portal GUI, WebSockets & SSE (:8081)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${WOLINEX_HOST_FQDN};

    ssl_certificate     ${CERT_PEM};
    ssl_certificate_key ${KEY_PEM};
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 200m;
    keepalive_timeout 600s;

    location ^~ /socket.io/ {
        include /etc/nginx/snippets/wolinet-cloudflare.conf;
        proxy_pass http://127.0.0.1:8081;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
        add_header X-Accel-Buffering no always;
        proxy_connect_timeout 60s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;
    }

    location / {
        include /etc/nginx/snippets/wolinet-cloudflare.conf;
        proxy_pass http://127.0.0.1:8081;
        proxy_buffering off;
        proxy_cache off;
        add_header X-Accel-Buffering no always;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
EOF

  run_root rm -f /etc/nginx/sites-enabled/default
  run_root ln -sf /etc/nginx/sites-available/wolinet-edge.conf /etc/nginx/sites-enabled/wolinet-edge.conf
  run_root nginx -t
  if [[ "${SKIP_RESTART}" == "0" ]] && has_systemd; then
    run_root systemctl enable --now nginx
    run_root systemctl reload nginx
  fi
  log_ok "Nginx edge vhosts active and validated ('nginx -t')"
}

configure_ufw_firewall() {
  if [[ "${SKIP_UFW}" == "1" ]]; then
    log_info "Skipping UFW firewall configuration (--skip-ufw)"
    return 0
  fi
  if ! command -v ufw >/dev/null 2>&1; then
    log_warn "ufw not installed; install via 'apt-get install -y ufw' before enforcing firewall rules"
    return 0
  fi

  log_header "Hardening UFW firewall (Cloudflare + SSH + EXTRA_OPEN_PORTS)"
  run_root ufw default deny incoming >/dev/null
  run_root ufw default allow outgoing >/dev/null
  run_root ufw allow 22/tcp comment 'SSH' >/dev/null

  # Explicitly deny direct internet access to internal backend ports
  for internal_port in 8888/tcp 9997/tcp 4000/tcp 8081/tcp 5433/tcp 6379/tcp; do
    run_root ufw deny "${internal_port}" >/dev/null || true
  done

  if [[ "${ALLOW_DIRECT_HTTP}" == "1" ]]; then
    run_root ufw allow 80/tcp >/dev/null
    run_root ufw allow 443/tcp >/dev/null
  else
    local cf_cidrs=(
      173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22
      141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20
      197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13
      104.24.0.0/14 172.64.0.0/13 131.0.72.0/22
      2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32
      2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32
    )
    local cidr
    for cidr in "${cf_cidrs[@]}"; do
      run_root ufw allow from "${cidr}" to any port 80 proto tcp comment 'Cloudflare HTTP' >/dev/null || true
      run_root ufw allow from "${cidr}" to any port 443 proto tcp comment 'Cloudflare HTTPS' >/dev/null || true
    done
  fi

  if [[ -n "${EXTRA_PORTS}" ]]; then
    local IFS=','
    read -ra extra_arr <<< "${EXTRA_PORTS}"
    for port_spec in "${extra_arr[@]}"; do
      port_spec="${port_spec//[[:space:]]/}"
      [[ -n "${port_spec}" ]] || continue
      run_root ufw allow "${port_spec}" comment 'EXTRA_OPEN_PORTS' >/dev/null
      log_ok "Opened EXTRA_OPEN_PORTS entry in ufw: ${port_spec}"
    done
  fi

  run_root ufw --force enable >/dev/null || true
  log_ok "UFW enabled"
}

upsert_cloudflare_dns() {
  if [[ -z "${CF_TOKEN}" ]]; then
    log_info "CLOUDFLARE_API_TOKEN not set; skipping automated Cloudflare DNS upsert"
    return 0
  fi

  if [[ -z "${PUBLIC_IP}" ]]; then
    PUBLIC_IP="$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null || true)"
  fi
  [[ -n "${PUBLIC_IP}" ]] || die "Unable to detect public IPv4 automatically; pass --public-ip <ipv4>"

  log_header "Upserting Cloudflare A records (${DOMAIN} -> ${PUBLIC_IP}, proxied=${CF_PROXIED})"
  python3 - "${CF_TOKEN}" "${DOMAIN}" "${CF_ZONE_ID}" "${PUBLIC_IP}" "${CF_PROXIED}" \
    "${PANEL_HOST}" "${MITAMBO_HOST_FQDN}" "${LANGO_HOST_FQDN}" "${WOLINEX_HOST_FQDN}" <<'PY'
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

token, domain, zone_id, target_ip, proxied_str, *hosts = sys.argv[1:]
proxied = proxied_str.lower() in ("1", "true", "yes")
base = "https://api.cloudflare.com/client/v4"

def cf_req(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    if not parsed.get("success"):
        raise RuntimeError(f"Cloudflare API failed for {path}: {parsed.get('errors')}")
    return parsed["result"]

if not zone_id:
    zones = cf_req("GET", f"/zones?name={urllib.parse.quote(domain)}")
    if not zones:
        raise RuntimeError(f"Zone not found in Cloudflare account for domain: {domain}")
    zone_id = zones[0]["id"]

for fqdn in hosts:
    q = urllib.parse.urlencode({"type": "A", "name": fqdn})
    existing = cf_req("GET", f"/zones/{zone_id}/dns_records?{q}")
    body = {"type": "A", "name": fqdn, "content": target_ip, "ttl": 1, "proxied": proxied}
    if existing:
        rec_id = existing[0]["id"]
        cf_req("PUT", f"/zones/{zone_id}/dns_records/{rec_id}", body)
        print(f"  updated A {fqdn} -> {target_ip} (proxied={proxied})")
    else:
        cf_req("POST", f"/zones/{zone_id}/dns_records", body)
        print(f"  created A {fqdn} -> {target_ip} (proxied={proxied})")
PY
}

configure_resolved_dns
ensure_loopback_bindings
stage_lango_static_ui
stage_tls_certificates
write_nginx_config
configure_ufw_firewall
upsert_cloudflare_dns

if [[ "${SKIP_RESTART}" == "0" ]] && has_systemd; then
  log_header "Restarting Mitambo, Lango & Wolinex Web to apply 127.0.0.1 & GUI env updates"
  run_root systemctl restart mitambo litellm-gateway wolinex-web
fi

log_ok "Contabo edge & Cloudflare routing ready:"
log_info "  1apanel Admin GUI  : https://${PANEL_HOST} (internal http://127.0.0.1:8888)"
log_info "  Mitambo GUI & API  : https://${MITAMBO_HOST_FQDN} (internal http://127.0.0.1:9997)"
log_info "  Lango Dashboard/API: https://${LANGO_HOST_FQDN}/ui & /v1 (internal http://127.0.0.1:4000)"
log_info "  Wolinex Web Portal : https://${WOLINEX_HOST_FQDN} (internal http://127.0.0.1:8081)"
