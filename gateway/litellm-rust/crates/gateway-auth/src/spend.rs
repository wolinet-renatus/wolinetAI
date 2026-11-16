use std::time::Duration;

use chrono::{DateTime, Utc};
use redis::AsyncCommands;
use serde_json::{Value, json};
use tokio::sync::mpsc;

use crate::{
    pricing::{CostInput, calculate_request_cost},
    store::PgPool,
};

const BATCH_SIZE: usize = 64;
const FLUSH_INTERVAL: Duration = Duration::from_millis(500);
const CHANNEL_CAPACITY: usize = 4096;

#[derive(Clone, Debug)]
pub struct SpendEvent {
    pub request_id: String,
    pub call_type: String,
    pub key_hash: String,
    pub user_id: Option<String>,
    pub team_id: Option<String>,
    pub organization_id: Option<String>,
    pub end_user: Option<String>,
    pub model_group: String,
    pub upstream_model: String,
    pub model_id: Option<String>,
    pub custom_llm_provider: String,
    pub api_base: String,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub cached_tokens: u64,
    pub override_input_cost: Option<f64>,
    pub override_output_cost: Option<f64>,
    pub override_cache_read_cost: Option<f64>,
    pub start_time_ms: i64,
    pub end_time_ms: i64,
    pub status: String,
    pub request_tags: Vec<String>,
}

impl SpendEvent {
    pub fn computed_spend(&self) -> f64 {
        calculate_request_cost(CostInput {
            model_group: &self.model_group,
            upstream_model: &self.upstream_model,
            prompt_tokens: self.prompt_tokens,
            completion_tokens: self.completion_tokens,
            cached_tokens: self.cached_tokens,
            override_input_cost: self.override_input_cost,
            override_output_cost: self.override_output_cost,
            override_cache_read_cost: self.override_cache_read_cost,
        })
    }

    pub fn total_tokens(&self) -> u64 {
        self.prompt_tokens.saturating_add(self.completion_tokens)
    }

    pub fn duration_ms(&self) -> i32 {
        (self.end_time_ms - self.start_time_ms).clamp(0, i32::MAX as i64) as i32
    }

    pub fn start_datetime(&self) -> DateTime<Utc> {
        DateTime::from_timestamp_millis(self.start_time_ms).unwrap_or_else(Utc::now)
    }

    pub fn end_datetime(&self) -> DateTime<Utc> {
        DateTime::from_timestamp_millis(self.end_time_ms).unwrap_or_else(Utc::now)
    }
}

#[derive(Clone)]
pub struct SpendLogger {
    tx: Option<mpsc::Sender<SpendEvent>>,
}

impl SpendLogger {
    pub fn disabled() -> Self {
        Self { tx: None }
    }

    pub fn spawn(pg_pool: Option<PgPool>, redis: Option<redis::aio::ConnectionManager>) -> Self {
        if pg_pool.is_none() && redis.is_none() {
            return Self::disabled();
        }
        let (tx, rx) = mpsc::channel(CHANNEL_CAPACITY);
        tokio::spawn(run_worker(rx, pg_pool, redis));
        Self { tx: Some(tx) }
    }

    pub fn record(&self, event: SpendEvent) {
        let Some(tx) = &self.tx else {
            return;
        };
        if let Err(err) = tx.try_send(event) {
            tracing::warn!("spend logger queue full or closed: {err}");
        }
    }
}

async fn run_worker(
    mut rx: mpsc::Receiver<SpendEvent>,
    pg_pool: Option<PgPool>,
    mut redis: Option<redis::aio::ConnectionManager>,
) {
    let mut batch: Vec<SpendEvent> = Vec::with_capacity(BATCH_SIZE);
    let mut interval = tokio::time::interval(FLUSH_INTERVAL);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

    loop {
        tokio::select! {
            maybe_event = rx.recv() => {
                match maybe_event {
                    Some(event) => {
                        batch.push(event);
                        if batch.len() >= BATCH_SIZE {
                            flush_batch(&mut batch, pg_pool.as_ref(), redis.as_mut()).await;
                        }
                    }
                    None => {
                        flush_batch(&mut batch, pg_pool.as_ref(), redis.as_mut()).await;
                        break;
                    }
                }
            }
            _ = interval.tick() => {
                if !batch.is_empty() {
                    flush_batch(&mut batch, pg_pool.as_ref(), redis.as_mut()).await;
                }
            }
        }
    }
}

