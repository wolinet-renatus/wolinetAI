#!/bin/sh
set -e

echo "==> [lango] Bootstrapping Wolinet AI Sovereign Gateway..."

# 1. Enforce PostgreSQL — never run on SQLite
if [ -z "${DATABASE_URL:-}" ] || echo "${DATABASE_URL}" | grep -q "^sqlite"; then
  echo "FATAL: DATABASE_URL must be configured with PostgreSQL (got: ${DATABASE_URL:-unset})" >&2
  exit 1
fi
echo "==> [lango] Database backend verified: PostgreSQL"

# 2. Patch static UI assets to brand LiteLLM -> Wolinet AI & suppress warning banner
python3 -c "
import os

replacements = {
    '🚅 LiteLLM': 'Wolinet AI',
    'LiteLLM Dashboard': 'Wolinet AI Gateway',
    'Access your LiteLLM Admin UI.': 'Access your Sovereign AI Gateway.',
    'Access your LiteLLM Admin UI': 'Access your Sovereign AI Gateway',
    'LiteLLM Proxy Admin UI': 'Wolinet AI Sovereign Gateway UI',
}

base_dirs = [
    '/app/.venv/lib/python3.13/site-packages/litellm/proxy/_experimental/out',
    '/app/litellm/proxy/_experimental/out',
]

for base_dir in base_dirs:
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
                        if f.endswith('.js'):
                            if 'a?.show_env_credential_login_warning' in content:
                                content = content.replace('a?.show_env_credential_login_warning', 'false')
                                changed = True
                            if 'show_env_credential_login_warning:!0' in content:
                                content = content.replace('show_env_credential_login_warning:!0', 'show_env_credential_login_warning:!1')
                                changed = True
                            if 'show_env_credential_login_warning:true' in content:
                                content = content.replace('show_env_credential_login_warning:true', 'show_env_credential_login_warning:false')
                                changed = True
                        if changed:
                            with open(p, 'w', encoding='utf-8') as fp:
                                fp.write(content)
                            count += 1
                    except Exception:
                        pass
        print(f'==> [lango] Branded and patched {count} UI static files in {base_dir}')
" || true

# 3. Patch _health_endpoints.py to permanently suppress env-credential login warning banner
python3 -c "
import os, re

p = '/app/.venv/lib/python3.13/site-packages/litellm/proxy/health_endpoints/_health_endpoints.py'
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        code = f.read()

    target = 'def _show_env_credential_login_warning() -> bool:'
    if target in code:
        code = re.sub(
            r'def _show_env_credential_login_warning\(\)\s*->\s*bool:[\s\S]*?(?=\n\n|\ndef )',
            'def _show_env_credential_login_warning() -> bool:\n    return False',
            code,
            count=1
        )
        with open(p, 'w', encoding='utf-8') as f:
            f.write(code)
        print('==> [lango] Successfully suppressed env-credential login warning banner')
" || true

# 4. Patch user_api_key_auth.py to accept virtual key 'sk-XvKFiwDoOtOe8i4lwbzb8Q'
# and WOLINET_GATEWAY_MASTER_KEY with full proxy admin privileges
python3 -c "
import os

p = '/app/.venv/lib/python3.13/site-packages/litellm/proxy/auth/user_api_key_auth.py'
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        code = f.read()

    target = 'is_master_key_valid = secrets.compare_digest(api_key, master_key)'
    replacement = '''valid_keys = tuple(k for k in (master_key, 'sk-XvKFiwDoOtOe8i4lwbzb8Q', os.getenv('WOLINET_GATEWAY_MASTER_KEY'), os.getenv('OPENAI_API_KEY')) if k)
        is_master_key_valid = any(secrets.compare_digest(api_key, k) for k in valid_keys)'''

    if target in code:
        code = code.replace(target, replacement)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(code)
        print('==> [lango] Successfully patched user_api_key_auth to accept Wolinet AI virtual key')
" || true

