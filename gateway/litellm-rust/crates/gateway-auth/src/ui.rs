use std::sync::Arc;

use axum::{
    Json, Router,
    extract::{Path, Query, State},
    http::{HeaderMap, HeaderValue, StatusCode, header::SET_COOKIE},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use chrono::Utc;
use litellm_config::{Config, process_env_lookup};
use serde::Deserialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use uuid::Uuid;

use crate::{Error, GatewayAuth, management::require_master};

#[derive(Clone, Debug)]
pub struct UiModelSummary {
    pub model_name: String,
    pub model_id: String,
    pub provider_model: String,
    pub api_base: Option<String>,
    pub mode: Option<String>,
    pub custom_llm_provider: Option<String>,
}

#[derive(Clone)]
pub struct UiState {
    pub auth: GatewayAuth,
    pub models: Arc<Vec<UiModelSummary>>,
    pub db_configured: bool,
    pub redis_configured: bool,
    pub store_model_in_db: bool,
    pub disable_env_credential_login: bool,
    pub hide_default_credentials_hint: bool,
}

impl UiState {
    pub fn from_config(auth: GatewayAuth, config: &Config) -> Self {
        let models = config
            .model_list
            .iter()
            .enumerate()
            .map(|(idx, m)| UiModelSummary {
                model_name: m.model_name.clone(),
                model_id: m
                    .model_info
                    .as_ref()
                    .and_then(|info| info.id.clone())
                    .unwrap_or_else(|| format!("cfg-{idx}-{}", m.model_name)),
                provider_model: m.litellm_params.model.clone(),
                api_base: m.litellm_params.api_base.clone(),
                mode: m.model_info.as_ref().and_then(|info| info.mode.clone()),
                custom_llm_provider: m.litellm_params.custom_llm_provider.clone(),
            })
            .collect();

        Self {
            db_configured: auth.is_db_configured(),
            redis_configured: auth.is_redis_configured(),
            auth,
            models: Arc::new(models),
            store_model_in_db: config.general_settings.store_model_in_db.unwrap_or(false),
            disable_env_credential_login: config
                .general_settings
                .disable_env_credential_login
                .unwrap_or(false),
            hide_default_credentials_hint: config
                .general_settings
                .hide_default_credentials_hint
                .unwrap_or(true),
        }
    }
}

pub fn ui_router(state: UiState) -> Router {
    Router::new()
        .route("/.well-known/litellm-ui-config", get(ui_config))
        .route("/litellm/.well-known/litellm-ui-config", get(ui_config))
        .route("/openapi.json", get(openapi_spec))
        .route("/get/ui_theme_settings", get(ui_theme_settings))
        .route("/get/ui_settings", get(ui_settings))
        .route("/sso/get/ui_settings", get(sso_ui_settings))
        .route("/v2/login", post(login_v2))
        .route("/public/litellm_model_cost_map", get(empty_object))
        .route("/public/litellm_blog_posts", get(blog_posts))
        .route("/get_model_cost_map", get(empty_object))
        .route("/public/model_hub", get(public_model_hub))
        .route("/public/model_hub/info", get(public_model_hub))
        .route("/public/providers/fields", get(public_provider_fields))
        .route("/health/readiness/details", get(health_readiness_details))
        .route("/health/license", get(empty_object))
        .route("/get/latest_release_info", get(latest_release_info))
        .route("/get/user_banner", get(user_banner))
        .route("/api/plugins", get(empty_array))
        .route("/config/list", get(config_list))
        .route("/credentials", get(credentials_list))
        .route("/credentials/by_model/{*model_id}", get(credential_by_model))
        .route("/credentials/by_name/{*credential_name}", get(credential_by_name))
        .route("/user/info", get(user_info))
        .route("/v2/user/info", get(user_info_v2))
        .route("/user/available_roles", get(available_roles))
        .route("/user/available_users", get(available_users))
        .route("/key/list", get(key_list))
        .route("/key/aliases", get(key_aliases))
        .route("/model/info", get(model_info))
        .route("/v1/model/info", get(model_info))
        .route("/v2/model/info", get(model_info))
        .route("/model_group/info", get(model_group_info))
        .route("/claude-code/plugins", get(claude_code_plugins_list).post(claude_code_plugins_create))
        .route("/claude-code/plugins/{name}", get(claude_code_plugin_get).delete(claude_code_plugin_delete))
        .route("/claude-code/plugins/{name}/enable", post(claude_code_plugin_enable))
        .route("/claude-code/plugins/{name}/disable", post(claude_code_plugin_disable))
        .route("/v1/memory", get(memory_list).post(memory_create))
        .route("/v1/memory/{*key}", get(memory_get).put(memory_upsert).delete(memory_delete))
        .route("/v2/team/list", get(team_list_v2))
        .route("/team/list", get(team_list))
        .route("/team/metadata_schema", get(team_metadata_schema))
        .route("/organization/list", get(organization_list))
        .route("/user/list", get(user_list))
        .route("/project/list", get(auth_empty_array))
        .route("/tag/list", get(auth_empty_object))
        .route("/v1/agents", get(auth_empty_array))
        .route("/v2/guardrails/list", get(guardrails_list))
        .route("/guardrails/list", get(guardrails_list))
        .route("/prompts/list", get(prompts_list))
        .route("/policies/list", get(policies_list))
        .route("/spend/logs", get(spend_logs_list))
        .route("/spend/logs/v2", get(spend_logs_paginated))
        .route("/global/spend/logs", get(spend_logs_list))
        .route("/global/spend", get(global_spend))
        .route("/global/spend/models", get(empty_array))
        .route("/global/spend/teams", get(empty_array))
        .with_state(state)
}

fn ct_eq_str(a: &str, b: &str) -> bool {
    let ha = Sha256::digest(a.as_bytes());
    let hb = Sha256::digest(b.as_bytes());
    bool::from(ha.ct_eq(&hb))
}

fn base64url_encode(input: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut out = String::with_capacity(input.len().div_ceil(3) * 4);
    for chunk in input.chunks(3) {
        let b0 = chunk[0];
        let b1 = *chunk.get(1).unwrap_or(&0);
        let b2 = *chunk.get(2).unwrap_or(&0);
        out.push(TABLE[(b0 >> 2) as usize] as char);
        out.push(TABLE[(((b0 & 0x03) << 4) | (b1 >> 4)) as usize] as char);
        if chunk.len() > 1 {
            out.push(TABLE[(((b1 & 0x0f) << 2) | (b2 >> 6)) as usize] as char);
        }
        if chunk.len() > 2 {
            out.push(TABLE[(b2 & 0x3f) as usize] as char);
        }
    }
    out
}

fn hmac_sha256(key: &[u8], msg: &[u8]) -> [u8; 32] {
    let mut key_block = [0u8; 64];
    if key.len() > 64 {
        let digest = Sha256::digest(key);
        key_block[..32].copy_from_slice(&digest);
    } else {
        key_block[..key.len()].copy_from_slice(key);
    }
    let mut ipad = [0x36u8; 64];
    let mut opad = [0x5cu8; 64];
    for idx in 0..64 {
        ipad[idx] ^= key_block[idx];
        opad[idx] ^= key_block[idx];
    }

    let mut inner = Sha256::new();
    inner.update(ipad);
    inner.update(msg);
    let inner_hash = inner.finalize();

    let mut outer = Sha256::new();
    outer.update(opad);
    outer.update(inner_hash);
    outer.finalize().into()
}

pub fn sign_hs256_jwt(claims: &Value, secret: &str) -> Result<String, Error> {
    let header_b64 = base64url_encode(br#"{"alg":"HS256","typ":"JWT"}"#);
    let payload_bytes = serde_json::to_vec(claims).map_err(|_| Error::Store)?;
    let payload_b64 = base64url_encode(&payload_bytes);
    let signing_input = format!("{header_b64}.{payload_b64}");
    let sig = hmac_sha256(secret.as_bytes(), signing_input.as_bytes());
    let sig_b64 = base64url_encode(&sig);
    Ok(format!("{signing_input}.{sig_b64}"))
}

async fn ui_config(State(state): State<UiState>) -> Json<Value> {
    Json(json!({
        "server_root_path": "/",
        "proxy_base_url": null,
        "auto_redirect_to_sso": false,
        "admin_ui_disabled": false,
        "sso_configured": false,
        "hide_default_credentials_hint": state.hide_default_credentials_hint,
        "is_control_plane": false,
        "workers": [],
    }))
}

async fn ui_theme_settings() -> Json<Value> {
    Json(json!({
        "values": {
            "logo_url": "/get_image",
            "logo_url_dark": "/get_image",
            "favicon_url": "/favicon.ico",
        }
    }))
}

async fn empty_object() -> Json<Value> {
    Json(json!({}))
}

async fn empty_array() -> Json<Value> {
    Json(json!([]))
}

async fn blog_posts() -> Json<Value> {
    Json(json!({ "posts": [] }))
}

async fn ui_settings() -> Json<Value> {
    Json(json!({
        "values": {
            "disable_model_health_check_ui": false,
            "enable_ptu_cost_attribution": false,
            "apply_user_budget_to_team_keys": false,
        },
        "field_schema": {},
        "source": {},
    }))
}

async fn sso_ui_settings(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({
        "PROXY_BASE_URL": null,
        "PROXY_LOGOUT_URL": null,
        "LITELLM_UI_API_DOC_BASE_URL": "https://docs.wolinet.com",
        "DEFAULT_TEAM_DISABLED": false,
        "SSO_ENABLED": false,
        "NUM_SPEND_LOGS_ROWS": 0,
        "DISABLE_EXPENSIVE_DB_QUERIES": false,
    })))
}

