use axum::{
    Json, Router,
    extract::{Query, State},
    http::{HeaderMap, header::AUTHORIZATION},
    routing::{get, post},
};
use chrono::{Duration, Utc};
use serde::Deserialize;
use serde_json::{Value, json};
use uuid::Uuid;

use crate::{Error, GatewayAuth, hash_token};

pub fn management_router(auth: GatewayAuth) -> Router {
    Router::new()
        .route("/key/generate", post(key_generate))
        .route("/key/info", get(key_info))
        .route("/key/update", post(key_update))
        .route("/key/delete", post(key_delete))
        .with_state(auth)
}

pub(crate) async fn require_master(auth: &GatewayAuth, headers: &HeaderMap) -> Result<(), Error> {
    let provided = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or(Error::InvalidToken)?;
    if auth.master_auth.verify_master_token(provided).await? {
        return Ok(());
    }
    Err(Error::InvalidToken)
}

fn require_pg(auth: &GatewayAuth) -> Result<&crate::store::PgPool, Error> {
    auth.pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))
}

pub fn normalize_key_or_hash(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.len() == 64 && trimmed.bytes().all(|b| b.is_ascii_hexdigit()) {
        trimmed.to_ascii_lowercase()
    } else {
        hash_token(trimmed)
    }
}

pub fn mask_key_name(raw: &str) -> String {
    if raw.len() <= 8 {
        return "****".to_owned();
    }
    let suffix = &raw[raw.len() - 4..];
    format!("sk-...{suffix}")
}

pub fn parse_duration_secs(raw: &str) -> Option<i64> {
    let s = raw.trim();
    if s.is_empty() {
        return None;
    }
    let (num_part, mult) = if let Some(v) = s.strip_suffix("ms") {
        let ms: i64 = v.trim().parse().ok()?;
        return Some((ms / 1000).max(1));
    } else if let Some(v) = s.strip_suffix('d') {
        (v, 86_400_i64)
    } else if let Some(v) = s.strip_suffix('h') {
        (v, 3_600_i64)
    } else if let Some(v) = s.strip_suffix('m') {
        (v, 60_i64)
    } else if let Some(v) = s.strip_suffix('s') {
        (v, 1_i64)
    } else {
        (s, 1_i64)
    };
    let n: i64 = num_part.trim().parse().ok()?;
    (n > 0).then(|| n.saturating_mul(mult))
}

#[derive(Deserialize)]
struct GenerateKeyRequest {
    key: Option<String>,
    key_alias: Option<String>,
    user_id: Option<String>,
    team_id: Option<String>,
    organization_id: Option<String>,
    #[serde(default)]
    models: Vec<String>,
    max_budget: Option<f64>,
    rpm_limit: Option<i64>,
    tpm_limit: Option<i64>,
    duration: Option<String>,
    metadata: Option<Value>,
}

async fn key_generate(
    State(auth): State<GatewayAuth>,
    headers: HeaderMap,
    Json(req): Json<GenerateKeyRequest>,
) -> Result<Json<Value>, Error> {
    require_master(&auth, &headers).await?;
    let pool = require_pg(&auth)?;

    let raw_key = req
        .key
        .map(|k| k.trim().to_owned())
        .filter(|k| !k.is_empty())
        .unwrap_or_else(|| format!("sk-{}", Uuid::new_v4().simple()));
    let token_hash = hash_token(&raw_key);
    let key_name = mask_key_name(&raw_key);
    let expires_at = match req.duration.as_deref() {
        Some(dur) => {
            let secs = parse_duration_secs(dur)
                .ok_or_else(|| Error::InvalidRequest(format!("invalid duration `{dur}`")))?;
            Some((Utc::now() + Duration::seconds(secs)).naive_utc())
        }
        None => None,
    };
    let metadata_json = req.metadata.unwrap_or_else(|| json!({}));

    let client = pool.get().await.map_err(|err| {
        tracing::error!("postgres pool acquisition failed in /key/generate: {err}");
        Error::Store
    })?;

    client
        .execute(
            r#"
            INSERT INTO "LiteLLM_VerificationToken" (
                token, key_name, key_alias, spend, total_spend, max_budget,
                expires, models, user_id, team_id, organization_id,
                rpm_limit, tpm_limit, metadata
            ) VALUES (
                $1, $2, $3, 0.0, 0.0, $4,
                $5, $6, $7, $8, $9,
                $10, $11, $12
            )
            "#,
            &[
                &token_hash,
                &key_name,
                &req.key_alias,
                &req.max_budget,
                &expires_at,
                &req.models,
                &req.user_id,
                &req.team_id,
                &req.organization_id,
                &req.rpm_limit,
                &req.tpm_limit,
                &metadata_json,
            ],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres insert failed in /key/generate: {err}");
            Error::Store
        })?;

    Ok(Json(json!({
        "key": raw_key,
        "token": token_hash,
        "key_name": key_name,
        "key_alias": req.key_alias,
        "user_id": req.user_id,
        "team_id": req.team_id,
        "organization_id": req.organization_id,
        "models": req.models,
        "max_budget": req.max_budget,
        "rpm_limit": req.rpm_limit,
        "tpm_limit": req.tpm_limit,
        "expires": expires_at.map(|dt| dt.and_utc().to_rfc3339()),
    })))
}

