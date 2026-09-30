#!/usr/bin/env bash
# Wolinet PostgreSQL cluster bootstrap. Runs only on an empty PGDATA volume.
set -euo pipefail

PRIMARY_DB="${POSTGRES_DB:-litellm}"
WEBUI_DB="webui"
PG_USER="${POSTGRES_USER:-postgres}"
SCHEMA_DIR="/docker-entrypoint-initdb.d/schema"

echo "==> [init-postgres] Creating '${WEBUI_DB}' database"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
  --set=webui_db="${WEBUI_DB}" --set=owner="${PG_USER}" <<'EOSQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'webui_db', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'webui_db')
\gexec
EOSQL

if [ -d "${SCHEMA_DIR}" ]; then
  if [ -f "${SCHEMA_DIR}/01_litellm_core.sql" ]; then
    echo "==> [init-postgres] Applying LiteLLM PostgreSQL schema"
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
        -f "${SCHEMA_DIR}/01_litellm_core.sql"
  fi

  if [ -f "${SCHEMA_DIR}/03_indexes.sql" ]; then
    echo "==> [init-postgres] Creating rolling spend-log partitions and indexes"
    psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
        -f "${SCHEMA_DIR}/03_indexes.sql"
  fi
fi

echo "==> [init-postgres] Cluster bootstrap complete"
