use std::{path::Path, sync::Arc, time::Duration};

use axum::{
    Extension, Json,
    extract::{Request, State},
    http::HeaderMap,
    response::{IntoResponse, Response},
};
use base64::{Engine, engine::general_purpose::STANDARD};
use litellm_core::{
    RouteError,
    audio_transcription::{audio_transcription, types::AudioTranscriptionRequest},
};
use litellm_http::{
    ClientVariant, request::truncate_error_body, transport::Error as TransportError,
};
use litellm_llms::{gemini, openai_compat};
use serde_json::{Value, json};

use crate::{
    Error, Gateway, providers, request,
    usage::{AuthMetadata, UsageSink, now_millis},
};

pub(crate) async fn create(
    State(gateway): State<Arc<Gateway>>,
    headers: HeaderMap,
    usage_sink: Option<Extension<UsageSink>>,
    auth_meta: Option<Extension<AuthMetadata>>,
    request: Request,
) -> Response {
    match handle(
        &gateway,
        &headers,
        usage_sink.map(|Extension(s)| s),
        auth_meta.map(|Extension(a)| a),
        request,
    )
    .await
    {
        Ok(response) => Json(response).into_response(),
        Err(error) => error.openai_response(),
    }
}

async fn handle(
    gateway: &Gateway,
    headers: &HeaderMap,
    usage_sink: Option<UsageSink>,
    auth_meta: Option<AuthMetadata>,
    request: Request,
) -> Result<Value, Error> {
    let (body, upload) = request::parse(request).await?;
    let requested_model = body
        .get("model")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::InvalidBody("model is required".into()))?
        .to_owned();
    let candidates = providers::candidates_for_auth(gateway, &requested_model, auth_meta.as_ref())?;
    let candidate = candidates[0];
    let (provider, upstream_model) = providers::split_provider_and_model(candidate)
        .ok_or_else(|| Error::Internal("unable to resolve provider for transcription".into()))?;

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
    let request_id = headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let start_time_ms = now_millis();

    if providers::is_gemini_provider(&provider, &upstream_model) {
        let (audio_bytes, mime_type) = match &upload {
            Some(up) => (up.bytes.as_ref(), up.mime_type.as_deref()),
            None => {
                return Err(Error::InvalidBody(
                    "multipart audio file upload is required for Gemini transcription".into(),
                ));
            }
        };
        let prompt = body.get("prompt").and_then(Value::as_str);
        let language = body.get("language").and_then(Value::as_str);
        let gem_req = gemini::audio_to_gemini_request(audio_bytes, mime_type, prompt, language);
        let url = gemini::endpoint_url(&upstream_model, api_base.as_deref(), "generateContent");
        let req_headers = api_key
            .as_deref()
            .map(gemini::auth_headers)
            .unwrap_or_default();
        let resolved_base = api_base.unwrap_or_else(|| gemini::DEFAULT_GEMINI_API_BASE.to_owned());
        let gem_resp = providers::post_json_raw(
            gateway,
            &url,
            req_headers,
            &gem_req,
            candidate.deployment.timeout,
        )
        .await?;
        let out = gemini::gemini_audio_to_openai(&gem_resp)
            .map_err(|e| Error::Internal(e.to_string()))?;
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "atranscription",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &out,
        );
        return Ok(out);
    }

    if openai_compat::is_openai_compat_provider(&provider)
        && let Some(up) = upload
    {
        let url =
            openai_compat::endpoint_url(&provider, api_base.as_deref(), "audio/transcriptions");
        let resolved_base =
            api_base.unwrap_or_else(|| openai_compat::default_api_base(&provider).to_owned());
        let client = gateway
            .resources
            .pool
            .client(&gateway.http, ClientVariant::Provider)
            .map_err(|e| Error::Internal(e.to_string()))?;
        let file_name = up.file_name.unwrap_or_else(|| "audio.mp3".to_owned());
        let mut part = reqwest::multipart::Part::bytes(up.bytes.to_vec()).file_name(file_name);
        if let Some(mime) = up.mime_type {
            part = part
                .mime_str(&mime)
                .map_err(|e| Error::InvalidBody(e.to_string()))?;
        }
        let mut form = reqwest::multipart::Form::new()
            .part("file", part)
            .text("model", upstream_model.clone());
        if let Some(lang) = body.get("language").and_then(Value::as_str) {
            form = form.text("language", lang.to_owned());
        }
        if let Some(prompt) = body.get("prompt").and_then(Value::as_str) {
            form = form.text("prompt", prompt.to_owned());
        }
        let mut req_builder = client
            .post(&url)
            .timeout(
                candidate
                    .deployment
                    .timeout
                    .unwrap_or(Duration::from_secs(120)),
            )
            .multipart(form);
        if let Some(key) = api_key {
            req_builder = req_builder.bearer_auth(key);
        }
        let resp = req_builder.send().await.map_err(|e| {
            Error::Route(RouteError::Transport(TransportError::Network(
                e.to_string(),
            )))
        })?;
        let status = resp.status();
        let text = resp.text().await.map_err(|e| {
            Error::Route(RouteError::Transport(TransportError::Network(
                e.to_string(),
            )))
        })?;
        if !status.is_success() {
            return Err(Error::Route(RouteError::Transport(TransportError::Http {
                status: status.as_u16(),
                body: truncate_error_body(&text),
            })));
        }
        let out: Value = serde_json::from_str(&text)
            .map_err(|e| Error::Internal(format!("invalid upstream transcription JSON: {e}")))?;
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "atranscription",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &out,
        );
        return Ok(out);
    }

    let audio = match upload {
        Some(upload) => {
            let format = upload
                .file_name
                .as_deref()
                .and_then(|name| Path::new(name).extension())
                .and_then(|extension| extension.to_str())
                .ok_or_else(|| {
                    Error::InvalidBody("audio file requires a filename extension".into())
                })?;
            json!({"data": STANDARD.encode(upload.bytes), "format": format.to_ascii_lowercase()})
        }
        None => body
            .get("audio")
            .cloned()
            .ok_or_else(|| Error::InvalidBody("audio is required".into()))?,
    };
    Ok(audio_transcription(
        &gateway.resources,
        &gateway.http,
        AudioTranscriptionRequest {
            model: &candidate.deployment.model,
            audio,
            api_key: api_key.as_deref(),
            api_base: api_base.as_deref(),
            custom_llm_provider: candidate.deployment.custom_llm_provider.as_deref(),
            extra_headers: None,
            optional_params: body
                .into_iter()
                .filter(|(name, _)| !matches!(name.as_str(), "model" | "audio"))
                .collect(),
            timeout: candidate.deployment.timeout,
        },
    )
    .await?)
}
