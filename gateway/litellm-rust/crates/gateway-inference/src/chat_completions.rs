use std::sync::Arc;

use axum::{
    Extension,
    body::Bytes,
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
};
use serde_json::{Map, Value};

use crate::{
    Error, Gateway, providers, request,
    usage::{AuthMetadata, UsageSink, now_millis},
};

pub(crate) async fn create(
    State(gateway): State<Arc<Gateway>>,
    headers: HeaderMap,
    usage_sink: Option<Extension<UsageSink>>,
    auth_meta: Option<Extension<AuthMetadata>>,
    body: Bytes,
) -> Response {
    respond(
        &gateway,
        headers,
        usage_sink.map(|Extension(s)| s),
        auth_meta.map(|Extension(a)| a),
        request::object(&body),
    )
    .await
}

pub(crate) async fn deployment(
    State(gateway): State<Arc<Gateway>>,
    headers: HeaderMap,
    usage_sink: Option<Extension<UsageSink>>,
    auth_meta: Option<Extension<AuthMetadata>>,
    Path(path): Path<String>,
    body: Bytes,
) -> Response {
    if let Some(model) = path
        .strip_suffix("/chat/completions")
        .filter(|model| !model.is_empty())
    {
        let body = request::object(&body).map(|body| {
            if body.get("model").is_some_and(|model| !model.is_null()) {
                return body;
            }
            body.into_iter()
                .chain([("model".into(), Value::String(model.into()))])
                .collect()
        });
        return respond(
            &gateway,
            headers,
            usage_sink.map(|Extension(s)| s),
            auth_meta.map(|Extension(a)| a),
            body,
        )
        .await;
    }
    if path.ends_with("/embeddings") || path.ends_with("/completions") {
        return Error::Unsupported(path).openai_response();
    }
    StatusCode::NOT_FOUND.into_response()
}

async fn respond(
    gateway: &Gateway,
    headers: HeaderMap,
    usage_sink: Option<UsageSink>,
    auth_meta: Option<AuthMetadata>,
    body: Result<Map<String, Value>, Error>,
) -> Response {
    let result = match body {
        Ok(body) => handle(gateway, headers, usage_sink, auth_meta, body).await,
        Err(error) => Err(error),
    };
    match result {
        Ok(response) => response,
        Err(error) => error.openai_response(),
    }
}

async fn handle(
    gateway: &Gateway,
    headers: HeaderMap,
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
    let stream = body.get("stream").and_then(Value::as_bool) == Some(true);
    if !body.contains_key("messages") {
        return Err(Error::InvalidBody("messages is required".into()));
    }
    let request_id = headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let start_time_ms = now_millis();

    let max_attempts = (gateway.models.num_retries() as usize)
        .saturating_add(1)
        .max(candidates.len());

    let mut last_error: Option<Error> = None;
    for attempt in 0..max_attempts {
        let candidate = candidates[attempt % candidates.len()];
        match providers::execute_chat_candidate(
            gateway,
            providers::ChatExecutionRequest {
                candidate,
                requested_model: &requested_model,
                body: &body,
                stream,
                sink: usage_sink.clone(),
                auth: auth_meta.clone(),
                request_id: request_id.clone(),
                start_time_ms,
            },
        )
        .await
        {
            Ok(resp) => {
                gateway.models.record_success(&candidate.deployment_id);
                return Ok(resp);
            }
            Err(err) => {
                let retryable = providers::is_retryable(&err);
                if retryable {
                    gateway.models.record_failure(&candidate.deployment_id);
                    last_error = Some(err);
                    continue;
                }
                return Err(err);
            }
        }
    }

    Err(last_error.unwrap_or_else(|| Error::Internal("all deployment candidates failed".into())))
}