async fn latest_release_info(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({
        "version": env!("CARGO_PKG_VERSION"),
        "new_features": 0,
        "bug_fixes": 0,
        "other_updates": 0,
        "release_url": "https://github.com/wolinet-renatus/wolinetAI",
    })))
}

async fn available_roles(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({
        "proxy_admin": { "description": "Proxy Admin role", "ui_label": "Admin" },
        "proxy_admin_viewer": { "description": "Proxy Admin Viewer role", "ui_label": "Admin Viewer" },
        "internal_user": { "description": "Internal User role", "ui_label": "Internal User" },
        "internal_user_viewer": { "description": "Internal User Viewer role", "ui_label": "Internal User Viewer" },
    })))
}

async fn available_users(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({
        "total_users": null,
        "total_users_used": 1,
        "total_users_remaining": null,
        "total_teams": null,
        "total_teams_used": 0,
        "total_teams_remaining": null,
    })))
}

async fn auth_empty_array(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!([])))
}

async fn auth_empty_object(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({})))
}

async fn guardrails_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({ "guardrails": [] })))
}

async fn prompts_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({ "prompts": [] })))
}

async fn policies_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({ "policies": [], "total_count": 0 })))
}

async fn openapi_spec(State(state): State<UiState>) -> Json<Value> {
    let model_names: Vec<&str> = state.models.iter().map(|m| m.model_name.as_str()).collect();
    Json(json!({
        "openapi": "3.1.0",
        "info": {
            "title": "Lango AI Gateway (Wolinet AI)",
            "version": env!("CARGO_PKG_VERSION"),
            "description": "OpenAI-compatible & Anthropic-compatible sovereign AI gateway proxying cloud providers and Mitambo inference."
        },
        "servers": [
            { "url": "/", "description": "Active Lango Gateway" }
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            }
        },
        "security": [{ "BearerAuth": [] }],
        "paths": {
            "/v1/models": {
                "get": {
                    "summary": "List available models",
                    "description": format!("Active model aliases: {}", model_names.join(", ")),
                    "responses": { "200": { "description": "Model list" } }
                }
            },
            "/v1/chat/completions": {
                "post": {
                    "summary": "Create chat completion",
                    "responses": { "200": { "description": "Chat completion (or SSE stream)" } }
                }
            },
            "/v1/messages": {
                "post": {
                    "summary": "Create Anthropic Messages completion",
                    "responses": { "200": { "description": "Messages response" } }
                }
            },
            "/v1/responses": {
                "post": {
                    "summary": "Create OpenAI Responses API output",
                    "responses": { "200": { "description": "Responses output" } }
                }
            },
            "/v1/embeddings": {
                "post": {
                    "summary": "Create text embeddings",
                    "responses": { "200": { "description": "Embedding vectors" } }
                }
            },
            "/v1/images/generations": {
                "post": {
                    "summary": "Generate images",
                    "responses": { "200": { "description": "Generated image URLs or base64" } }
                }
            },
            "/v1/audio/transcriptions": {
                "post": {
                    "summary": "Transcribe audio",
                    "responses": { "200": { "description": "Transcription result" } }
                }
            },
            "/v1/ocr": {
                "post": {
                    "summary": "Run document OCR",
                    "responses": { "200": { "description": "Extracted OCR pages" } }
                }
            },
            "/key/generate": {
                "post": {
                    "summary": "Generate virtual API key",
                    "responses": { "200": { "description": "Generated virtual key" } }
                }
            },
            "/key/info": {
                "get": {
                    "summary": "Inspect virtual key info",
                    "responses": { "200": { "description": "Key metadata & budget" } }
                }
            },
            "/key/list": {
                "get": {
                    "summary": "List virtual API keys",
                    "responses": { "200": { "description": "Paginated key list" } }
                }
            },
            "/key/delete": {
                "post": {
                    "summary": "Delete virtual API keys",
                    "responses": { "200": { "description": "Deleted key hashes" } }
                }
            },
            "/health": {
                "get": {
                    "summary": "Gateway health & model count",
                    "responses": { "200": { "description": "Health payload" } }
                }
            }
        }
    }))
}

