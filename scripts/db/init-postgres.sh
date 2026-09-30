#!/usr/bin/env bash
# Wolinet PostgreSQL cluster bootstrap. Runs only on an empty PGDATA volume.
set -euo pipefail

LITELLM_DB="${POSTGRES_DB:-litellm}"
WEBUI_DB="webui"
PG_USER="${POSTGRES_USER:-postgres}"
SCHEMA_DIR="/docker-entrypoint-initdb.d/schema"

echo "==> [init-postgres] Creating '${WEBUI_DB}' database"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${LITELLM_DB}" <<-EOSQL
    SELECT 'CREATE DATABASE ${WEBUI_DB} OWNER ${PG_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${WEBUI_DB}')
    \gexec
EOSQL

echo "==> [init-postgres] Applying LiteLLM PostgreSQL schema"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${LITELLM_DB}" \
    -f "${SCHEMA_DIR}/01_litellm_core.sql"

echo "==> [init-postgres] Creating rolling spend-log partitions and indexes"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${LITELLM_DB}" \
    -f "${SCHEMA_DIR}/03_indexes.sql"

echo "==> [init-postgres] Cluster bootstrap complete"
