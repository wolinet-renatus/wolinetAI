use std::{convert::Infallible, time::Duration};

use axum::{
    Json,
    body::{Body, Bytes},
    http::{StatusCode, header},
    response::{IntoResponse, Response},
};
use futures_util::StreamExt;
use litellm_core::RouteError;
use litellm_core_utils::get_llm_provider_logic::get_custom_llm_provider;
use litellm_http::{
    ClientVariant, request::truncate_error_body, transport::Error as TransportError,
};
use litellm_llms::{
    gemini,
    openai_compat::{self, TokenUsage},
};
use litellm_router::ModelDeployment;
use litellm_secrets::source::SecretSource;
use serde_json::{Map, Value};

use crate::{
    Error, Gateway,
    usage::{AuthMetadata, UsageRecord, UsageSink, now_millis, now_secs},
};

const ENV_PREFIX: &str = "os.environ/";
const DEFAULT_UPSTREAM_TIMEOUT: Duration = Duration::from_secs(120);

pub(crate) async fn resolve_secret_str(
    secrets: &dyn SecretSource,
    raw: Option<&str>,
) -> Result<Option<String>, Error> {
    let Some(raw) = raw.map(str::trim).filter(|s| !s.is_empty()) else {
        return Ok(None);
    };
    if let Some(var_name) = raw.strip_prefix(ENV_PREFIX) {
        if var_name.is_empty() {
            return Err(Error::Internal("empty os.environ/ secret name".into()));
        }
        let resolved = secrets
            .get_secret_str(var_name)
            .await
            .map_err(|e| Error::Internal(format!("secret lookup failed: {e}")))?;
        return Ok(resolved.map(|s| s.expose().to_owned()));
    }
    Ok(Some(raw.to_owned()))
}

pub(crate) fn split_provider_and_model(deployment: &ModelDeployment) -> Option<(String, String)> {
    let parsed = get_custom_llm_provider(
        &deployment.deployment.model,
        deployment.deployment.custom_llm_provider.as_deref(),
    )?;
    Some((
        parsed.custom_llm_provider.to_owned(),
        parsed.model.to_owned(),
    ))
}

pub(crate) fn is_gemini_provider(provider: &str, upstream_model: &str) -> bool {
    provider == "gemini"
        || (provider == "vertex_ai" && upstream_model.to_ascii_lowercase().starts_with("gemini"))
}

pub(crate) fn candidates_for<'a>(
    gateway: &'a Gateway,
    requested_model: &str,
) -> Result<Vec<&'a ModelDeployment>, Error> {
    let list = gateway.models.candidates(requested_model);
    if list.is_empty() {
        return Err(Error::UnknownModel(requested_model.to_owned()));
    }
    Ok(list)
}

pub(crate) fn is_retryable(error: &Error) -> bool {
    match error {
        Error::Route(RouteError::Transport(
            TransportError::Connect(_) | TransportError::Network(_),
        )) => true,
        Error::Route(RouteError::Transport(TransportError::Http { status, .. })) => {
            *status == 429 || *status >= 500
        }
        _ => false,
    }
}

pub(crate) async fn post_json_raw(
    gateway: &Gateway,
    url: &str,
    headers: Vec<(String, String)>,
    payload: &Value,
    timeout: Option<Duration>,
) -> Result<Value, Error> {
    let client = gateway
        .resources
        .pool
        .client(&gateway.http, ClientVariant::Provider)
        .map_err(|e| Error::Internal(e.to_string()))?;
    let mut builder = client
        .post(url)
        .timeout(timeout.unwrap_or(DEFAULT_UPSTREAM_TIMEOUT))
        .json(payload);
    for (name, val) in headers {
        builder = builder.header(&name, &val);
    }
    let response = builder.send().await.map_err(map_reqwest_err)?;
    let status = response.status();
    let text = response.text().await.map_err(map_reqwest_err)?;
    if !status.is_success() {
        return Err(Error::Route(RouteError::Transport(TransportError::Http {
            status: status.as_u16(),
            body: truncate_error_body(&text),
        })));
    }
    serde_json::from_str(&text)
        .map_err(|e| Error::Internal(format!("invalid upstream JSON response: {e}")))
}

