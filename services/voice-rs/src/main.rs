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
    "wolinet-voice-v1".to_string()
}
fn default_voice() -> String {
    "baraka".to_string()
}
fn default_format() -> String {
    "wav".to_string()
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
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
    pub runtime: String,
    pub active_models: Vec<String>,
}

pub struct AppState {
    pub python_backend_url: String,
    pub client: reqwest::Client,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let python_backend_url = std::env::var("VOICE_BACKEND_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8089".to_string());

    let state = Arc::new(AppState {
        python_backend_url,
        client: reqwest::Client::new(),
    });

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/v1/models", get(models_handler))
        .route("/models", get(models_handler))
        .route("/v1/audio/speech", post(speech_handler))
        .route("/audio/speech", post(speech_handler))
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
        version: "1.0.0".to_string(),
        runtime: "Rust (Axum + Tokio SIMD Native)".to_string(),
        active_models: vec![
            "wolinet-voice-v1".to_string(),
            "underdog-woof".to_string(),
            "swahili-voice-ad".to_string(),
            "tts-1".to_string(),
        ],
    })
}

async fn models_handler() -> Json<ModelListResponse> {
    Json(ModelListResponse {
        object: "list".to_string(),
        data: vec![
            ModelItem {
                id: "wolinet-voice-v1".to_string(),
                object: "model".to_string(),
                owned_by: "wolinet-ai".to_string(),
                permission: vec!["sovereign".to_string()],
            },
            ModelItem {
                id: "swahili-voice-ad".to_string(),
                object: "model".to_string(),
                owned_by: "wolinet-ai".to_string(),
                permission: vec!["sovereign".to_string()],
            },
            ModelItem {
                id: "underdog-woof".to_string(),
                object: "model".to_string(),
                owned_by: "wolinet-ai".to_string(),
                permission: vec!["sovereign".to_string()],
            },
            ModelItem {
                id: "tts-1".to_string(),
                object: "model".to_string(),
                owned_by: "wolinet-ai".to_string(),
                permission: vec!["sovereign".to_string()],
            },
        ],
    })
}

// Swahili language detector: checks for common Swahili grammatical markers and vocabulary
fn is_swahili(input: &str) -> bool {
    let swahili_markers = [
        "habari", "jambo", "karibu", "kwa", "katika", "mimi", "wewe", "sisi",
        "wao", "yangu", "yetu", "yenu", "wote", "kuja", "kutumia", "mifumo",
        "bei", "nafuu", "tumeijenga", "tuijenga", "ajili", "lugha", "adhimu",
        "kiswahili", "asubuhi", "jua", "mvua", "watu", "sana", "ndio", "hapa",
        "nchi", "taifa", "mji", "kazi", "nzuri", "gani", "nawakaribisha",
        "nawakalibisha", "wote", "huku", "mbona", "lakini", "kwamba"
    ];
    let lower = input.to_lowercase();
    let words: Vec<&str> = lower
        .split(|c: char| !c.is_alphabetic())
        .filter(|s| !s.is_empty())
        .collect();
    words.iter().any(|w| swahili_markers.contains(w))
}

async fn speech_handler(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    Json(mut req): Json<SpeechRequest>,
) -> Result<Response, (StatusCode, String)> {
    let model_lower = req.model.to_lowercase();
    let voice_lower = req.voice.to_lowercase();
    let swahili_detected = is_swahili(&req.input);

    // If text is Swahili or model targets Swahili/sovereign voice, route to native East African audio
    if swahili_detected || model_lower == "swahili-voice-ad" || model_lower == "wolinet-voice-v1" {
        req.model = "swahili-voice-ad".to_string();

        // Voice 1 (Male Native East African): baraka, alloy, onyx, echo, male, juno
        // Voice 2 (Female Native East African): zawadi, nova, shimmer, female, female_1, mira
        // Voice 3 (Female 2 Native East African): amina, neema, fable, female_2
        if voice_lower == "zawadi"
            || voice_lower == "mira"
            || voice_lower == "nova"
            || voice_lower == "shimmer"
            || voice_lower == "female"
            || voice_lower == "female_1"
        {
            req.voice = "female_1".to_string();
        } else if voice_lower == "amina"
            || voice_lower == "neema"
            || voice_lower == "fable"
            || voice_lower == "female_2"
        {
            req.voice = "female_2".to_string();
        } else {
            req.voice = "male".to_string();
        }
    } else if model_lower == "underdog-woof" {
        // English-only Underdog-Woof fast edge synthesis
        req.model = "underdog-woof".to_string();
        if voice_lower != "mira" {
            req.voice = "juno".to_string();
        }
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
    headers.insert(
        header::CONTENT_TYPE,
        content_type.parse().unwrap(),
    );
    headers.insert(
        "x-wolinet-model",
        "wolinet-voice-v1".parse().unwrap(),
    );
    headers.insert(
        "x-wolinet-owner",
        "Wolinet AI Technologies".parse().unwrap(),
    );

    Ok((headers, bytes).into_response())
}
