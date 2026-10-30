#!/usr/bin/env bash
# ==============================================================================
# Wolinet PMP (Platform Package Manager) Installer
# Installs 'pmp' CLI automation tool for Wolinet AI SDKs
# ==============================================================================
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "${INSTALL_DIR}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [ -n "${SCRIPT_DIR}" ] && [ -f "${SCRIPT_DIR}/pmp" ]; then
    cp "${SCRIPT_DIR}/pmp" "${INSTALL_DIR}/pmp"
    chmod +x "${INSTALL_DIR}/pmp"
else
    # Remote installer fallback
    echo "==> Fetching pmp CLI tool..."
    curl -fsSL https://raw.githubusercontent.com/wolinet/wolinetai/main/scripts/pmp -o "${INSTALL_DIR}/pmp" || {
        echo "Error: Failed to download pmp CLI."
        exit 1
    }
    chmod +x "${INSTALL_DIR}/pmp"
fi

echo "=========================================================="
echo " Wolinet Platform Package Manager (pmp) installed!"
echo " Location: ${INSTALL_DIR}/pmp"
echo "=========================================================="

case ":$PATH:" in
    *":${INSTALL_DIR}:"*) ;;
    *)
        echo "Tip: Add ~/.local/bin to your PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac

echo ""
echo "Run 'pmp status' to inspect available client SDKs."
