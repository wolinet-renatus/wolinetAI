use axum::{
    extract::Json,
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::CorsLayer;
use tracing::{info, warn};

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct SpeechRequest {
    #[serde(default = "default_model")]
    pub model: String,
    pub input: String,
    #[serde(default = "default_voice")]
    pub voice: String,
    #[serde(default = "default_format")]
    pub response_format: String,
    #[serde(default = "default_speed")]
    pub speed: f32,
    pub nfe_step: Option<u32>,
}

fn default_model() -> String {
    "Wolinet Voice".to_string()
}
fn default_voice() -> String {
    "Renatus".to_string()
}
fn default_format() -> String {
    "mp3".to_string()
}
fn default_speed() -> f32 {
    1.0
}

#[derive(Serialize)]
pub struct ModelItem {
    pub id: String,
    pub object: String,
    pub owned_by: String,
    pub permission: Vec<String>,
}

#[derive(Serialize)]
pub struct ModelListResponse {
    pub object: String,
    pub data: Vec<ModelItem>,
}

#[derive(Serialize)]
pub struct VoiceItem {
    pub id: String,
    pub name: String,
}

#[derive(Serialize)]
pub struct VoiceListResponse {
    pub voices: Vec<VoiceItem>,
}

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
    pub runtime: String,
    pub active_models: Vec<String>,
    pub voices: Vec<String>,
}

pub struct AppState {
    pub python_backend_url: String,
    pub llm_backend_url: String,
    pub client: reqwest::Client,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let python_backend_url = std::env::var("VOICE_BACKEND_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8089".to_string());
    let llm_backend_url = std::env::var("VOICE_LLM_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8088".to_string());

    let state = Arc::new(AppState {
        python_backend_url,
        llm_backend_url,
        client: reqwest::Client::builder()
            .no_proxy()
            .timeout(std::time::Duration::from_secs(600))
            .build()
            .unwrap(),
    });

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/v1/models", get(models_handler))
        .route("/models", get(models_handler))
        .route("/v1/audio/voices", get(voices_handler))
        .route("/audio/voices", get(voices_handler))
        .route("/v1/audio/speech", post(speech_handler))
        .route("/audio/speech", post(speech_handler))
        .route("/v1/chat/completions", post(chat_handler))
        .route("/chat/completions", post(chat_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let port: u16 = std::env::var("VOICE_RS_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8090);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("[voice-rs] Wolinet Sovereign Rust Voice Engine listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health_handler() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        service: "wolinet-voice-rs".to_string(),
        version: "1.1.0".to_string(),
        runtime: "Rust (Axum + Tokio SIMD Native)".to_string(),
        active_models: vec!["Wolinet Voice".to_string()],
        voices: vec![
            "Renatus (Male Native Voice)".to_string(),
            "Witness (Female Native Voice)".to_string(),
        ],
    })
}

async fn models_handler() -> Json<ModelListResponse> {
    Json(ModelListResponse {
        object: "list".to_string(),
        data: vec![ModelItem {
            id: "Wolinet Voice".to_string(),
            object: "model".to_string(),
            owned_by: "wolinet-ai".to_string(),
            permission: vec!["sovereign".to_string()],
        }],
    })
}

async fn voices_handler() -> Json<VoiceListResponse> {
    Json(VoiceListResponse {
        voices: vec![
            VoiceItem {
                id: "Renatus".to_string(),
                name: "Renatus (Male)".to_string(),
            },
            VoiceItem {
                id: "Witness".to_string(),
                name: "Witness (Female)".to_string(),
            },
        ],
    })
}

async fn speech_handler(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    Json(mut req): Json<SpeechRequest>,
) -> Result<Response, (StatusCode, String)> {
    let voice_lower = req.voice.to_lowercase();

    // Unified sovereign voice model
    req.model = "Wolinet Voice".to_string();
    if req.response_format.is_empty() {
        req.response_format = "mp3".to_string();
    }

    // Clean dual-voice mapping:
    // Female voice: Witness (with Angela alias)
    // Male voice: Renatus
    if voice_lower == "witness"
        || voice_lower == "angela"
        || voice_lower == "female"
        || voice_lower == "nova"
        || voice_lower == "shimmer"
        || voice_lower == "mira"
        || voice_lower == "zawadi"
    {
        req.voice = "Witness".to_string();
    } else {
        req.voice = "Renatus".to_string();
    }

    let target_url = format!("{}/v1/audio/speech", state.python_backend_url);

    let res = state
        .client
        .post(&target_url)
        .json(&req)
        .send()
        .await
        .map_err(|e| {
            warn!("[voice-rs] Backend synthesis connection failed: {}", e);
            (
                StatusCode::BAD_GATEWAY,
                format!("Synthesis backend unavailable: {}", e),
            )
        })?;

    if !res.status().is_success() {
        let err_text = res.text().await.unwrap_or_default();
        return Err((StatusCode::INTERNAL_SERVER_ERROR, err_text));
    }

    let content_type = res
        .headers()
        .get(header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("audio/wav")
        .to_string();

    let bytes = res.bytes().await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Failed to read audio stream: {}", e),
        )
    })?;

    let mut headers = HeaderMap::new();
    headers.insert(header::CONTENT_TYPE, content_type.parse().unwrap());
    headers.insert("x-wolinet-model", "Wolinet Voice".parse().unwrap());
    headers.insert(
        "x-wolinet-owner",
        "Wolinet AI Technologies".parse().unwrap(),
    );

    Ok((headers, bytes).into_response())
}

