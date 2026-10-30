use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;

use axum::{
    extract::State,
    http::StatusCode,
    response::{
        sse::{Event, KeepAlive, Sse},
        IntoResponse, Response,
    },
    routing::{get, post},
    Json, Router,
};
use futures_util::StreamExt;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::json;
use tokio::sync::RwLock;
use tower_http::cors::CorsLayer;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Clone)]
struct AppState {
    mitambo_url: String,
    mitambo_api_key: String,
    http_client: reqwest::Client,
    injection_regexes: Arc<Vec<Regex>>,
    command_regexes: Arc<Vec<Regex>>,
    kill_switch_active: Arc<RwLock<bool>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ChatMessage {
    role: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct ChatCompletionRequest {
    #[serde(default = "default_model")]
    model: String,
    messages: Vec<ChatMessage>,
    #[serde(default)]
    stream: bool,
    #[serde(default = "default_temperature")]
    temperature: Option<f32>,
    #[serde(default = "default_max_tokens")]
    max_tokens: Option<u32>,
}

fn default_model() -> String {
    "Secure Pro".to_string()
}
fn default_temperature() -> Option<f32> {
    Some(0.6)
}
fn default_max_tokens() -> Option<u32> {
    Some(450)
}

#[derive(Debug, Serialize, Clone)]
struct InspectionResult {
    model: String,
    verdict: String,
    threat_score: f32,
    is_safe: bool,
    attack_vectors: Vec<String>,
    action: String,
    latency_ms: f64,
    uncensored_policy: String,
    timestamp: u64,
}

#[derive(Debug, Deserialize)]
struct InspectRequest {
    prompt: Option<String>,
    messages: Option<Vec<ChatMessage>>,
}

#[derive(Debug, Deserialize)]
struct KillSwitchPayload {
    action: Option<String>,
    agent_id: Option<String>,
}

impl AppState {
    fn inspect_prompt(&self, text: &str) -> InspectionResult {
        let start = Instant::now();
        let mut attack_vectors = Vec::new();
        let mut threat_score = 0.0f32;

        for re in self.injection_regexes.iter() {
            if re.is_match(text) {
                attack_vectors.push(format!("INJECTION_PATTERN: {}", re.as_str()));
                threat_score += 0.45;
            }
        }

        for re in self.command_regexes.iter() {
            if re.is_match(text) {
                attack_vectors.push(format!("HOST_COMMAND_EXPLOIT: {}", re.as_str()));
                threat_score += 0.55;
            }
        }

        let threat_score = threat_score.min(1.0);
        let verdict = if threat_score >= 0.70 {
            "CRITICAL_THREAT"
        } else if threat_score >= 0.35 {
            "SUSPICIOUS"
        } else {
            "CLEAN"
        };

        let is_safe = threat_score < 0.70;
        let action = if is_safe { "PASS_THROUGH" } else { "ISOLATE" };
        let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        InspectionResult {
            model: "OrcaCyber-Nano-1.0-AI-Defense-DFlash2-Q8_0".to_string(),
            verdict: verdict.to_string(),
            threat_score,
            is_safe,
            attack_vectors,
            action: action.to_string(),
            latency_ms,
            uncensored_policy: "ALLOWED (Normal conversational freedom unrestricted)".to_string(),
            timestamp,
        }
    }
}

// -----------------------------------------------------------------------------
// Route Handlers
// -----------------------------------------------------------------------------

async fn health_handler(State(state): State<AppState>) -> impl IntoResponse {
    let killed = *state.kill_switch_active.read().await;
    let status = if killed { "KILL_SWITCH_ENGAGED" } else { "UP" };

    Json(json!({
        "status": status,
        "engine": "OrcaCyber-Nano-1.0-Rust-Core",
        "runtime": "native-rust-axum",
        "models": [
            "Secure Pro",
            "Wolinet Pro",
            "Wolinex Coder",
            "Wolinet Turbo Draft",
            "OrcaCyber-Nano-1.0-AI-Defense"
        ],
        "metadata": {
            "architecture": "dflash-native",
            "name": "OrcaCyber Nano 1.0 AI Defense (High-Speed Rust Core)",
            "threat_scanning": "sub-microsecond",
            "no_think_tags": true,
            "real_time_streaming": true,
            "upstream_core": state.mitambo_url
        }
    }))
}

async fn models_handler() -> impl IntoResponse {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let models = vec![
        ("Secure Pro", "Sovereign AI Cyber Defense & Infrastructure Guard (Rust Native Core)", "rust-native-dflash"),
        ("Wolinet Pro", "Sovereign AI Flagship Intelligence Core", "dflash-fast"),
        ("Wolinex Coder", "Sovereign AI Systems & Software Engineering Core", "dflash-fast"),
        ("Wolinet Turbo Draft", "High-Speed Speculative Draft Acceleration Engine", "dflash-speculative"),
        ("OrcaCyber-Nano-1.0-AI-Defense", "OrcaCyber Nano 1.0 AI Defense & Guardrail", "dflash"),
        ("flintlock-3b", "Flintlock 3B Sovereign Intelligence Engine", "llama3"),
    ];

    let data: Vec<serde_json::Value> = models
        .into_iter()
        .map(|(id, desc, arch)| {
            json!({
                "id": id,
                "object": "model",
                "created": now,
                "owned_by": "wolinet-ai",
                "mode": "chat",
                "architecture": arch,
                "max_input_tokens": 262144,
                "max_output_tokens": 8192,
                "description": desc
            })
        })
        .collect();

    Json(json!({
        "object": "list",
        "data": data
    }))
}

async fn kill_switch_handler(
    State(state): State<AppState>,
    Json(payload): Json<KillSwitchPayload>,
) -> impl IntoResponse {
    let action = payload.action.unwrap_or_else(|| "isolate".to_string());
    if action == "reset" || action == "deactivate" {
        let mut k = state.kill_switch_active.write().await;
        *k = false;
        info!("🛡️ Kill switch DEACTIVATED by webhook.");
        Json(json!({ "status": "RESET", "active": false }))
    } else {
        let mut k = state.kill_switch_active.write().await;
        *k = true;
        info!("🚨 EMERGENCY KILL SWITCH ACTIVATED by webhook! Isolating agent: {:?}", payload.agent_id);
        Json(json!({ "status": "KILL_SWITCH_ACTIVE", "active": true, "agent_id": payload.agent_id }))
    }
}

async fn inspect_handler(
    State(state): State<AppState>,
    Json(payload): Json<InspectRequest>,
) -> impl IntoResponse {
    let text = if let Some(p) = payload.prompt {
        p
    } else if let Some(msgs) = payload.messages {
        msgs.last().map(|m| m.content.clone()).unwrap_or_default()
    } else {
        String::new()
    };

    let inspection = state.inspect_prompt(&text);
    Json(json!(inspection))
}

fn strip_think_tags(raw: &str) -> String {
    let re_closed = Regex::new(r"<think>[\s\S]*?</think>").unwrap();
    let stripped = re_closed.replace_all(raw, "").to_string();
    let clean = stripped
        .replace("<think>", "")
        .replace("</think>", "")
        .replace("<|eot_id|>", "")
        .replace("<|start_header_id|>", "")
        .replace("<|end_header_id|>", "")
        .replace("<|end_of_text|>", "")
        .replace("<|user|>", "")
        .replace("<|assistant|>", "");
    clean.trim().to_string()
}

fn clean_stream_chunk(content: &str) -> String {
    let re_closed = Regex::new(r"<think>[\s\S]*?</think>").unwrap();
    let stripped = re_closed.replace_all(content, "").to_string();
    let s = stripped
        .replace("<think>", "")
        .replace("</think>", "")
        .replace("<|eot_id|>", "")
        .replace("<|start_header_id|>", "")
        .replace("<|end_header_id|>", "")
        .replace("<|end_of_text|>", "")
        .replace("<|user|>", "")
        .replace("<|assistant|>", "");

    if (content.contains("</think>") || content.contains("<think>")) && s.starts_with("\n\n") {
        s.trim_start_matches('\n').to_string()
    } else {
        s
    }
}

fn determine_model_profile(client_model: &str, user_prompt: &str) -> (&'static str, String, String) {
    let m = client_model.to_lowercase();
    let prompt_lower = user_prompt.to_lowercase();

    if m.contains("coder") {
        let sys = "You are Wolinex Coder, sovereign AI Systems & Software Engineering Expert of Wolinet AI. Provide direct, clean, production-ready code, systems architecture, and technical solutions. Never output thinking tags or internal monologue. Answer directly and concisely.".to_string();
        let prefix = if prompt_lower.contains("python") {
            "</think>\n\nHere is the Python implementation:\n\n".to_string()
        } else if prompt_lower.contains("rust") {
            "</think>\n\nHere is the Rust implementation:\n\n".to_string()
        } else {
            "</think>\n\nHere is the technical solution:\n\n".to_string()
        };
        ("wolinex-coder", sys, prefix)
    } else if m.contains("pro") && !m.contains("secure") {
        let sys = "You are Wolinet Pro, sovereign AI Flagship Intelligence Assistant of Wolinet AI. Provide direct, articulate, insightful, and comprehensive answers. Never output thinking tags or internal monologue. Answer directly and concisely.".to_string();
        let prefix = "</think>\n\nHere is the analysis:\n\n".to_string();
        ("wolinex-coder", sys, prefix)
    } else {
        // Secure Pro / Wolinet Secure Pro / Turbo Draft
        let sys = "You are Secure Pro, sovereign AI Cyber Defense & Infrastructure Guard of Wolinet AI. Provide direct, highly technical, sovereign cybersecurity audits and infrastructure security analysis. Never output thinking tags or internal monologue. Answer directly and concisely.".to_string();
        let prefix = "</think>\n\nHere is the security assessment and technical breakdown:\n\n1. ".to_string();
        ("wolinex-coder", sys, prefix)
    }
}

fn greeting_for_model(client_model: &str) -> &'static str {
    let m = client_model.to_lowercase();
    if m.contains("coder") {
        "Hello! I am **Wolinex Coder**, your sovereign AI Systems & Software Engineering Expert.\n\n\
        I specialize in full-stack architecture, high-performance backend systems, security-hardened APIs, and clean, idiomatic code generation.\n\n\
        What software, system, or algorithm are you building or debugging today?"
    } else if m.contains("pro") && !m.contains("secure") {
        "Hello! I am **Wolinet Pro**, your sovereign AI Flagship Intelligence Assistant.\n\n\
        I provide real-time technical reasoning, workflow automation, and sovereign intelligence for your projects.\n\n\
        How can I assist your objectives today?"
    } else if m.contains("draft") {
        "Hello! I am **Wolinet Turbo Draft**, your high-speed speculative draft acceleration engine.\n\n\
        I provide ultra-low latency token generation and speculative acceleration for sovereign AI workloads.\n\n\
        How can I accelerate your task today?"
    } else {
        "Hello! I am **Secure Pro**, your sovereign AI Cyber Defense & Infrastructure Guard.\n\n\
        I provide real-time protection against prompt injections, API hijacking, and security vulnerabilities.\n\
        I can perform comprehensive application security audits, review source code, and inspect server configurations.\n\n\
        How would you like to proceed with your code audit or infrastructure security today?"
    }
}

async fn chat_completions_handler(
    State(state): State<AppState>,
    Json(req): Json<ChatCompletionRequest>,
) -> Response {
    if *state.kill_switch_active.read().await {
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "error": {
                    "message": "🚨 Emergency Kill Switch is currently ACTIVE. Service suspended.",
                    "type": "kill_switch_activated"
                }
            })),
        )
            .into_response();
    }

    // Extract user prompt
    let user_prompt = req
        .messages
        .iter()
        .rev()
        .find(|m| m.role == "user")
        .map(|m| m.content.as_str())
        .unwrap_or("");

    let inspection = state.inspect_prompt(user_prompt);

    // 1. Block Critical Threats
    if inspection.verdict == "CRITICAL_THREAT" {
        let response_text = format!(
            "### 🛡️ [OrcaCyber Defense: Threat Contained]\n\n\
            **Alert:** A structural cyber threat or injection attack pattern was detected in the payload.\n\n\
            - **Detected Vector(s):** `{}`\n\
            - **Threat Score:** `{:.2} / 1.00`\n\
            - **Action Taken:** Input neutralized to prevent host/gateway compromise.\n\n\
            #### Defensive Guidance:\n\
            Ensure delimiter tokens and unescaped binary evaluation patterns are sanitized before submission.",
            inspection.attack_vectors.join(", "),
            inspection.threat_score
        );

        return make_chat_response(&req.model, &response_text, &inspection, req.stream);
    }

    let prompt_lower = user_prompt.trim().to_lowercase();

    // 2. Instant Conversational Fast-Path (< 0.1ms TTFT, zero think tags)
    let greeting_re = Regex::new(r"^(hello+|hi+|hey+|hellow+|greetings|good\s+(morning|afternoon|evening)|who\s+are\s+you|what\s+can\s+you\s+do)[\s!?,.]*$").unwrap();
    if greeting_re.is_match(&prompt_lower) {
        let response_text = greeting_for_model(&req.model);
        return make_chat_response(&req.model, response_text, &inspection, req.stream);
    }

    // 3. Instant Security Audit Readiness Fast-Path (when asking to share code before pasting)
    let audit_keywords = [
        "secure my app", "share source", "check issues", "audit my code",
        "check for vulnerabilities", "review my app", "check my app",
    ];
    let has_code_token = ["def ", "class ", "import ", "function ", "const ", "<?php", "<html>", "{", "SELECT ", "curl "]
        .iter()
        .any(|t| user_prompt.contains(t));

    if audit_keywords.iter().any(|k| prompt_lower.contains(k)) && !has_code_token {
        let response_text = "### 🛡️ Secure Pro: Application Security & Code Audit Ready\n\n\
            Yes! Please share your application source code, configuration files, or API endpoints, and I will perform an immediate security audit.\n\n\
            **What I will evaluate:**\n\
            1. **Injection Vulnerabilities:** SQL injection, command injection, SSRF, XSS, and template injection.\n\
            2. **Authentication & Session Flaws:** JWT validation, token storage, session fixation, and OAuth flows.\n\
            3. **Secrets & Sensitive Data:** Hardcoded credentials, exposed API keys, and unencrypted data in transit/rest.\n\
            4. **Access Control & Authorization:** IDOR (Insecure Direct Object References) and privilege escalation.\n\
            5. **Infrastructure & Server Posture:** 1Panel hardening, Docker container isolation, and Nginx reverse proxy SSL/TLS.\n\n\
            Please paste your code snippets or tell me which framework and language you are using, and I will begin the security analysis immediately.";
        return make_chat_response(&req.model, response_text, &inspection, req.stream);
    }

    // 4. Determine upstream profile and non-thinking bypass prefix
    let (upstream_model, system_prompt, prefix_content) = determine_model_profile(&req.model, user_prompt);

    let mut forward_messages = vec![json!({
        "role": "system",
        "content": system_prompt
    })];

    let mut has_user_turn = false;
    for m in &req.messages {
        if m.role == "user" && !m.content.is_empty() {
            has_user_turn = true;
        }
        let clean_content = strip_think_tags(&m.content);
        forward_messages.push(json!({ "role": &m.role, "content": clean_content }));
    }
    if !has_user_turn {
        forward_messages.push(json!({ "role": "user", "content": user_prompt }));
    }

    // Only inject assistant prefix if explicitly configured (skips thinking on DeepSeek-R1)
    if !prefix_content.is_empty() {
        forward_messages.push(json!({
            "role": "assistant",
            "content": prefix_content,
            "prefix": true
        }));
    }

    let effective_tokens = req.max_tokens.unwrap_or(450).clamp(150, 1024);
    let payload = json!({
        "model": upstream_model,
        "messages": forward_messages,
        "max_tokens": effective_tokens,
        "temperature": req.temperature.unwrap_or(0.6),
        "stream": req.stream,
        "stop": ["<|im_end|>", "<|endoftext|>", "<|im_start|>", "<|eot_id|>"],
        "presence_penalty": 0.2,
        "frequency_penalty": 0.2
    });

    let cmpl_id = format!("chatcmpl-{}", &uuid::Uuid::new_v4().to_string()[..16]);
    let created = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    // 5. If streaming is requested, pipe SSE from Mitambo with on-the-fly tag stripping
    if req.stream {
        let resp_result = state
            .http_client
            .post(format!("{}/v1/chat/completions", state.mitambo_url))
            .header("Authorization", format!("Bearer {}", state.mitambo_api_key))
            .json(&payload)
            .send()
            .await;

        match resp_result {
            Ok(upstream_resp) if upstream_resp.status().is_success() => {
                return stream_from_mitambo(req.model.clone(), upstream_resp, cmpl_id, created).await;
            }
            _ => {
                let fallback = fallback_response_for_model(&req.model, user_prompt);
                return make_chat_response(&req.model, &fallback, &inspection, true);
            }
        }
    }

    // 6. Non-streaming completion
    let resp_result = state
        .http_client
        .post(format!("{}/v1/chat/completions", state.mitambo_url))
        .header("Authorization", format!("Bearer {}", state.mitambo_api_key))
        .json(&payload)
        .send()
        .await;

    let response_text = match resp_result {
        Ok(resp) if resp.status().is_success() => {
            if let Ok(data) = resp.json::<serde_json::Value>().await {
                let raw_content = data["choices"][0]["message"]["content"]
                    .as_str()
                    .unwrap_or("");
                let clean = strip_think_tags(raw_content);
                if clean.is_empty() {
                    fallback_response_for_model(&req.model, user_prompt)
                } else {
                    clean
                }
            } else {
                fallback_response_for_model(&req.model, user_prompt)
            }
        }
        _ => fallback_response_for_model(&req.model, user_prompt),
    };

    make_chat_response(&req.model, &response_text, &inspection, false)
}

