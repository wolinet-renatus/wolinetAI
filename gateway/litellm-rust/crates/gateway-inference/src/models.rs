use std::sync::Arc;

use axum::{
    Json,
    extract::State,
    response::{IntoResponse, Response},
};
use serde_json::{Value, json};

use crate::Gateway;

pub(crate) async fn list(State(gateway): State<Arc<Gateway>>) -> Response {
    let data: Vec<Value> = gateway
        .models
        .model_names()
        .iter()
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
