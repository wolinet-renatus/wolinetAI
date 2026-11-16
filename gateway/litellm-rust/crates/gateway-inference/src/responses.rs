use std::sync::Arc;

use axum::{
    Extension, Json,
    body::Bytes,
    extract::State,
    http::HeaderMap,
    response::{IntoResponse, Response},
};
use litellm_llms::{gemini, openai_compat};
use serde_json::{Map, Value, json};

use crate::{
    Error, Gateway, providers, request,
    usage::{AuthMetadata, UsageSink, now_millis, now_secs},
};

pub(crate) async fn create(
    State(gateway): State<Arc<Gateway>>,
    headers: HeaderMap,
    usage_sink: Option<Extension<UsageSink>>,
    auth_meta: Option<Extension<AuthMetadata>>,
    body: Bytes,
) -> Response {
    let result = match request::object(&body) {
        Ok(parsed) => {
            handle(
                &gateway,
                &headers,
                usage_sink.map(|Extension(s)| s),
                auth_meta.map(|Extension(a)| a),
                parsed,
            )
            .await
        }
        Err(err) => Err(err),
    };
    match result {
        Ok(resp) => resp,
        Err(err) => err.openai_response(),
    }
}

async fn handle(
    gateway: &Gateway,
    headers: &HeaderMap,
    usage_sink: Option<UsageSink>,
    auth_meta: Option<AuthMetadata>,
    body: Map<String, Value>,
) -> Result<Response, Error> {
    let requested_model = body
        .get("model")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::InvalidBody("model is required".into()))?
        .to_owned();
    let candidates = providers::candidates_for(gateway, &requested_model)?;
    let candidate = candidates[0];
    let (provider, upstream_model) = providers::split_provider_and_model(candidate)
        .ok_or_else(|| Error::Internal("unable to resolve provider for responses".into()))?;
    let api_key = providers::resolve_secret_str(
        gateway.secrets.as_ref(),
        candidate.deployment.api_key.as_deref(),
    )
    .await?;
    let api_base = providers::resolve_secret_str(
        gateway.secrets.as_ref(),
        candidate.deployment.api_base.as_deref(),
    )
    .await?;
    let stream = body.get("stream").and_then(Value::as_bool) == Some(true);
    let request_id = headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let start_time_ms = now_millis();

    let messages = responses_input_to_messages(&body)?;

    if providers::is_gemini_provider(&provider, &upstream_model) {
        let mut chat_body = Map::new();
        chat_body.insert("messages".to_owned(), Value::Array(messages));
        if let Some(max_out) = body.get("max_output_tokens").cloned() {
            chat_body.insert("max_tokens".to_owned(), max_out);
        }
        if let Some(temp) = body.get("temperature").cloned() {
            chat_body.insert("temperature".to_owned(), temp);
        }
        if let Some(top_p) = body.get("top_p").cloned() {
            chat_body.insert("top_p".to_owned(), top_p);
        }
        if let Some(tools) = body.get("tools").cloned() {
            chat_body.insert("tools".to_owned(), tools);
        }

        let gem_req =
            gemini::openai_chat_to_gemini(&chat_body, candidate.temperature, candidate.top_p)
                .map_err(|e| Error::InvalidBody(e.to_string()))?;
        let action = if stream {
            "streamGenerateContent?alt=sse"
        } else {
            "generateContent"
        };
        let url = gemini::endpoint_url(&upstream_model, api_base.as_deref(), action);
        let req_headers = api_key
            .as_deref()
            .map(gemini::auth_headers)
            .unwrap_or_default();
        let resolved_base = api_base.unwrap_or_else(|| gemini::DEFAULT_GEMINI_API_BASE.to_owned());
        let response_id = format!("resp_{}", uuid::Uuid::new_v4().simple());
        let created = now_secs();

        if stream {
            let upstream = providers::post_stream_raw(
                gateway,
                &url,
                req_headers,
                &gem_req,
                candidate.deployment.timeout,
            )
            .await?;
            return Ok(providers::build_sse_response(
                upstream,
                providers::StreamFormat::Gemini,
                providers::StreamMeta {
                    sink: usage_sink,
                    auth: auth_meta,
                    request_id,
                    call_type: "aresponses".to_owned(),
                    requested_model,
                    deployment: candidate.clone(),
                    provider,
                    upstream_model,
                    api_base: resolved_base,
                    start_time_ms,
                    response_id,
                    created,
                },
            ));
        }

        let gem_resp = providers::post_json_raw(
            gateway,
            &url,
            req_headers,
            &gem_req,
            candidate.deployment.timeout,
        )
        .await?;
        let chat_resp =
            gemini::gemini_response_to_openai(&gem_resp, &requested_model, &response_id, created);
        let out = chat_to_responses_object(&chat_resp, &requested_model, &response_id, created);
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "aresponses",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &chat_resp,
        );
        return Ok(Json(out).into_response());
    }

    if openai_compat::is_openai_compat_provider(&provider) {
        let mut chat_body = Map::new();
        chat_body.insert("model".to_owned(), Value::String(upstream_model.clone()));
        chat_body.insert("messages".to_owned(), Value::Array(messages));
        chat_body.insert("stream".to_owned(), Value::Bool(stream));
        if let Some(max_out) = body.get("max_output_tokens").cloned() {
            chat_body.insert("max_tokens".to_owned(), max_out);
        }
        if let Some(temp) = body.get("temperature").cloned() {
            chat_body.insert("temperature".to_owned(), temp);
        }
        if let Some(top_p) = body.get("top_p").cloned() {
            chat_body.insert("top_p".to_owned(), top_p);
        }
        let prepared = Value::Object(openai_compat::prepare_chat_request(
            &upstream_model,
            chat_body,
            candidate.temperature,
            candidate.top_p,
        ));
        let url = openai_compat::endpoint_url(&provider, api_base.as_deref(), "chat/completions");
        let resolved_base =
            api_base.unwrap_or_else(|| openai_compat::default_api_base(&provider).to_owned());
        let req_headers = api_key
            .map(|k| vec![("authorization".to_owned(), format!("Bearer {k}"))])
            .unwrap_or_default();

        if stream {
            let upstream = providers::post_stream_raw(
                gateway,
                &url,
                req_headers,
                &prepared,
                candidate.deployment.timeout,
            )
            .await?;
            return Ok(providers::build_sse_response(
                upstream,
                providers::StreamFormat::OpenAiCompat,
                providers::StreamMeta {
                    sink: usage_sink,
                    auth: auth_meta,
                    request_id,
                    call_type: "aresponses".to_owned(),
                    requested_model,
                    deployment: candidate.clone(),
                    provider,
                    upstream_model,
                    api_base: resolved_base,
                    start_time_ms,
                    response_id: String::new(),
                    created: now_secs(),
                },
            ));
        }

        let raw_json = providers::post_json_raw(
            gateway,
            &url,
            req_headers,
            &prepared,
            candidate.deployment.timeout,
        )
        .await?;
        let response_id = format!("resp_{}", uuid::Uuid::new_v4().simple());
        let created = now_secs();
        let out = chat_to_responses_object(&raw_json, &requested_model, &response_id, created);
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "aresponses",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &raw_json,
        );
        return Ok(Json(out).into_response());
    }

    Err(Error::Unsupported(format!(
        "responses API for provider {provider}"
    )))
}

