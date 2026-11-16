mod error;
pub mod pricing;
pub mod spend;
pub mod store;

use std::{sync::Arc, time::Duration};

use axum::{
    extract::{FromRequestParts, Request, State},
    http::{HeaderMap, header::AUTHORIZATION, request::Parts},
    middleware::Next,
    response::Response,
};
use chrono::Utc;
use litellm_auth_types::SecretValue;
use litellm_config::{Config, UserHeaderMapping, process_env_lookup, resolve_env_str};
use litellm_secrets::source::SecretSource;
use moka::future::Cache;
use sha2::{Digest, Sha256};
use store::{PgPool, build_pg_pool};
use subtle::ConstantTimeEq;

pub use error::Error;
pub use spend::{SpendEvent, SpendLogger};
pub use store::{VirtualKeyRecord, fetch_virtual_key, validate_key_record};

#[derive(Clone)]
pub struct Auth {
    master_key: Option<SecretValue>,
    secrets: Arc<dyn SecretSource>,
}

impl Auth {
    pub fn from_config(config: &Config, secrets: Arc<dyn SecretSource>) -> Self {
        Self {
            master_key: config.general_settings.master_key.clone(),
            secrets,
        }
    }

    async fn master_key(&self) -> Result<SecretValue, Error> {
        let configured = self.master_key.as_ref().ok_or(Error::Unconfigured)?;
        let resolved = match configured.expose().strip_prefix("os.environ/") {
            Some(name) if !name.is_empty() => self
                .secrets
                .get_secret_str(name)
                .await?
                .ok_or(Error::Unconfigured)?,
            Some(_) => return Err(Error::Unconfigured),
            None => configured.clone(),
        };
        if resolved.expose().trim().is_empty() {
            return Err(Error::Unconfigured);
        }
        Ok(resolved)
    }

    pub async fn verify_master_token(&self, provided: &str) -> Result<bool, Error> {
        let expected = self.master_key().await?;
        let actual_hash = Sha256::digest(provided.as_bytes());
        let expected_hash = Sha256::digest(expected.expose().as_bytes());
        Ok(bool::from(actual_hash.ct_eq(&expected_hash)))
    }
}

pub fn hash_token(token: &str) -> String {
    format!("{:x}", Sha256::digest(token.as_bytes()))
}

pub struct RequireMasterKey;

impl FromRequestParts<Auth> for RequireMasterKey {
    type Rejection = Error;