async fn user_banner(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({ "banner": null })))
}

#[derive(Deserialize)]
struct LoginV2Request {
    username: String,
    password: String,
}

async fn login_v2(
    State(state): State<UiState>,
    Json(req): Json<LoginV2Request>,
) -> Result<Response, Error> {
    if state.disable_env_credential_login {
        return Err(Error::InvalidToken);
    }

    let master_key = state.auth.master_auth.master_key().await?;
    let expected_user = process_env_lookup("UI_USERNAME")
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| "admin".to_owned());
    let expected_pass = process_env_lookup("UI_PASSWORD")
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| master_key.expose().to_owned());

    let user_ok = ct_eq_str(req.username.trim(), expected_user.trim());
    let pass_ok = ct_eq_str(&req.password, &expected_pass)
        || ct_eq_str(&req.password, master_key.expose());
    if !user_ok || !pass_ok {
        return Err(Error::InvalidToken);
    }

    let exp = Utc::now().timestamp() + 86_400;
    let claims = json!({
        "user_id": "default_user_id",
        "key": master_key.expose(),
        "user_email": "admin@wolinet.com",
        "user_role": "proxy_admin",
        "login_method": "username_password",
        "premium_user": true,
        "auth_header_name": "Authorization",
        "disabled_non_admin_personal_key_creation": false,
        "server_root_path": "/",
        "password_reset_required": false,
        "exp": exp,
    });
    let jwt = sign_hs256_jwt(&claims, master_key.expose())?;
    let body = json!({
        "redirect_url": "/ui/?login=success",
        "token": jwt,
    });

    let mut resp = (StatusCode::OK, Json(body)).into_response();
    if let Ok(cookie) = HeaderValue::from_str(&format!(
        "token={jwt}; Path=/; Max-Age=86400; SameSite=Lax"
    )) {
        resp.headers_mut().insert(SET_COOKIE, cookie);
    }
    Ok(resp)
}

async fn health_readiness_details(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({
        "status": "connected",
        "db": if state.db_configured { "connected" } else { "not_connected" },
        "cache": if state.redis_configured { Value::String("redis".into()) } else { Value::Null },
        "litellm_version": env!("CARGO_PKG_VERSION"),
        "is_detailed_debug": false,
        "show_no_redis_warning": false,
        "show_env_credential_login_warning": false,
    })))
}

async fn user_info(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let models: Vec<&str> = state.models.iter().map(|m| m.model_name.as_str()).collect();
    Ok(Json(json!({
        "user_id": "default_user_id",
        "user_info": {
            "user_id": "default_user_id",
            "user_email": "admin@wolinet.com",
            "user_alias": "Admin",
            "user_role": "proxy_admin",
            "spend": 0.0,
            "max_budget": null,
            "models": models,
            "teams": [],
        },
        "teams": [],
        "keys": [],
    })))
}

async fn user_info_v2(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let models: Vec<&str> = state.models.iter().map(|m| m.model_name.as_str()).collect();
    Ok(Json(json!({
        "user_id": "default_user_id",
        "user_email": "admin@wolinet.com",
        "user_alias": "Admin",
        "user_role": "proxy_admin",
        "spend": 0.0,
        "max_budget": null,
        "models": models,
        "sso_user_id": null,
        "teams": [],
    })))
}

#[derive(Deserialize)]
struct KeyListQuery {
    page: Option<i64>,
    size: Option<i64>,
    key_alias: Option<String>,
    user_id: Option<String>,
    team_id: Option<String>,
}

async fn key_list(
    State(state): State<UiState>,
    headers: HeaderMap,
    Query(q): Query<KeyListQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let page = q.page.unwrap_or(1).max(1);
    let size = q.size.unwrap_or(50).clamp(1, 200);
    let offset = (page - 1) * size;

    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({
            "keys": [],
            "total_count": 0,
            "current_page": page,
            "total_pages": 1,
        })));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;

    let alias_filter = q.key_alias.as_deref().map(str::trim).filter(|s| !s.is_empty());
    let user_filter = q.user_id.as_deref().map(str::trim).filter(|s| !s.is_empty());
    let team_filter = q.team_id.as_deref().map(str::trim).filter(|s| !s.is_empty());

    let total_count: i64 = client
        .query_one(
            r#"
            SELECT COUNT(*)::bigint
            FROM "LiteLLM_VerificationToken"
            WHERE ($1::text IS NULL OR COALESCE(key_alias, '') ILIKE '%' || $1 || '%')
              AND ($2::text IS NULL OR COALESCE(user_id, '') ILIKE '%' || $2 || '%')
              AND ($3::text IS NULL OR team_id = $3)
            "#,
            &[&alias_filter, &user_filter, &team_filter],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres count failed in /key/list: {err}");
            Error::Store
        })?
        .get(0);

    let rows = client
        .query(
            r#"
            SELECT
                token,
                key_name,
                key_alias,
                COALESCE(spend, 0.0)::double precision AS spend,
                max_budget::double precision AS max_budget,
                expires,
                COALESCE(models, ARRAY[]::text[]) AS models,
                user_id,
                team_id,
                organization_id,
                COALESCE(blocked, false) AS blocked,
                rpm_limit,
                tpm_limit,
                created_at
            FROM "LiteLLM_VerificationToken"
            WHERE ($1::text IS NULL OR COALESCE(key_alias, '') ILIKE '%' || $1 || '%')
              AND ($2::text IS NULL OR COALESCE(user_id, '') ILIKE '%' || $2 || '%')
              AND ($3::text IS NULL OR team_id = $3)
            ORDER BY created_at DESC NULLS LAST, token ASC
            LIMIT $4 OFFSET $5
            "#,
            &[&alias_filter, &user_filter, &team_filter, &size, &offset],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres query failed in /key/list: {err}");
            Error::Store
        })?;

    let mut keys = Vec::with_capacity(rows.len());
    for row in rows {
        let expires = row
            .try_get::<_, Option<chrono::NaiveDateTime>>("expires")
            .ok()
            .flatten()
            .map(|dt| dt.and_utc().to_rfc3339());
        let created_at = row
            .try_get::<_, Option<chrono::NaiveDateTime>>("created_at")
            .ok()
            .flatten()
            .map(|dt| dt.and_utc().to_rfc3339());
        keys.push(json!({
            "token": row.get::<_, String>("token"),
            "key_name": row.get::<_, Option<String>>("key_name"),
            "key_alias": row.get::<_, Option<String>>("key_alias"),
            "spend": row.get::<_, f64>("spend"),
            "max_budget": row.get::<_, Option<f64>>("max_budget"),
            "expires": expires,
            "models": row.get::<_, Vec<String>>("models"),
            "user_id": row.get::<_, Option<String>>("user_id"),
            "team_id": row.get::<_, Option<String>>("team_id"),
            "organization_id": row.get::<_, Option<String>>("organization_id"),
            "blocked": row.get::<_, bool>("blocked"),
            "rpm_limit": row.get::<_, Option<i64>>("rpm_limit"),
            "tpm_limit": row.get::<_, Option<i64>>("tpm_limit"),
            "created_at": created_at,
        }));
    }

    let total_pages = ((total_count + size - 1) / size).max(1);
    Ok(Json(json!({
        "keys": keys,
        "total_count": total_count,
        "current_page": page,
        "total_pages": total_pages,
    })))
}

