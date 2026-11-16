use litellm_config::{Config, Error};
use rstest::{fixture, rstest};
use tempfile::TempDir;

#[fixture]
fn directory() -> TempDir {
    tempfile::tempdir().unwrap()
}

#[fixture]
fn model_list_yaml() -> &'static str {
    r#"
model_list:
  - model_name: assistant
    litellm_params:
      model: anthropic/test-model
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: local
    litellm_params:
      model: test-model
      api_base: http://localhost:8000/v1
      custom_llm_provider: openai
"#
}

#[rstest]
fn loads_model_list_from_file(directory: TempDir, model_list_yaml: &str) {
    let path = directory.path().join("config.yaml");
    std::fs::write(&path, model_list_yaml).unwrap();

    let config = Config::load(path).unwrap();
    assert_eq!(config.model_list.len(), 2);
    let anthropic = &config.model_list[0];
    assert_eq!(anthropic.model_name, "assistant");
    assert_eq!(anthropic.litellm_params.model, "anthropic/test-model");
    assert_eq!(
        anthropic.litellm_params.api_key.as_ref().unwrap().expose(),
        "os.environ/ANTHROPIC_API_KEY"
    );
    assert!(anthropic.litellm_params.api_base.is_none());
    assert!(anthropic.litellm_params.custom_llm_provider.is_none());
    let local = &config.model_list[1];
    assert_eq!(local.model_name, "local");
    assert_eq!(local.litellm_params.model, "test-model");
    assert!(local.litellm_params.api_key.is_none());
    assert_eq!(
        local.litellm_params.api_base.as_deref(),
        Some("http://localhost:8000/v1")
    );
    assert_eq!(
        local.litellm_params.custom_llm_provider.as_deref(),
        Some("openai")
    );
}

#[rstest]
fn config_debug_redacts_api_keys() {
    let config = Config::from_yaml(
        "model_list: [{model_name: assistant, litellm_params: {model: anthropic/test-model, api_key: secret-value}}]",
    )
    .unwrap();
    assert_eq!(
        config.model_list[0]
            .litellm_params
            .api_key
            .as_ref()
            .unwrap()
            .expose(),
        "secret-value"
    );
    assert!(!format!("{config:?}").contains("secret-value"));
}

#[rstest]
#[case::malformed_yaml("model_list: [")]
#[case::missing_model_list("{}")]
#[case::missing_params("model_list: [{model_name: assistant}]")]
#[case::missing_model("model_list: [{model_name: assistant, litellm_params: {api_key: key}}]")]
#[case::unsupported_settings("model_list: []\ngeneral_settings: {unknown: true}")]
#[case::misspelled_param(
    "model_list: [{model_name: assistant, litellm_params: {model: test, api_bsae: url}}]"
)]
fn rejects_malformed_incomplete_and_unsupported_config(#[case] yaml: &str) {
    assert!(matches!(Config::from_yaml(yaml), Err(Error::Parse(_))));
}

#[rstest]
fn distinguishes_read_errors_from_parse_errors(directory: TempDir) {
    assert!(matches!(
        Config::load(directory.path().join("missing.yaml")),
        Err(Error::Read(error)) if error.kind() == std::io::ErrorKind::NotFound
    ));
}

#[rstest]
#[case::literal("secret-master-key")]
#[case::reference("os.environ/LITELLM_MASTER_KEY")]
fn loads_and_redacts_the_master_key(#[case] key: &str) {
    let config = Config::from_yaml(&format!(
        "model_list: []\ngeneral_settings:\n  master_key: {key}\n"
    ))
    .unwrap();
    assert_eq!(
        config
            .general_settings
            .master_key
            .as_ref()
            .unwrap()
            .expose(),
        key
    );
    assert!(!format!("{config:?}").contains(key));
}

#[rstest]
fn missing_general_settings_has_no_master_key() {
    let config = Config::from_yaml("model_list: []").unwrap();
    assert!(config.general_settings.master_key.is_none());
}

#[rstest]
fn parses_production_gateway_config_yaml_and_resolves_env_references() {
    let config_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../config.yaml");
    let config = Config::load(&config_path).unwrap();

    assert!(!config.model_list.is_empty());
    assert!(
        config
            .model_list
            .iter()
            .any(|m| m.model_name == "Wolinet Max"
                && m.model_info.as_ref().and_then(|i| i.mode.as_deref()) == Some("chat"))
    );
    assert!(
        config
            .general_settings
            .pass_through_endpoints
            .iter()
            .any(|ep| ep.path == "/v1/defense/inspect")
    );
    assert!(
        config
            .general_settings
            .user_header_mappings
            .iter()
            .any(|m| m.header_name == "X-OpenWebUI-User-Id")
    );
    assert!(!config.litellm_settings.model_alias.is_empty());
    assert!(!config.router_settings.fallbacks.is_empty());

    let resolved = config.resolve_env_with(&|name| match name {
        "LITELLM_MASTER_KEY" => Some("sk-master-test".into()),
        "DATABASE_URL" => Some("postgres://user:pass@127.0.0.1:5433/litellm".into()),
        "WOLINET_INFERENCE_URL" => Some("http://127.0.0.1:9997".into()),
        "MOONSHOT_API_KEY" => Some("sk-moonshot-test".into()),
        "DEEPSEEK_API_KEY" => Some("sk-deepseek-test".into()),
        "REDIS_HOST" => Some("127.0.0.1".into()),
        "REDIS_PORT" => Some("6379".into()),
        "REDIS_PASSWORD" => Some("redis-pass".into()),
        _ => None,
    });

    assert_eq!(
        resolved
            .general_settings
            .master_key
            .as_ref()
            .unwrap()
            .expose(),
        "sk-master-test"
    );
    assert_eq!(
        resolved
            .general_settings
            .database_url
            .as_ref()
            .unwrap()
            .expose(),
        "postgres://user:pass@127.0.0.1:5433/litellm"
    );
    assert_eq!(
        resolved
            .general_settings
            .pass_through_endpoints
            .iter()
            .find(|ep| ep.path == "/v1/rerank")
            .unwrap()
            .target,
        "http://127.0.0.1:9997"
    );
    assert_eq!(
        config
            .resolved_redis_url_with(&|name| match name {
                "REDIS_HOST" => Some("127.0.0.1".into()),
                "REDIS_PORT" => Some("6379".into()),
                "REDIS_PASSWORD" => Some("redis-pass".into()),
                _ => None,
            })
            .as_deref(),
        Some("redis://:redis-pass@127.0.0.1:6379")
    );
}
