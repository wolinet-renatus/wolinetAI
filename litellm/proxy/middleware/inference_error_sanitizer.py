"""Replace internal inference outage details in client-facing model errors."""

from __future__ import annotations

import json
import logging
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

PUBLIC_UNAVAILABLE_MESSAGE = "Sorry, our AI service is temporarily unavailable. Please try again later."
UNAVAILABLE_MARKERS = (
    "no deployments available",
    "no healthy deployment available",
    "all deployments for selected model are in cooldown",
    "all deployments exhausted",
    "model not found in the model list",
    "no active models",
    "no model is currently running",
    "model is not running",
    "no models configured on proxy",
    "model_unavailable",
)


def _is_model_api_path(path: str) -> bool:
    normalized = path.rstrip("/")
    return (
        normalized.endswith("/chat/completions")
        or normalized.endswith("/completions")
        or normalized.endswith("/responses")
        or normalized.endswith("/messages")
        or "/audio/" in normalized
    )


def _sanitize_error_body(body: bytes) -> bytes | None:
    try:
        payload: Any = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else payload.get("detail")
    if not isinstance(message, str):
        return None
    lowered = message.casefold()
    if not any(marker in lowered for marker in UNAVAILABLE_MARKERS):
        return None

    logger.warning("Inference unavailable; sanitizing client error: %s", message)
    if isinstance(error, dict):
        safe_error = {
            key: error[key]
            for key in ("call_id", "request_id")
            if isinstance(error.get(key), str)
        }
        safe_error.update(
            message=PUBLIC_UNAVAILABLE_MESSAGE,
            type="service_unavailable",
            param=None,
            code="model_unavailable",
        )
        payload = {"error": safe_error}
    else:
        payload = {"detail": PUBLIC_UNAVAILABLE_MESSAGE}
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class InferenceErrorSanitizerMiddleware:
    """Sanitize known model/inference outages without changing other errors."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or not _is_model_api_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        response_start: Message | None = None
        body_chunks: list[bytes] = []
        content_type = ""

        async def send_wrapped(message: Message) -> None:
            nonlocal response_start, content_type
            if message["type"] == "http.response.start":
                headers = {key.lower(): value.lower() for key, value in message.get("headers", [])}
                status_code = message.get("status", 200)
                content_type = headers.get(b"content-type", b"").decode("latin-1")
                if status_code < 400 or "json" not in content_type or b"content-encoding" in headers:
                    await send(message)
                else:
                    response_start = message
                return

            if message["type"] != "http.response.body" or response_start is None:
                await send(message)
                return

            body_chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            original_body = b"".join(body_chunks)
            sanitized_body = _sanitize_error_body(original_body)
            if sanitized_body is None:
                await send(response_start)
                await send({"type": "http.response.body", "body": original_body})
                return

            response_start["status"] = 503
            response_start["headers"] = [
                (key, value)
                for key, value in response_start.get("headers", [])
                if key.lower() not in {b"content-length", b"content-encoding"}
            ]
            response_start["headers"].append((b"content-type", b"application/json"))
            response_start["headers"].append((b"content-length", str(len(sanitized_body)).encode("ascii")))
            await send(response_start)
            await send({"type": "http.response.body", "body": sanitized_body})

        await self.app(scope, receive, send_wrapped)
