use std::sync::Arc;

use axum::{
    Extension, Json,
    extract::State,
    response::{IntoResponse, Response},
};
use serde_json::{Value, json};

use crate::{Gateway, usage::AuthMetadata};

pub(crate) async fn list(
    State(gateway): State<Arc<Gateway>>,
    auth_meta: Option<Extension<AuthMetadata>>,
) -> Response {
    let meta = auth_meta.map(|Extension(a)| a);
    let data: Vec<Value> = gateway
        .models
        .model_names()
        .iter()
        .filter(|name| {
            meta.as_ref()
                .is_none_or(|m| m.is_model_allowed(name, Some(name)))
        })
        .map(|name| {
            json!({
                "id": name,
                "object": "model",
                "created": 1700000000u64,
                "owned_by": "litellm"
            })
        })
        .collect();
    Json(json!({
        "object": "list",
        "data": data
    }))
    .into_response()
}
