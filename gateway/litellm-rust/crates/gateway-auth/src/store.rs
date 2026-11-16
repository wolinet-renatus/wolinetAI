use chrono::{DateTime, Utc};
use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use moka::future::Cache;
use redis::AsyncCommands;
use rustls::{ClientConfig, RootCertStore};
use serde::{Deserialize, Serialize};
use tokio_postgres::{Config as PgConfig, NoTls};
use tokio_postgres_rustls::MakeRustlsConnect;

use crate::Error;

pub type PgPool = Pool;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VirtualKeyRecord {
    pub token_hash: String,
    pub spend: f64,
    pub max_budget: Option<f64>,
    pub expires: Option<DateTime<Utc>>,
    pub models: Vec<String>,
    pub user_id: Option<String>,
    pub team_id: Option<String>,
    pub organization_id: Option<String>,
    pub blocked: bool,
    pub rpm_limit: Option<i64>,
    pub tpm_limit: Option<i64>,
}

pub fn build_pg_pool(database_url: &str, max_size: usize) -> Result<PgPool, String> {
    let pg_config: PgConfig = database_url
        .parse()
        .map_err(|e| format!("invalid DATABASE_URL: {e}"))?;
    let mgr_config = ManagerConfig {
        recycling_method: RecyclingMethod::Fast,
    };
    let use_tls = database_url.contains("sslmode=require")
        || database_url.contains("sslmode=verify-ca")
        || database_url.contains("sslmode=verify-full");

    let mgr = if use_tls {
        let mut root_store = RootCertStore::empty();
        for cert in rustls_native_certs::load_native_certs().certs {
            let _ = root_store.add(cert);
        }
        let tls_config = ClientConfig::builder()
            .with_root_certificates(root_store)
            .with_no_client_auth();
        let tls = MakeRustlsConnect::new(tls_config);
        Manager::from_config(pg_config, tls, mgr_config)
    } else {
        Manager::from_config(pg_config, NoTls, mgr_config)
    };

    Pool::builder(mgr)
        .max_size(max_size.max(1))
        .build()
        .map_err(|e| format!("failed to build Postgres pool: {e}"))
}

pub fn validate_key_record(
    record: &VirtualKeyRecord,
    requested_model: Option<&str>,
    now: DateTime<Utc>,
) -> Result<(), Error> {
    if record.blocked {
        return Err(Error::BlockedKey);
    }
    if let Some(expires) = record.expires
        && expires <= now
    {
        return Err(Error::ExpiredToken);
    }
    if let Some(max_budget) = record.max_budget
        && record.spend >= max_budget
    {
        return Err(Error::BudgetExceeded);
    }
    if let Some(model) = requested_model
        && !record.models.is_empty()
        && !record
            .models
            .iter()
            .any(|m| m == "*" || m == "all-proxy-models" || m == model)
    {
        return Err(Error::ModelNotAllowed(model.to_owned()));
    }
    Ok(())
}

pub fn redis_vkey_cache_key(key_hash: &str) -> String {
    format!("litellm:vkey:{key_hash}")
}

pub fn redis_rpm_key(key_hash: &str, epoch_minute: i64) -> String {
    format!("litellm:rpm:{key_hash}:{epoch_minute}")
}

pub fn redis_tpm_key(key_hash: &str, epoch_minute: i64) -> String {
    format!("litellm:tpm:{key_hash}:{epoch_minute}")
}

pub async fn fetch_virtual_key(
    key_hash: &str,
    cache: &Cache<String, VirtualKeyRecord>,
    redis: Option<&mut redis::aio::ConnectionManager>,
    pg_pool: &PgPool,
    redis_ttl_secs: u64,
) -> Result<Option<VirtualKeyRecord>, Error> {
    if let Some(hit) = cache.get(key_hash).await {
        return Ok(Some(hit));
    }

    if let Some(conn) = redis {
        let rkey = redis_vkey_cache_key(key_hash);
        if let Ok(Some(raw)) = conn.get::<_, Option<String>>(&rkey).await
            && let Ok(record) = serde_json::from_str::<VirtualKeyRecord>(&raw)
        {
            cache.insert(key_hash.to_owned(), record.clone()).await;
            return Ok(Some(record));
        }

        return fetch_from_pg_and_cache(key_hash, cache, Some(conn), pg_pool, redis_ttl_secs).await;
    }

    fetch_from_pg_and_cache(key_hash, cache, None, pg_pool, redis_ttl_secs).await
}

