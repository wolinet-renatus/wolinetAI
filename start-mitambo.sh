#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — Sovereign Inference Engine Bootstrap (mitambo)
# ==============================================================================
# Ensures frontend static assets, permissions, and Wolinet AI branding are
# in place before starting Xinference local daemon.
# ==============================================================================
set -e

echo "==> [mitambo] Bootstrapping Wolinet AI Inference Engine..."

# 1. Locate Xinference Python package directory
PKG_DIR=$(python3 -c "import xinference, os; print(os.path.dirname(xinference.__file__))" 2>/dev/null || python -c "import xinference, os; print(os.path.dirname(xinference.__file__))" 2>/dev/null || true)
echo "==> [mitambo] Xinference package detected at: ${PKG_DIR:-unknown}"

# 2. Prepare UI distribution directory
# Candidate source locations for the built Wolinet AI UI bundle
SRC_DIR=""
for candidate in "/app/dist" "/ui" "${PKG_DIR}/ui/web/dist" "/root/dist"; do
  if [ -d "$candidate" ] && [ -f "$candidate/index.html" ]; then
    SRC_DIR="$candidate"
    break
  fi
done

mkdir -p /ui

if [ -n "$SRC_DIR" ] && [ "$SRC_DIR" != "/ui" ]; then
  echo "==> [mitambo] Staging UI bundle from ${SRC_DIR} to /ui..."
  cp -r "${SRC_DIR}/." /ui/ 2>/dev/null || true
fi

# Also ensure the package's internal ui/web/dist is populated
if [ -n "$PKG_DIR" ] && [ -d "/ui" ] && [ -f "/ui/index.html" ]; then
  mkdir -p "${PKG_DIR}/ui/web/dist"
  if [ ! -f "${PKG_DIR}/ui/web/dist/index.html" ] || [ "/ui" -nt "${PKG_DIR}/ui/web/dist/index.html" ]; then
    cp -r /ui/. "${PKG_DIR}/ui/web/dist/" 2>/dev/null || true
  fi
fi

# 3. Ensure permissions so all files are world-readable
chmod -R a+rX /ui 2>/dev/null || true
if [ -n "$PKG_DIR" ]; then
  chmod -R a+rX "${PKG_DIR}/ui/web/dist" 2>/dev/null || true
fi

# 4. Verify /ui/index.html exists; if somehow still missing, generate fallback
if [ ! -f "/ui/index.html" ]; then
  echo "==> [mitambo] WARNING: /ui/index.html was not found; creating resilient fallback..."
  cat <<'EOF' > /ui/index.html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Wolinet AI — Inference Platform</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
    .card { background: #1e293b; padding: 2.5rem; border-radius: 1rem; border: 1px solid #334155; max-width: 480px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    h1 { color: #38bdf8; margin-top: 0; }
    p { color: #94a3b8; line-height: 1.6; }
    a.btn { display: inline-block; background: #0284c7; color: #fff; padding: 0.75rem 1.5rem; border-radius: 0.5rem; text-decoration: none; font-weight: 600; margin-top: 1rem; }
    a.btn:hover { background: #0369a1; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Wolinet AI</h1>
    <p>Inference Engine is initializing. If this screen persists, please refresh your browser.</p>
    <a class="btn" href="javascript:location.reload()">Refresh Interface</a>
  </div>
</body>
</html>
EOF
fi

UI_COUNT=$(find /ui -type f 2>/dev/null | wc -l || echo "0")
echo "==> [mitambo] Verified UI static assets: ${UI_COUNT} files in /ui"

# 5. Execute CMD
echo "==> [mitambo] Starting Xinference local daemon..."
exec "$@"
