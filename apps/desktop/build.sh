#!/usr/bin/env bash
# ==============================================================================
# Build Wolinet AI Desktop (Native Intel macOS App)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WEB_CLIENT_DIR="${ROOT_DIR}/apps/web-client"

echo "[Wolinet Desktop] Compiling native Intel macOS app bundle..."
cd "${WEB_CLIENT_DIR}"
npm run desktop:build

echo "[Wolinet Desktop] Syncing built bundle to apps/desktop/WolinetAI.app..."
rm -rf "${SCRIPT_DIR}/WolinetAI.app"
cp -R "${WEB_CLIENT_DIR}/release-artifacts/Litespeed.app" "${SCRIPT_DIR}/WolinetAI.app"

echo "[Wolinet Desktop] Build complete! You can run ./apps/desktop/run.sh or open WolinetAI.app"
