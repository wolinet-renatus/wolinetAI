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
DEFAULT_PUBLIC_MODEL = "Wolinet Coder"
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


def _inference_urls() -> list[str]:
    """Return the internal endpoint first, then configured cross-stack URLs."""
    urls = [os.environ.get("XINFERENCE_BASE_URL", "http://mitambo:9997")]
    urls.extend(os.environ.get("XINFERENCE_FALLBACK_URLS", "").split(","))
    return list(dict.fromkeys(url.strip().rstrip("/") for url in urls if url.strip()))


def _fetch_active_models_from_urls(api_key: str) -> tuple[str, dict[str, dict[str, Any]]]:
    failures: list[str] = []
    for inference_url in _inference_urls():
        try:
            return inference_url, _fetch_active_models(inference_url, api_key)
        except Exception as exc:
            failures.append(f"{inference_url}: {exc}")
            log.warning("Xinference endpoint unavailable at %s: %s", inference_url, exc)
    raise RuntimeError("All Xinference endpoints failed: " + "; ".join(failures))


def _upsert_model(gateway_url: str, gateway_key: str, model_name: str, model_uid: str,
                  inference_api_base: str, inference_key: str, existing: dict[str, Any] | None) -> None:
    if existing:
        existing_info = _model_info(existing)
        existing_metadata = existing_info.get("metadata") or {}
        existing_params = existing.get("litellm_params") or {}
        if isinstance(existing_metadata, str):
            try:
                existing_metadata = json.loads(existing_metadata)
            except json.JSONDecodeError:
                existing_metadata = {}
        if (
            isinstance(existing_metadata, dict)
            and existing_metadata.get("xinference_model_uid") == model_uid
            and existing_params.get("model") == f"wolinet_ai/{model_uid}"
            and str(existing_params.get("api_base", "")).rstrip("/") == inference_api_base.rstrip("/")
        ):
            return
    model_info = {
        "mode": "chat",
        "metadata": {
            "wolinet_sync_source": MANAGED_SOURCE,
            "xinference_model_uid": model_uid,
        },
    }
    if existing:
        model_info["id"] = _model_info(existing).get("id")
    payload = {
        "model_name": model_name,
        "litellm_params": {
            "model": f"wolinet_ai/{model_uid}",
            "api_base": inference_api_base,
            "api_key": inference_key,
            "timeout": 600,
        },
        "model_info": model_info,
    }
    endpoint = "/model/update" if existing and model_info.get("id") else "/model/new"
    _request_json(f"{gateway_url.rstrip('/')}{endpoint}", gateway_key, "POST", payload)


def _fetch_gateway_models(gateway_url: str, api_key: str) -> list[dict[str, Any]]:
    return _data_list(_request_json(f"{gateway_url.rstrip('/')}/model/info", api_key))


def sync_once() -> None:
    gateway_url = os.environ.get("LITELLM_BASE_URL", "http://lango:4000")
    gateway_key = os.environ["LITELLM_MASTER_KEY"]
    inference_key = os.environ["XINFERENCE_API_KEY"]

    inference_url, active = _fetch_active_models_from_urls(inference_key)
    inference_api_base = f"{inference_url.rstrip('/')}/v1"
    current = _fetch_gateway_models(gateway_url, gateway_key)
    known_inference_urls = _inference_urls()
    managed = {
        str(entry.get("model_name")): entry
        for entry in current
        if any(_is_managed(entry, url) for url in known_inference_urls)
    }
    current_by_name = {str(entry.get("model_name")): entry for entry in current if entry.get("model_name")}

    for model_id, model in active.items():
        if model_id in current_by_name and model_id not in managed:
            log.warning("Skipping active Xinference model %s because LiteLLM already has that name", model_id)
            continue
        _upsert_model(gateway_url, gateway_key, model_id, model_id, inference_api_base,
                      inference_key, managed.get(model_id))
        log.info("Synced running Xinference model in LiteLLM: %s", model_id)

    # Keep the public default name stable while the actual inference UID stays
    # dynamic. An explicit UID can select a preferred active model; otherwise
    # choose the first active UID deterministically.
    preferred_uid = os.environ.get("XINFERENCE_DEFAULT_MODEL_UID", "").strip()
    default_uid = preferred_uid if preferred_uid in active else (sorted(active)[0] if active else None)
    default_entry = managed.get(DEFAULT_PUBLIC_MODEL)
    if default_uid:
        _upsert_model(gateway_url, gateway_key, DEFAULT_PUBLIC_MODEL, default_uid,
                      inference_api_base, inference_key, default_entry)
        log.info("Public model %s routes to active Xinference model %s", DEFAULT_PUBLIC_MODEL, default_uid)

    for model_id, entry in managed.items():
        if model_id == DEFAULT_PUBLIC_MODEL and default_uid:
            continue
        if model_id != DEFAULT_PUBLIC_MODEL and model_id in active:
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