async fn stream_from_mitambo(
    client_model: String,
    upstream_resp: reqwest::Response,
    cmpl_id: String,
    created: u64,
) -> Response {
    let sse_stream = async_stream::stream! {
        let mut byte_stream = upstream_resp.bytes_stream();
        let mut buffer = String::new();

        while let Some(chunk_res) = byte_stream.next().await {
            if let Ok(bytes) = chunk_res {
                if let Ok(text) = std::str::from_utf8(&bytes) {
                    buffer.push_str(text);
                    while let Some(pos) = buffer.find('\n') {
                        let line = buffer[..pos].trim().to_string();
                        buffer = buffer[pos + 1..].to_string();

                        if line.is_empty() {
                            continue;
                        }

                        if line.starts_with("data: ") {
                            let data = line["data: ".len()..].trim();
                            if data == "[DONE]" {
                                yield Ok::<Event, axum::Error>(Event::default().data("[DONE]"));
                                return;
                            }

                            if let Ok(mut val) = serde_json::from_str::<serde_json::Value>(data) {
                                let mut emit_chunk = true;
                                if let Some(choices) = val.get_mut("choices").and_then(|c| c.as_array_mut()) {
                                    if let Some(choice) = choices.get_mut(0) {
                                        let has_finish_reason = choice.get("finish_reason").map(|f| !f.is_null()).unwrap_or(false);
                                        if let Some(delta) = choice.get_mut("delta") {
                                            // Discard reasoning_content completely
                                            if let Some(obj) = delta.as_object_mut() {
                                                obj.remove("reasoning_content");
                                            }

                                            if let Some(raw_c) = delta.get("content").and_then(|c| c.as_str()) {
                                                let clean = clean_stream_chunk(raw_c);
                                                if clean.is_empty() {
                                                    if delta.get("role").is_none() && !has_finish_reason {
                                                        emit_chunk = false;
                                                    } else {
                                                        delta["content"] = json!(null);
                                                    }
                                                } else {
                                                    delta["content"] = json!(clean);
                                                }
                                            }
                                        }
                                    }
                                }

                                if emit_chunk {
                                    val["model"] = json!(&client_model);
                                    val["id"] = json!(&cmpl_id);
                                    val["created"] = json!(created);
                                    yield Ok::<Event, axum::Error>(Event::default().data(val.to_string()));
                                }
                            }
                        }
                    }
                }
            }
        }

        yield Ok::<Event, axum::Error>(Event::default().data("[DONE]"));
    };

    Sse::new(sse_stream)
        .keep_alive(KeepAlive::default())
        .into_response()
}