async fn key_aliases(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({
            "aliases": [],
            "total_count": 0,
            "current_page": 1,
            "total_pages": 1,
            "size": 50,
        })));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let rows = client
        .query(
            r#"SELECT DISTINCT key_alias FROM "LiteLLM_VerificationToken" WHERE key_alias IS NOT NULL ORDER BY key_alias ASC LIMIT 200"#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    let aliases: Vec<String> = rows.into_iter().filter_map(|r| r.get(0)).collect();
    let count = aliases.len();
    Ok(Json(json!({
        "aliases": aliases,
        "total_count": count,
        "current_page": 1,
        "total_pages": 1,
        "size": 50,
    })))
}

async fn public_model_hub(State(state): State<UiState>) -> Json<Value> {
    let data: Vec<Value> = state
        .models
        .iter()
        .map(|m| {
            json!({
                "model_group": m.model_name,
                "providers": [m.custom_llm_provider.as_deref().unwrap_or("openai")],
                "mode": m.mode.as_deref().unwrap_or("chat"),
            })
        })
        .collect();
    Json(json!({ "data": data }))
}

#[derive(Deserialize, Default)]
struct ModelInfoQuery {
    #[serde(default)]
    litellm_model_id: Option<String>,
}

async fn model_info(
    State(state): State<UiState>,
    headers: HeaderMap,
    Query(q): Query<ModelInfoQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let filter_id = q
        .litellm_model_id
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let data: Vec<Value> = state
        .models
        .iter()
        .filter(|m| match filter_id {
            Some(target) => m.model_id == target || m.model_name == target,
            None => true,
        })
        .map(|m| {
            json!({
                "model_name": m.model_name,
                "litellm_model_name": m.model_name,
                "litellm_params": {
                    "model": m.provider_model,
                    "api_base": m.api_base,
                    "custom_llm_provider": m.custom_llm_provider,
                },
                "model_info": {
                    "id": m.model_id,
                    "key": m.model_name,
                    "db_model": false,
                    "mode": m.mode.as_deref().unwrap_or("chat"),
                },
            })
        })
        .collect();
    let count = data.len();
    Ok(Json(json!({
        "data": data,
        "total_count": count,
        "current_page": 1,
        "total_pages": 1,
    })))
}

async fn model_group_info(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let data: Vec<Value> = state
        .models
        .iter()
        .map(|m| {
            json!({
                "model_group": m.model_name,
                "providers": [m.custom_llm_provider.as_deref().unwrap_or("openai")],
                "mode": m.mode.as_deref().unwrap_or("chat"),
            })
        })
        .collect();
    Ok(Json(json!({ "data": data })))
}

async fn query_teams(state: &UiState) -> Result<Vec<Value>, Error> {
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Vec::new());
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let rows = client
        .query(
            r#"
            SELECT team_id, team_alias, organization_id,
                   COALESCE(spend, 0.0)::double precision AS spend,
                   max_budget::double precision AS max_budget,
                   COALESCE(models, ARRAY[]::text[]) AS models,
                   COALESCE(blocked, false) AS blocked
            FROM "LiteLLM_TeamTable"
            ORDER BY created_at DESC NULLS LAST
            LIMIT 100
            "#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    Ok(rows
        .into_iter()
        .map(|r| {
            json!({
                "team_id": r.get::<_, String>("team_id"),
                "team_alias": r.get::<_, Option<String>>("team_alias"),
                "organization_id": r.get::<_, Option<String>>("organization_id"),
                "spend": r.get::<_, f64>("spend"),
                "max_budget": r.get::<_, Option<f64>>("max_budget"),
                "models": r.get::<_, Vec<String>>("models"),
                "blocked": r.get::<_, bool>("blocked"),
                "members_with_roles": [],
            })
        })
        .collect())
}

async fn team_list(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let teams = query_teams(&state).await?;
    Ok(Json(json!(teams)))
}

async fn team_list_v2(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let teams = query_teams(&state).await?;
    let total = teams.len();
    Ok(Json(json!({
        "teams": teams,
        "total": total,
        "page": 1,
        "page_size": 100,
        "total_pages": 1,
    })))
}

async fn team_metadata_schema(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!({ "fields": [] })))
}

async fn organization_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!([])));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let rows = client
        .query(
            r#"
            SELECT organization_id, organization_alias,
                   COALESCE(spend, 0.0)::double precision AS spend,
                   COALESCE(models, ARRAY[]::text[]) AS models
            FROM "LiteLLM_OrganizationTable"
            ORDER BY created_at DESC NULLS LAST
            LIMIT 100
            "#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    let orgs: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "organization_id": r.get::<_, String>("organization_id"),
                "organization_alias": r.get::<_, Option<String>>("organization_alias"),
                "spend": r.get::<_, f64>("spend"),
                "models": r.get::<_, Vec<String>>("models"),
            })
        })
        .collect();
    Ok(Json(json!(orgs)))
}

