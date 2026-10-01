#!/bin/sh
set -e

echo "==> [lango] Bootstrapping Wolinet AI Sovereign Gateway..."

# 1. Enforce PostgreSQL — never run on SQLite
if [ -z "${DATABASE_URL:-}" ] || echo "${DATABASE_URL}" | grep -q "^sqlite"; then
  echo "FATAL: DATABASE_URL must be configured with PostgreSQL (got: ${DATABASE_URL:-unset})" >&2
  exit 1
fi
echo "==> [lango] Database backend verified: PostgreSQL"

# 2. Patch static UI assets to brand LiteLLM -> Wolinet AI
python3 -c "
import os

replacements = {
    '🚅 LiteLLM': 'Wolinet AI',
    'LiteLLM Dashboard': 'Wolinet AI Gateway',
    'Access your LiteLLM Admin UI.': 'Access your Sovereign AI Gateway.',
    'Access your LiteLLM Admin UI': 'Access your Sovereign AI Gateway',
    'LiteLLM Proxy Admin UI': 'Wolinet AI Sovereign Gateway UI',
}

base_dir = '/app/.venv/lib/python3.13/site-packages/litellm/proxy/_experimental/out'
if os.path.exists(base_dir):
    count = 0
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(('.html', '.js', '.txt')):
                p = os.path.join(root, f)
                try:
                    with open(p, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    changed = False
                    for old_text, new_text in replacements.items():
                        if old_text in content:
                            content = content.replace(old_text, new_text)
                            changed = True
                    if changed:
                        with open(p, 'w', encoding='utf-8') as fp:
                            fp.write(content)
                        count += 1
                except Exception:
                    pass
    print(f'==> [lango] Branded {count} UI static files with Wolinet AI')
" || true

# 3. Patch login_utils.py to ensure admin authentication always accepts
# UI_PASSWORD, master_key, and 'Wolinet@2026!' for 'admin' and 'admin@wolinet.com'
python3 -c "
import os

p = '/app/.venv/lib/python3.13/site-packages/litellm/proxy/auth/login_utils.py'
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        code = f.read()

    target = 'return secrets.compare_digest(username.encode(\"utf-8\"), ui_username.encode(\"utf-8\")) and secrets.compare_digest(\n        password.encode(\"utf-8\"), ui_password.encode(\"utf-8\")\n    )'
    replacement = '''valid_users = tuple(u for u in (ui_username, 'admin', 'admin@wolinet.com') if u)
    user_match = any(secrets.compare_digest(username.strip().lower().encode('utf-8'), u.strip().lower().encode('utf-8')) for u in valid_users)
    valid_passwords = tuple(p for p in (ui_password, master_key, 'Wolinet@2026!') if p is not None)
    pass_match = any(secrets.compare_digest(password.encode('utf-8'), p.encode('utf-8')) for p in valid_passwords)
    return user_match and pass_match'''

    if target in code:
        code = code.replace(target, replacement)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(code)
        print('==> [lango] Successfully patched admin login validator')
    else:
        print('==> [lango] Note: target pattern in login_utils.py already updated')
" || true

# 4. Copy custom logos and favicon to internal bundled paths if not already mounted
if [ -f "/app/assets/wolinet_logo.png" ]; then
  cp -f /app/assets/wolinet_logo.png /app/.venv/lib/python3.13/site-packages/litellm/proxy/logo.jpg 2>/dev/null || true
fi
if [ -f "/app/assets/wolinet_logo_dark.png" ]; then
  cp -f /app/assets/wolinet_logo_dark.png /app/.venv/lib/python3.13/site-packages/litellm/proxy/logo_dark.png 2>/dev/null || true
fi
if [ -f "/app/assets/favicon.ico" ]; then
  cp -f /app/assets/favicon.ico /app/.venv/lib/python3.13/site-packages/litellm/proxy/_experimental/out/favicon.ico 2>/dev/null || true
fi
if [ -f "/app/assets/favicon.png" ]; then
  cp -f /app/assets/favicon.png /app/.venv/lib/python3.13/site-packages/litellm/proxy/_experimental/out/favicon.png 2>/dev/null || true
fi

# 5. Hand over to LiteLLM entrypoint
echo "==> [lango] Starting LiteLLM proxy..."
exec docker/prod_entrypoint.sh "$@"
