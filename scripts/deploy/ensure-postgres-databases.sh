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
\gexec
EOSQL

for database in litellm webui; do
  psql --set=ON_ERROR_STOP=1 --dbname="${database}" --tuples-only --no-align \
    --command='SELECT current_database()' | grep -Fx "${database}"
done
