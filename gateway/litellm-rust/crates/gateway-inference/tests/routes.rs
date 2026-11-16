mod support;

use std::{collections::BTreeMap, sync::Arc, time::Duration};

use axum::{
    body::{Body, to_bytes},
    http::Request,
};
use litellm_core::resources::CoreResources;
use litellm_gateway_inference::{Deployment, Gateway, PassThroughRoute, router_with_passthrough};
use litellm_http::{HttpClientPool, HttpSettings, Resolution, media::PublicDnsResolver};
use litellm_llms::base_llm::ocr::settings::OcrSettings;
use litellm_secrets::{SecretValue, source::SecretSource};
use rstest::rstest;
use serde_json::{Value, json};
use tower::ServiceExt;
use wiremock::{
    Mock, MockServer, ResponseTemplate,
    matchers::{body_partial_json, header, method, path as match_path},
};

#[rstest]
#[case("/chat/completions", Some("public/model"))]
#[case("/v1/chat/completions", Some("public/model"))]
#[case("/engines/public/model/chat/completions", None)]
#[case("/openai/deployments/public/model/chat/completions", None)]
#[case("/openai/deployments/unused/chat/completions", Some("public/model"))]
#[tokio::test]
async fn chat_aliases_call_core_and_use_the_body_model_before_the_path(
    #[case] route: &str,
    #[case] model: Option<&str>,
) {
    let upstream = MockServer::start().await;
    let messages = json!([{"role": "user", "content": "hi"}]);
    Mock::given(method("POST"))
        .and(body_partial_json(
            json!({"model": "test-model", "max_tokens": 16}),
        ))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "msg_test", "model": "test-model", "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}
        })))
        .expect(1)
        .mount(&upstream)
        .await;
    let response = support::post(
        support::app("anthropic/test-model", &upstream.uri()),
        route,
        json!({"model": model, "messages": messages, "max_tokens": 16}),
    )
    .await;
    assert_eq!(response.status(), 200);
    assert_eq!(
        support::json(response).await["choices"][0]["message"]["content"],
        "hello"
    );
}

struct NoSecrets;

impl SecretSource for NoSecrets {
    fn get_secret_str<'a>(
        &'a self,
        _: &'a str,
    ) -> futures_util::future::BoxFuture<'a, Result<Option<SecretValue>, litellm_secrets::Error>>
    {
        Box::pin(async { Ok(None) })
    }
}

#[rstest]
#[case("/engines/public/model/embeddings")]
#[case("/openai/deployments/public/model/completions")]
#[tokio::test]
async fn unimplemented_deployment_subroutes_return_an_explicit_error(#[case] path: &str) {
    let response = support::post(
        support::app("anthropic/test-model", "http://127.0.0.1:1"),
        path,
        json!({}),
    )
    .await;
    assert_eq!(response.status(), 501);
    assert!(
        support::json(response).await["error"]["message"]
            .as_str()
            .unwrap()
            .contains("not implemented")
    );
}

#[rstest]
#[case("/responses")]
#[case("/v1/responses")]
#[case("/embeddings")]
#[case("/v1/embeddings")]
#[case("/completions")]
#[case("/v1/completions")]
#[tokio::test]
async fn newly_implemented_routes_validate_requests_and_reject_unsupported_providers(
    #[case] path: &str,
) {
    let response = support::post(
        support::app("anthropic/test-model", "http://127.0.0.1:1"),
        path,
        json!({"model": "public/model", "input": "hi", "prompt": "hi"}),
    )
    .await;
    assert_eq!(response.status(), 501);
}

#[rstest]
#[tokio::test]
async fn models_endpoint_lists_configured_models() {
    let app = support::app("openai/Deepseeker Coder", "http://127.0.0.1:1");
    let response = app
        .oneshot(Request::get("/v1/models").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), 200);
    let body = support::json(response).await;
    assert_eq!(body["object"], "list");
    assert_eq!(body["data"][0]["id"], "public/model");
}

#[rstest]
#[tokio::test]
async fn openai_compat_streaming_and_deepseek_reasoning_work() {
    let upstream = MockServer::start().await;
    Mock::given(method("POST"))
        .and(match_path("/v1/chat/completions"))
        .and(header("authorization", "Bearer test-key"))
        .and(body_partial_json(json!({"model": "deepseek-v4-pro", "stream": true})))
        .respond_with(
            ResponseTemplate::new(200)
                .insert_header("content-type", "text/event-stream")
                .set_body_string(
                    "data: {\"id\":\"1\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"index\":0,\"delta\":{\"reasoning_content\":\"think\"}}]}\n\ndata: {\"id\":\"1\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\"ok\"},\"finish_reason\":\"stop\"}],\"usage\":{\"prompt_tokens\":10,\"completion_tokens\":2,\"prompt_cache_hit_tokens\":5}}\n\ndata: [DONE]\n\n",
                ),
        )
        .expect(1)
        .mount(&upstream)
        .await;

    let response = support::post(
        support::app("deepseek/deepseek-v4-pro", &upstream.uri()),
        "/v1/chat/completions",
        json!({"model": "public/model", "messages": [{"role": "user", "content": "hi"}], "stream": true}),
    )
    .await;
    assert_eq!(response.status(), 200);
    let bytes = to_bytes(response.into_body(), 1024 * 1024).await.unwrap();
    let text = String::from_utf8(bytes.to_vec()).unwrap();
    assert!(text.contains("\"reasoning_content\":\"think\""));
    assert!(text.contains("\"cached_tokens\":5"));
    assert!(text.contains("data: [DONE]"));
}