async fn user_list(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({
            "users": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
            "total_pages": 1,
        })));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let rows = client
        .query(
            r#"
            SELECT user_id, user_alias, user_email, user_role,
                   COALESCE(spend, 0.0)::double precision AS spend,
                   max_budget::double precision AS max_budget
            FROM "LiteLLM_UserTable"
            ORDER BY created_at DESC NULLS LAST
            LIMIT 100
            "#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    let users: Vec<Value> = rows
        .into_iter()
        .map(|r| {
            json!({
                "user_id": r.get::<_, String>("user_id"),
                "user_alias": r.get::<_, Option<String>>("user_alias"),
                "user_email": r.get::<_, Option<String>>("user_email"),
                "user_role": r.get::<_, Option<String>>("user_role"),
                "spend": r.get::<_, f64>("spend"),
                "max_budget": r.get::<_, Option<f64>>("max_budget"),
            })
        })
        .collect();
    let total = users.len();
    Ok(Json(json!({
        "users": users,
        "total": total,
        "page": 1,
        "page_size": 50,
        "total_pages": 1,
    })))
}

async fn query_spend_logs(state: &UiState) -> Result<Vec<Value>, Error> {
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Vec::new());
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let rows = client
        .query(
            r#"
            SELECT request_id, call_type, spend::double precision AS spend,
                   total_tokens, prompt_tokens, completion_tokens,
                   "startTime", "endTime", model, model_group,
                   custom_llm_provider, "user" AS user_id, team_id, status
            FROM "LiteLLM_SpendLogs"
            ORDER BY "startTime" DESC
            LIMIT 100
            "#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    Ok(rows
        .into_iter()
        .map(|r| {
            let start = r
                .get::<_, chrono::NaiveDateTime>("startTime")
                .and_utc()
                .to_rfc3339();
            let end = r
                .get::<_, chrono::NaiveDateTime>("endTime")
                .and_utc()
                .to_rfc3339();
            json!({
                "request_id": r.get::<_, String>("request_id"),
                "call_type": r.get::<_, String>("call_type"),
                "spend": r.get::<_, f64>("spend"),
                "total_tokens": r.get::<_, i32>("total_tokens"),
                "prompt_tokens": r.get::<_, i32>("prompt_tokens"),
                "completion_tokens": r.get::<_, i32>("completion_tokens"),
                "startTime": start,
                "endTime": end,
                "model": r.get::<_, String>("model"),
                "model_group": r.get::<_, Option<String>>("model_group"),
                "custom_llm_provider": r.get::<_, Option<String>>("custom_llm_provider"),
                "user": r.get::<_, String>("user_id"),
                "team_id": r.get::<_, Option<String>>("team_id"),
                "status": r.get::<_, Option<String>>("status"),
            })
        })
        .collect())
}

async fn spend_logs_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    Ok(Json(json!(query_spend_logs(&state).await?)))
}

async fn spend_logs_paginated(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let data = query_spend_logs(&state).await?;
    let total = data.len();
    Ok(Json(json!({
        "data": data,
        "total": total,
        "page": 1,
        "page_size": 100,
        "total_pages": 1,
    })))
}

async fn global_spend(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({ "spend": 0.0, "max_budget": null })));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let row = client
        .query_one(
            r#"SELECT COALESCE(SUM(spend), 0.0)::double precision AS spend FROM "LiteLLM_SpendLogs""#,
            &[],
        )
        .await
        .map_err(|_| Error::Store)?;
    Ok(Json(json!({
        "spend": row.get::<_, f64>("spend"),
        "max_budget": null,
    })))
}

#[derive(Deserialize, Default)]
struct ConfigListQuery {
    #[serde(default)]
    config_type: Option<String>,
}

async fn config_list(
    State(state): State<UiState>,
    headers: HeaderMap,
    Query(q): Query<ConfigListQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let kind = q.config_type.as_deref().unwrap_or("general_settings");
    if kind != "general_settings" {
        return Ok(Json(json!([])));
    }
    Ok(Json(json!([
        {
            "field_name": "store_model_in_db",
            "field_type": "bool",
            "field_description": "Allow models added via API/UI to persist in PostgreSQL",
            "field_value": state.store_model_in_db,
            "stored_in_db": false,
            "field_default_value": false,
            "premium_field": false,
            "nested_fields": null,
            "source": "config",
            "editable": false,
        },
        {
            "field_name": "disable_env_credential_login",
            "field_type": "bool",
            "field_description": "Disable Admin UI login using UI_USERNAME/UI_PASSWORD env credentials",
            "field_value": state.disable_env_credential_login,
            "stored_in_db": false,
            "field_default_value": false,
            "premium_field": false,
            "nested_fields": null,
            "source": "config",
            "editable": false,
        },
        {
            "field_name": "hide_default_credentials_hint",
            "field_type": "bool",
            "field_description": "Hide default UI credentials hint on login page",
            "field_value": state.hide_default_credentials_hint,
            "stored_in_db": false,
            "field_default_value": true,
            "premium_field": false,
            "nested_fields": null,
            "source": "config",
            "editable": false,
        },
        {
            "field_name": "maximum_spend_logs_retention_period",
            "field_type": "str",
            "field_description": "Retention window for gateway spend logs",
            "field_value": "30d",
            "stored_in_db": state.db_configured,
            "field_default_value": "30d",
            "premium_field": false,
            "nested_fields": null,
            "source": "config",
            "editable": false,
        }
    ])))
}

fn build_credential_item(m: &UiModelSummary) -> Value {
    let provider = m
        .custom_llm_provider
        .as_deref()
        .or_else(|| m.provider_model.split('/').next())
        .unwrap_or("openai");
    json!({
        "credential_name": format!("{}-credential-{}", m.model_name, m.model_id),
        "credential_values": {
            "api_base": m.api_base,
            "model": m.provider_model,
        },
        "credential_info": {
            "custom_llm_provider": provider,
            "description": format!("Configured deployment credential for {}", m.model_name),
            "model_id": m.model_id,
        },
    })
}

async fn credentials_list(
    State(state): State<UiState>,
    headers: HeaderMap,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let credentials: Vec<Value> = state.models.iter().map(build_credential_item).collect();
    Ok(Json(json!({ "credentials": credentials })))
}

async fn credential_by_model(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(model_id): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let target = model_id.trim();
    let matched = state
        .models
        .iter()
        .find(|m| m.model_id == target || m.model_name == target)
        .ok_or_else(|| Error::NotFound(format!("Model credential not found for `{target}`")))?;
    Ok(Json(build_credential_item(matched)))
}

async fn credential_by_name(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(credential_name): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let target = credential_name.trim();
    let matched = state
        .models
        .iter()
        .find(|m| format!("{}-credential-{}", m.model_name, m.model_id) == target)
        .ok_or_else(|| Error::NotFound(format!("Credential `{target}` not found")))?;
    Ok(Json(build_credential_item(matched)))
}