fn responses_input_to_messages(body: &Map<String, Value>) -> Result<Vec<Value>, Error> {
    let mut messages = Vec::new();
    if let Some(instructions) = body.get("instructions").and_then(Value::as_str)
        && !instructions.is_empty()
    {
        messages.push(json!({ "role": "system", "content": instructions }));
    }
    match body.get("input") {
        Some(Value::String(s)) => {
            messages.push(json!({ "role": "user", "content": s }));
        }
        Some(Value::Array(items)) => {
            for item in items {
                if let Some(role) = item.get("role").and_then(Value::as_str) {
                    let content = item.get("content").cloned().unwrap_or(Value::Null);
                    messages.push(json!({ "role": role, "content": content }));
                } else if let Some(text) = item.as_str() {
                    messages.push(json!({ "role": "user", "content": text }));
                }
            }
        }
        _ => return Err(Error::InvalidBody("input is required".into())),
    }
    Ok(messages)
}

fn chat_to_responses_object(
    chat: &Value,
    requested_model: &str,
    response_id: &str,
    created: u64,
) -> Value {
    let text = chat["choices"][0]["message"]["content"]
        .as_str()
        .unwrap_or_default();
    let prompt_tokens = chat["usage"]["prompt_tokens"].as_u64().unwrap_or(0);
    let completion_tokens = chat["usage"]["completion_tokens"].as_u64().unwrap_or(0);
    let total_tokens = chat["usage"]["total_tokens"]
        .as_u64()
        .unwrap_or(prompt_tokens + completion_tokens);
    json!({
        "id": response_id,
        "object": "response",
        "created_at": created,
        "status": "completed",
        "model": requested_model,
        "output": [{
            "id": format!("msg_{}", uuid::Uuid::new_v4().simple()),
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": text,
                "annotations": []
            }]
        }],
        "output_text": text,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
    })
}