#[rstest]
#[tokio::test]
async fn gemini_vertex_api_base_routes_chat_stream_embeddings_and_images() {
    let upstream = MockServer::start().await;
    let vertex_base = format!(
        "{}/v1/projects/123/locations/global/publishers/google",
        upstream.uri()
    );

    Mock::given(method("POST"))
        .and(match_path("/v1/projects/123/locations/global/publishers/google/models/gemini-3.8-flash:streamGenerateContent"))
        .and(header("x-goog-api-key", "test-key"))
        .respond_with(
            ResponseTemplate::new(200)
                .insert_header("content-type", "text/event-stream")
                .set_body_string(
                    "data: {\"candidates\":[{\"index\":0,\"content\":{\"parts\":[{\"text\":\"Jambo\"}]},\"finishReason\":\"STOP\"}],\"usageMetadata\":{\"promptTokenCount\":4,\"candidatesTokenCount\":1,\"totalTokenCount\":5}}\n\n",
                ),
        )
        .expect(1)
        .mount(&upstream)
        .await;

    let chat_resp = support::post(
        support::app("gemini/gemini-3.8-flash", &vertex_base),
        "/v1/chat/completions",
        json!({"model": "public/model", "messages": [{"role": "user", "content": "hi"}], "stream": true}),
    )
    .await;
    assert_eq!(chat_resp.status(), 200);
    let chat_sse = String::from_utf8(
        to_bytes(chat_resp.into_body(), 1024 * 1024)
            .await
            .unwrap()
            .to_vec(),
    )
    .unwrap();
    assert!(chat_sse.contains("\"content\":\"Jambo\""));
    assert!(chat_sse.contains("data: [DONE]"));

    Mock::given(method("POST"))
        .and(match_path("/v1/projects/123/locations/global/publishers/google/models/text-embedding-004:embedContent"))
        .and(header("x-goog-api-key", "test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "embedding": { "values": [0.1, 0.2, 0.3] }
        })))
        .expect(1)
        .mount(&upstream)
        .await;

    let emb_resp = support::post(
        support::app("gemini/text-embedding-004", &vertex_base),
        "/v1/embeddings",
        json!({"model": "public/model", "input": "hello"}),
    )
    .await;
    assert_eq!(emb_resp.status(), 200);
    assert_eq!(
        support::json(emb_resp).await["data"][0]["embedding"],
        json!([0.1, 0.2, 0.3])
    );

    Mock::given(method("POST"))
        .and(match_path("/v1/projects/123/locations/global/publishers/google/models/gemini-3.1-flash-image:generateContent"))
        .and(header("x-goog-api-key", "test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "candidates": [{
                "content": { "parts": [{ "inlineData": { "mimeType": "image/png", "data": "SU1BR0U=" } }] }
            }]
        })))
        .expect(1)
        .mount(&upstream)
        .await;

    let img_resp = support::post(
        support::app("gemini/gemini-3.1-flash-image", &vertex_base),
        "/v1/images/generations",
        json!({"model": "public/model", "prompt": "a lion"}),
    )
    .await;
    assert_eq!(img_resp.status(), 200);
    assert_eq!(
        support::json(img_resp).await["data"][0]["b64_json"],
        "SU1BR0U="
    );
}

#[rstest]
#[tokio::test]
async fn pass_through_endpoints_proxy_requests_to_internal_services() {
    let upstream = MockServer::start().await;
    Mock::given(method("POST"))
        .and(match_path("/v1/defense/inspect"))
        .and(body_partial_json(json!({"payload": "check"})))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"safe": true})))
        .expect(1)
        .mount(&upstream)
        .await;

    let pool = Arc::new(HttpClientPool::new(Arc::new(PublicDnsResolver)));
    let http = Resolution::from(&HttpSettings::default()).config;
    let secrets = Arc::new(NoSecrets);
    let resources = CoreResources::new(pool);
    let ocr = resources
        .ocr_client(
            &http,
            Default::default(),
            OcrSettings::default(),
            secrets.clone(),
        )
        .unwrap();
    let gw = Arc::new(Gateway {
        resources,
        http,
        secrets,
        ocr,
        models: [(
            "public/model".into(),
            Deployment {
                model: "openai/test".into(),
                timeout: Some(Duration::from_secs(5)),
                ..Default::default()
            },
        )]
        .into_iter()
        .collect(),
    });
    let app = router_with_passthrough(
        gw,
        &[PassThroughRoute {
            path: "/v1/defense/inspect".into(),
            target: upstream.uri(),
            headers: BTreeMap::new(),
            include_subpath: false,
        }],
    );

    let resp = support::post(app, "/v1/defense/inspect", json!({"payload": "check"})).await;
    assert_eq!(resp.status(), 200);
    assert_eq!(support::json(resp).await["safe"], true);
}

#[rstest]
#[case("/audio/transcriptions")]
#[case("/v1/audio/transcriptions")]
#[tokio::test]
async fn transcription_aliases_reach_core_validation(#[case] path: &str) {
    let response = support::post(
        support::app("bedrock/test-model", "http://127.0.0.1:1"),
        path,
        json!({"model": "public/model", "audio": {"data": "YWJj", "format": "invalid"}}),
    )
    .await;
    assert_eq!(response.status(), 400);
    let body: Value = support::json(response).await;
    assert!(
        body["error"]["message"]
            .as_str()
            .unwrap()
            .contains("audio.format")
    );
}