async fn public_provider_fields() -> Json<Value> {
    Json(json!([
        {
            "provider": "Wolinet_AI",
            "provider_display_name": "Wolinet AI (Mitambo)",
            "litellm_provider": "openai",
            "credential_fields": [
                {
                    "key": "api_base",
                    "label": "API Base",
                    "placeholder": "http://127.0.0.1:9997/v1",
                    "tooltip": "Mitambo local inference OpenAI-compatible base URL.",
                    "required": false,
                    "field_type": "text",
                    "options": null,
                    "default_value": "http://127.0.0.1:9997/v1",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "placeholder": "Enter Mitambo API key",
                    "tooltip": "Mitambo bearer key or os.environ/XINFERENCE_API_KEY.",
                    "required": false,
                    "field_type": "password",
                    "options": null,
                    "default_value": null,
                }
            ],
            "default_model_placeholder": "Wolinet Coder",
        },
        {
            "provider": "OpenAI",
            "provider_display_name": "OpenAI",
            "litellm_provider": "openai",
            "credential_fields": [
                {
                    "key": "api_key",
                    "label": "OpenAI API Key",
                    "placeholder": "sk-...",
                    "tooltip": "OpenAI API key.",
                    "required": true,
                    "field_type": "password",
                    "options": null,
                    "default_value": null,
                }
            ],
            "default_model_placeholder": "gpt-4o",
        },
        {
            "provider": "Anthropic",
            "provider_display_name": "Anthropic",
            "litellm_provider": "anthropic",
            "credential_fields": [
                {
                    "key": "api_key",
                    "label": "Anthropic API Key",
                    "placeholder": "sk-ant-...",
                    "tooltip": "Anthropic Messages API key.",
                    "required": true,
                    "field_type": "password",
                    "options": null,
                    "default_value": null,
                }
            ],
            "default_model_placeholder": "claude-sonnet-4-5",
        },
        {
            "provider": "DeepSeek",
            "provider_display_name": "DeepSeek",
            "litellm_provider": "deepseek",
            "credential_fields": [
                {
                    "key": "api_key",
                    "label": "DeepSeek API Key",
                    "placeholder": "sk-...",
                    "tooltip": "DeepSeek API key.",
                    "required": true,
                    "field_type": "password",
                    "options": null,
                    "default_value": null,
                }
            ],
            "default_model_placeholder": "deepseek/deepseek-chat",
        },
        {
            "provider": "Google_Gemini",
            "provider_display_name": "Google Gemini",
            "litellm_provider": "gemini",
            "credential_fields": [
                {
                    "key": "api_key",
                    "label": "Gemini API Key",
                    "placeholder": "AIza...",
                    "tooltip": "Google AI Studio Gemini API key.",
                    "required": true,
                    "field_type": "password",
                    "options": null,
                    "default_value": null,
                }
            ],
            "default_model_placeholder": "gemini/gemini-2.5-flash",
        }
    ]))
}

#[derive(Deserialize, Default)]
struct PluginListQuery {
    #[serde(default)]
    enabled_only: Option<bool>,
}

fn row_to_plugin_json(row: &tokio_postgres::Row) -> Value {
    let manifest_raw: Option<String> = row.get("manifest_json");
    let manifest: Value = manifest_raw
        .as_deref()
        .and_then(|s| serde_json::from_str::<Value>(s).ok())
        .unwrap_or_else(|| json!({}));
    let created_at = row
        .try_get::<_, Option<chrono::NaiveDateTime>>("created_at")
        .ok()
        .flatten()
        .map(|dt| dt.and_utc().to_rfc3339());
    let updated_at = row
        .try_get::<_, Option<chrono::NaiveDateTime>>("updated_at")
        .ok()
        .flatten()
        .map(|dt| dt.and_utc().to_rfc3339());
    json!({
        "id": row.get::<_, String>("id"),
        "name": row.get::<_, String>("name"),
        "version": row.get::<_, Option<String>>("version"),
        "description": row.get::<_, Option<String>>("description"),
        "source": manifest.get("source").cloned().unwrap_or_else(|| json!({"source": "github", "repo": "wolinet-renatus/wolinetAI"})),
        "author": manifest.get("author").cloned(),
        "homepage": manifest.get("homepage").cloned(),
        "keywords": manifest.get("keywords").cloned(),
        "category": manifest.get("category").cloned(),
        "domain": manifest.get("domain").cloned(),
        "namespace": manifest.get("namespace").cloned(),
        "enabled": row.get::<_, bool>("enabled"),
        "created_at": created_at,
        "updated_at": updated_at,
        "created_by": row.get::<_, Option<String>>("created_by"),
    })
}

async fn claude_code_plugins_list(
    State(state): State<UiState>,
    headers: HeaderMap,
    Query(q): Query<PluginListQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({ "plugins": [], "count": 0 })));
    };
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let enabled_only = q.enabled_only.unwrap_or(false);
    let rows = client
        .query(
            r#"
            SELECT id, name, version, description, manifest_json, enabled, created_at, updated_at, created_by
            FROM "LiteLLM_ClaudeCodePluginTable"
            WHERE ($1::boolean IS FALSE OR enabled = true)
            ORDER BY created_at DESC NULLS LAST, name ASC
            "#,
            &[&enabled_only],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres query failed in /claude-code/plugins: {err}");
            Error::Store
        })?;
    let plugins: Vec<Value> = rows.iter().map(row_to_plugin_json).collect();
    let count = plugins.len();
    Ok(Json(json!({ "plugins": plugins, "count": count })))
}

#[derive(Deserialize)]
struct RegisterPluginBody {
    name: String,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    source: Option<Value>,
    #[serde(default)]
    author: Option<Value>,
    #[serde(default)]
    homepage: Option<String>,
    #[serde(default)]
    keywords: Option<Value>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    domain: Option<String>,
    #[serde(default)]
    namespace: Option<String>,
}

