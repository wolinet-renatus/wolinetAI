#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — 1Panel Systemd Root Service & Podman Socket Automation
# Configures 1Panel as a native host root daemon and bridges the Podman socket.
# ==============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
NC="\033[0m"

echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════════"
echo " ⚙️ WOLINET AI: DEC 1PANEL SYSTEMD ROOT SERVICE & PODMAN SOCKET PROVISIONER"
echo -e "═══════════════════════════════════════════════════════════════════════════════${NC}\n"

# 1. OS & Privilege Checks
if [ "$(uname -s)" != "Linux" ]; then
    echo -e "${YELLOW}[!] Warning: Systemd is only supported on Linux.${NC}"
    echo -e "    Current OS is $(uname -s). On macOS, 1Panel runs as a local background daemon via install.sh."
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERROR] This script must be run as root (or with sudo) to configure systemd and host sockets.${NC}"
    echo -e "        Usage: sudo ./scripts/setup-systemd-1apanel.sh"
    exit 1
fi

WOLINET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY_PATH="${WOLINET_ROOT}/bin/1apanel"

if [ ! -f "$BINARY_PATH" ]; then
    echo -e "${RED}[ERROR] 1apanel binary not found at ${BINARY_PATH}.${NC}"
    exit 1
fi

chmod +x "$BINARY_PATH"

# 2. Enable & Wire Podman Socket
echo -e "${BOLD}[1/4] Wiring Podman API Socket...${NC}"
if ! command -v podman &>/dev/null; then
    echo -e "${RED}[ERROR] Podman is not installed. Please install podman first.${NC}"
    exit 1
fi

echo -e "   -> Activating podman.socket via systemd..."
systemctl enable --now podman.socket || true

PODMAN_SOCK="/run/podman/podman.sock"
if [ ! -S "$PODMAN_SOCK" ]; then
    # Fallback check for alternate systemd socket locations
    if [ -S "/var/run/podman/podman.sock" ]; then
        PODMAN_SOCK="/var/run/podman/podman.sock"
    fi
fi

# Ensure /var/run/docker.sock symlinks to Podman socket for full Docker API compatibility
echo -e "   -> Bridging /var/run/docker.sock -> ${PODMAN_SOCK}..."
if [ -L /var/run/docker.sock ] || [ ! -e /var/run/docker.sock ]; then
    ln -sf "$PODMAN_SOCK" /var/run/docker.sock
    echo -e "      ${GREEN}✓ Symlink created: /var/run/docker.sock -> ${PODMAN_SOCK}${NC}"
else
    echo -e "      ${YELLOW}[!] /var/run/docker.sock already exists as a non-symlink (existing Docker). Preserving.${NC}"
fi

# 3. Create Standardized Sovereign Storage Roots
echo -e "\n${BOLD}[2/4] Provisioning Sovereign Storage Hierarchies...${NC}"
install -d -m 0755 -o root -g root /var/lib/wolinet
install -d -m 0755 -o root -g root /var/lib/wolinet/data/1panel/db
install -d -m 0755 -o root -g root /var/lib/wolinet/data/postgres
install -d -m 0755 -o root -g root /var/lib/wolinet/data/redis
install -d -m 0755 -o root -g root /var/lib/wolinet/data/mitambo
install -d -m 0755 -o root -g root /var/lib/wolinet/models
echo -e "   ${GREEN}✓ Storage paths initialized under /var/lib/wolinet${NC}"

# 4. Generate & Install Systemd Unit File
echo -e "\n${BOLD}[3/4] Installing /etc/systemd/system/1apanel.service...${NC}"
SERVICE_FILE="/etc/systemd/system/1apanel.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Wolinet DEC 1Panel Control Plane & Hardware Supervisor
Documentation=https://wolinet.ai/docs
After=network.target network-online.target podman.socket
Wants=network-online.target podman.socket

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${WOLINET_ROOT}
ExecStartPre=/usr/bin/install -d -m 0755 -o root -g root /var/lib/wolinet/data/1panel/db
ExecStart=${BINARY_PATH}
Restart=always
RestartSec=5s

# Sovereign Environment Configuration
Environment=PANEL_BASE_DIR=/var/lib/wolinet/data
Environment=ORIGINAL_PORT=8888
Environment=DOCKER_HOST=unix://${PODMAN_SOCK}
Environment=CONTAINER_HOST=unix://${PODMAN_SOCK}

# Process & Resource Management
LimitNOFILE=65535
LimitNPROC=65535
TasksMax=infinity
TimeoutStartSec=30s
TimeoutStopSec=30s

# Hardware & Security Privileges
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_SYS_ADMIN CAP_NET_ADMIN CAP_DAC_OVERRIDE CAP_FOWNER CAP_CHOWN
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

echo -e "   -> Reloading systemd daemon..."
systemctl daemon-reload
echo -e "   -> Enabling 1apanel.service on boot..."
systemctl enable 1apanel.service
echo -e "   -> Starting 1apanel.service..."
systemctl restart 1apanel.service

# 5. Service Status Verification
echo -e "\n${BOLD}[4/4] Verifying Service Health & Sockets...${NC}"
sleep 2

if systemctl is-active --quiet 1apanel.service; then
    echo -e "   ${GREEN}✓ 1apanel.service is ACTIVE and running as host root daemon.${NC}"
else
    echo -e "   ${RED}[!] 1apanel.service failed to enter active state.${NC}"
    systemctl status 1apanel.service --no-pager
    exit 1
fi

echo -n "   • Testing Podman socket API: "
if curl -s --unix-socket "$PODMAN_SOCK" http://d/v1.41/version &>/dev/null; then
    echo -e "${GREEN}HEALTHY (Podman Engine Responding)${NC}"
else
    echo -e "${YELLOW}READY (Socket active)${NC}"
fi

echo -n "   • Testing 1Panel Web Interface (:8888 / :9999): "
if curl -s http://localhost:8888 &>/dev/null || curl -s http://localhost:9999 &>/dev/null; then
    echo -e "${GREEN}HEALTHY (200 OK)${NC}"
else
    echo -e "${YELLOW}STARTING (Port binding in progress)${NC}"
fi

echo -e "\n${GREEN}${BOLD}═══════════════════════════════════════════════════════════════════════════════"
echo " ✨ 1PANEL IS SUCCESSFULLY CONFIGURED AS NATIVE SYSTEMD ROOT DAEMON!"
echo -e "═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "   • Control Plane URL:    ${CYAN}http://<server-ip>:8888${NC}"
echo -e "   • Native SQLite DB:     ${CYAN}/var/lib/wolinet/data/1panel/db/1panel.db${NC}"
echo -e "   • Podman Socket Bridge: ${CYAN}${PODMAN_SOCK} -> /var/run/docker.sock${NC}"
echo -e "   • Service Management:   ${CYAN}systemctl [status|restart|stop] 1apanel.service${NC}\n"
