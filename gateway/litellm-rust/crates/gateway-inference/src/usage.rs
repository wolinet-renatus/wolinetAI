use std::{
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};

#[derive(Clone, Debug, Default)]
pub struct AuthMetadata {
    pub key_hash: Option<String>,
    pub user_id: Option<String>,
    pub team_id: Option<String>,
    pub end_user: Option<String>,
    pub organization_id: Option<String>,
    pub tags: Vec<String>,
    pub allowed_models: Vec<String>,
}

impl AuthMetadata {
    pub fn is_model_allowed(&self, requested_model: &str, resolved_group: Option<&str>) -> bool {
        if self.allowed_models.is_empty()
            || self
                .allowed_models
                .iter()
                .any(|m| m == "*" || m == "all-proxy-models")
        {
            return true;
        }
        self.allowed_models
            .iter()
            .any(|m| m == requested_model || resolved_group.is_some_and(|group| m == group))
    }
}

#[derive(Clone, Debug)]
pub struct UsageRecord {
    pub request_id: String,
    pub call_type: String,
    pub model_group: String,
    pub upstream_model: String,
    pub model_id: Option<String>,
    pub custom_llm_provider: String,
    pub api_base: String,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub cached_tokens: u64,
    pub input_cost_per_token: Option<f64>,
    pub output_cost_per_token: Option<f64>,
    pub cache_read_input_token_cost: Option<f64>,
    pub start_time_ms: i64,
    pub end_time_ms: i64,
    pub status: String,
    pub auth: Option<AuthMetadata>,
}

pub type UsageSink = Arc<dyn Fn(UsageRecord) + Send + Sync>;

pub fn now_millis() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

pub fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
