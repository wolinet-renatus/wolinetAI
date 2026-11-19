use std::sync::Arc;

use axum::{
    Json, Router,
    extract::{Query, State},
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
        .route("/v2/login", post(login_v2))
        .route("/public/litellm_model_cost_map", get(empty_object))
        .route("/get_model_cost_map", get(empty_object))
        .route("/public/model_hub", get(public_model_hub))
        .route("/public/model_hub/info", get(public_model_hub))
        .route("/health/readiness/details", get(health_readiness_details))
        .route("/health/license", get(empty_object))
        .route("/get/user_banner", get(user_banner))
        .route("/api/plugins", get(empty_array))
        .route("/user/info", get(user_info))
        .route("/v2/user/info", get(user_info_v2))
        .route("/key/list", get(key_list))
        .route("/key/aliases", get(key_aliases))
        .route("/model/info", get(model_info))
        .route("/v2/model/info", get(model_info))
        .route("/model_group/info", get(model_group_info))
        .route("/v2/team/list", get(team_list))
        .route("/team/list", get(team_list))
        .route("/organization/list", get(organization_list))
        .route("/user/list", get(user_list))
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

async fn model_info(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let data: Vec<Value> = state
        .models
        .iter()
        .map(|m| {
            json!({
                "model_name": m.model_name,
                "litellm_params": {
                    "model": m.provider_model,
                    "api_base": m.api_base,
                    "custom_llm_provider": m.custom_llm_provider,
                },
                "model_info": {
                    "id": m.model_id,
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

async fn team_list(State(state): State<UiState>, headers: HeaderMap) -> Result<Json<Value>, Error> {
    require_master(&state.auth, &headers).await?;
    let Some(pool) = state.auth.pg_pool.as_ref() else {
        return Ok(Json(json!({
            "teams": [],
            "total": 0,
            "page": 1,
            "page_size": 100,
            "total_pages": 1,
        })));
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
    let teams: Vec<Value> = rows
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
            })
        })
        .collect();
    let total = teams.len();
    Ok(Json(json!({
        "teams": teams,
        "total": total,
        "page": 1,
        "page_size": 100,
        "total_pages": 1,
    })))
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
            .oneshot(
                Request::get("/v2/model/info")
                    .header(AUTHORIZATION, "Bearer sk-master-test")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(models_resp.status(), StatusCode::OK);
    }
}