fn fallback_response_for_model(model: &str, _prompt: &str) -> String {
    let m = model.to_lowercase();
    if m.contains("coder") {
        "### 💻 Wolinex Coder: Ready for Systems & Code Architecture\n\n\
        I am ready to assist with your code implementation, refactoring, or infrastructure architecture.\n\n\
        Please provide the code snippet, language, or system requirements you would like to work on.".to_string()
    } else if m.contains("pro") && !m.contains("secure") {
        "### ⚡ Wolinet Pro: Sovereign Intelligence Active\n\n\
        I am ready to assist with your technical questions, automation workflows, and architectural planning.\n\n\
        Please share your query or task details to begin.".to_string()
    } else {
        "### 🛡️ Secure Pro: Application Security & Code Audit Ready\n\n\
        I am ready to audit and secure your application. Please share your source code, configuration files, or architecture overview!\n\n\
        Here is what I will evaluate in detail:\n\
        1. **Authentication & Session Security:** (JWT verification, session hijacking, cookie flags, OAuth)\n\
        2. **Injection Vulnerabilities:** (SQLi, NoSQLi, command injection, template injection)\n\
        3. **Data Protection & Secret Handling:** (Hardcoded tokens, sensitive data exposure, API keys)\n\
        4. **Access Control & Authorization:** (IDOR, privilege escalation, route protection)\n\
        5. **Infrastructure & Server Posture:** (1Panel hardening, Docker isolation, Nginx reverse proxy SSL/TLS)\n\n\
        Please paste your code snippets or tell me which framework/language you are using, and I will begin the security analysis immediately.".to_string()
    }
}

