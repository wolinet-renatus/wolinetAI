#!/usr/bin/env bash
# Wolinet PostgreSQL cluster bootstrap. Runs only on an empty PGDATA volume.
set -euo pipefail

PRIMARY_DB="${POSTGRES_DB:-litellm}"
WEBUI_DB="webui"
PG_USER="${POSTGRES_USER:-postgres}"
SCHEMA_DIR="/docker-entrypoint-initdb.d/schema"

echo "==> [init-postgres] Creating '${WEBUI_DB}' and 'wolinex' databases"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
  --set=webui_db="${WEBUI_DB}" --set=owner="${PG_USER}" <<'EOSQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'webui_db', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'webui_db')
UNION ALL
SELECT format('CREATE DATABASE %I OWNER %I', 'wolinex', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wolinex')
\gexec
EOSQL

if [ -d "${SCHEMA_DIR}" ]; then
  # LiteLLM manages its schema natively via Prisma (192 migrations).
  # Raw DDL from 01_litellm_core.sql is guarded to prevent Prisma baseline conflicts.
  if [ -f "${SCHEMA_DIR}/01_litellm_core.sql" ] && [ "${APPLY_MANUAL_LITELLM_DDL:-false}" = "true" ]; then
    echo "==> [init-postgres] Applying LiteLLM PostgreSQL schema"
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
        -f "${SCHEMA_DIR}/01_litellm_core.sql"
  fi

  # Open WebUI manages its schema natively via Alembic migrations.
  if [ -f "${SCHEMA_DIR}/02_webui_core.sql" ] && [ "${APPLY_MANUAL_WEBUI_DDL:-false}" = "true" ]; then
    echo "==> [init-postgres] Applying WebUI PostgreSQL schema to '${WEBUI_DB}' and 'wolinex'"
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${WEBUI_DB}" \
        -f "${SCHEMA_DIR}/02_webui_core.sql" || true
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "wolinex" \
        -f "${SCHEMA_DIR}/02_webui_core.sql" || true
  fi

  # Performance indexes and partitioning are applied after Prisma migrations
  if [ -f "${SCHEMA_DIR}/03_indexes.sql" ] && [ "${APPLY_MANUAL_LITELLM_DDL:-false}" = "true" ]; then
    echo "==> [init-postgres] Creating rolling spend-log partitions and indexes"
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
        -f "${SCHEMA_DIR}/03_indexes.sql"
  fi
fi

echo "==> [init-postgres] Cluster bootstrap complete"
