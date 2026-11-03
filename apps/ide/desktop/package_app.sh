#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${IDE_DIR}/../.." && pwd)"
OUT_DIR="${IDE_DIR}/out/WolinexCode-darwin-x64"
BASE_APP="${ROOT_DIR}/apps/WolinexIde/ui/desktop/out/Wolinex-darwin-x64/Wolinex.app"

if [ ! -d "${BASE_APP}" ] && [ -d "/Applications/Wolinex.app" ]; then
  BASE_APP="/Applications/Wolinex.app"
fi

echo "=========================================================="
echo " 📦 Packaging Standalone Wolinex Code IDE (WolinexCode.app)"
echo " Engine: OpenIDEA Rust Backend + High-Perf Workbench UI"
echo " Base Application: ${BASE_APP}"
echo "=========================================================="

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

TARGET_APP="${OUT_DIR}/WolinexCode.app"
cp -R "${BASE_APP}" "${TARGET_APP}"

echo "1. Configuring bundle properties and URL scheme..."
PLIST="${TARGET_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName 'WolinexCode'" "${PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName 'Wolinex Code'" "${PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier 'com.wolinet.wolinexcode'" "${PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable 'WolinexCode'" "${PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleURLTypes:0:CFBundleURLName 'WolinexCodeProtocol'" "${PLIST}" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleURLTypes:0:CFBundleURLSchemes:0 'wolinex-code'" "${PLIST}" 2>/dev/null || true

# Rename main binary
if [ -f "${TARGET_APP}/Contents/MacOS/Wolinex" ]; then
  mv "${TARGET_APP}/Contents/MacOS/Wolinex" "${TARGET_APP}/Contents/MacOS/WolinexCode"
fi

# Rename helper apps in Frameworks to match CFBundleName
cd "${TARGET_APP}/Contents/Frameworks"
for app in "Wolinex Helper"*; do
  if [ -d "$app" ]; then
    new_app="${app/Wolinex /WolinexCode }"
    mv "$app" "$new_app"
    if [ -d "$new_app/Contents/MacOS" ]; then
      for bin in "$new_app/Contents/MacOS/Wolinex Helper"*; do
        if [ -f "$bin" ]; then
          new_bin="${bin/Wolinex /WolinexCode }"
          mv "$bin" "$new_bin" 2>/dev/null || true
          /usr/libexec/PlistBuddy -c "Set :CFBundleExecutable '$(basename "$new_bin")'" "$new_app/Contents/Info.plist" 2>/dev/null || true
        fi
      done
    fi
  fi
done

echo "2. Packing Wolinex Code app.asar..."
TMP_SRC="/tmp/wolinex_code_bundle_$$"
mkdir -p "${TMP_SRC}/src"
cp "${SCRIPT_DIR}/package.json" "${TMP_SRC}/"
cp "${SCRIPT_DIR}/src/main.cjs" "${TMP_SRC}/src/"
cp "${SCRIPT_DIR}/src/preload.cjs" "${TMP_SRC}/src/"
if [ -f "${SCRIPT_DIR}/src/languages.json" ]; then
  cp "${SCRIPT_DIR}/src/languages.json" "${TMP_SRC}/src/"
fi
cp -R "${IDE_DIR}/dist" "${TMP_SRC}/dist"

ASAR_CLI="${ROOT_DIR}/apps/WolinexIde/ui/node_modules/.bin/asar"
"${ASAR_CLI}" pack "${TMP_SRC}" "${TARGET_APP}/Contents/Resources/app.asar"
rm -rf "${TMP_SRC}"

# Compute header integrity hash for ASAR directly with Node (prevents triggering SIGTRAP / macOS crash reporter)
echo "3. Calculating ASAR integrity hash..."
ASAR_FILE="${TARGET_APP}/Contents/Resources/app.asar"
CALCULATED_HASH=$(node -e '
const fs = require("fs");
const crypto = require("crypto");
const asarPath = process.argv[1];
const fd = fs.openSync(asarPath, "r");
const headerSizeBuf = Buffer.alloc(16);
fs.readSync(fd, headerSizeBuf, 0, 16, 0);
const jsonLen = headerSizeBuf.readUInt32LE(12);
const jsonBuf = Buffer.alloc(jsonLen);
fs.readSync(fd, jsonBuf, 0, jsonLen, 16);
fs.closeSync(fd);
process.stdout.write(crypto.createHash("sha256").update(jsonBuf).digest("hex"));
' "${ASAR_FILE}")

if [ -n "${CALCULATED_HASH}" ]; then
  echo "Updating ElectronAsarIntegrity to: ${CALCULATED_HASH}"
  /usr/libexec/PlistBuddy -c "Set :ElectronAsarIntegrity:Resources/app.asar:hash '${CALCULATED_HASH}'" "${PLIST}" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :ElectronAsarIntegrity:Resources/app.asar:hash string '${CALCULATED_HASH}'" "${PLIST}"
fi

# Copy openidea-server binary
if [ -f "${IDE_DIR}/bin/openidea-server" ]; then
  mkdir -p "${TARGET_APP}/Contents/Resources/bin"
  cp "${IDE_DIR}/bin/openidea-server" "${TARGET_APP}/Contents/Resources/bin/openidea-server"
  chmod +x "${TARGET_APP}/Contents/Resources/bin/openidea-server"
fi

# Copy icon
if [ -f "${ROOT_DIR}/assets/branding/icon.icns" ]; then
  cp "${ROOT_DIR}/assets/branding/icon.icns" "${TARGET_APP}/Contents/Resources/electron.icns"
fi

echo "4. Ad-hoc codesigning bundle..."
xattr -cr "${TARGET_APP}"
codesign --force --deep --sign - "${TARGET_APP}"

echo "5. Installing to /Applications/WolinexCode.app..."
rm -rf "/Applications/WolinexCode.app"
cp -R "${TARGET_APP}" "/Applications/WolinexCode.app"
xattr -cr "/Applications/WolinexCode.app"
chmod -R +x "/Applications/WolinexCode.app/Contents/MacOS/WolinexCode"
chmod -R +x "/Applications/WolinexCode.app/Contents/Resources/bin/"* 2>/dev/null || true

echo "6. Creating distribution zip archive..."
cd "${IDE_DIR}/out"
zip -q -r -y "WolinexCode-darwin-x64.zip" "WolinexCode-darwin-x64"
mkdir -p "${ROOT_DIR}/dist/binaries"
ln -sf "../../apps/ide/out/WolinexCode-darwin-x64.zip" "${ROOT_DIR}/dist/binaries/WolinexCode-darwin-x64.zip"
shasum -a 256 "${IDE_DIR}/out/WolinexCode-darwin-x64.zip" > "${ROOT_DIR}/dist/binaries/WolinexCode-darwin-x64.zip.sha256"

echo "=========================================================="
echo " ✓ Standalone Wolinex Code packaged & installed successfully!"
echo " App Bundle: /Applications/WolinexCode.app"
echo " Distribution: ${IDE_DIR}/out/WolinexCode-darwin-x64.zip"
echo "=========================================================="
