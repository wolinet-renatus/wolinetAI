use std::sync::Arc;

use axum::{
    Extension, Json,
    body::Bytes,
    extract::State,
    http::HeaderMap,
    response::{IntoResponse, Response},
};
use litellm_llms::{gemini, openai_compat};
use serde_json::{Map, Value};

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
    mut body: Map<String, Value>,
) -> Result<Response, Error> {
    let requested_model = body
        .get("model")
        .and_then(Value::as_str)
        .unwrap_or("dall-e-3")
        .to_owned();
    let candidates = providers::candidates_for(gateway, &requested_model)?;
    let candidate = candidates[0];
    let (provider, upstream_model) = providers::split_provider_and_model(candidate)
        .ok_or_else(|| Error::Internal("unable to resolve provider for image generation".into()))?;
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

    if providers::is_gemini_provider(&provider, &upstream_model)
        || (provider == "vertex_ai" && gemini::is_imagen_model(&upstream_model))
    {
        let (gem_req, is_imagen) = gemini::openai_image_to_gemini(&upstream_model, &body)
            .map_err(|e| Error::InvalidBody(e.to_string()))?;
        let action = if is_imagen {
            "predict"
        } else {
            "generateContent"
        };
        let url = gemini::endpoint_url(&upstream_model, api_base.as_deref(), action);
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
        let openai_resp = gemini::gemini_image_to_openai(&gem_resp, is_imagen, now_secs())
            .map_err(|e| Error::Internal(e.to_string()))?;
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "aimage_generation",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &openai_resp,
        );
        return Ok(Json(openai_resp).into_response());
    }

    if openai_compat::is_openai_compat_provider(&provider) {
        let url = openai_compat::endpoint_url(&provider, api_base.as_deref(), "images/generations");
        let resolved_base =
            api_base.unwrap_or_else(|| openai_compat::default_api_base(&provider).to_owned());
        let req_headers = api_key
            .map(|k| vec![("authorization".to_owned(), format!("Bearer {k}"))])
            .unwrap_or_default();
        body.insert("model".to_owned(), Value::String(upstream_model.clone()));
        let resp = providers::post_json_raw(
            gateway,
            &url,
            req_headers,
            &Value::Object(body),
            candidate.deployment.timeout,
        )
        .await?;
        providers::emit_json_usage(
            providers::CallMeta {
                sink: usage_sink.as_ref(),
                auth: auth_meta,
                request_id,
                call_type: "aimage_generation",
                requested_model: &requested_model,
                deployment: candidate,
                provider: &provider,
                upstream_model: &upstream_model,
                api_base: &resolved_base,
                start_time_ms,
            },
            &resp,
        );
        return Ok(Json(resp).into_response());
    }

    Err(Error::Unsupported(format!(
        "image generation for provider {provider}"
    )))
}
