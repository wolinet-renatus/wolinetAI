-- ==============================================================================
-- Wolinet AI — Alembic / Manual DDL Migration: Full Production Schema
-- Target: PostgreSQL 14+
-- Run order:
--   01_litellm_core.sql   ← this file (LiteLLM shared tables)
--   02_webui_core.sql     ← Open WebUI tables (run against 'webui' DB)
--   03_indexes.sql        ← Composite indexes (billing, audit, search)
-- ==============================================================================

-- Extension for UUID generation (used by WebUI)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===========================================================================
-- LITELLM CORE TABLES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Virtual API Keys (LiteLLM_VerificationToken)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "LiteLLM_VerificationToken" (
    "token"                     TEXT            PRIMARY KEY,
    "key_name"                  TEXT,
    "key_alias"                 TEXT,
    "soft_budget_cooldown"      BOOLEAN         NOT NULL DEFAULT FALSE,
    "spend"                     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "max_budget"                DOUBLE PRECISION,
    "expires"                   TIMESTAMPTZ,
    "models"                    JSONB,
    "aliases"                   JSONB,
    "config"                    JSONB,
    "user_id"                   TEXT,
    "team_id"                   TEXT,
    "permissions"               JSONB,
    "max_parallel_requests"     INTEGER,
    "metadata"                  JSONB,
    "blocked"                   BOOLEAN         NOT NULL DEFAULT FALSE,
    "rpm_limit"                 INTEGER,
    "tpm_limit"                 BIGINT,
    "allowed_cache_controls"    JSONB,
    "budget_duration"           TEXT,
    "budget_reset_at"           TIMESTAMPTZ,
    "allowed_routes"            JSONB,
    "org_id"                    TEXT,
    "tags"                      JSONB,
    "created_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "updated_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- User Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "LiteLLM_UserTable" (
    "user_id"                   TEXT            PRIMARY KEY,
    "user_alias"                TEXT,
    "team_id"                   TEXT,
    "org_id"                    TEXT,
    "user_email"                TEXT            UNIQUE,
    "user_role"                 TEXT            NOT NULL DEFAULT 'internal_user',
    "spend"                     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "max_budget"                DOUBLE PRECISION,
    "budget_duration"           TEXT,
    "budget_reset_at"           TIMESTAMPTZ,
    "models"                    JSONB,
    "tpm_limit"                 BIGINT,
    "rpm_limit"                 INTEGER,
    "model_spend"               JSONB,
    "model_max_budget"          JSONB,
    "allowed_cache_controls"    JSONB,
    "metadata"                  JSONB,
    "teams"                     JSONB,
    "created_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "updated_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Team Table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "LiteLLM_TeamTable" (
    "team_id"                   TEXT            PRIMARY KEY,
    "team_alias"                TEXT,
    "admin_viewer"              JSONB,
    "organization_id"           TEXT,
    "metadata"                  JSONB,
    "models"                    JSONB,
    "spend"                     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "max_budget"                DOUBLE PRECISION,
    "budget_duration"           TEXT,
    "budget_reset_at"           TIMESTAMPTZ,
    "blocked"                   BOOLEAN         NOT NULL DEFAULT FALSE,
    "members_with_roles"        JSONB,
    "tpm_limit"                 BIGINT,
    "rpm_limit"                 INTEGER,
    "model_id"                  INTEGER,
    "litellm_model_table"       JSONB,
    "created_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "updated_at"                TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Spend Logs (write-optimised — partitioned by month for scale)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "LiteLLMSpendLogs" (
    "request_id"                TEXT            NOT NULL,
    "call_type"                 TEXT            NOT NULL DEFAULT '',
    "api_key"                   TEXT            NOT NULL DEFAULT '',
    "spend"                     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "total_tokens"              INTEGER         NOT NULL DEFAULT 0,
    "prompt_tokens"             INTEGER         NOT NULL DEFAULT 0,
    "completion_tokens"         INTEGER         NOT NULL DEFAULT 0,
    "startTime"                 TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "endTime"                   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    "completionStartTime"       TIMESTAMPTZ,
    "model"                     TEXT            NOT NULL DEFAULT '',
    "model_id"                  TEXT,
    "model_group"               TEXT,
    "api_base"                  TEXT,
    "user"                      TEXT,
    "team_id"                   TEXT,
    "org_id"                    TEXT,
    "metadata"                  JSONB,
    "cache_hit"                 TEXT,
    "cache_key"                 TEXT,
    "request_tags"              JSONB,
    "requester_ip_address"      TEXT,
    "messages"                  JSONB,
    "response"                  JSONB,
    "proxy_server_request"      JSONB,
    "session_id"                TEXT,
    "error_str"                 TEXT,
    PRIMARY KEY ("request_id", "startTime")
) PARTITION BY RANGE ("startTime");

-- Current + rolling partitions (run monthly in cron/migration)
CREATE TABLE IF NOT EXISTS "LiteLLMSpendLogs_2026_09"
    PARTITION OF "LiteLLMSpendLogs"
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

CREATE TABLE IF NOT EXISTS "LiteLLMSpendLogs_2026_10"
    PARTITION OF "LiteLLMSpendLogs"
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

CREATE TABLE IF NOT EXISTS "LiteLLMSpendLogs_2026_11"
    PARTITION OF "LiteLLMSpendLogs"
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

-- ---------------------------------------------------------------------------
-- Portal tables (sovereign developer portal — wolinet_portal.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portal_users (
    id              TEXT            PRIMARY KEY,
    name            TEXT            NOT NULL,
    email           TEXT            UNIQUE NOT NULL,
    password_hash   TEXT            NOT NULL,
    salt            TEXT            NOT NULL,
    role            TEXT            NOT NULL DEFAULT 'developer',
    api_key         TEXT            NOT NULL,
    created_at      DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS portal_keys (
    id              TEXT            PRIMARY KEY,
    user_id         TEXT            NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
    key             TEXT            UNIQUE NOT NULL,
    key_alias       TEXT,
    max_budget      DOUBLE PRECISION DEFAULT 25.0,
    spend           DOUBLE PRECISION DEFAULT 0.0,
    duration        TEXT,
    expires_at      DOUBLE PRECISION,
    status          TEXT            NOT NULL DEFAULT 'active',
    created_at      DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS portal_sessions (
    token           TEXT            PRIMARY KEY,
    user_id         TEXT            NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
    expires_at      DOUBLE PRECISION NOT NULL,
    created_at      DOUBLE PRECISION NOT NULL
);

-- ===========================================================================
-- INDEXES
-- ===========================================================================

-- Virtual keys
CREATE INDEX IF NOT EXISTS idx_token_user_id    ON "LiteLLM_VerificationToken" ("user_id");
CREATE INDEX IF NOT EXISTS idx_token_team_id    ON "LiteLLM_VerificationToken" ("team_id");
CREATE INDEX IF NOT EXISTS idx_token_expires    ON "LiteLLM_VerificationToken" ("expires");
CREATE INDEX IF NOT EXISTS idx_token_blocked    ON "LiteLLM_VerificationToken" ("blocked") WHERE "blocked" = FALSE;

-- Users
CREATE INDEX IF NOT EXISTS idx_user_email       ON "LiteLLM_UserTable" ("user_email");
CREATE INDEX IF NOT EXISTS idx_user_role        ON "LiteLLM_UserTable" ("user_role");

-- Spend logs
CREATE INDEX IF NOT EXISTS idx_spend_logs_user_time     ON "LiteLLMSpendLogs" ("user", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_apikey_time   ON "LiteLLMSpendLogs" ("api_key", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_team_time     ON "LiteLLMSpendLogs" ("team_id", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_model_time    ON "LiteLLMSpendLogs" ("model", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_metadata_gin  ON "LiteLLMSpendLogs" USING GIN ("metadata");
CREATE INDEX IF NOT EXISTS idx_spend_logs_request_tags  ON "LiteLLMSpendLogs" USING GIN ("request_tags");

-- Portal indexes
CREATE INDEX IF NOT EXISTS idx_portal_users_email       ON portal_users(email);
CREATE INDEX IF NOT EXISTS idx_portal_keys_user         ON portal_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_portal_keys_key          ON portal_keys(key);
CREATE INDEX IF NOT EXISTS idx_portal_keys_status       ON portal_keys(status, user_id);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_token    ON portal_sessions(token);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_user     ON portal_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_portal_sessions_expires  ON portal_sessions(expires_at);