#[derive(Deserialize)]
struct KeyInfoQuery {
    key: String,
}

async fn key_info(
    State(auth): State<GatewayAuth>,
    headers: HeaderMap,
    Query(query): Query<KeyInfoQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&auth, &headers).await?;
    let pool = require_pg(&auth)?;
    if query.key.trim().is_empty() {
        return Err(Error::InvalidRequest(
            "key query parameter is required".into(),
        ));
    }
    let token_hash = normalize_key_or_hash(&query.key);
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let row = client
        .query_opt(
            r#"
            SELECT
                token, key_name, key_alias,
                COALESCE(spend, 0.0)::double precision AS spend,
                COALESCE(total_spend, 0.0)::double precision AS total_spend,
                max_budget::double precision AS max_budget,
                expires,
                COALESCE(models, ARRAY[]::text[]) AS models,
                user_id, team_id, organization_id,
                COALESCE(blocked, false) AS blocked,
                rpm_limit, tpm_limit
            FROM "LiteLLM_VerificationToken"
            WHERE token = $1
            LIMIT 1
            "#,
            &[&token_hash],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres query failed in /key/info: {err}");
            Error::Store
        })?
        .ok_or_else(|| Error::NotFound(format!("key `{token_hash}` not found")))?;

    let expires = row
        .try_get::<_, Option<chrono::NaiveDateTime>>("expires")
        .map_err(|_| Error::Store)?
        .map(|dt| dt.and_utc().to_rfc3339());
    let models = row
        .try_get::<_, Vec<String>>("models")
        .map_err(|_| Error::Store)?;

    Ok(Json(json!({
        "key": token_hash,
        "info": {
            "token": row.try_get::<_, String>("token").map_err(|_| Error::Store)?,
            "key_name": row.try_get::<_, Option<String>>("key_name").map_err(|_| Error::Store)?,
            "key_alias": row.try_get::<_, Option<String>>("key_alias").map_err(|_| Error::Store)?,
            "spend": row.try_get::<_, f64>("spend").map_err(|_| Error::Store)?,
            "total_spend": row.try_get::<_, f64>("total_spend").map_err(|_| Error::Store)?,
            "max_budget": row.try_get::<_, Option<f64>>("max_budget").map_err(|_| Error::Store)?,
            "expires": expires,
            "models": models,
            "user_id": row.try_get::<_, Option<String>>("user_id").map_err(|_| Error::Store)?,
            "team_id": row.try_get::<_, Option<String>>("team_id").map_err(|_| Error::Store)?,
            "organization_id": row.try_get::<_, Option<String>>("organization_id").map_err(|_| Error::Store)?,
            "blocked": row.try_get::<_, bool>("blocked").map_err(|_| Error::Store)?,
            "rpm_limit": row.try_get::<_, Option<i64>>("rpm_limit").map_err(|_| Error::Store)?,
            "tpm_limit": row.try_get::<_, Option<i64>>("tpm_limit").map_err(|_| Error::Store)?,
        }
    })))
}

#[derive(Deserialize)]
struct UpdateKeyRequest {
    key: String,
    key_alias: Option<String>,
    max_budget: Option<f64>,
    rpm_limit: Option<i64>,
    tpm_limit: Option<i64>,
    models: Option<Vec<String>>,
    blocked: Option<bool>,
    duration: Option<String>,
}

