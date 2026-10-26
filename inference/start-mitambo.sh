#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — Sovereign Inference Engine Bootstrap (mitambo)
# ==============================================================================
# Ensures frontend static assets, permissions, and Wolinet AI branding are
# in place before starting Xinference local daemon.
# ==============================================================================
set -e

export PATH="/opt/conda/bin:/usr/local/bin:$PATH"

echo "==> [mitambo] Bootstrapping Wolinet AI Inference Engine..."

# 1. Locate Xinference Python package directory
PKG_DIR=$(python3 -c "import xinference, os; print(os.path.dirname(xinference.__file__))" 2>/dev/null || python -c "import xinference, os; print(os.path.dirname(xinference.__file__))" 2>/dev/null || true)
echo "==> [mitambo] Xinference package detected at: ${PKG_DIR:-unknown}"

# 2. Prepare UI distribution directory
# Candidate source locations for the built Wolinet AI UI bundle
SRC_DIR=""
for candidate in "/app/dist" "/app/out" "/ui" "${PKG_DIR}/ui/web/dist" "/root/dist"; do
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

# 5. Background Auth & Model Auto-Launcher
(
  echo "==> [mitambo-init] Starting background initialization daemon..."
  for attempt in $(seq 1 60); do
    sleep 4
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9997/status', timeout=3)" >/dev/null 2>&1; then
      if python3 - << 'PY'
import os, sys, time, json, urllib.request, hashlib, sqlite3

endpoint = 'http://127.0.0.1:9997'
admin_user = os.environ.get('XINFERENCE_ADMIN_USER', 'admin')
admin_pass = os.environ.get('XINFERENCE_ADMIN_PASSWORD', 'Woli@1211')
gateway_key = os.environ.get('XINFERENCE_API_KEY', 'sk-XvKFiwDoOtOe8i4lwbzb8Q')

# 1. Setup Admin Account if needed
try:
    req = urllib.request.Request(f'{endpoint}/v1/admin/setup/status')
    with urllib.request.urlopen(req, timeout=5) as resp:
        status_data = json.loads(resp.read().decode())
    if status_data.get('needs_setup'):
        print('==> [mitambo-init] Performing first-run admin setup...')
        payload = json.dumps({'username': admin_user, 'password': admin_pass}).encode('utf-8')
        sreq = urllib.request.Request(f'{endpoint}/v1/admin/setup', data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(sreq, timeout=5) as sresp:
            print('==> [mitambo-init] Admin account initialized successfully.')
except Exception as e:
    print(f'==> [mitambo-init] Setup note: {e}')

# 2. Pre-seed Gateway API Key in auth.db
try:
    db_path = os.environ.get('XINFERENCE_AUTH_DB_PATH', '/root/.xinference/auth/auth.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE username = ?', (admin_user,))
        user_row = cur.fetchone()
        
        # Ensure admin user has correct password hash matching admin_pass
        try:
            import bcrypt
            p_bytes = admin_pass.encode('utf-8')
            if len(p_bytes) > 72:
                p_bytes = hashlib.sha256(p_bytes).digest()[:72]
            p_hash = bcrypt.hashpw(p_bytes, bcrypt.gensalt()).decode('utf-8')
            if user_row:
                uid = user_row[0]
                cur.execute('UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?', (p_hash, uid))
            else:
                cur.execute('INSERT INTO users (username, password_hash, source, enabled, must_change_password) VALUES (?, ?, ?, ?, ?)', (admin_user, p_hash, 'local', 1, 0))
                uid = cur.lastrowid
            conn.commit()
        except Exception as _pwe:
            print(f'==> [mitambo-init] Password sync note: {_pwe}')

        if uid:
            key_hash = hashlib.sha256(gateway_key.encode('utf-8')).hexdigest()
            key_prefix = gateway_key[:7]
            cur.execute('SELECT id FROM api_keys WHERE key_hash = ?', (key_hash,))
            krow = cur.fetchone()
            if not krow:
                cur.execute('''
                    INSERT INTO api_keys (user_id, key_hash, key_encrypted, key_prefix, name, enabled)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (uid, key_hash, 'gateway_key_direct', key_prefix, 'lango-gateway'))
                kid = cur.lastrowid
                cur.execute('''
                    INSERT INTO api_key_model_permissions (api_key_id, permission_type, permission_value)
                    VALUES (?, 'all', NULL)
                ''', (kid,))
                conn.commit()
                print(f'==> [mitambo-init] Registered gateway API key ({key_prefix}...) into auth.db')
        conn.close()
except Exception as e:
    print(f'==> [mitambo-init] API key seeding note: {e}')

# 3. Connect via RESTfulClient, login, and report the models already running.
# Models are launched and stopped through Xinference; the model-sync sidecar
# mirrors that live catalog into LiteLLM without changing inference state.
try:
    from xinference.client import RESTfulClient
    client = RESTfulClient(endpoint)
    client.login(admin_user, admin_pass)

    try:
        token = client._get_token() if hasattr(client, "_get_token") else getattr(client, "_token", None)
        if token:
            auth_dir = '/root/.xinference/auth'
            os.makedirs(auth_dir, exist_ok=True)
            for ep_variant in (endpoint, 'http://127.0.0.1:9997', 'http://127.0.0.1:9997/', 'http://localhost:9997', 'http://localhost:9997/', 'http://0.0.0.0:9997', 'http://0.0.0.0:9997/'):
                h = hashlib.sha256(ep_variant.encode('utf-8')).hexdigest()
                with open(os.path.join(auth_dir, h), 'w') as f:
                    f.write(token)
    except Exception:
        pass

    running_models = client.list_models()
    print(f'==> [mitambo-init] Currently active models: {list(running_models.keys())}')

    # 4. Auto-launch Wolinet Pro (Qwen 2.5 1.5B) if not running
    if "wolinet-pro" not in running_models and "qwen2.5-instruct" not in running_models:
        qwen_src = "/root/.xinference/cache/v2/qwen2.5-instruct-ggufv2-1_5b-q4_k_m/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        if os.path.exists(qwen_src):
            try:
                qwen_alt_dir = "/root/.xinference/cache/v2/qwen2_5-instruct-ggufv2-1_5b-q4_k_m"
                os.makedirs(qwen_alt_dir, exist_ok=True)
                qwen_alt = os.path.join(qwen_alt_dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf")
                if not os.path.exists(qwen_alt) or os.path.getsize(qwen_alt) != os.path.getsize(qwen_src):
                    import shutil
                    shutil.copyfile(qwen_src, qwen_alt)

                print("==> [mitambo-init] Auto-launching Wolinet Pro (Qwen 2.5 1.5B)...")
                client.launch_model(
                    model_name="qwen2.5-instruct",
                    model_uid="wolinet-pro",
                    model_engine="llama.cpp",
                    model_format="ggufv2",
                    model_size_in_billions="1_5",
                    quantization="q4_k_m",
                    model_path=qwen_src,
                    n_gpu_layers=0,
                    n_ctx=4096,
                    n_parallel=1,
                    n_threads=int(os.environ.get("XINFERENCE_THREADS", "8")),
                    n_batch=2048,
                    n_ubatch=512,
                    cache_ram_mib=8192,
                )
                print("==> [mitambo-init] Wolinet Pro auto-launched successfully.")
            except Exception as pe:
                print(f"==> [mitambo-init] Notice launching Wolinet Pro: {pe}")

    # 5. Auto-launch Wolinet Coder (DeepSeek Coder 1.3B) if not running
    if "deepseek-coder-instruct" not in running_models:
        try:
            print("==> [mitambo-init] Auto-launching Wolinet Coder (DeepSeek Coder 1.3B)...")
            client.launch_model(
                model_name="deepseek-coder-instruct",
                model_uid="deepseek-coder-instruct",
                model_engine="llama.cpp",
                model_format="ggufv2",
                model_size_in_billions="1_3",
                quantization="Q4_K_M",
                n_gpu_layers=0,
                n_ctx=4096,
                n_parallel=1,
                n_threads=int(os.environ.get("XINFERENCE_THREADS", "8")),
                n_batch=2048,
                n_ubatch=512,
                cache_ram_mib=4096,
            )
            print("==> [mitambo-init] Wolinet Coder auto-launched successfully.")
        except Exception as ce:
            print(f"==> [mitambo-init] Notice launching Wolinet Coder: {ce}")

    running_models = client.list_models()
    print(f'==> [mitambo-init] Active Xinference models now: {list(running_models.keys())}')
    sys.exit(0)
except Exception as me:
    print(f'==> [mitambo-init] Init attempt notice (will retry): {me}')
    sys.exit(1)
PY
      then
        echo "==> [mitambo-init] Initialization and model launch complete."
        break
      fi
    fi
  done
) &

# 6. Execute CMD
echo "==> [mitambo] Starting Xinference local daemon..."
exec "$@"
