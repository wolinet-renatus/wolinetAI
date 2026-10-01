#!/bin/sh
set -eu

attempt=0
until pg_isready --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}"; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 60 ]; then
    echo "PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 2
done

psql --set=ON_ERROR_STOP=1 --dbname=litellm <<'EOSQL'
SELECT format('CREATE DATABASE %I OWNER %I', 'webui', current_user)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'webui')
UNION ALL
SELECT format('CREATE DATABASE %I OWNER %I', 'wolinex', current_user)
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wolinex')
\gexec
EOSQL

for database in litellm webui wolinex; do
  psql --set=ON_ERROR_STOP=1 --dbname="${database}" --tuples-only --no-align \
    --command='SELECT current_database()' | grep -Fx "${database}"
done

psql --dbname=litellm <<'EOSQL' 2>/dev/null || true
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'LiteLLM_UserTable') THEN
    INSERT INTO "LiteLLM_UserTable" (user_id, user_email, user_role, password, models)
    VALUES ('admin', 'admin', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
    ON CONFLICT (user_id) DO UPDATE SET
      user_email = 'admin',
      user_role = 'proxy_admin',
      password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';
  END IF;
END $$;
EOSQL

