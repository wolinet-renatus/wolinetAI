-- ==============================================================================
-- Wolinet AI — WebUI Database Migration (PostgreSQL-native)
-- Run against the 'webui' database.
-- All text-based JSON → JSONB
-- All flexible string types → VARCHAR / TEXT with explicit constraints
-- Binary blobs → BYTEA
-- Composite indexes on user_id, timestamp, api_key
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Users (identity + profile)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "user" (
    id                          VARCHAR(255)    PRIMARY KEY,
    email                       VARCHAR(255)    UNIQUE NOT NULL,
    username                    VARCHAR(50),
    role                        VARCHAR(32)     NOT NULL DEFAULT 'pending',
    name                        TEXT            NOT NULL,
    profile_image_url           TEXT,
    profile_banner_image_url    TEXT,
    bio                         TEXT,
    gender                      TEXT,
    location                    TEXT,
    website                     TEXT,
    birthday                    DATE,
    last_active_at              BIGINT,
    created_at                  BIGINT,
    updated_at                  BIGINT,
    api_key                     VARCHAR(255)    UNIQUE,
    settings                    JSONB,
    info                        JSONB,
    oauth_sub                   TEXT,
    permissions                 JSONB,
    is_active                   BOOLEAN         NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_user_email           ON "user" (email);
CREATE INDEX IF NOT EXISTS idx_user_role            ON "user" (role);
CREATE INDEX IF NOT EXISTS idx_user_last_active     ON "user" (last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_api_key         ON "user" (api_key) WHERE api_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Auth (credential ↔ user linkage)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth (
    id          VARCHAR(255)    PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
    email       VARCHAR(255)    UNIQUE NOT NULL,
    password    TEXT            NOT NULL,
    active      BOOLEAN         NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_auth_email   ON auth (email);
CREATE INDEX IF NOT EXISTS idx_auth_active  ON auth (active) WHERE active = TRUE;

-- ---------------------------------------------------------------------------
-- Chat sessions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat (
    id              VARCHAR(255)    PRIMARY KEY,
    user_id         VARCHAR(255)    NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    title           TEXT            NOT NULL DEFAULT 'New Chat',
    chat            JSONB,
    created_at      BIGINT,
    updated_at      BIGINT,
    share_id        VARCHAR(255)    UNIQUE,
    archived        BOOLEAN         NOT NULL DEFAULT FALSE,
    pinned          BOOLEAN,
    meta            JSONB,
    folder_id       VARCHAR(255),
    session_id      VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_chat_user_updated    ON chat (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_user_archived   ON chat (user_id, archived);
CREATE INDEX IF NOT EXISTS idx_chat_share_id        ON chat (share_id) WHERE share_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_folder          ON chat (folder_id) WHERE folder_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_updated         ON chat (updated_at DESC);
-- GIN index enables JSONB key-value filtering on chat content (search feature)
CREATE INDEX IF NOT EXISTS idx_chat_content_gin     ON chat USING GIN (chat);

-- ---------------------------------------------------------------------------
-- Chat messages (separate table for high-volume realtime saves)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_message (
    id              VARCHAR(255)    PRIMARY KEY,
    user_id         VARCHAR(255)    NOT NULL,
    channel_id      VARCHAR(255),
    parent_id       VARCHAR(255),
    content         TEXT,
    data            JSONB,
    meta            JSONB,
    created_at      BIGINT,
    updated_at      BIGINT,
    CONSTRAINT fk_chat_message_user FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_message_user        ON chat_message (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_message_channel     ON chat_message (channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_message_parent      ON chat_message (parent_id);

-- ---------------------------------------------------------------------------
-- Knowledge base
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge (
    id              VARCHAR(255)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    name            TEXT            NOT NULL,
    description     TEXT,
    data            JSONB,
    meta            JSONB,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_user       ON knowledge (user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_updated    ON knowledge (updated_at DESC);

-- Knowledge ↔ File join table
CREATE TABLE IF NOT EXISTS knowledge_file (
    knowledge_id    VARCHAR(255)    NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    file_id         VARCHAR(255)    NOT NULL,
    PRIMARY KEY (knowledge_id, file_id)
);

-- ---------------------------------------------------------------------------
-- Files (uploaded documents, embeddings source)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS file (
    id              VARCHAR(255)    PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    hash            TEXT,
    filename        TEXT            NOT NULL,
    path            TEXT,
    data            JSONB,
    meta            JSONB,
    access_control  JSONB,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_file_user        ON file (user_id);
CREATE INDEX IF NOT EXISTS idx_file_hash        ON file (hash) WHERE hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_file_created_at  ON file (created_at DESC);

-- ---------------------------------------------------------------------------
-- Prompts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompt (
    command         VARCHAR(255)    PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    title           TEXT            NOT NULL,
    content         TEXT            NOT NULL,
    timestamp       BIGINT,
    access_control  JSONB
);

CREATE INDEX IF NOT EXISTS idx_prompt_user      ON prompt (user_id);
CREATE INDEX IF NOT EXISTS idx_prompt_timestamp ON prompt (timestamp DESC);

-- ---------------------------------------------------------------------------
-- Models (custom model cards)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model (
    id              TEXT            PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    base_model_id   TEXT,
    name            TEXT            NOT NULL,
    params          JSONB,
    meta            JSONB,
    access_control  JSONB,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_model_user       ON model (user_id);
CREATE INDEX IF NOT EXISTS idx_model_active     ON model (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_model_updated    ON model (updated_at DESC);

-- ---------------------------------------------------------------------------
-- Tools
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool (
    id              TEXT            PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    name            TEXT            NOT NULL,
    content         TEXT,
    specs           JSONB,
    meta            JSONB,
    valves          JSONB,
    access_control  JSONB,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      BIGINT,
    updated_at      BIGINT
);

-- ---------------------------------------------------------------------------
-- Functions (serverless pipeline functions)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS function (
    id              TEXT            PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    name            TEXT            NOT NULL,
    type            TEXT,
    content         TEXT,
    meta            JSONB,
    valves          JSONB,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_global       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      BIGINT,
    updated_at      BIGINT
);

-- ---------------------------------------------------------------------------
-- Memory (user-scoped long-term memory)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memory (
    id              VARCHAR(255)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    user_id         VARCHAR(255)    NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    content         TEXT,
    updated_at      BIGINT,
    created_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_memory_user ON memory (user_id);

-- ---------------------------------------------------------------------------
-- Feedbacks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id              VARCHAR(255)    PRIMARY KEY,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    version         INTEGER         NOT NULL DEFAULT 0,
    type            TEXT,
    data            JSONB,
    meta            JSONB,
    snapshot        JSONB,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_feedback_user    ON feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type    ON feedback (type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at DESC);

-- ---------------------------------------------------------------------------
-- OAuth sessions (for SSO providers)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS oauth_session (
    id              VARCHAR(255)    PRIMARY KEY,
    code_challenge  TEXT            UNIQUE,
    redirect_uri    TEXT,
    created_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_oauth_session_code ON oauth_session (code_challenge) WHERE code_challenge IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Groups (team / org level access control)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "group" (
    id              VARCHAR(255)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    name            TEXT            NOT NULL,
    description     TEXT,
    data            JSONB,
    meta            JSONB,
    permissions     JSONB,
    user_ids        JSONB,
    admin_ids       JSONB,
    is_public       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_group_user ON "group" (user_id);

-- ---------------------------------------------------------------------------
-- Channels (real-time messaging)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS channel (
    id              VARCHAR(255)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE SET NULL,
    type            TEXT,
    name            TEXT            NOT NULL,
    description     TEXT,
    data            JSONB,
    meta            JSONB,
    access_control  JSONB,
    created_at      BIGINT,
    updated_at      BIGINT
);

-- ---------------------------------------------------------------------------
-- Folders (chat organisation)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS folder (
    id              VARCHAR(255)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    parent_id       VARCHAR(255),
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE CASCADE,
    name            TEXT            NOT NULL,
    type            TEXT,
    items           JSONB,
    meta            JSONB,
    is_expanded     BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      BIGINT,
    updated_at      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_folder_user ON folder (user_id);

-- ---------------------------------------------------------------------------
-- Tags
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag (
    id              TEXT,
    name            TEXT            NOT NULL,
    user_id         VARCHAR(255)    REFERENCES "user"(id) ON DELETE CASCADE,
    PRIMARY KEY (id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_tag_user ON tag (user_id);

-- ---------------------------------------------------------------------------
-- Config (Key-Value configuration store + legacy backup)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS config (
    key         TEXT            PRIMARY KEY,
    value       JSONB           NOT NULL,
    updated_at  BIGINT
);

CREATE TABLE IF NOT EXISTS config_old (
    id          SERIAL          PRIMARY KEY,
    data        JSONB           NOT NULL,
    version     INTEGER         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     DEFAULT NOW()
);