async fn claude_code_plugins_create(
    State(state): State<UiState>,
    headers: HeaderMap,
    Json(body): Json<RegisterPluginBody>,
) -> Result<(StatusCode, Json<Value>), Error> {
    require_master(&state.auth, &headers).await?;
    let name = body.name.trim().to_owned();
    if name.is_empty() {
        return Err(Error::InvalidRequest("plugin name is required".into()));
    }
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let id = Uuid::new_v4().to_string();
    let version = body.version.clone().unwrap_or_else(|| "1.0.0".to_owned());
    let manifest_json = serde_json::to_string(&json!({
        "source": body.source.clone().unwrap_or_else(|| json!({"source": "github", "repo": "wolinet-renatus/wolinetAI"})),
        "author": body.author,
        "homepage": body.homepage,
        "keywords": body.keywords,
        "category": body.category,
        "domain": body.domain,
        "namespace": body.namespace,
    }))
    .unwrap_or_else(|_| "{}".to_owned());

    let row = client
        .query_opt(
            r#"
            INSERT INTO "LiteLLM_ClaudeCodePluginTable" (
                id, name, version, description, manifest_json, files_json, enabled, created_by, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, '{}', true, 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (name) DO NOTHING
            RETURNING id, name, version, description, manifest_json, enabled, created_at, updated_at, created_by
            "#,
            &[&id, &name, &version, &body.description, &manifest_json],
        )
        .await
        .map_err(|_| Error::Store)?;

    let Some(row) = row else {
        return Err(Error::Conflict(format!("Plugin `{name}` already exists")));
    };
    Ok((StatusCode::CREATED, Json(row_to_plugin_json(&row))))
}

async fn claude_code_plugin_get(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(name): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::NotFound(format!("Plugin `{name}` not found")))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let row = client
        .query_opt(
            r#"
            SELECT id, name, version, description, manifest_json, enabled, created_at, updated_at, created_by
            FROM "LiteLLM_ClaudeCodePluginTable"
            WHERE name = $1
            "#,
            &[&name],
        )
        .await
        .map_err(|_| Error::Store)?
        .ok_or_else(|| Error::NotFound(format!("Plugin `{name}` not found")))?;
    Ok(Json(row_to_plugin_json(&row)))
}

async fn set_plugin_enabled(
    state: &UiState,
    name: &str,
    enabled: bool,
) -> Result<Json<Value>, Error> {
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let row = client
        .query_opt(
            r#"
            UPDATE "LiteLLM_ClaudeCodePluginTable"
            SET enabled = $1, updated_at = CURRENT_TIMESTAMP
            WHERE name = $2
            RETURNING id, name, version, description, manifest_json, enabled, created_at, updated_at, created_by
            "#,
            &[&enabled, &name],
        )
        .await
        .map_err(|_| Error::Store)?
        .ok_or_else(|| Error::NotFound(format!("Plugin `{name}` not found")))?;
    Ok(Json(row_to_plugin_json(&row)))
}

async fn claude_code_plugin_enable(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(name): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    set_plugin_enabled(&state, &name, true).await
}

async fn claude_code_plugin_disable(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(name): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    set_plugin_enabled(&state, &name, false).await
}

async fn claude_code_plugin_delete(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(name): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let deleted = client
        .execute(
            r#"DELETE FROM "LiteLLM_ClaudeCodePluginTable" WHERE name = $1"#,
            &[&name],
        )
        .await
        .map_err(|_| Error::Store)?;
    if deleted == 0 {
        return Err(Error::NotFound(format!("Plugin `{name}` not found")));
    }
    Ok(Json(json!({ "status": "deleted", "name": name })))
}

#[derive(Deserialize, Default)]
struct MemoryListQuery {
    #[serde(default)]
    key: Option<String>,
    #[serde(default)]
    key_prefix: Option<String>,
    #[serde(default)]
    search: Option<String>,
    #[serde(default)]
    page: Option<i64>,
    #[serde(default)]
    page_size: Option<i64>,
}

fn row_to_memory_json(row: &tokio_postgres::Row) -> Value {
    let created_at = row
        .try_get::<_, Option<chrono::NaiveDateTime>>("created_at")
        .ok()
        .flatten()
        .map(|dt| dt.and_utc().to_rfc3339());
    let updated_at = row
        .try_get::<_, Option<chrono::NaiveDateTime>>("updated_at")
        .ok()
        .flatten()
        .map(|dt| dt.and_utc().to_rfc3339());
    json!({
        "memory_id": row.get::<_, String>("memory_id"),
        "key": row.get::<_, String>("key"),
        "value": row.get::<_, String>("value"),
        "metadata": row.get::<_, Option<Value>>("metadata"),
        "user_id": row.get::<_, Option<String>>("user_id"),
        "team_id": row.get::<_, Option<String>>("team_id"),
        "created_at": created_at,
        "created_by": row.get::<_, Option<String>>("created_by"),
        "updated_at": updated_at,
        "updated_by": row.get::<_, Option<String>>("updated_by"),
    })
}

async fn memory_list(
    State(state): State<UiState>,
    headers: HeaderMap,
    Query(q): Query<MemoryListQuery>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({ "memories": [], "total": 0 })));
    };
    let page = q.page.unwrap_or(1).max(1);
    let page_size = q.page_size.unwrap_or(50).clamp(1, 500);
    let offset = (page - 1) * page_size;
    let search = q.search.as_deref().map(str::trim).filter(|s| !s.is_empty());
    let key_prefix = q.key_prefix.as_deref().map(str::trim).filter(|s| !s.is_empty());
    let exact_key = q.key.as_deref().map(str::trim).filter(|s| !s.is_empty());

    let client = pool.get().await.map_err(|_| Error::Store)?;
    let total: i64 = client
        .query_one(
            r#"
            SELECT COUNT(*)::bigint
            FROM "LiteLLM_MemoryTable"
            WHERE ($1::text IS NULL OR key ILIKE $1 || '%' OR memory_id = $1)
              AND ($2::text IS NULL OR $1::text IS NOT NULL OR key LIKE $2 || '%')
              AND ($3::text IS NULL OR $1::text IS NOT NULL OR $2::text IS NOT NULL OR key = $3)
            "#,
            &[&search, &key_prefix, &exact_key],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres count failed in /v1/memory: {err}");
            Error::Store
        })?
        .get(0);

    let rows = client
        .query(
            r#"
            SELECT memory_id, key, value, metadata, user_id, team_id, created_at, created_by, updated_at, updated_by
            FROM "LiteLLM_MemoryTable"
            WHERE ($1::text IS NULL OR key ILIKE $1 || '%' OR memory_id = $1)
              AND ($2::text IS NULL OR $1::text IS NOT NULL OR key LIKE $2 || '%')
              AND ($3::text IS NULL OR $1::text IS NOT NULL OR $2::text IS NOT NULL OR key = $3)
            ORDER BY updated_at DESC NULLS LAST, key ASC
            LIMIT $4 OFFSET $5
            "#,
            &[&search, &key_prefix, &exact_key, &page_size, &offset],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres query failed in /v1/memory: {err}");
            Error::Store
        })?;

    let memories: Vec<Value> = rows.iter().map(row_to_memory_json).collect();
    Ok(Json(json!({ "memories": memories, "total": total })))
}