async fn flush_batch(
    batch: &mut Vec<SpendEvent>,
    pg_pool: Option<&PgPool>,
    redis: Option<&mut redis::aio::ConnectionManager>,
) {
    if batch.is_empty() {
        return;
    }
    let items: Vec<SpendEvent> = std::mem::take(batch);

    if let Some(conn) = redis {
        let minute = Utc::now().timestamp() / 60;
        for ev in &items {
            let total = ev.total_tokens() as i64;
            if total > 0 && !ev.key_hash.is_empty() {
                let key = crate::store::redis_tpm_key(&ev.key_hash, minute);
                let _: Result<(), _> = conn.incr::<_, _, i64>(&key, total).await.map(|_| ());
                let _: Result<(), _> = conn.expire::<_, bool>(&key, 120).await.map(|_| ());
            }
        }
    }

    let Some(pool) = pg_pool else {
        return;
    };

    let Ok(client) = pool.get().await else {
        tracing::warn!("failed to acquire postgres connection for spend log batch");
        return;
    };

    for ev in items {
        let spend = ev.computed_spend();
        let total = ev.total_tokens() as i32;
        let prompt = ev.prompt_tokens as i32;
        let completion = ev.completion_tokens as i32;
        let duration_ms = ev.duration_ms();
        let start_dt = ev.start_datetime();
        let end_dt = ev.end_datetime();
        let tags_json: Value = json!(ev.request_tags);
        let metadata_json: Value = json!({});
        let model_id = ev.model_id.as_deref().unwrap_or("");
        let user_str = ev.user_id.as_deref().unwrap_or("");

        let insert_res = client
            .execute(
                r#"
                INSERT INTO "LiteLLM_SpendLogs" (
                    request_id, call_type, api_key, spend, total_tokens,
                    prompt_tokens, completion_tokens, "startTime", "endTime",
                    request_duration_ms, model, model_id, model_group,
                    custom_llm_provider, api_base, "user", metadata,
                    request_tags, team_id, organization_id, end_user, status
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12, $13,
                    $14, $15, $16, $17,
                    $18, $19, $20, $21, $22
                )
                ON CONFLICT (request_id) DO NOTHING
                "#,
                &[
                    &ev.request_id,
                    &ev.call_type,
                    &ev.key_hash,
                    &spend,
                    &total,
                    &prompt,
                    &completion,
                    &start_dt,
                    &end_dt,
                    &duration_ms,
                    &ev.upstream_model,
                    &model_id,
                    &ev.model_group,
                    &ev.custom_llm_provider,
                    &ev.api_base,
                    &user_str,
                    &metadata_json,
                    &tags_json,
                    &ev.team_id,
                    &ev.organization_id,
                    &ev.end_user,
                    &ev.status,
                ],
            )
            .await;

        if let Err(err) = insert_res {
            tracing::warn!("failed to insert LiteLLM_SpendLogs row: {err}");
        }

        if spend > 0.0 && !ev.key_hash.is_empty() {
            let _ = client
                .execute(
                    r#"UPDATE "LiteLLM_VerificationToken" SET spend = COALESCE(spend, 0.0) + $1, total_spend = COALESCE(total_spend, 0.0) + $1, last_active = NOW() WHERE token = $2"#,
                    &[&spend, &ev.key_hash],
                )
                .await;

            if let Some(user_id) = ev.user_id.as_deref().filter(|s| !s.is_empty()) {
                let _ = client
                    .execute(
                        r#"UPDATE "LiteLLM_UserTable" SET spend = COALESCE(spend, 0.0) + $1 WHERE user_id = $2"#,
                        &[&spend, &user_id],
                    )
                    .await;
            }

            if let Some(team_id) = ev.team_id.as_deref().filter(|s| !s.is_empty()) {
                let _ = client
                    .execute(
                        r#"UPDATE "LiteLLM_TeamTable" SET spend = COALESCE(spend, 0.0) + $1 WHERE team_id = $2"#,
                        &[&spend, &team_id],
                    )
                    .await;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spend_event_computes_cost_and_duration_cleanly() {
        let ev = SpendEvent {
            request_id: "req-1".into(),
            call_type: "acompletion".into(),
            key_hash: "abc".into(),
            user_id: Some("user-1".into()),
            team_id: Some("team-1".into()),
            organization_id: None,
            end_user: None,
            model_group: "Scorpio".into(),
            upstream_model: "deepseek/deepseek-flash".into(),
            model_id: Some("scorpio".into()),
            custom_llm_provider: "deepseek".into(),
            api_base: "https://api.deepseek.com".into(),
            prompt_tokens: 1000,
            completion_tokens: 200,
            cached_tokens: 0,
            override_input_cost: Some(0.000001),
            override_output_cost: Some(0.000002),
            override_cache_read_cost: None,
            start_time_ms: 1_700_000_000_000,
            end_time_ms: 1_700_000_000_250,
            status: "success".into(),
            request_tags: vec![],
        };
        assert!((ev.computed_spend() - 0.0014).abs() < 1e-12);
        assert_eq!(ev.total_tokens(), 1200);
        assert_eq!(ev.duration_ms(), 250);
    }
}