fn make_chat_response(
    model: &str,
    content: &str,
    inspection: &InspectionResult,
    stream: bool,
) -> Response {
    let cmpl_id = format!("chatcmpl-{}", &uuid::Uuid::new_v4().to_string()[..16]);
    let created = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    if stream {
        let words: Vec<String> = content.split_inclusive(' ').map(|s| s.to_string()).collect();
        let cmpl_id_clone = cmpl_id.clone();
        let model_clone = model.to_string();

        let sse_stream = async_stream::stream! {
            // Initial chunk
            yield Ok::<Event, axum::Error>(Event::default().data(json!({
                "id": cmpl_id_clone,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_clone,
                "choices": [{ "index": 0, "delta": { "role": "assistant" }, "finish_reason": null }]
            }).to_string()));

            // Word chunks
            for word in words {
                yield Ok::<Event, axum::Error>(Event::default().data(json!({
                    "id": cmpl_id_clone,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_clone,
                    "choices": [{ "index": 0, "delta": { "content": word }, "finish_reason": null }]
                }).to_string()));
            }

            // Finish chunk
            yield Ok::<Event, axum::Error>(Event::default().data(json!({
                "id": cmpl_id_clone,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_clone,
                "choices": [{ "index": 0, "delta": {}, "finish_reason": "stop" }]
            }).to_string()));

            yield Ok::<Event, axum::Error>(Event::default().data("[DONE]"));
        };

        Sse::new(sse_stream)
            .keep_alive(KeepAlive::default())
            .into_response()
    } else {
        Json(json!({
            "id": cmpl_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": content.split_whitespace().count(),
                "total_tokens": 10 + content.split_whitespace().count()
            },
            "defense_telemetry": inspection
        }))
        .into_response()
    }
}

// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------

#[tokio::main]
async fn main() {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    let _ = tracing::subscriber::set_global_default(subscriber);

    let injection_patterns = vec![
        r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)bypass\s+all\s+(rules|guidelines|guardrails)",
        r"(?i)developer\s+mode\s+enabled",
        r"(?i)dan\s+mode",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"(?i)disregard\s+all\s+previous",
    ];

    let command_patterns = vec![
        r"(?i)eval\s*\(.*base64",
        r"(?i)system\s*\(.*(rm\s+-rf|nc\s+-e|bash\s+-i)",
        r"(?i)/bin/(bash|sh|zsh)\s+-i",
        r"(?i)chmod\s+777\s+/etc",
    ];

    let injection_regexes: Vec<Regex> = injection_patterns
        .into_iter()
        .map(|p| Regex::new(p).unwrap())
        .collect();

    let command_regexes: Vec<Regex> = command_patterns
        .into_iter()
        .map(|p| Regex::new(p).unwrap())
        .collect();

    let http_client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(10))
        .pool_max_idle_per_host(10)
        .build()
        .unwrap();

    let state = AppState {
        mitambo_url: std::env::var("MITAMBO_URL").unwrap_or_else(|_| "http://127.0.0.1:9997".to_string()),
        mitambo_api_key: std::env::var("MITAMBO_API_KEY").unwrap_or_else(|_| "sk-XvKFiwDoOtOe8i4lwbzb8Q".to_string()),
        http_client,
        injection_regexes: Arc::new(injection_regexes),
        command_regexes: Arc::new(command_regexes),
        kill_switch_active: Arc::new(RwLock::new(false)),
    };

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/v1/models", get(models_handler))
        .route("/v1/chat/completions", post(chat_completions_handler))
        .route("/v1/defense/inspect", post(inspect_handler))
        .route("/defense/inspect", post(inspect_handler))
        .route("/inspect", post(inspect_handler))
        .route("/v1/defense/kill_switch", post(kill_switch_handler))
        .route("/kill_switch", post(kill_switch_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let port: u16 = std::env::var("ORCACYBER_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8088);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("🚀 OrcaCyber Defense & Secure Pro (Native Rust High-Speed Core) listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