async fn key_update(
    State(auth): State<GatewayAuth>,
    headers: HeaderMap,
    Json(req): Json<UpdateKeyRequest>,
) -> Result<Json<Value>, Error> {
    require_master(&auth, &headers).await?;
    let pool = require_pg(&auth)?;
    if req.key.trim().is_empty() {
        return Err(Error::InvalidRequest("key is required".into()));
    }
    let token_hash = normalize_key_or_hash(&req.key);
    let expires_at = match req.duration.as_deref() {
        Some(dur) => {
            let secs = parse_duration_secs(dur)
                .ok_or_else(|| Error::InvalidRequest(format!("invalid duration `{dur}`")))?;
            Some((Utc::now() + Duration::seconds(secs)).naive_utc())
        }
        None => None,
    };

    let client = pool.get().await.map_err(|_| Error::Store)?;
    let affected = client
        .execute(
            r#"
            UPDATE "LiteLLM_VerificationToken"
            SET
                key_alias = COALESCE($2, key_alias),
                max_budget = COALESCE($3, max_budget),
                rpm_limit = COALESCE($4, rpm_limit),
                tpm_limit = COALESCE($5, tpm_limit),
                models = COALESCE($6, models),
                blocked = COALESCE($7, blocked),
                expires = COALESCE($8, expires),
                updated_at = NOW()
            WHERE token = $1
            "#,
            &[
                &token_hash,
                &req.key_alias,
                &req.max_budget,
                &req.rpm_limit,
                &req.tpm_limit,
                &req.models,
                &req.blocked,
                &expires_at,
            ],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres update failed in /key/update: {err}");
            Error::Store
        })?;
    if affected == 0 {
        return Err(Error::NotFound(format!("key `{token_hash}` not found")));
    }

    auth.invalidate_key(&token_hash).await;
    Ok(Json(json!({ "key": token_hash, "status": "updated" })))
}

#[derive(Deserialize)]
struct DeleteKeyRequest {
    keys: Vec<String>,
}

async fn key_delete(
    State(auth): State<GatewayAuth>,
    headers: HeaderMap,
    Json(req): Json<DeleteKeyRequest>,
) -> Result<Json<Value>, Error> {
    require_master(&auth, &headers).await?;
    let pool = require_pg(&auth)?;
    if req.keys.is_empty() {
        return Err(Error::InvalidRequest("keys list must not be empty".into()));
    }
    let hashes: Vec<String> = req.keys.iter().map(|k| normalize_key_or_hash(k)).collect();
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let deleted_rows = client
        .query(
            r#"DELETE FROM "LiteLLM_VerificationToken" WHERE token = ANY($1) RETURNING token"#,
            &[&hashes],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres delete failed in /key/delete: {err}");
            Error::Store
        })?;

    let mut deleted = Vec::with_capacity(deleted_rows.len());
    for row in deleted_rows {
        if let Ok(tok) = row.try_get::<_, String>("token") {
            auth.invalidate_key(&tok).await;
            deleted.push(tok);
        }
    }
    Ok(Json(json!({ "deleted_keys": deleted })))
}

#[cfg(test)]
mod tests {
    use axum::{
        body::Body,
        http::{Request, StatusCode},
    };
    use futures_util::future::BoxFuture;
    use litellm_auth_types::SecretValue;
    use litellm_config::Config;
    use litellm_secrets::source::SecretSource;
    use std::sync::Arc;
    use tower::ServiceExt;

    use super::*;

    struct DummySecrets;

    impl SecretSource for DummySecrets {
        fn get_secret_str<'a>(
            &'a self,
            _name: &'a str,
        ) -> BoxFuture<'a, Result<Option<SecretValue>, litellm_secrets::Error>> {
            Box::pin(async { Ok(None) })
        }
    }

    #[test]
    fn normalizes_keys_durations_and_masks() {
        let raw = "sk-abc123def456";
        let hash = hash_token(raw);
        assert_eq!(normalize_key_or_hash(raw), hash);
        assert_eq!(normalize_key_or_hash(&hash.to_uppercase()), hash);
        assert_eq!(mask_key_name(raw), "sk-...f456");
        assert_eq!(parse_duration_secs("30d"), Some(30 * 86_400));
        assert_eq!(parse_duration_secs("12h"), Some(12 * 3_600));
        assert_eq!(parse_duration_secs("5m"), Some(300));
        assert_eq!(parse_duration_secs("bad"), None);
    }

    #[tokio::test]
    async fn management_endpoints_require_master_key() {
        let cfg =
            Config::from_yaml("model_list: []\ngeneral_settings:\n  master_key: sk-master-test\n")
                .unwrap();
        let auth = GatewayAuth::stateless(&cfg, Arc::new(DummySecrets));
        let app = management_router(auth);

        let unauth = app
            .clone()
            .oneshot(
                Request::post("/key/generate")
                    .header("content-type", "application/json")
                    .body(Body::from("{}"))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(unauth.status(), StatusCode::UNAUTHORIZED);

        let wrong = app
            .oneshot(
                Request::get("/key/info?key=abc")
                    .header("authorization", "Bearer wrong")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(wrong.status(), StatusCode::UNAUTHORIZED);
    }
}
