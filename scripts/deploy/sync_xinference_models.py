#!/usr/bin/env python3
"""Keep LiteLLM's local model catalog in sync with running Xinference LLMs."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("xinference-model-sync")

MANAGED_SOURCE = "xinference"
LEGACY_MODEL_NAMES = frozenset(
    {
        "wolinet-coder",
        "deepseek-coder-1.3b",
        "deepseek-coder-instruct",
        "deepseek-coder",
        "wolinex-coder",
        "wolinex-coder-pro",
        "wolinex-coder-lite",
        "wolinex-omni",
        "Wolinet Coder",
        "wolinet coder",
    }
)


def _data_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def active_chat_models(payload: Any) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for item in _data_list(payload):
        model_id = item.get("id")
        model_type = str(item.get("model_type", "")).lower()
        abilities = item.get("model_ability") or ["chat"]
        if isinstance(abilities, str):
            abilities = [abilities]
        if (
            model_id
            and model_type == "llm"
            and any(ability in {"chat", "generate"} for ability in abilities if isinstance(ability, str))
        ):
            active[str(model_id)] = item
    return active


def _model_info(model: dict[str, Any]) -> dict[str, Any]:
    info = model.get("model_info")
    return info if isinstance(info, dict) else {}


def _is_managed(entry: dict[str, Any], inference_url: str) -> bool:
    info = _model_info(entry)
    metadata = info.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = None
    if isinstance(metadata, dict) and metadata.get("wolinet_sync_source") == MANAGED_SOURCE:
        return True

    litellm_params = entry.get("litellm_params")
    model_name = str(entry.get("model_name", ""))
    return (
        model_name in LEGACY_MODEL_NAMES
        and isinstance(litellm_params, dict)
        and str(litellm_params.get("api_base", "")).rstrip("/") == f"{inference_url.rstrip('/')}/v1"
    )


def _request_json(url: str, api_key: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
        return json.loads(payload) if payload else {}


def _fetch_active_models(inference_url: str, api_key: str) -> dict[str, dict[str, Any]]:
    response = _request_json(f"{inference_url.rstrip('/')}/v1/models", api_key)
    return active_chat_models(response)


def _fetch_gateway_models(gateway_url: str, api_key: str) -> list[dict[str, Any]]:
    return _data_list(_request_json(f"{gateway_url.rstrip('/')}/model/info", api_key))


def sync_once() -> None:
    gateway_url = os.environ.get("LITELLM_BASE_URL", "http://lango:4000")
    gateway_key = os.environ["LITELLM_MASTER_KEY"]
    inference_url = os.environ.get("XINFERENCE_BASE_URL", "http://mitambo:9997")
    inference_key = os.environ["XINFERENCE_API_KEY"]
    inference_api_base = f"{inference_url.rstrip('/')}/v1"

    active = _fetch_active_models(inference_url, inference_key)
    current = _fetch_gateway_models(gateway_url, gateway_key)
    managed = {str(entry.get("model_name")): entry for entry in current if _is_managed(entry, inference_url)}
    current_by_name = {str(entry.get("model_name")): entry for entry in current if entry.get("model_name")}

    for model_id, model in active.items():
        if model_id in current_by_name and model_id not in managed:
            log.warning("Skipping active Xinference model %s because LiteLLM already has that name", model_id)
            continue
        if model_id in managed:
            continue

        payload = {
            "model_name": model_id,
            "litellm_params": {
                "model": f"openai/{model_id}",
                "api_base": inference_api_base,
                "api_key": inference_key,
                "timeout": 600,
            },
            "model_info": {
                "mode": "chat",
                "metadata": {
                    "wolinet_sync_source": MANAGED_SOURCE,
                    "xinference_model_uid": model_id,
                },
            },
        }
        _request_json(f"{gateway_url.rstrip('/')}/model/new", gateway_key, "POST", payload)
        log.info("Enabled running Xinference model in LiteLLM: %s", model_id)

    for model_id, entry in managed.items():
        if model_id in active:
            continue
        model_info = _model_info(entry)
        entry_id = model_info.get("id")
        if not entry_id:
            log.warning("Cannot remove inactive managed model without LiteLLM model id: %s", model_id)
            continue
        _request_json(
            f"{gateway_url.rstrip('/')}/model/delete",
            gateway_key,
            "POST",
            {"id": str(entry_id)},
        )
        log.info("Removed stopped Xinference model from LiteLLM: %s", model_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    interval = max(10, int(os.environ.get("XINFERENCE_MODEL_SYNC_INTERVAL", "30")))

    while True:
        try:
            sync_once()
        except Exception:
            log.exception("Model catalog sync failed; it will retry")
        if not args.watch:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
