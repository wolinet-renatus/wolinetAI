use std::{sync::Arc, time::Instant};

use axum::{
    Extension, Json, Router,
    body::{Body, Bytes},
    extract::Request,
    middleware::{self, Next},
    response::Response,
    routing::get,
};
use http_body_util::BodyExt;

use litellm_config::Config;
use litellm_core::resources::CoreResources;
use litellm_gateway_auth::{
    Auth, AuthContext, GatewayAuth, RequireMasterKey, SpendEvent, authenticate_middleware,
};
use litellm_gateway_inference::{
    AuthMetadata, Gateway, ModelList, PassThroughRoute, UsageRecord, UsageSink,
};
use litellm_http::{
    ClientVariant, HttpClientPool, HttpSettings, Resolution, media::PublicDnsResolver,
};
use litellm_llms::base_llm::ocr::settings::OcrSettings;
use litellm_secrets::source::EnvironmentSecrets;
use litellm_tracing::ByteChunk;
use serde_json::json;
use uuid::Uuid;

pub fn build_inference(config: &Config) -> Result<Arc<Gateway>, litellm_http::Error> {
    let pool = Arc::new(HttpClientPool::new(Arc::new(PublicDnsResolver)));
    let http = Resolution::from(&HttpSettings::default()).config;
    let client = pool.client(&http, ClientVariant::Provider)?;
    let secrets = Arc::new(EnvironmentSecrets::python_compatible(client));
    let resources = CoreResources::new(pool);
    let ocr = resources.ocr_client(
        &http,
        Default::default(),
        OcrSettings::default(),
        secrets.clone(),
    )?;

    Ok(Arc::new(Gateway {
        resources,
        http,
        secrets,
        models: ModelList::from_config(config),
        ocr,
    }))
}

fn map_pass_through(config: &Config) -> Vec<PassThroughRoute> {
    config
        .general_settings
        .pass_through_endpoints
        .iter()
        .map(|ep| PassThroughRoute {
            path: ep.path.clone(),
            target: ep.target.clone(),
            headers: ep.headers.clone(),
            include_subpath: ep.include_subpath.unwrap_or(false),
        })
        .collect()
}

pub fn router(inference: Arc<Gateway>, config: &Config) -> Router {
    let auth = Auth::from_config(config, inference.secrets.clone());
    let pass_through = map_pass_through(config);
    let model_count = inference.models.model_names().len();
    let inference_router =
        litellm_gateway_inference::router_with_passthrough(inference, &pass_through)
            .route_layer(middleware::from_extractor_with_state::<RequireMasterKey, _>(auth));

    Router::new()
        .route("/health/liveliness", get(|| async { Json("I'm alive!") }))
        .route(
            "/health",
            get(move || async move {
                Json(json!({
                    "status": "healthy",
                    "postgres": false,
                    "redis": false,
                    "models": model_count
                }))
            }),
        )
        .merge(inference_router)
        .layer(middleware::from_fn(log_request))
}

pub async fn build_router(inference: Arc<Gateway>, config: &Config) -> Router {
    let gateway_auth = GatewayAuth::connect(config, inference.secrets.clone()).await;
    let db_configured = gateway_auth.is_db_configured();
    let redis_configured = gateway_auth.is_redis_configured();
    let model_count = inference.models.model_names().len();
    let spend_logger = gateway_auth.spend_logger().clone();

    let usage_sink: UsageSink = Arc::new(move |rec: UsageRecord| {
        let auth = rec.auth.unwrap_or(AuthMetadata {
            key_hash: None,
            user_id: None,
            team_id: None,
            end_user: None,
            organization_id: None,
            tags: Vec::new(),
        });
        spend_logger.record(SpendEvent {
            request_id: rec.request_id,
            call_type: rec.call_type,
            key_hash: auth.key_hash.unwrap_or_default(),
            user_id: auth.user_id,
            team_id: auth.team_id,
            organization_id: auth.organization_id,
            end_user: auth.end_user,
            model_group: rec.model_group,
            upstream_model: rec.upstream_model,
            model_id: rec.model_id,
            custom_llm_provider: rec.custom_llm_provider,
            api_base: rec.api_base,
            prompt_tokens: rec.prompt_tokens,
            completion_tokens: rec.completion_tokens,
            cached_tokens: rec.cached_tokens,
            override_input_cost: rec.input_cost_per_token,
            override_output_cost: rec.output_cost_per_token,
            override_cache_read_cost: rec.cache_read_input_token_cost,
            start_time_ms: rec.start_time_ms,
            end_time_ms: rec.end_time_ms,
            status: rec.status,
            request_tags: auth.tags,
        });
    });

    let pass_through = map_pass_through(config);
    let inference_router =
        litellm_gateway_inference::router_with_passthrough(inference, &pass_through)
            .layer(Extension(usage_sink))
            .route_layer(middleware::from_fn(bridge_auth_context))
            .route_layer(middleware::from_fn_with_state(
                gateway_auth,
                authenticate_middleware,
            ));

    Router::new()
        .route("/health/liveliness", get(|| async { Json("I'm alive!") }))
        .route(
            "/health",
            get(move || async move {
                Json(json!({
                    "status": "healthy",
                    "postgres": db_configured,
                    "redis": redis_configured,
                    "models": model_count
                }))
            }),
        )
        .merge(inference_router)
        .layer(middleware::from_fn(log_request))
}