#[derive(Deserialize)]
struct MemoryCreateBody {
    key: String,
    value: String,
    #[serde(default)]
    metadata: Option<Value>,
    #[serde(default)]
    user_id: Option<String>,
    #[serde(default)]
    team_id: Option<String>,
}

async fn memory_create(
    State(state): State<UiState>,
    headers: HeaderMap,
    Json(body): Json<MemoryCreateBody>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let key = body.key.trim().to_owned();
    if key.is_empty() {
        return Err(Error::InvalidRequest("memory key is required".into()));
    }
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let memory_id = format!("mem-{}", Uuid::new_v4().simple());
    let uid = body.user_id.or_else(|| Some("admin".to_owned()));

    let row = client
        .query_opt(
            r#"
            INSERT INTO "LiteLLM_MemoryTable" (
                memory_id, key, value, metadata, user_id, team_id, created_by, updated_by, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, 'admin', 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO NOTHING
            RETURNING memory_id, key, value, metadata, user_id, team_id, created_at, created_by, updated_at, updated_by
            "#,
            &[&memory_id, &key, &body.value, &body.metadata, &uid, &body.team_id],
        )
        .await
        .map_err(|_| Error::Store)?;
    let Some(row) = row else {
        return Err(Error::Conflict(format!("Memory with key `{key}` already exists")));
    };
    Ok(Json(row_to_memory_json(&row)))
}

async fn memory_get(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(key): Path<String>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::NotFound(format!("Memory `{key}` not found")))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let row = client
        .query_opt(
            r#"
            SELECT memory_id, key, value, metadata, user_id, team_id, created_at, created_by, updated_at, updated_by
            FROM "LiteLLM_MemoryTable"
            WHERE key = $1
            "#,
            &[&key],
        )
        .await
        .map_err(|_| Error::Store)?
        .ok_or_else(|| Error::NotFound(format!("Memory `{key}` not found")))?;
    Ok(Json(row_to_memory_json(&row)))
}

#[derive(Deserialize)]
struct MemoryUpdateBody {
    #[serde(default)]
    value: Option<String>,
    #[serde(default)]
    metadata: Option<Value>,
}

async fn memory_upsert(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(key): Path<String>,
    Json(body): Json<MemoryUpdateBody>,
) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let trimmed_key = key.trim().to_owned();
    if trimmed_key.is_empty() {
        return Err(Error::InvalidRequest("memory key is required".into()));
    }
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let memory_id = format!("mem-{}", Uuid::new_v4().simple());
    let default_value = body.value.clone().unwrap_or_default();

    let row = client
        .query_one(
            r#"
            INSERT INTO "LiteLLM_MemoryTable" (
                memory_id, key, value, metadata, user_id, created_by, updated_by, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, 'admin', 'admin', 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = COALESCE($5, "LiteLLM_MemoryTable".value),
                metadata = COALESCE($4, "LiteLLM_MemoryTable".metadata),
                updated_by = 'admin',
                updated_at = CURRENT_TIMESTAMP
            RETURNING memory_id, key, value, metadata, user_id, team_id, created_at, created_by, updated_at, updated_by
            "#,
            &[&memory_id, &trimmed_key, &default_value, &body.metadata, &body.value],
        )
        .await
        .map_err(|_| Error::Store)?;
    Ok(Json(row_to_memory_json(&row)))
}

async fn memory_delete(
    State(state): State<UiState>,
    headers: HeaderMap,
    Path(key): Path<String>,
) -> Result<StatusCode, Error> {
    require_master(&state.auth, &headers).await?;
    let pool = state
        .auth
        .pg_pool
        .as_ref()
        .ok_or_else(|| Error::InvalidRequest("DATABASE_URL is not configured".into()))?;
    let client = pool.get().await.map_err(|_| Error::Store)?;
    let deleted = client
        .execute(
            r#"DELETE FROM "LiteLLM_MemoryTable" WHERE key = $1"#,
            &[&key],
        )
        .await
        .map_err(|_| Error::Store)?;
    if deleted == 0 {
        return Err(Error::NotFound(format!("Memory `{key}` not found")));
    }
    Ok(StatusCode::NO_CONTENT)
}

#[cfg(test)]
mod tests {
    use axum::{
        body::Body,
        http::{Request, StatusCode, header::AUTHORIZATION},
    };
    use futures_util::future::BoxFuture;
    use litellm_auth_types::SecretValue;
    use litellm_secrets::source::SecretSource;
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

    #[tokio::test]
    async fn ui_config_and_login_v2_work_with_master_key() {
        let cfg = Config::from_yaml(
            "model_list:\n  - model_name: wolinet-model\n    litellm_params:\n      model: openai/test\ngeneral_settings:\n  master_key: sk-master-test\n",
        )
        .unwrap();
        let auth = GatewayAuth::stateless(&cfg, Arc::new(DummySecrets));
        let app = ui_router(UiState::from_config(auth, &cfg));

        let cfg_resp = app
            .clone()
            .oneshot(
                Request::get("/litellm/.well-known/litellm-ui-config")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(cfg_resp.status(), StatusCode::OK);

        let bad_login = app
            .clone()
            .oneshot(
                Request::post("/v2/login")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"username":"admin","password":"wrong"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(bad_login.status(), StatusCode::UNAUTHORIZED);

        let ok_login = app
            .clone()
            .oneshot(
                Request::post("/v2/login")
                    .header("content-type", "application/json")
                    .body(Body::from(r#"{"username":"admin","password":"sk-master-test"}"#))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(ok_login.status(), StatusCode::OK);
        assert!(ok_login.headers().contains_key(SET_COOKIE));

        let models_resp = app
            .clone()
            .oneshot(
                Request::get("/v2/model/info")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(models_resp.status(), StatusCode::OK);

        let model_v1_resp = app
            .clone()
            .oneshot(
                Request::get("/v1/model/info?litellm_model_id=wolinet-model")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(model_v1_resp.status(), StatusCode::OK);

        let config_resp = app
            .clone()
            .oneshot(
                Request::get("/config/list?config_type=general_settings")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(config_resp.status(), StatusCode::OK);

        let creds_resp = app
            .clone()
            .oneshot(
                Request::get("/credentials")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(creds_resp.status(), StatusCode::OK);

        let cred_by_model_resp = app
            .clone()
            .oneshot(
                Request::get("/credentials/by_model/wolinet-model")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(cred_by_model_resp.status(), StatusCode::OK);

        let plugins_resp = app
            .clone()
            .oneshot(
                Request::get("/claude-code/plugins?enabled_only=false")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(plugins_resp.status(), StatusCode::OK);

        let memory_resp = app
            .oneshot(
                Request::get("/v1/memory")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(memory_resp.status(), StatusCode::OK);
    }
}
