"""
Wolinet AI Python SDK Client
Supports both Synchronous (WolinetAI) and Asynchronous (AsyncWolinetAI) workflows.
"""

import json
import os
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union
import httpx

from .types import (
    ChatMessage,
    ChatCompletionChunk,
    ChatCompletionResponse,
    EmbeddingResponse,
    RerankResponse,
)


class _ChatCompletionsSync:
    def __init__(self, client: "WolinetAI"):
        self._c = client

    def create(
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[ChatCompletionResponse, Iterator[ChatCompletionChunk]]:
        url = f"{self._c.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages or [],
            "temperature": temperature,
            "stream": stream,
            **kwargs,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if not stream:
            with httpx.Client(timeout=self._c.timeout) as http:
                resp = http.post(url, json=payload, headers=self._c._headers)
                resp.raise_for_status()
                return ChatCompletionResponse.model_validate(resp.json())

        def _gen() -> Iterator[ChatCompletionChunk]:
            with httpx.Client(timeout=self._c.timeout) as http:
                with http.stream("POST", url, json=payload, headers=self._c._headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        trimmed = line.strip()
                        if not trimmed or trimmed.startswith(":"):
                            continue
                        if trimmed == "data: [DONE]":
                            break
                        if trimmed.startswith("data: "):
                            raw = trimmed[6:].strip()
                            try:
                                yield ChatCompletionChunk.model_validate_json(raw)
                            except Exception:
                                continue

        return _gen()


class _ChatCompletionsAsync:
    def __init__(self, client: "AsyncWolinetAI"):
        self._c = client

    async def create(
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[ChatCompletionResponse, AsyncIterator[ChatCompletionChunk]]:
        url = f"{self._c.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages or [],
            "temperature": temperature,
            "stream": stream,
            **kwargs,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if not stream:
            async with httpx.AsyncClient(timeout=self._c.timeout) as http:
                resp = await http.post(url, json=payload, headers=self._c._headers)
                resp.raise_for_status()
                return ChatCompletionResponse.model_validate(resp.json())

        async def _agen() -> AsyncIterator[ChatCompletionChunk]:
            async with httpx.AsyncClient(timeout=self._c.timeout) as http:
                async with http.stream("POST", url, json=payload, headers=self._c._headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        trimmed = line.strip()
                        if not trimmed or trimmed.startswith(":"):
                            continue
                        if trimmed == "data: [DONE]":
                            break
                        if trimmed.startswith("data: "):
                            raw = trimmed[6:].strip()
                            try:
                                yield ChatCompletionChunk.model_validate_json(raw)
                            except Exception:
                                continue

        return _agen()


class _EmbeddingsSync:
    def __init__(self, client: "WolinetAI"):
        self._c = client

    def create(self, model: str = "bge-small-en-v1.5", input: Union[str, List[str]] = "") -> EmbeddingResponse:
        url = f"{self._c.base_url}/v1/embeddings"
        with httpx.Client(timeout=self._c.timeout) as http:
            resp = http.post(url, json={"model": model, "input": input}, headers=self._c._headers)
            resp.raise_for_status()
            return EmbeddingResponse.model_validate(resp.json())


class _RerankSync:
    def __init__(self, client: "WolinetAI"):
        self._c = client

    def create(
        self,
        model: str = "bge-reranker-v2-m3",
        query: str = "",
        documents: Optional[List[str]] = None,
        top_n: Optional[int] = None,
    ) -> RerankResponse:
        url = f"{self._c.base_url}/v1/rerank"
        payload: Dict[str, Any] = {"model": model, "query": query, "documents": documents or []}
        if top_n is not None:
            payload["top_n"] = top_n
        with httpx.Client(timeout=self._c.timeout) as http:
            resp = http.post(url, json=payload, headers=self._c._headers)
            resp.raise_for_status()
            return RerankResponse.model_validate(resp.json())


class WolinetAI:
    """Synchronous Client for Wolinet AI Sovereign Gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or os.getenv("WOLINET_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.api_key = api_key or os.getenv("WOLINET_API_KEY", "sk-wolinet-local-dev")
        self.timeout = timeout

        self.chat = _ChatCompletionsSync(self)
        self.embeddings = _EmbeddingsSync(self)
        self.rerank = _RerankSync(self)

    @property
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WolinetAI-Python-SDK/1.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def status(self) -> Dict[str, Any]:
        """Fetch live telemetry, health, spend, and cluster nodes."""
        url = f"{self.base_url}/wolinet/status"
        with httpx.Client(timeout=10.0) as http:
            resp = http.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    def get_key(self) -> Dict[str, Any]:
        """Resolve active development API key."""
        url = f"{self.base_url}/wolinet/key"
        with httpx.Client(timeout=10.0) as http:
            resp = http.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    def models(self) -> List[Dict[str, Any]]:
        """List active sovereign models on the inference cluster."""
        url = f"{self.base_url}/v1/models"
        with httpx.Client(timeout=10.0) as http:
            resp = http.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("data", [])


class AsyncWolinetAI:
    """Asynchronous Client for Wolinet AI Sovereign Gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or os.getenv("WOLINET_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.api_key = api_key or os.getenv("WOLINET_API_KEY", "sk-wolinet-local-dev")
        self.timeout = timeout

        self.chat = _ChatCompletionsAsync(self)

    @property
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WolinetAI-Python-AsyncSDK/1.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def status(self) -> Dict[str, Any]:
        url = f"{self.base_url}/wolinet/status"
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()