    async fn from_request_parts(parts: &mut Parts, state: &Auth) -> Result<Self, Error> {
        let expected = state.master_key().await?;
        let provided = parts
            .headers
            .get(AUTHORIZATION)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.strip_prefix("Bearer "))
            .map(str::trim)
            .ok_or(Error::InvalidToken)?;
        let actual_hash = Sha256::digest(provided.as_bytes());
        let expected_hash = Sha256::digest(expected.expose().as_bytes());
        match bool::from(actual_hash.ct_eq(&expected_hash)) {
            true => Ok(Self),
            false => Err(Error::InvalidToken),
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct AuthContext {
    pub key_hash: String,
    pub is_master_key: bool,
    pub user_id: Option<String>,
    pub team_id: Option<String>,
    pub organization_id: Option<String>,
    pub end_user: Option<String>,
    pub tags: Vec<String>,
    pub allowed_models: Vec<String>,
}

#[derive(Clone)]
pub struct GatewayAuth {
    master_auth: Auth,
    pg_pool: Option<PgPool>,
    redis: Option<redis::aio::ConnectionManager>,
    cache: Cache<String, VirtualKeyRecord>,
    user_header_mappings: Vec<UserHeaderMapping>,
    extra_spend_tag_headers: Vec<String>,
    cache_ttl_secs: u64,
    spend_logger: SpendLogger,
}

impl GatewayAuth {
    pub fn stateless(config: &Config, secrets: Arc<dyn SecretSource>) -> Self {
        let ttl = config
            .general_settings
            .user_api_key_cache_ttl
            .unwrap_or(300);
        Self {
            master_auth: Auth::from_config(config, secrets),
            pg_pool: None,
            redis: None,
            cache: Cache::builder()
                .max_capacity(10_000)
                .time_to_live(Duration::from_secs(ttl.max(5)))
                .build(),
            user_header_mappings: config.general_settings.user_header_mappings.clone(),
            extra_spend_tag_headers: config.litellm_settings.extra_spend_tag_headers.clone(),
            cache_ttl_secs: ttl,
            spend_logger: SpendLogger::disabled(),
        }
    }

    pub async fn connect(config: &Config, secrets: Arc<dyn SecretSource>) -> Self {
        let mut state = Self::stateless(config, secrets.clone());

        let db_url = config
            .general_settings
            .database_url
            .as_ref()
            .and_then(|s| resolve_env_str(s.expose(), &process_env_lookup))
            .or_else(|| process_env_lookup("DATABASE_URL"));

        if let Some(url) = db_url {
            let max_conns = config
                .general_settings
                .database_connection_pool_limit
                .unwrap_or(20)
                .max(1) as usize;
            match build_pg_pool(&url, max_conns) {
                Ok(pool) => {
                    state.pg_pool = Some(pool);
                }
                Err(err) => {
                    tracing::warn!("could not configure Postgres pool (continuing): {err}");
                }
            }
        }

        let redis_url = config
            .resolved_redis_url_with(&process_env_lookup)
            .or_else(|| process_env_lookup("REDIS_URL"));

        if let Some(rurl) = redis_url {
            match redis::Client::open(rurl.as_str()) {
                Ok(client) => match client.get_connection_manager().await {
                    Ok(mgr) => {
                        state.redis = Some(mgr);
                    }
                    Err(err) => {
                        tracing::warn!(
                            "Redis unavailable at startup (continuing without Redis): {err}"
                        );
                    }
                },
                Err(err) => {
                    tracing::warn!("invalid Redis URL (continuing without Redis): {err}");
                }
            }
        }

        state.spend_logger = SpendLogger::spawn(state.pg_pool.clone(), state.redis.clone());
        state
    }

    pub fn is_db_configured(&self) -> bool {
        self.pg_pool.is_some()
    }

    pub fn is_redis_configured(&self) -> bool {
        self.redis.is_some()
    }

    pub fn spend_logger(&self) -> &SpendLogger {
        &self.spend_logger
    }

    pub async fn authenticate_headers(&self, headers: &HeaderMap) -> Result<AuthContext, Error> {
        let provided = headers
            .get(AUTHORIZATION)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.strip_prefix("Bearer "))
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .ok_or(Error::InvalidToken)?;

        match self.master_auth.verify_master_token(provided).await {
            Ok(true) => {
                let mut ctx = AuthContext {
                    key_hash: hash_token(provided),
                    is_master_key: true,
                    ..Default::default()
                };
                apply_header_mappings(
                    headers,
                    &self.user_header_mappings,
                    &self.extra_spend_tag_headers,
                    &mut ctx,
                );
                return Ok(ctx);
            }
            Ok(false) => {
                if self.pg_pool.is_none() {
                    return Err(Error::InvalidToken);
                }
            }
            Err(Error::Unconfigured) => {
                if self.pg_pool.is_none() {
                    return Err(Error::Unconfigured);
                }
            }
            Err(err) => return Err(err),
        }

        let pool = self.pg_pool.as_ref().ok_or(Error::InvalidToken)?;
        let key_hash = hash_token(provided);
        let mut redis_conn = self.redis.clone();
        let record = store::fetch_virtual_key(
            &key_hash,
            &self.cache,
            redis_conn.as_mut(),
            pool,
            self.cache_ttl_secs,
        )
        .await?
        .ok_or(Error::InvalidToken)?;

        let now = Utc::now();
        store::validate_key_record(&record, None, now)?;
        if let Some(ref mut conn) = redis_conn {
            store::check_redis_rate_limits(conn, &record, now.timestamp()).await?;
        }

        let mut ctx = AuthContext {
            key_hash,
            is_master_key: false,
            user_id: record.user_id,
            team_id: record.team_id,
            organization_id: record.organization_id,
            end_user: None,
            tags: Vec::new(),
            allowed_models: record.models,
        };
        apply_header_mappings(
            headers,
            &self.user_header_mappings,
            &self.extra_spend_tag_headers,
            &mut ctx,
        );
        Ok(ctx)
    }
}

fn apply_header_mappings(
    headers: &HeaderMap,
    mappings: &[UserHeaderMapping],
    tag_headers: &[String],
    ctx: &mut AuthContext,
) {
    for mapping in mappings {
        if let Some(val) = headers
            .get(mapping.header_name.as_str())
            .and_then(|v| v.to_str().ok())
            .map(str::trim)
            .filter(|s| !s.is_empty())
        {
            match mapping.litellm_user_role.as_deref() {
                Some("customer") => {
                    if ctx.end_user.is_none() {
                        ctx.end_user = Some(val.to_owned());
                    }
                }
                _ => {
                    if ctx.user_id.is_none() {
                        ctx.user_id = Some(val.to_owned());
                    }
                }
            }
        }
    }

    for tag_header in tag_headers {
        if let Some(val) = headers
            .get(tag_header.as_str())
            .and_then(|v| v.to_str().ok())
            .map(str::trim)
            .filter(|s| !s.is_empty())
        {
            ctx.tags.push(format!("{tag_header}: {val}"));
        }
    }
}

pub async fn authenticate_middleware(
    State(auth): State<GatewayAuth>,
    mut request: Request,
    next: Next,
) -> Result<Response, Error> {
    let ctx = auth.authenticate_headers(request.headers()).await?;
    request.extensions_mut().insert(ctx);
    Ok(next.run(request).await)
}