async fn fetch_from_pg_and_cache(
    key_hash: &str,
    cache: &Cache<String, VirtualKeyRecord>,
    redis: Option<&mut redis::aio::ConnectionManager>,
    pg_pool: &PgPool,
    redis_ttl_secs: u64,
) -> Result<Option<VirtualKeyRecord>, Error> {
    let client = pg_pool.get().await.map_err(|err| {
        tracing::error!("postgres pool acquisition failed: {err}");
        Error::Store
    })?;

    let row = client
        .query_opt(
            r#"
            SELECT
                v.token,
                COALESCE(v.spend, 0.0)::double precision AS spend,
                v.max_budget::double precision AS max_budget,
                v.expires,
                COALESCE(v.models, ARRAY[]::text[]) AS models,
                v.user_id,
                v.team_id,
                v.organization_id,
                COALESCE(v.blocked, false) AS blocked,
                v.rpm_limit,
                v.tpm_limit
            FROM "LiteLLM_VerificationToken" v
            WHERE v.token = $1
            LIMIT 1
            "#,
            &[&key_hash],
        )
        .await
        .map_err(|err| {
            tracing::error!("postgres virtual key lookup failed: {err}");
            Error::Store
        })?;

    let Some(row) = row else {
        return Ok(None);
    };

    let record = VirtualKeyRecord {
        token_hash: row.try_get("token").map_err(|_| Error::Store)?,
        spend: row.try_get("spend").map_err(|_| Error::Store)?,
        max_budget: row.try_get("max_budget").map_err(|_| Error::Store)?,
        expires: row.try_get("expires").map_err(|_| Error::Store)?,
        models: row.try_get("models").map_err(|_| Error::Store)?,
        user_id: row.try_get("user_id").map_err(|_| Error::Store)?,
        team_id: row.try_get("team_id").map_err(|_| Error::Store)?,
        organization_id: row.try_get("organization_id").map_err(|_| Error::Store)?,
        blocked: row.try_get("blocked").map_err(|_| Error::Store)?,
        rpm_limit: row.try_get("rpm_limit").map_err(|_| Error::Store)?,
        tpm_limit: row.try_get("tpm_limit").map_err(|_| Error::Store)?,
    };

    cache.insert(key_hash.to_owned(), record.clone()).await;
    if let Some(conn) = redis
        && let Ok(serialized) = serde_json::to_string(&record)
    {
        let ttl = redis_ttl_secs.max(5);
        let _: Result<(), _> = conn
            .set_ex::<_, _, ()>(redis_vkey_cache_key(key_hash), serialized, ttl)
            .await;
    }

    Ok(Some(record))
}

pub async fn check_redis_rate_limits(
    conn: &mut redis::aio::ConnectionManager,
    record: &VirtualKeyRecord,
    now_secs: i64,
) -> Result<(), Error> {
    let epoch_minute = now_secs / 60;
    if let Some(rpm_limit) = record.rpm_limit
        && rpm_limit > 0
    {
        let rkey = redis_rpm_key(&record.token_hash, epoch_minute);
        let count: i64 = conn.incr(&rkey, 1).await.unwrap_or(0);
        if count == 1 {
            let _: Result<(), _> = conn.expire(&rkey, 70).await;
        }
        if count > rpm_limit {
            return Err(Error::RateLimitExceeded(format!(
                "RPM limit ({rpm_limit}) exceeded"
            )));
        }
    }

    if let Some(tpm_limit) = record.tpm_limit
        && tpm_limit > 0
    {
        let tkey = redis_tpm_key(&record.token_hash, epoch_minute);
        let current_tokens: i64 = conn
            .get::<_, Option<i64>>(&tkey)
            .await
            .ok()
            .flatten()
            .unwrap_or(0);
        if current_tokens >= tpm_limit {
            return Err(Error::RateLimitExceeded(format!(
                "TPM limit ({tpm_limit}) exceeded"
            )));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use chrono::Duration;

    use super::*;

    fn sample_record() -> VirtualKeyRecord {
        VirtualKeyRecord {
            token_hash: "hash1".into(),
            spend: 1.0,
            max_budget: Some(5.0),
            expires: None,
            models: vec![],
            user_id: Some("u1".into()),
            team_id: None,
            organization_id: None,
            blocked: false,
            rpm_limit: Some(10),
            tpm_limit: Some(1000),
        }
    }

    #[test]
    fn validates_blocked_expired_budget_and_model_acls() {
        let now = Utc::now();
        assert!(validate_key_record(&sample_record(), Some("Wolinet Max"), now).is_ok());

        let mut blocked = sample_record();
        blocked.blocked = true;
        assert!(matches!(
            validate_key_record(&blocked, None, now),
            Err(Error::BlockedKey)
        ));

        let mut expired = sample_record();
        expired.expires = Some(now - Duration::seconds(10));
        assert!(matches!(
            validate_key_record(&expired, None, now),
            Err(Error::ExpiredToken)
        ));

        let mut over = sample_record();
        over.spend = 5.0;
        assert!(matches!(
            validate_key_record(&over, None, now),
            Err(Error::BudgetExceeded)
        ));

        let mut restricted = sample_record();
        restricted.models = vec!["Scorpio".into()];
        assert!(matches!(
            validate_key_record(&restricted, Some("Wolinet Max"), now),
            Err(Error::ModelNotAllowed(_))
        ));
        assert!(validate_key_record(&restricted, Some("Scorpio"), now).is_ok());
    }
}
