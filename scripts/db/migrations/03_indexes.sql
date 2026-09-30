-- PostgreSQL 14+ operational indexes and rolling LiteLLM spend partitions.
-- Safe to run repeatedly from deployment automation or a monthly scheduler.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class table_class
        JOIN pg_namespace namespace ON namespace.oid = table_class.relnamespace
        WHERE namespace.nspname = current_schema()
          AND table_class.relname = 'LiteLLMSpendLogs'
          AND NOT EXISTS (
              SELECT 1 FROM pg_partitioned_table WHERE partrelid = table_class.oid
          )
    ) THEN
        ALTER TABLE "LiteLLMSpendLogs" RENAME TO "LiteLLMSpendLogs_legacy_flat";

        DROP INDEX IF EXISTS idx_spend_logs_user_time;
        DROP INDEX IF EXISTS idx_spend_logs_apikey_time;
        DROP INDEX IF EXISTS idx_spend_logs_team_time;
        DROP INDEX IF EXISTS idx_spend_logs_model_time;
        DROP INDEX IF EXISTS idx_spend_logs_metadata_gin;
        DROP INDEX IF EXISTS idx_spend_logs_request_tags;

        CREATE TABLE "LiteLLMSpendLogs" (
            "request_id" TEXT NOT NULL,
            "call_type" TEXT NOT NULL DEFAULT '',
            "api_key" TEXT NOT NULL DEFAULT '',
            "spend" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            "total_tokens" INTEGER NOT NULL DEFAULT 0,
            "prompt_tokens" INTEGER NOT NULL DEFAULT 0,
            "completion_tokens" INTEGER NOT NULL DEFAULT 0,
            "startTime" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "endTime" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "completionStartTime" TIMESTAMPTZ,
            "model" TEXT NOT NULL DEFAULT '',
            "model_id" TEXT,
            "model_group" TEXT,
            "api_base" TEXT,
            "user" TEXT,
            "team_id" TEXT,
            "org_id" TEXT,
            "metadata" JSONB,
            "cache_hit" TEXT,
            "cache_key" TEXT,
            "request_tags" JSONB,
            "requester_ip_address" TEXT,
            "messages" JSONB,
            "response" JSONB,
            "proxy_server_request" JSONB,
            "session_id" TEXT,
            "error_str" TEXT,
            PRIMARY KEY ("request_id", "startTime")
        ) PARTITION BY RANGE ("startTime");

        CREATE TABLE "LiteLLMSpendLogs_default" PARTITION OF "LiteLLMSpendLogs" DEFAULT;

    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION ensure_litellm_spend_log_partitions(months_ahead integer DEFAULT 2)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    partition_start date;
    partition_end date;
    partition_name text;
    offset integer;
BEGIN
    FOR offset IN 0..months_ahead LOOP
        partition_start := date_trunc('month', CURRENT_DATE)::date + make_interval(months => offset);
        partition_end := partition_start + INTERVAL '1 month';
        partition_name := format('LiteLLMSpendLogs_%s', to_char(partition_start, 'YYYY_MM'));
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF "LiteLLMSpendLogs" FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_start,
            partition_end
        );
    END LOOP;
END;
$$;

SELECT ensure_litellm_spend_log_partitions(2);

DO $$
BEGIN
    IF to_regclass('"LiteLLMSpendLogs_legacy_flat"') IS NOT NULL THEN
        INSERT INTO "LiteLLMSpendLogs" (
            "request_id", "call_type", "api_key", "spend", "total_tokens", "prompt_tokens",
            "completion_tokens", "startTime", "endTime", "model", "user", "team_id", "metadata",
            "cache_hit", "cache_key", "request_tags", "requester_ip_address", "messages", "response",
            "proxy_server_request"
        )
        SELECT
            "request_id", "call_type", "api_key", "spend", "total_tokens", "prompt_tokens",
            "completion_tokens", "startTime", "endTime", "model", "user", "team_id", "metadata",
            "cache_hit", "cache_key", "request_tags", "requester_ip_address", "messages", "response",
            "proxy_server_request"
        FROM "LiteLLMSpendLogs_legacy_flat"
        ON CONFLICT ("request_id", "startTime") DO NOTHING;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_spend_logs_user_time ON "LiteLLMSpendLogs" ("user", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_apikey_time ON "LiteLLMSpendLogs" ("api_key", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_user_apikey_time ON "LiteLLMSpendLogs" ("user", "api_key", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_team_time ON "LiteLLMSpendLogs" ("team_id", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_model_time ON "LiteLLMSpendLogs" ("model", "startTime" DESC);
CREATE INDEX IF NOT EXISTS idx_spend_logs_metadata_gin ON "LiteLLMSpendLogs" USING GIN ("metadata");
CREATE INDEX IF NOT EXISTS idx_spend_logs_request_tags ON "LiteLLMSpendLogs" USING GIN ("request_tags");

-- Virtual token composite lookup and billing indexes
CREATE INDEX IF NOT EXISTS idx_token_user_created ON "LiteLLM_VerificationToken" ("user_id", "created_at" DESC);
CREATE INDEX IF NOT EXISTS idx_token_user_spend ON "LiteLLM_VerificationToken" ("user_id", "spend" DESC);

