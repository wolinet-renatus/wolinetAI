//! The proxy's inference endpoints as an axum [`Router`] a server mounts.
//!
//! Authentication, rate limiting and logging are the mounting server's layers; this crate
//! maps a public model name to its deployment and runs the core route.

mod audio_transcription;
mod chat_completions;
mod completions;
mod embeddings;
mod error;
mod images;
pub mod messages;
mod models;
mod ocr;
pub mod passthrough;
mod providers;
mod request;
mod responses;
pub mod usage;

use std::sync::Arc;

use axum::{
    Router,
    routing::{any, get, post},
};
use litellm_core::resources::CoreResources;
use litellm_http::HttpClientConfig;
use litellm_llms::base_llm::ocr::handler::OcrClient;
use litellm_secrets::source::SecretSource;

pub use error::Error;
pub use litellm_router::{Deployment, ModelDeployment, Router as ModelList};
pub use passthrough::PassThroughRoute;
pub use usage::{AuthMetadata, UsageRecord, UsageSink};

pub struct Gateway {
    pub resources: CoreResources,
    pub http: HttpClientConfig,
    pub secrets: Arc<dyn SecretSource>,
    pub models: ModelList,
    pub ocr: OcrClient,
}

pub fn router(gateway: Arc<Gateway>) -> Router {
    router_with_passthrough(gateway, &[])
}

pub fn router_with_passthrough(gateway: Arc<Gateway>, pass_through: &[PassThroughRoute]) -> Router {
    let mut app = Router::new()
        .route("/models", get(models::list))
        .route("/v1/models", get(models::list))
        .route("/v1/messages", post(messages::create))
        .route("/ocr", post(ocr::create))
        .route("/v1/ocr", post(ocr::create))
        .route("/chat/completions", post(chat_completions::create))
        .route("/v1/chat/completions", post(chat_completions::create))
        .route("/engines/{*path}", post(chat_completions::deployment))
        .route(
            "/openai/deployments/{*path}",
            post(chat_completions::deployment),
        )
        .route("/audio/transcriptions", post(audio_transcription::create))
        .route(
            "/v1/audio/transcriptions",
            post(audio_transcription::create),
        )
        .route("/embeddings", post(embeddings::create))
        .route("/v1/embeddings", post(embeddings::create))
        .route("/images/generations", post(images::create))
        .route("/v1/images/generations", post(images::create))
        .route("/completions", post(completions::create))
        .route("/v1/completions", post(completions::create))
        .route("/responses", post(responses::create))
        .route("/v1/responses", post(responses::create))
        .layer(axum::extract::DefaultBodyLimit::max(
            request::MAX_BODY_BYTES,
        ))
        .with_state(gateway.clone());

    for route_cfg in pass_through {
        let normalized = if route_cfg.path.starts_with('/') {
            route_cfg.path.clone()
        } else {
            format!("/{}", route_cfg.path)
        };
        let state = passthrough::PassThroughState {
            gateway: gateway.clone(),
            route: route_cfg.clone(),
        };
        let pt_router = Router::new()
            .route(&normalized, any(passthrough::forward))
            .with_state(state.clone());
        app = app.merge(pt_router);

        if route_cfg.include_subpath {
            let sub = format!("{}/{{*rest}}", normalized.trim_end_matches('/'));
            let sub_router = Router::new()
                .route(&sub, any(passthrough::forward))
                .with_state(state);
            app = app.merge(sub_router);
        }
    }

    app
}