async fn chat_handler(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    Json(mut payload): Json<serde_json::Value>,
) -> Result<Response, (StatusCode, String)> {
    info!("[voice-rs] Received chat completion request");
    if let Some(obj) = payload.as_object_mut() {
        obj.insert(
            "model".to_string(),
            serde_json::Value::String("Deepseeker Coder".to_string()),
        );
    }

    let is_stream = payload
        .get("stream")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let target_url = format!("{}/v1/chat/completions", state.llm_backend_url);

    let res = state
        .client
        .post(&target_url)
        .header("Authorization", "Bearer sk-XvKFiwDoOtOe8i4lwbzb8Q")
        .json(&payload)
        .send()
        .await
        .map_err(|e| {
            warn!("[voice-rs] Chat upstream connection failed: {}", e);
            (
                StatusCode::BAD_GATEWAY,
                format!("LLM backend unavailable: {}", e),
            )
        })?;

    if !res.status().is_success() {
        let status =
            StatusCode::from_u16(res.status().as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
        let err_text = res.text().await.unwrap_or_default();
        return Err((status, err_text));
    }

    if is_stream {
        let content_type = res
            .headers()
            .get(header::CONTENT_TYPE)
            .and_then(|v| v.to_str().ok())
            .unwrap_or("text/event-stream")
            .to_string();

        let stream = res.bytes_stream();
        let body = axum::body::Body::from_stream(stream);

        let mut headers = HeaderMap::new();
        headers.insert(header::CONTENT_TYPE, content_type.parse().unwrap());
        headers.insert(header::CACHE_CONTROL, "no-cache".parse().unwrap());
        headers.insert("x-wolinet-model", "Wolinet Voice".parse().unwrap());

        Ok((headers, body).into_response())
    } else {
        let mut data: serde_json::Value = res.json().await.map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Failed to parse upstream response: {}", e),
            )
        })?;

        if let Some(obj) = data.as_object_mut() {
            obj.insert(
                "model".to_string(),
                serde_json::Value::String("Wolinet Voice".to_string()),
            );
        }

        let mut headers = HeaderMap::new();
        headers.insert(header::CONTENT_TYPE, "application/json".parse().unwrap());
        headers.insert("x-wolinet-model", "Wolinet Voice".parse().unwrap());

        Ok((headers, Json(data)).into_response())
    }
}
