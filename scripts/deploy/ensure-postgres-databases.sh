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

# Check if litellm has unmanaged tables without _prisma_migrations ledger
has_prisma_migrations=$(psql --dbname=litellm --tuples-only --no-align -c "SELECT to_regclass('public._prisma_migrations')" 2>/dev/null || echo "")
has_litellm_tables=$(psql --dbname=litellm --tuples-only --no-align -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null || echo "0")

# Normalize whitespace
has_prisma_migrations=$(echo "${has_prisma_migrations}" | tr -d '[:space:]')
has_litellm_tables=$(echo "${has_litellm_tables}" | tr -d '[:space:]')

if [ -z "${has_prisma_migrations}" ] || [ "${has_prisma_migrations}" = "" ] || [ "${has_prisma_migrations}" = "NULL" ]; then
  if [ -n "${has_litellm_tables}" ] && [ "${has_litellm_tables}" -gt 0 ]; then
    echo "==> [db-init] Detected ${has_litellm_tables} unmanaged tables in litellm database without _prisma_migrations ledger."
    echo "==> [db-init] Resetting litellm public schema so LiteLLM Prisma can deploy its 192 canonical migrations cleanly..."
    psql --set=ON_ERROR_STOP=1 --dbname=litellm <<'EOSQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
EOSQL
    echo "==> [db-init] litellm public schema reset complete."
  fi
fi

# Ensure admin user exists if LiteLLM_UserTable is already present
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

    INSERT INTO "LiteLLM_UserTable" (user_id, user_email, user_role, password, models)
    VALUES ('admin@wolinet.com', 'admin@wolinet.com', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
    ON CONFLICT (user_id) DO UPDATE SET
      user_email = 'admin@wolinet.com',
      user_role = 'proxy_admin',
      password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';
  END IF;
END $$;
EOSQL