pub(crate) async fn post_stream_raw(
    gateway: &Gateway,
    url: &str,
    headers: Vec<(String, String)>,
    payload: &Value,
    timeout: Option<Duration>,
) -> Result<reqwest::Response, Error> {
    let client = gateway
        .resources
        .pool
        .client(&gateway.http, ClientVariant::Provider)
        .map_err(|e| Error::Internal(e.to_string()))?;
    let mut builder = client
        .post(url)
        .timeout(timeout.unwrap_or(DEFAULT_UPSTREAM_TIMEOUT))
        .json(payload);
    for (name, val) in headers {
        builder = builder.header(&name, &val);
    }
    let response = builder.send().await.map_err(map_reqwest_err)?;
    let status = response.status();
    if !status.is_success() {
        let text = response.text().await.unwrap_or_default();
        return Err(Error::Route(RouteError::Transport(TransportError::Http {
            status: status.as_u16(),
            body: truncate_error_body(&text),
        })));
    }
    Ok(response)
}

fn map_reqwest_err(err: reqwest::Error) -> Error {
    if err.is_connect() || err.is_builder() {
        Error::Route(RouteError::Transport(TransportError::Connect(
            err.to_string(),
        )))
    } else {
        Error::Route(RouteError::Transport(TransportError::Network(
            err.to_string(),
        )))
    }
}

#[derive(Clone, Copy)]
pub(crate) enum StreamFormat {
    OpenAiCompat,
    Gemini,
}

pub(crate) struct StreamMeta {
    pub sink: Option<UsageSink>,
    pub auth: Option<AuthMetadata>,
    pub request_id: String,
    pub call_type: String,
    pub requested_model: String,
    pub deployment: ModelDeployment,
    pub provider: String,
    pub upstream_model: String,
    pub api_base: String,
    pub start_time_ms: i64,
    pub response_id: String,
    pub created: u64,
}

pub(crate) fn build_sse_response(
    upstream: reqwest::Response,
    format: StreamFormat,
    meta: StreamMeta,
) -> Response {
    let byte_stream = upstream.bytes_stream();

    let out_stream = futures_util::stream::unfold(
        (
            byte_stream,
            String::new(),
            TokenUsage::default(),
            false,
            Some(meta),
        ),
        move |(mut stream, mut buf, mut tracked_usage, mut done, mut meta_opt)| async move {
            loop {
                if let Some(newline_pos) = buf.find('\n') {
                    let raw_line = buf[..newline_pos].trim_end_matches('\r').to_owned();
                    buf.drain(..=newline_pos);

                    let Some(data) = raw_line.strip_prefix("data:") else {
                        continue;
                    };
                    let trimmed = data.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    if trimmed == "[DONE]" {
                        done = true;
                        if let Some(m) = meta_opt.take() {
                            emit_stream_usage(m, tracked_usage, "success");
                        }
                        return Some((
                            Ok::<Bytes, Infallible>(Bytes::from_static(b"data: [DONE]\n\n")),
                            (stream, buf, tracked_usage, done, meta_opt),
                        ));
                    }

                    let Ok(parsed) = serde_json::from_str::<Value>(trimmed) else {
                        continue;
                    };

                    if let Some(m_ref) = meta_opt.as_ref() {
                        let transformed = match format {
                            StreamFormat::OpenAiCompat => {
                                if let Some(u) = openai_compat::extract_usage(&parsed) {
                                    tracked_usage = u;
                                }
                                Some(openai_compat::normalize_sse_chunk(
                                    parsed,
                                    &m_ref.requested_model,
                                ))
                            }
                            StreamFormat::Gemini => {
                                let out = gemini::gemini_sse_chunk_to_openai(
                                    &parsed,
                                    &m_ref.requested_model,
                                    &m_ref.response_id,
                                    m_ref.created,
                                );
                                if let Some(ref val) = out
                                    && let Some(u) = openai_compat::extract_usage(val)
                                {
                                    tracked_usage = u;
                                }
                                out
                            }
                        };

                        if let Some(chunk_val) = transformed {
                            let frame = format!("data: {chunk_val}\n\n");
                            return Some((
                                Ok::<Bytes, Infallible>(Bytes::from(frame)),
                                (stream, buf, tracked_usage, done, meta_opt),
                            ));
                        }
                    }
                    continue;
                }

                match stream.next().await {
                    Some(Ok(bytes)) => {
                        buf.push_str(&String::from_utf8_lossy(&bytes));
                    }
                    Some(Err(err)) => {
                        if let Some(m) = meta_opt.take() {
                            emit_stream_usage(m, tracked_usage, "failure");
                        }
                        let frame = Error::Route(RouteError::Transport(TransportError::Network(
                            err.to_string(),
                        )))
                        .sse_frame();
                        return Some((
                            Ok::<Bytes, Infallible>(Bytes::from(frame)),
                            (stream, buf, tracked_usage, true, None),
                        ));
                    }
                    None => {
                        if !done {
                            done = true;
                            if let Some(m) = meta_opt.take() {
                                emit_stream_usage(m, tracked_usage, "success");
                            }
                            return Some((
                                Ok::<Bytes, Infallible>(Bytes::from_static(b"data: [DONE]\n\n")),
                                (stream, buf, tracked_usage, done, meta_opt),
                            ));
                        }
                        return None;
                    }
                }
            }
        },
    );

    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, "text/event-stream; charset=utf-8"),
            (header::CACHE_CONTROL, "no-cache"),
        ],
        Body::from_stream(out_stream),
    )
        .into_response()
}

