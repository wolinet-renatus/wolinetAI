#!/usr/bin/env bash
set -euo pipefail

PRIMARY_DB="${POSTGRES_DB:-litellm}"
WEBUI_DB=webui
PG_USER="${POSTGRES_USER:-postgres}"

psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${PRIMARY_DB}" \
  --set=webui_db="${WEBUI_DB}" --set=owner="${PG_USER}" <<'EOSQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'webui_db', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'webui_db')
\gexec
EOSQL
