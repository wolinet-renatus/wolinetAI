#!/usr/bin/env bash
# ==============================================================================
# Wolinet AI — PostgreSQL Cluster Initialisation Script
# Runs once inside the official postgres:16 container at first boot.
# Creates two separate databases inside the shared cluster:
#   - litellm   (primary, already created by POSTGRES_DB env var)
#   - webui     (Open WebUI state — chats, files, models, auth)
# Also creates composite indexes for critical spend / audit tables.
# ==============================================================================
set -euo pipefail

LITELLM_DB="${POSTGRES_DB:-litellm}"
WEBUI_DB="webui"
PG_USER="${POSTGRES_USER:-postgres}"

echo "==> [init-postgres] Creating '${WEBUI_DB}' database …"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${LITELLM_DB}" <<-EOSQL
    SELECT 'CREATE DATABASE ${WEBUI_DB} OWNER ${PG_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${WEBUI_DB}')
    \gexec
EOSQL

echo "==> [init-postgres] Applying LiteLLM performance indexes …"
psql -v ON_ERROR_STOP=1 --username "${PG_USER}" --dbname "${LITELLM_DB}" <<-EOSQL
    -- -----------------------------------------------------------------------
    -- LiteLLMSpendLogs — fastest billing & audit queries
    -- -----------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS "LiteLLMSpendLogs" (
        "request_id"        TEXT        PRIMARY KEY,
        "call_type"         TEXT        NOT NULL DEFAULT '',
        "api_key"           TEXT        NOT NULL DEFAULT '',
        "spend"             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        "total_tokens"      INTEGER     NOT NULL DEFAULT 0,
        "prompt_tokens"     INTEGER     NOT NULL DEFAULT 0,
        "completion_tokens" INTEGER     NOT NULL DEFAULT 0,
        "startTime"         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        "endTime"           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        "model"             TEXT        NOT NULL DEFAULT '',
        "user"              TEXT,
        "team_id"           TEXT,
        "metadata"          JSONB,
        "cache_hit"         TEXT,
        "cache_key"         TEXT,
        "request_tags"      JSONB,
        "requester_ip_address" TEXT,
        "messages"          JSONB,
        "response"          JSONB,
        "proxy_server_request" JSONB
    );

    -- Composite index: user spend lookups (dashboards, budget caps)
    CREATE INDEX IF NOT EXISTS idx_spend_logs_user_time
        ON "LiteLLMSpendLogs" ("user", "startTime" DESC);

    -- Composite index: API key billing (portal key detail page)
    CREATE INDEX IF NOT EXISTS idx_spend_logs_apikey_time
        ON "LiteLLMSpendLogs" ("api_key", "startTime" DESC);

    -- Composite index: team-level spend aggregation
    CREATE INDEX IF NOT EXISTS idx_spend_logs_team_time
        ON "LiteLLMSpendLogs" ("team_id", "startTime" DESC);

    -- JSONB GIN index: metadata tag filtering
    CREATE INDEX IF NOT EXISTS idx_spend_logs_metadata_gin
        ON "LiteLLMSpendLogs" USING GIN ("metadata");

    -- -----------------------------------------------------------------------
    -- VerificationToken (Virtual Keys)
    -- -----------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS "LiteLLM_VerificationToken" (
        "token"             TEXT        PRIMARY KEY,
        "key_name"          TEXT,
        "key_alias"         TEXT,
        "soft_budget_cooldown" BOOLEAN DEFAULT FALSE,
        "spend"             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        "max_budget"        DOUBLE PRECISION,
        "expires"           TIMESTAMPTZ,
        "models"            JSONB,
        "aliases"           JSONB,
        "config"            JSONB,
        "user_id"           TEXT,
        "team_id"           TEXT,
        "permissions"       JSONB,
        "max_parallel_requests" INTEGER,
        "metadata"          JSONB,
        "blocked"           BOOLEAN DEFAULT FALSE,
        "rpm_limit"         INTEGER,
        "tpm_limit"         BIGINT,
        "allowed_cache_controls" JSONB,
        "budget_duration"   TEXT,
        "budget_reset_at"   TIMESTAMPTZ,
        "allowed_routes"    JSONB,
        "org_id"            TEXT,
        "tags"              JSONB,
        "created_at"        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        "updated_at"        TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_token_user_id
        ON "LiteLLM_VerificationToken" ("user_id");

    CREATE INDEX IF NOT EXISTS idx_token_team_id
        ON "LiteLLM_VerificationToken" ("team_id");

    CREATE INDEX IF NOT EXISTS idx_token_expires
        ON "LiteLLM_VerificationToken" ("expires");

    -- -----------------------------------------------------------------------
    -- UserTable
    -- -----------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS "LiteLLM_UserTable" (
        "user_id"           TEXT        PRIMARY KEY,
        "user_alias"        TEXT,
        "team_id"           TEXT,
        "org_id"            TEXT,
        "user_email"        TEXT        UNIQUE,
        "user_role"         TEXT        NOT NULL DEFAULT 'internal_user',
        "spend"             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        "max_budget"        DOUBLE PRECISION,
        "budget_duration"   TEXT,
        "budget_reset_at"   TIMESTAMPTZ,
        "models"            JSONB,
        "tpm_limit"         BIGINT,
        "rpm_limit"         INTEGER,
        "model_spend"       JSONB,
        "model_max_budget"  JSONB,
        "allowed_cache_controls" JSONB,
        "metadata"          JSONB,
        "teams"             JSONB,
        "created_at"        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        "updated_at"        TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_user_email
        ON "LiteLLM_UserTable" ("user_email");

    CREATE INDEX IF NOT EXISTS idx_user_role
        ON "LiteLLM_UserTable" ("user_role");

    -- -----------------------------------------------------------------------
    -- Portal tables (used by wolinet_portal.py)
    -- -----------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS portal_users (
        id              TEXT        PRIMARY KEY,
        name            TEXT        NOT NULL,
        email           TEXT        UNIQUE NOT NULL,
        password_hash   TEXT        NOT NULL,
        salt            TEXT        NOT NULL,
        role            TEXT        NOT NULL DEFAULT 'developer',
        api_key         TEXT        NOT NULL,
        created_at      DOUBLE PRECISION NOT NULL
    );

    CREATE TABLE IF NOT EXISTS portal_keys (
        id              TEXT        PRIMARY KEY,
        user_id         TEXT        NOT NULL,
        key             TEXT        UNIQUE NOT NULL,
        key_alias       TEXT,
        max_budget      DOUBLE PRECISION DEFAULT 25.0,
        spend           DOUBLE PRECISION DEFAULT 0.0,
        duration        TEXT,
        expires_at      DOUBLE PRECISION,
        status          TEXT        DEFAULT 'active',
        created_at      DOUBLE PRECISION NOT NULL,
        CONSTRAINT fk_portal_keys_user FOREIGN KEY (user_id) REFERENCES portal_users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS portal_sessions (
        token           TEXT        PRIMARY KEY,
        user_id         TEXT        NOT NULL,
        expires_at      DOUBLE PRECISION NOT NULL,
        created_at      DOUBLE PRECISION NOT NULL,
        CONSTRAINT fk_portal_sessions_user FOREIGN KEY (user_id) REFERENCES portal_users(id) ON DELETE CASCADE
    );

    -- Portal indexes
    CREATE INDEX IF NOT EXISTS idx_portal_users_email     ON portal_users(email);
    CREATE INDEX IF NOT EXISTS idx_portal_keys_user       ON portal_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_portal_keys_key        ON portal_keys(key);
    CREATE INDEX IF NOT EXISTS idx_portal_sessions_token  ON portal_sessions(token);
    CREATE INDEX IF NOT EXISTS idx_portal_sessions_user   ON portal_sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_portal_keys_status     ON portal_keys(status, user_id);
EOSQL

echo "==> [init-postgres] All databases and indexes ready."