async fn bridge_auth_context(mut request: Request, next: Next) -> Response {
    if let Some(ctx) = request.extensions().get::<AuthContext>().cloned() {
        request.extensions_mut().insert(AuthMetadata {
            key_hash: Some(ctx.key_hash),
            user_id: ctx.user_id,
            team_id: ctx.team_id,
            end_user: ctx.end_user,
            organization_id: ctx.organization_id,
            tags: ctx.tags,
        });
    }
    next.run(request).await
}

async fn log_request(request: Request, next: Next) -> Response {
    let request_id = Uuid::new_v4().to_string();
    let log_body_chunks = tracing::enabled!(tracing::Level::DEBUG);
    let method = request.method().clone();
    let path = request.uri().path().to_owned();
    let started = Instant::now();
    let request = if log_body_chunks {
        request.map(|body| logged_body(body, request_id.clone(), "input"))
    } else {
        request
    };
    let response = next.run(request).await;
    tracing::info!(
        %request_id,
        %method,
        %path,
        status = response.status().as_u16(),
        time_to_headers_ms = started.elapsed().as_secs_f64() * 1000.0,
        "response headers"
    );
    if log_body_chunks {
        response.map(|body| logged_body(body, request_id, "output"))
    } else {
        response
    }
}

fn logged_body(body: Body, request_id: String, direction: &'static str) -> Body {
    Body::new(body.map_frame(move |frame| {
        if let Some(data) = frame.data_ref() {
            log_chunk(&request_id, direction, data);
        }
        frame
    }))
}

fn log_chunk(request_id: &str, direction: &str, data: &Bytes) {
    let chunk = ByteChunk::new(data);
    tracing::debug!(request_id, direction, encoding = chunk.encoding(), chunk = %chunk, "body chunk");
}

#[cfg(test)]
mod tests {
    use std::{convert::Infallible, sync::mpsc};

    use axum::{body::to_bytes, http::StatusCode, routing::post};
    use futures_util::stream;
    use litellm_tracing::{Logger, Metadata, Record, Sink};
    use rstest::rstest;
    use serde_json::{Value, json};
    use tower::ServiceExt;

    use super::*;

    struct LogSink(mpsc::Sender<Value>);

    impl Sink for LogSink {
        fn enabled(&self, _: &Metadata<'_>) -> bool {
            true
        }

        fn emit(&self, record: &Record) {
            self.0
                .send(json!({"message": record.message, "fields": record.fields}))
                .unwrap();
        }
    }

    #[rstest]
    #[tokio::test]
    async fn logs_each_body_chunk_without_changing_streamed_bytes() {
        let app = Router::new()
            .route(
                "/stream",
                post(|_: Bytes| async {
                    (
                        StatusCode::OK,
                        Body::from_stream(stream::iter([
                            Ok::<_, Infallible>(Bytes::from_static(b"event: first\n\n")),
                            Ok(Bytes::from_static(b"event: second\n\n")),
                        ])),
                    )
                }),
            )
            .layer(axum::middleware::from_fn(log_request));
        let request_chunks = [
            Ok::<_, Infallible>(Bytes::from_static(b"hello")),
            Ok(Bytes::from_static(b" world")),
        ];
        let request = Request::post("/stream")
            .body(Body::from_stream(stream::iter(request_chunks)))
            .unwrap();
        let (sender, receiver) = mpsc::channel();
        let logger = Logger::new(LogSink(sender));

        let output = logger
            .instrument(async {
                let response = app.oneshot(request).await.unwrap();
                to_bytes(response.into_body(), 1024).await.unwrap()
            })
            .await;

        assert_eq!(output, "event: first\n\nevent: second\n\n");
        let records: Vec<Value> = receiver.try_iter().collect();
        assert_eq!(records.len(), 5);
        assert_eq!(records[0]["fields"]["chunk"], "hello");
        assert_eq!(records[1]["fields"]["chunk"], " world");
        assert_eq!(records[2]["fields"]["status"], 200);
        assert_eq!(records[3]["fields"]["chunk"], "event: first\n\n");
        assert_eq!(records[4]["fields"]["chunk"], "event: second\n\n");
        let request_id = &records[2]["fields"]["request_id"];
        assert!(request_id.as_str().is_some());
        assert!(
            records
                .iter()
                .all(|record| &record["fields"]["request_id"] == request_id)
        );
    }
}
