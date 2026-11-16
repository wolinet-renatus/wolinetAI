use std::{collections::BTreeMap, convert::Infallible, sync::Arc, time::Duration};

use axum::{
    body::{Body, Bytes, to_bytes},
    extract::{Request, State},
    http::{HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
};
use futures_util::StreamExt;
use litellm_http::ClientVariant;

use crate::{Error, Gateway, providers, request};

#[derive(Clone, Debug)]
pub struct PassThroughRoute {
    pub path: String,
    pub target: String,
    pub headers: BTreeMap<String, String>,
    pub include_subpath: bool,
}

#[derive(Clone)]
pub(crate) struct PassThroughState {
    pub gateway: Arc<Gateway>,
    pub route: PassThroughRoute,
}

pub(crate) async fn forward(State(state): State<PassThroughState>, request: Request) -> Response {
    match forward_inner(&state, request).await {
        Ok(resp) => resp,
        Err(err) => err.openai_response(),
    }
}

async fn forward_inner(state: &PassThroughState, request: Request) -> Result<Response, Error> {
    let resolved_target =
        providers::resolve_secret_str(state.gateway.secrets.as_ref(), Some(&state.route.target))
            .await?
            .ok_or_else(|| {
                Error::Internal(format!("unresolved target for {}", state.route.path))
            })?;

    let method = request.method().clone();
    let uri = request.uri().clone();
    let headers = request.headers().clone();
    let path_and_query = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or(&state.route.path);

    let target_url = build_target_url(&resolved_target, path_and_query);
    let body_bytes = to_bytes(request.into_body(), request::MAX_BODY_BYTES)
        .await
        .map_err(|_| Error::BodyTooLarge)?;

    let client = state
        .gateway
        .resources
        .pool
        .client(&state.gateway.http, ClientVariant::Provider)
        .map_err(|e| Error::Internal(e.to_string()))?;

    let mut builder = client
        .request(method, &target_url)
        .timeout(Duration::from_secs(120))
        .body(body_bytes);

    for (name, value) in &headers {
        let lower = name.as_str().to_ascii_lowercase();
        if matches!(
            lower.as_str(),
            "host" | "content-length" | "connection" | "transfer-encoding" | "authorization"
        ) {
            continue;
        }
        builder = builder.header(name, value);
    }

    for (k, v) in &state.route.headers {
        if let Some(resolved_val) =
            providers::resolve_secret_str(state.gateway.secrets.as_ref(), Some(v)).await?
        {
            builder = builder.header(k.as_str(), resolved_val);
        }
    }

    let upstream = builder
        .send()
        .await
        .map_err(|e| Error::Internal(format!("passthrough error: {e}")))?;
    let status =
        StatusCode::from_u16(upstream.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let resp_headers = upstream.headers().clone();
    let stream = upstream
        .bytes_stream()
        .map(|chunk| chunk.map_err(|e| std::io::Error::other(e.to_string())));

    let mut out = Response::new(Body::from_stream(stream.map(|res| match res {
        Ok(b) => Ok::<Bytes, Infallible>(b),
        Err(_) => Ok(Bytes::new()),
    })));
    *out.status_mut() = status;
    for (name, val) in &resp_headers {
        let lower = name.as_str().to_ascii_lowercase();
        if matches!(lower.as_str(), "transfer-encoding" | "connection") {
            continue;
        }
        if let (Ok(hname), Ok(hval)) = (
            HeaderName::from_bytes(name.as_str().as_bytes()),
            HeaderValue::from_bytes(val.as_bytes()),
        ) {
            out.headers_mut().insert(hname, hval);
        }
    }
    Ok(out.into_response())
}

pub fn build_target_url(target: &str, path_and_query: &str) -> String {
    let trimmed = target.trim_end_matches('/');
    let path_only = path_and_query.split('?').next().unwrap_or(path_and_query);
    if trimmed.ends_with(path_only) {
        match path_and_query.split_once('?') {
            Some((_, query)) => format!("{trimmed}?{query}"),
            None => trimmed.to_owned(),
        }
    } else if path_and_query.starts_with('/') {
        format!("{trimmed}{path_and_query}")
    } else {
        format!("{trimmed}/{path_and_query}")
    }
}
