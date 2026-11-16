use serde_json::{Map, Value, json};

pub fn is_openai_compat_provider(provider: &str) -> bool {
    matches!(
        provider,
        "openai"
            | "deepseek"
            | "moonshot"
            | "xinference"
            | "openai_like"
            | "hosted_vllm"
            | "custom_openai"
    )
}

pub fn default_api_base(provider: &str) -> &'static str {
    match provider {
        "deepseek" => "https://api.deepseek.com/v1",
        "moonshot" => "https://api.moonshot.ai/v1",
        "xinference" => "http://127.0.0.1:9997/v1",
        _ => "https://api.openai.com/v1",
    }
}

pub fn endpoint_url(provider: &str, api_base: Option<&str>, endpoint_path: &str) -> String {
    let base = api_base
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default_api_base(provider))
        .trim_end_matches('/');
    let trimmed_path = endpoint_path.trim_start_matches('/');
    if base.ends_with("/v1")
        || base.ends_with("/v1beta")
        || base.ends_with("/beta")
        || base.contains("/v1/")
        || base.ends_with(&format!("/{trimmed_path}"))
    {
        if base.ends_with(&format!("/{trimmed_path}")) {
            base.to_owned()
        } else {
            format!("{base}/{trimmed_path}")
        }
    } else {
        format!("{base}/v1/{trimmed_path}")
    }
}

pub fn prepare_chat_request(
    upstream_model: &str,
    mut body: Map<String, Value>,
    default_temperature: Option<f64>,
    default_top_p: Option<f64>,
) -> Map<String, Value> {
    body.insert("model".to_owned(), Value::String(upstream_model.to_owned()));
    if body.get("stream").and_then(Value::as_bool) == Some(true)
        && !body.contains_key("stream_options")
    {
        body.insert(
            "stream_options".to_owned(),
            json!({ "include_usage": true }),
        );
    }
    if !body.contains_key("temperature")
        && let Some(temp) = default_temperature
    {
        body.insert("temperature".to_owned(), json!(temp));
    }
    if !body.contains_key("top_p")
        && let Some(top_p) = default_top_p
    {
        body.insert("top_p".to_owned(), json!(top_p));
    }
    body
}

pub fn normalize_chat_response(
    mut response: Value,
    requested_model: &str,
    merge_reasoning: bool,
) -> Value {
    let Some(root) = response.as_object_mut() else {
        return response;
    };
    root.insert(
        "model".to_owned(),
        Value::String(requested_model.to_owned()),
    );
    normalize_usage_object(root);

    if merge_reasoning && let Some(choices) = root.get_mut("choices").and_then(Value::as_array_mut)
    {
        for choice in choices {
            let Some(message) = choice.get_mut("message").and_then(Value::as_object_mut) else {
                continue;
            };
            let reasoning = message
                .get("reasoning_content")
                .and_then(Value::as_str)
                .map(str::to_owned);
            if let Some(reasoning_text) = reasoning
                && !reasoning_text.is_empty()
            {
                let existing = message
                    .get("content")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                if !existing.contains("<think>") {
                    message.insert(
                        "content".to_owned(),
                        Value::String(format!("<think>\n{reasoning_text}\n</think>\n{existing}")),
                    );
                }
            }
        }
    }

    response
}

pub fn normalize_sse_chunk(mut chunk: Value, requested_model: &str) -> Value {
    if let Some(root) = chunk.as_object_mut() {
        root.insert(
            "model".to_owned(),
            Value::String(requested_model.to_owned()),
        );
        normalize_usage_object(root);
    }
    chunk
}

fn normalize_usage_object(root: &mut Map<String, Value>) {
    let Some(usage) = root.get_mut("usage").and_then(Value::as_object_mut) else {
        return;
    };
    if !usage.contains_key("prompt_tokens_details")
        && let Some(hit) = usage.get("prompt_cache_hit_tokens").and_then(Value::as_u64)
    {
        usage.insert(
            "prompt_tokens_details".to_owned(),
            json!({ "cached_tokens": hit }),
        );
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct TokenUsage {
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub cached_tokens: u64,
}

pub fn extract_usage(payload: &Value) -> Option<TokenUsage> {
    let usage = payload.get("usage")?.as_object()?;
    let prompt_tokens = usage
        .get("prompt_tokens")
        .or_else(|| usage.get("input_tokens"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let completion_tokens = usage
        .get("completion_tokens")
        .or_else(|| usage.get("output_tokens"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let cached_tokens = usage
        .get("prompt_tokens_details")
        .and_then(|d| d.get("cached_tokens"))
        .or_else(|| usage.get("prompt_cache_hit_tokens"))
        .or_else(|| usage.get("cache_read_input_tokens"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    Some(TokenUsage {
        prompt_tokens,
        completion_tokens,
        cached_tokens,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_urls_across_deepseek_moonshot_and_xinference() {
        assert_eq!(
            endpoint_url(
                "deepseek",
                Some("https://api.deepseek.com"),
                "chat/completions"
            ),
            "https://api.deepseek.com/v1/chat/completions"
        );
        assert_eq!(
            endpoint_url(
                "moonshot",
                Some("https://api.moonshot.ai/v1"),
                "chat/completions"
            ),
            "https://api.moonshot.ai/v1/chat/completions"
        );
        assert_eq!(
            endpoint_url("xinference", Some("http://127.0.0.1:9997"), "embeddings"),
            "http://127.0.0.1:9997/v1/embeddings"
        );
        assert_eq!(
            endpoint_url(
                "openai",
                Some("http://host.docker.internal:8088/v1"),
                "chat/completions"
            ),
            "http://host.docker.internal:8088/v1/chat/completions"
        );
    }

    #[test]
    fn preserves_reasoning_content_and_deepseek_cache_usage() {
        let raw = json!({
            "id": "chatcmpl-1",
            "model": "deepseek-reasoner",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "reasoning_content": "step by step",
                    "content": "42"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 64,
                "prompt_cache_miss_tokens": 36
            }
        });

        let normalized = normalize_chat_response(raw.clone(), "Scorpio Pro", false);
        assert_eq!(normalized["model"], "Scorpio Pro");
        assert_eq!(
            normalized["choices"][0]["message"]["reasoning_content"],
            "step by step"
        );
        assert_eq!(
            normalized["usage"]["prompt_tokens_details"]["cached_tokens"],
            64
        );
        assert_eq!(
            extract_usage(&normalized),
            Some(TokenUsage {
                prompt_tokens: 100,
                completion_tokens: 20,
                cached_tokens: 64
            })
        );

        let merged = normalize_chat_response(raw, "Scorpio Pro", true);
        assert_eq!(
            merged["choices"][0]["message"]["content"],
            "<think>\nstep by step\n</think>\n42"
        );
    }
}
