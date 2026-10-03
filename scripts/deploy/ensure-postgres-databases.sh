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

# Remove the legacy hard-coded Open WebUI model entry. Model choices now come
# from the live LiteLLM catalog, so stopped or unregistered models stay hidden.
for database in webui wolinex; do
  psql --dbname="${database}" <<'EOSQL' 2>/dev/null || true
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'model') THEN
    DELETE FROM model WHERE id = 'wolinet-coder';
  END IF;

  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'alembic_version') THEN
    -- If alembic_version has d4c1a8e37b62 (foreign/future revision from other image) or any unknown revision,
    -- reset it to current Open WebUI head 'f2a4b6c8d0e1' so migrations complete cleanly.
    UPDATE alembic_version SET version_num = 'f2a4b6c8d0e1'
    WHERE version_num = 'd4c1a8e37b62' OR version_num NOT IN (
      'f2a4b6c8d0e1', 'f1e2d3c4b5a6', 'e1f2a3b4c5d6', 'd4e5f6a7b8c9',
      'd31026856c01', 'ca81bd47c050', 'c69f45358db4', 'c440947495f3',
      'c29facfe716b', 'c1d2e3f4a5b6', 'c0fbf31ca0db', 'b7c8d9e0f1a2',
      'b2c3d4e5f6a7', 'b10670c03dd5', 'af906e964978', 'a5c220713937',
      'a3dd5bedd151', 'a1b2c3d4e5f6', 'a0b1c2d3e4f5', '9f0c9cd09105',
      '922e7a387820', '90ef40d4714e', '8452d01d26d7', '81cc2ce44d79',
      '7e5b5dc7342b', '7826ab40b532', '6a39f3d8e55c', '6283dc0e4d8d',
      '57c599a3cb57', '56359461a091', '4de81c2a3af1', '4ace53fd72c8',
      '461111b60977', '3e0e00844bb0', '3c9b0ca343fd', '3af16a1c9fb6',
      '3ab32c4b8f59', '38d63c18f30f', '37f288994c47', '3781e22d8b01',
      '374d2f66af06', '2f1211949ecc', '242a2047eae0', '1af9b942657b',
      '018012973d35'
    );
  END IF;
END $$;
EOSQL
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

# Ensure admin user and virtual key exist if tables are already present
psql --dbname=litellm <<'EOSQL' 2>/dev/null || true
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'LiteLLM_UserTable') THEN
    INSERT INTO "LiteLLM_UserTable" (user_id, user_email, user_role, password, models)
    VALUES ('admin', 'admin@wolinet.com', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
    ON CONFLICT (user_id) DO UPDATE SET
      user_email = 'admin@wolinet.com',
      user_role = 'proxy_admin',
      password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';

    INSERT INTO "LiteLLM_UserTable" (user_id, user_email, user_role, password, models)
    VALUES ('admin@wolinet.com', 'admin@wolinet.com', 'proxy_admin', '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355', ARRAY[]::text[])
    ON CONFLICT (user_id) DO UPDATE SET
      user_email = 'admin@wolinet.com',
      user_role = 'proxy_admin',
      password = '58c4e871c3d18f4160f5df22dbcb7a467377228fced8743af316b6615cd34355';
  END IF;

  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'LiteLLM_VerificationToken') THEN
    INSERT INTO "LiteLLM_VerificationToken" (
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
  END IF;
END $$;
EOSQL