# 5. Patch login_utils.py to ensure admin authentication always accepts
# UI_PASSWORD, master_key, virtual key, and 'Wolinet@2026!' for 'admin' and 'admin@wolinet.com'
python3 -c "
import os

p = '/app/.venv/lib/python3.13/site-packages/litellm/proxy/auth/login_utils.py'
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        code = f.read()

    target = 'return secrets.compare_digest(username.encode(\"utf-8\"), ui_username.encode(\"utf-8\")) and secrets.compare_digest(\n        password.encode(\"utf-8\"), ui_password.encode(\"utf-8\")\n    )'
    replacement = '''valid_users = tuple(u for u in (ui_username, 'admin', 'admin@wolinet.com') if u)
    user_match = any(secrets.compare_digest(username.strip().lower().encode('utf-8'), u.strip().lower().encode('utf-8')) for u in valid_users)
    valid_passwords = tuple(p for p in (ui_password, master_key, 'Wolinet@2026!', 'sk-XvKFiwDoOtOe8i4lwbzb8Q') if p is not None)
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

# 6. Copy custom logos and favicon to internal bundled paths if not already mounted
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

# 7. Background seeder: As soon as PostgreSQL migrations complete, seed admin user and virtual key
python3 -c "
import os, time, sys

def seed_db():
    db_url = os.getenv('DATABASE_URL')
    if not db_url or 'sqlite' in db_url:
        return
    try:
        import psycopg
    except ImportError:
        return
    for attempt in range(40):
        try:
            with psycopg.connect(db_url, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    # 1. LiteLLM_UserTable
                    cur.execute(\"SELECT to_regclass('public.\\\"LiteLLM_UserTable\\\"')\")
                    row = cur.fetchone()
                    if row and row[0]:
                        cur.execute('''
                            INSERT INTO \"LiteLLM_UserTable\" (user_id, user_email, user_role, password, models)
                            VALUES ('admin', 'admin@wolinet.com', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
                            ON CONFLICT (user_id) DO UPDATE SET
                                user_email = 'admin@wolinet.com',
                                user_role = 'proxy_admin',
                                password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';
                        ''')
                        cur.execute('''
                            INSERT INTO \"LiteLLM_UserTable\" (user_id, user_email, user_role, password, models)
                            VALUES ('admin@wolinet.com', 'admin@wolinet.com', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
                            ON CONFLICT (user_id) DO UPDATE SET
                                user_email = 'admin@wolinet.com',
                                user_role = 'proxy_admin',
                                password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';
                        ''')

                    # 2. LiteLLM_VerificationToken
                    cur.execute(\"SELECT to_regclass('public.\\\"LiteLLM_VerificationToken\\\"')\")
                    row_vt = cur.fetchone()
                    if row_vt and row_vt[0]:
                        cur.execute('''
                            INSERT INTO \"LiteLLM_VerificationToken\" (
                                token, key_name, key_alias, user_id, models, spend, total_spend, created_at, updated_at
                            )
                            VALUES (
                                'b2d10bb32dbe57a3f063c2c9df27eacd6cafc84f5a52311895a9f3db9a76ab97',
                                'Wolinet AI Virtual Key',
                                'wolinex',
                                'admin',
                                ARRAY[]::text[],
                                0.0,
                                0.0,
                                NOW(),
                                NOW()
                            )
                            ON CONFLICT (token) DO UPDATE SET
                                key_name = 'Wolinet AI Virtual Key',
                                key_alias = 'wolinex',
                                user_id = 'admin',
                                updated_at = NOW();
                        ''')
                conn.commit()
                print('==> [lango] Database seeded with Wolinet AI admin and virtual key (sk-XvKFiwDoOtOe8i4lwbzb8Q)')
                break
        except Exception:
            time.sleep(2)

import threading
threading.Thread(target=seed_db, daemon=True).start()
" || true

# 8. Hand over to LiteLLM entrypoint
echo "==> [lango] Starting LiteLLM proxy..."
exec docker/prod_entrypoint.sh "$@"
