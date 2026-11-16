use axum::{
    Json,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("gateway auth not configured")]
    Unconfigured,
    #[error("missing or invalid bearer token")]
    InvalidToken,
    #[error("virtual key has expired")]
    ExpiredToken,
    #[error("virtual key is blocked")]
    BlockedKey,
    #[error("virtual key does not have access to model: {0}")]
    ModelNotAllowed(String),
    #[error("virtual key budget exceeded")]
    BudgetExceeded,
    #[error("rate limit exceeded: {0}")]
    RateLimitExceeded(String),
    #[error("gateway authentication unavailable")]
    Secret(#[from] litellm_secrets::Error),
    #[error("authentication store error")]
    Store,
}

impl IntoResponse for Error {
    fn into_response(self) -> Response {
        let status = match &self {
            Self::InvalidToken | Self::ExpiredToken => StatusCode::UNAUTHORIZED,
            Self::BlockedKey | Self::ModelNotAllowed(_) => StatusCode::FORBIDDEN,
            Self::BudgetExceeded => StatusCode::PAYMENT_REQUIRED,
            Self::RateLimitExceeded(_) => StatusCode::TOO_MANY_REQUESTS,
            Self::Unconfigured | Self::Secret(_) | Self::Store => StatusCode::INTERNAL_SERVER_ERROR,
        };
        if matches!(
            self,
            Self::Unconfigured | Self::InvalidToken | Self::Secret(_)
        ) {
            return (status, self.to_string()).into_response();
        }
        (
            status,
            Json(json!({
                "error": {
                    "message": self.to_string(),
                    "type": "authentication_error",
                    "code": status.as_u16()
                }
            })),
        )
            .into_response()
    }
}