fn emit_stream_usage(meta: StreamMeta, usage: TokenUsage, status: &str) {
    let Some(sink) = meta.sink else {
        return;
    };
    sink(UsageRecord {
        request_id: meta.request_id,
        call_type: meta.call_type,
        model_group: meta.requested_model,
        upstream_model: meta.upstream_model,
        model_id: meta.deployment.id,
        custom_llm_provider: meta.provider,
        api_base: meta.api_base,
        prompt_tokens: usage.prompt_tokens,
        completion_tokens: usage.completion_tokens,
        cached_tokens: usage.cached_tokens,
        input_cost_per_token: meta.deployment.input_cost_per_token,
        output_cost_per_token: meta.deployment.output_cost_per_token,
        cache_read_input_token_cost: meta.deployment.cache_read_input_token_cost,
        start_time_ms: meta.start_time_ms,
        end_time_ms: now_millis(),
        status: status.to_owned(),
        auth: meta.auth,
    });
}

pub(crate) struct CallMeta<'a> {
    pub sink: Option<&'a UsageSink>,
    pub auth: Option<AuthMetadata>,
    pub request_id: String,
    pub call_type: &'a str,
    pub requested_model: &'a str,
    pub deployment: &'a ModelDeployment,
    pub provider: &'a str,
    pub upstream_model: &'a str,
    pub api_base: &'a str,
    pub start_time_ms: i64,
}

pub(crate) fn emit_json_usage(meta: CallMeta<'_>, response: &Value) {
    let Some(sink) = meta.sink else {
        return;
    };
    let usage = openai_compat::extract_usage(response).unwrap_or_default();
    sink(UsageRecord {
        request_id: meta.request_id,
        call_type: meta.call_type.to_owned(),
        model_group: meta.requested_model.to_owned(),
        upstream_model: meta.upstream_model.to_owned(),
        model_id: meta.deployment.id.clone(),
        custom_llm_provider: meta.provider.to_owned(),
        api_base: meta.api_base.to_owned(),
        prompt_tokens: usage.prompt_tokens,
        completion_tokens: usage.completion_tokens,
        cached_tokens: usage.cached_tokens,
        input_cost_per_token: meta.deployment.input_cost_per_token,
        output_cost_per_token: meta.deployment.output_cost_per_token,
        cache_read_input_token_cost: meta.deployment.cache_read_input_token_cost,
        start_time_ms: meta.start_time_ms,
        end_time_ms: now_millis(),
        status: "success".to_owned(),
        auth: meta.auth,
    });
}

pub(crate) struct ChatExecutionRequest<'a> {
    pub candidate: &'a ModelDeployment,
    pub requested_model: &'a str,
    pub body: &'a Map<String, Value>,
    pub stream: bool,
    pub sink: Option<UsageSink>,
    pub auth: Option<AuthMetadata>,
    pub request_id: String,
    pub start_time_ms: i64,
}

