mod error;

use std::{collections::BTreeMap, path::Path};

use litellm_auth_types::SecretValue;
use serde::{Deserialize, Deserializer};

pub use error::Error;

const ENV_PREFIX: &str = "os.environ/";

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub model_list: Box<[Model]>,
    #[serde(default)]
    pub general_settings: GeneralSettings,
    #[serde(default)]
    pub litellm_settings: LiteLlmSettings,
    #[serde(default)]
    pub router_settings: RouterSettings,
    #[serde(default)]
    pub mcp_servers: BTreeMap<String, McpServer>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GeneralSettings {
    pub master_key: Option<SecretValue>,
    pub database_url: Option<SecretValue>,
    pub redis_url: Option<SecretValue>,
    pub database_connection_pool_limit: Option<u32>,
    pub database_connection_timeout: Option<u64>,
    pub user_api_key_cache_ttl: Option<u64>,
    pub forward_client_headers_to_llm_api: Option<bool>,
    pub forward_llm_provider_auth_headers: Option<bool>,
    #[serde(default)]
    pub pass_through_endpoints: Vec<PassThroughEndpoint>,
    pub store_model_in_db: Option<bool>,
    pub disable_env_credential_login: Option<bool>,
    pub hide_default_credentials_hint: Option<bool>,
    #[serde(default)]
    pub user_header_mappings: Vec<UserHeaderMapping>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PassThroughEndpoint {
    pub path: String,
    pub target: String,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub include_subpath: Option<bool>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UserHeaderMapping {
    pub header_name: String,
    pub litellm_user_role: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LiteLlmSettings {
    #[serde(default)]
    pub model_alias: BTreeMap<String, String>,
    #[serde(default)]
    pub extra_spend_tag_headers: Vec<String>,
    pub drop_params: Option<bool>,
    pub request_timeout: Option<f64>,
    pub num_retries: Option<u32>,
    pub enable_anthropic_prompt_caching: Option<bool>,
    pub openai_system_messages_first: Option<bool>,
    pub websearch_interception_params: Option<WebsearchInterceptionParams>,
    #[serde(default)]
    pub callbacks: Vec<String>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WebsearchInterceptionParams {
    pub enabled: Option<bool>,
    #[serde(default)]
    pub enabled_providers: Vec<String>,
    pub search_tool_name: Option<String>,
    pub max_agentic_loops: Option<u32>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RouterSettings {
    #[serde(default)]
    pub fallbacks: Vec<BTreeMap<String, Vec<String>>>,
    #[serde(default)]
    pub context_window_fallbacks: Vec<BTreeMap<String, Vec<String>>>,
    pub num_retries: Option<u32>,
    pub redis_host: Option<String>,
    #[serde(default, deserialize_with = "deserialize_opt_string_or_u16")]
    pub redis_port: Option<String>,
    pub redis_password: Option<SecretValue>,
    pub routing_strategy: Option<String>,
    pub timeout: Option<f64>,
    pub allowed_fails: Option<u32>,
    pub cooldown_time: Option<u64>,
    pub enable_pre_call_checks: Option<bool>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct McpServer {
    pub url: String,
    pub transport: Option<String>,
    pub description: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Model {
    pub model_name: String,
    pub litellm_params: LiteLlmParams,
    pub model_info: Option<ModelInfo>,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelInfo {
    pub id: Option<String>,
    pub mode: Option<String>,
    pub base_model: Option<String>,
    pub max_input_tokens: Option<u64>,
    pub max_output_tokens: Option<u64>,
    pub rpm: Option<u64>,
    pub tpm: Option<u64>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LiteLlmParams {
    pub model: String,
    pub api_key: Option<SecretValue>,
    pub api_base: Option<String>,
    pub custom_llm_provider: Option<String>,
    pub timeout: Option<f64>,
    pub temperature: Option<f64>,
    pub top_p: Option<f64>,
    pub merge_reasoning_content_in_choices: Option<bool>,
    pub input_cost_per_token: Option<f64>,
    pub output_cost_per_token: Option<f64>,
    pub cache_read_input_token_cost: Option<f64>,
    pub rpm: Option<u64>,
    pub tpm: Option<u64>,
}

pub fn resolve_env_str(raw: &str, lookup: &impl Fn(&str) -> Option<String>) -> Option<String> {
    if let Some(var_name) = raw.strip_prefix(ENV_PREFIX) {
        if var_name.is_empty() {
            return None;
        }
        return lookup(var_name).filter(|v| !v.is_empty());
    }
    Some(raw.to_owned())
}

pub fn resolve_env_secret(
    raw: &SecretValue,
    lookup: &impl Fn(&str) -> Option<String>,
) -> Option<SecretValue> {
    resolve_env_str(raw.expose(), lookup).map(SecretValue::new)
}

pub fn process_env_lookup(name: &str) -> Option<String> {
    std::env::var(name).ok()
}

impl Config {
    pub fn from_yaml(yaml: &str) -> Result<Self, Error> {
        Ok(serde_yaml_ng::from_str(yaml)?)
    }

    pub fn load(path: impl AsRef<Path>) -> Result<Self, Error> {
        Self::from_yaml(&std::fs::read_to_string(path)?)
    }

    pub fn resolve_env(&self) -> Self {
        self.resolve_env_with(&process_env_lookup)
    }

    pub fn resolve_env_with(&self, lookup: &impl Fn(&str) -> Option<String>) -> Self {
        let model_list = self
            .model_list
            .iter()
            .map(|m| Model {
                model_name: m.model_name.clone(),
                model_info: m.model_info.clone(),
                litellm_params: LiteLlmParams {
                    model: m.litellm_params.model.clone(),
                    api_key: m
                        .litellm_params
                        .api_key
                        .as_ref()
                        .and_then(|v| resolve_env_secret(v, lookup)),
                    api_base: m
                        .litellm_params
                        .api_base
                        .as_deref()
                        .and_then(|v| resolve_env_str(v, lookup)),
                    custom_llm_provider: m.litellm_params.custom_llm_provider.clone(),
                    timeout: m.litellm_params.timeout,
                    temperature: m.litellm_params.temperature,
                    top_p: m.litellm_params.top_p,
                    merge_reasoning_content_in_choices: m
                        .litellm_params
                        .merge_reasoning_content_in_choices,
                    input_cost_per_token: m.litellm_params.input_cost_per_token,
                    output_cost_per_token: m.litellm_params.output_cost_per_token,
                    cache_read_input_token_cost: m.litellm_params.cache_read_input_token_cost,
                    rpm: m.litellm_params.rpm,
                    tpm: m.litellm_params.tpm,
                },
            })
            .collect::<Vec<_>>()
            .into_boxed_slice();

        let general_settings = GeneralSettings {
            master_key: self
                .general_settings
                .master_key
                .as_ref()
                .and_then(|v| resolve_env_secret(v, lookup)),
            database_url: self
                .general_settings
                .database_url
                .as_ref()
                .and_then(|v| resolve_env_secret(v, lookup)),
            redis_url: self
                .general_settings
                .redis_url
                .as_ref()
                .and_then(|v| resolve_env_secret(v, lookup)),
            pass_through_endpoints: self
                .general_settings
                .pass_through_endpoints
                .iter()
                .map(|ep| PassThroughEndpoint {
                    path: ep.path.clone(),
                    target: resolve_env_str(&ep.target, lookup).unwrap_or_default(),
                    headers: ep
                        .headers
                        .iter()
                        .filter_map(|(k, v)| {
                            resolve_env_str(v, lookup).map(|resolved| (k.clone(), resolved))
                        })
                        .collect(),
                    include_subpath: ep.include_subpath,
                })
                .collect(),
            ..self.general_settings.clone()
        };

        let router_settings = RouterSettings {
            redis_host: self
                .router_settings
                .redis_host
                .as_deref()
                .and_then(|v| resolve_env_str(v, lookup)),
            redis_port: self
                .router_settings
                .redis_port
                .as_deref()
                .and_then(|v| resolve_env_str(v, lookup)),
            redis_password: self
                .router_settings
                .redis_password
                .as_ref()
                .and_then(|v| resolve_env_secret(v, lookup)),
            ..self.router_settings.clone()
        };

        Self {
            model_list,
            general_settings,
            litellm_settings: self.litellm_settings.clone(),
            router_settings,
            mcp_servers: self.mcp_servers.clone(),
        }
    }

    pub fn resolved_redis_url_with(
        &self,
        lookup: &impl Fn(&str) -> Option<String>,
    ) -> Option<String> {
        if let Some(url) = self
            .general_settings
            .redis_url
            .as_ref()
            .and_then(|v| resolve_env_secret(v, lookup))
        {
            return Some(url.expose().to_owned());
        }
        let host = self
            .router_settings
            .redis_host
            .as_deref()
            .and_then(|v| resolve_env_str(v, lookup))?;
        let port = self
            .router_settings
            .redis_port
            .as_deref()
            .and_then(|v| resolve_env_str(v, lookup))
            .unwrap_or_else(|| "6379".to_owned());
        let password = self
            .router_settings
            .redis_password
            .as_ref()
            .and_then(|v| resolve_env_secret(v, lookup));
        match password {
            Some(pass) => Some(format!("redis://:{}@{host}:{port}", pass.expose())),
            None => Some(format!("redis://{host}:{port}")),
        }
    }
}

fn deserialize_opt_string_or_u16<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum StringOrU16 {
        Str(String),
        Num(u16),
    }

    Ok(
        Option::<StringOrU16>::deserialize(deserializer)?.map(|v| match v {
            StringOrU16::Str(s) => s,
            StringOrU16::Num(n) => n.to_string(),
        }),
    )
}