pub(crate) async fn execute_chat_candidate(
    gateway: &Gateway,
    req: ChatExecutionRequest<'_>,
) -> Result<Response, Error> {
    let ChatExecutionRequest {
        candidate,
        requested_model,
        body,
        stream,
        sink,
        auth,
        request_id,
        start_time_ms,
    } = req;
    let (provider, upstream_model) = split_provider_and_model(candidate)
        .ok_or_else(|| Error::Internal("unable to resolve provider from model".into()))?;
    let api_key = resolve_secret_str(
        gateway.secrets.as_ref(),
        candidate.deployment.api_key.as_deref(),
    )
    .await?;
    let api_base = resolve_secret_str(
        gateway.secrets.as_ref(),
        candidate.deployment.api_base.as_deref(),
    )
    .await?;

    if is_gemini_provider(&provider, &upstream_model) {
        let action = if stream {
            "streamGenerateContent?alt=sse"
        } else {
            "generateContent"
        };
        let url = gemini::endpoint_url(&upstream_model, api_base.as_deref(), action);
        let headers = api_key
            .as_deref()
            .map(gemini::auth_headers)
            .unwrap_or_default();
        let gem_payload =
            gemini::openai_chat_to_gemini(body, candidate.temperature, candidate.top_p)
                .map_err(|e| Error::InvalidBody(e.to_string()))?;

        let response_id = format!("chatcmpl-{}", uuid::Uuid::new_v4().simple());
        let created = now_secs();
        let resolved_base = api_base.unwrap_or_else(|| gemini::DEFAULT_GEMINI_API_BASE.to_owned());

        if stream {
            let upstream = post_stream_raw(
                gateway,
                &url,
                headers,
                &gem_payload,
                candidate.deployment.timeout,
            )
            .await?;
            return Ok(build_sse_response(
                upstream,
                StreamFormat::Gemini,
                StreamMeta {
                    sink,
                    auth,
                    request_id,
                    call_type: "acompletion".to_owned(),
                    requested_model: requested_model.to_owned(),
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

        let gem_json = post_json_raw(
            gateway,
            &url,
            headers,
            &gem_payload,
            candidate.deployment.timeout,
        )
        .await?;
        let openai_json =
            gemini::gemini_response_to_openai(&gem_json, requested_model, &response_id, created);
        emit_json_usage(
            CallMeta {
                sink: sink.as_ref(),
                auth,
                request_id,
                call_type: "acompletion",
                requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &openai_json,
        );
        return Ok(Json(openai_json).into_response());
    }

    if openai_compat::is_openai_compat_provider(&provider) {
        let url = openai_compat::endpoint_url(&provider, api_base.as_deref(), "chat/completions");
        let resolved_base =
            api_base.unwrap_or_else(|| openai_compat::default_api_base(&provider).to_owned());
        let headers = api_key
            .map(|k| vec![("authorization".to_owned(), format!("Bearer {k}"))])
            .unwrap_or_default();
        let prepared = Value::Object(openai_compat::prepare_chat_request(
            &upstream_model,
            body.clone(),
            candidate.temperature,
            candidate.top_p,
        ));

        if stream {
            let upstream = post_stream_raw(
                gateway,
                &url,
                headers,
                &prepared,
                candidate.deployment.timeout,
            )
            .await?;
            return Ok(build_sse_response(
                upstream,
                StreamFormat::OpenAiCompat,
                StreamMeta {
                    sink,
                    auth,
                    request_id,
                    call_type: "acompletion".to_owned(),
                    requested_model: requested_model.to_owned(),
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

        let raw_json = post_json_raw(
            gateway,
            &url,
            headers,
            &prepared,
            candidate.deployment.timeout,
        )
        .await?;
        let normalized = openai_compat::normalize_chat_response(
            raw_json,
            requested_model,
            candidate
                .merge_reasoning_content_in_choices
                .unwrap_or(false),
        );
        emit_json_usage(
            CallMeta {
                sink: sink.as_ref(),
                auth,
                request_id,
                call_type: "acompletion",
                requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &normalized,
        );
        return Ok(Json(normalized).into_response());
    }

    // Legacy core path (Anthropic, Bedrock)
    if stream {
        return Err(Error::Unsupported(format!(
            "streaming chat completions for provider {provider}"
        )));
    }
    let messages = body
        .get("messages")
        .cloned()
        .ok_or_else(|| Error::InvalidBody("messages is required".into()))?;
    let optional_params = body
        .iter()
        .filter(|(name, _)| !matches!(name.as_str(), "model" | "messages" | "stream"))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let response = litellm_core::chat_completions::chat_completions(
        &gateway.resources,
        &gateway.http,
        litellm_core::chat_completions::types::ChatCompletionsRequest {
            model: &candidate.deployment.model,
            messages,
            optional_params,
            api_key: api_key.as_deref(),
            api_base: api_base.as_deref(),
            custom_llm_provider: candidate.deployment.custom_llm_provider.as_deref(),
            extra_headers: None,
            timeout: candidate.deployment.timeout,
        },
    )
    .await?;
    let json_val = serde_json::to_value(&response).map_err(|e| Error::Internal(e.to_string()))?;
    emit_json_usage(
        CallMeta {
            sink: sink.as_ref(),
            auth,
            request_id,
            call_type: "acompletion",
            requested_model,
            deployment: candidate,
            provider: &provider,
            upstream_model: &upstream_model,
            api_base: api_base.as_deref().unwrap_or_default(),
            start_time_ms,
        },
        &json_val,
    );
    Ok(Json(response).into_response())
}
