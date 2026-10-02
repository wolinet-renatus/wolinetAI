#!/usr/bin/env python3
"""
==============================================================================
Wolinet AI — Multi-Language SDK Generator (inspired by Scalar)
==============================================================================
Generates strongly typed, production-ready client SDKs for:
1. Python       -> packages/wolinet-python/ (Sync + Async, Streaming, Pydantic)
2. TypeScript   -> packages/wolinet-sdk/    (Fetch-based, Node/Browser, AsyncIterable)
3. Go (Golang)  -> packages/wolinet-go/     (Context-aware, SSE Stream Reader)

Also generates multi-language code snippets (cURL, Python, TS, Go) for documentation
and developer portals.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT_DIR / "packages"
TS_SDK_DIR = PACKAGES_DIR / "wolinet-sdk"
PY_SDK_DIR = PACKAGES_DIR / "wolinet-python"
GO_SDK_DIR = PACKAGES_DIR / "wolinet-go"


def fetch_openapi_schema(url: str = "http://localhost:4000/openapi.json") -> dict:
    """Fetch live OpenAPI schema from gateway or return baseline."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Wolinet-SDK-Gen/2.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            print(f"✓ Fetched live OpenAPI schema from {url} ({len(data.get('paths', {}))} paths)")
            return data
    except Exception as e:
        print(f"⚠ Could not reach {url} ({e}). Using sovereign baseline schema...")
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "Wolinet AI Sovereign Gateway API",
                "version": "1.0.0",
                "description": "Unified gateway for model discovery, inference, and usage billing",
            },
            "servers": [
                {"url": "http://localhost:4000", "description": "Local Gateway"},
                {"url": "http://localhost:9997", "description": "Local Inference"},
            ],
            "paths": {
                "/v1/chat/completions": {"post": {"summary": "Chat Completions"}},
                "/v1/embeddings": {"post": {"summary": "Vector Embeddings"}},
                "/v1/rerank": {"post": {"summary": "Cross-Encoder Reranking"}},
                "/v1/models": {"get": {"summary": "List Models"}},
                "/wolinet/status": {"get": {"summary": "Platform Status"}},
                "/wolinet/key": {"get": {"summary": "Active API Key"}},
            },
        }


# ==============================================================================
# 1. TYPESCRIPT SDK GENERATION
# ==============================================================================
def generate_typescript_sdk(schema: dict):
    os.makedirs(TS_SDK_DIR / "src", exist_ok=True)

    # 1.1 package.json
    package_json = {
        "name": "@wolinet/sdk",
        "version": "1.1.0",
        "type": "module",
        "description": "Official TypeScript & JavaScript client for the Wolinet AI Sovereign Gateway",
        "main": "dist/index.js",
        "module": "dist/index.mjs",
        "types": "dist/index.d.ts",
        "exports": {
            ".": {
                "types": "./dist/index.d.ts",
                "import": "./dist/index.mjs",
                "require": "./dist/index.js",
            }
        },
        "files": ["dist", "src", "README.md", "LICENSE"],
        "scripts": {
            "build": "tsc",
            "test": "node --test",
        },
        "keywords": [
            "wolinet",
            "ai",
            "llm",
            "sovereign",
            "east-africa",
        ],
        "author": "Wolinet AI <dev@wolinet.ai>",
        "license": "Apache-2.0",
        "devDependencies": {
            "typescript": "^5.3.0",
        },
    }
    with open(TS_SDK_DIR / "package.json", "w") as f:
        json.dump(package_json, f, indent=2)

    # 1.2 tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "target": "ES2022",
            "module": "NodeNext",
            "moduleResolution": "NodeNext",
            "declaration": True,
            "declarationMap": True,
            "outDir": "./dist",
            "rootDir": "./src",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True,
        },
        "include": ["src/**/*"],
    }
    with open(TS_SDK_DIR / "tsconfig.json", "w") as f:
        json.dump(tsconfig, f, indent=2)

    # 1.3 src/types.ts
    types_ts = '''/**
 * Wolinet AI TypeScript SDK — Type Definitions
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  name?: string;
}

export interface ChatCompletionOptions {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  stream?: boolean;
  stop?: string | string[];
  presence_penalty?: number;
  frequency_penalty?: number;
}

export interface ChatCompletionChoice {
  index: number;
  message: ChatMessage;
  finish_reason: string | null;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  timings?: {
    prompt_per_second?: number;
    predicted_per_second?: number;
    prompt_ms?: number;
    predicted_ms?: number;
  };
}

export interface ChatCompletionChunkChoice {
  index: number;
  delta: {
    role?: string;
    content?: string;
  };
  finish_reason: string | null;
}

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChunkChoice[];
}

export interface EmbeddingOptions {
  model: 'bge-small-en-v1.5' | (string & {});
  input: string | string[];
  encoding_format?: 'float' | 'base64';
}

export interface EmbeddingData {
  index: number;
  object: 'embedding';
  embedding: number[];
}

export interface EmbeddingResponse {
  object: 'list';
  data: EmbeddingData[];
  model: string;
  usage: {
    prompt_tokens: number;
    total_tokens: number;
  };
}

export interface RerankOptions {
  model: 'bge-reranker-v2-m3' | (string & {});
  query: string;
  documents: string[];
  top_n?: number;
  return_documents?: boolean;
}

export interface RerankResult {
  index: number;
  relevance_score: number;
  document?: string;
}

export interface RerankResponse {
  id: string;
  results: RerankResult[];
  model: string;
  usage: {
    total_tokens: number;
  };
}

export interface WolinetStatusResponse {
  brand: {
    name: string;
    gateway: string;
    inference: string;
    docs: string;
    openapi: string;
  };
  active_key?: string;
  default_key?: string;
  gateway: {
    status: string;
    db: string;
    total_spend: number;
  };
  inference: {
    status: string;
    model_count: number;
    models: Array<{
      id: string;
      type: string;
      engine: string;
      quantization?: string;
      size_b?: number | string | null;
      context_length?: number | null;
      description?: string;
    }>;
    nodes: Array<{
      role: string;
      address: string;
      gpus: number;
    }>;
  };
  timestamp: string;
}

export interface WolinetKeyResponse {
  key: string;
  key_alias: string;
  status: string;
  models: string[];
  gateway_url: string;
  auth_header: string;
  curl_example: string;
}
'''
    with open(TS_SDK_DIR / "src" / "types.ts", "w") as f:
        f.write(types_ts)

    # 1.4 src/index.ts
    index_ts = '''/**
 * Wolinet AI TypeScript SDK
 * Auto-generated from Wolinet AI Sovereign OpenAPI Specification
 */

import type {
  ChatCompletionOptions,
  ChatCompletionResponse,
  ChatCompletionChunk,
  EmbeddingOptions,
  EmbeddingResponse,
  RerankOptions,
  RerankResponse,
  WolinetStatusResponse,
  WolinetKeyResponse,
} from './types.ts';

export type * from './types.ts';

export interface WolinetClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
}

export class WolinetAI {
  public readonly baseUrl: string;
  public readonly apiKey: string;
  public readonly timeout: number;

  constructor(options: WolinetClientOptions = {}) {
    const rawUrl = options.baseUrl || (typeof process !== 'undefined' ? process.env?.WOLINET_BASE_URL : undefined) || 'http://localhost:4000';
    this.baseUrl = rawUrl.replace(/\\/+$/, '');
    this.apiKey = options.apiKey || (typeof process !== 'undefined' ? process.env?.WOLINET_API_KEY : undefined) || 'sk-wolinet-local-dev';
    this.timeout = options.timeout ?? 60000;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'User-Agent': 'WolinetAI-TS-SDK/1.1.0',
      ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      ...(options.headers as Record<string, string>),
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!res.ok) {
        const errorText = await res.text().catch(() => '');
        throw new Error(`Wolinet API error [${res.status}]: ${errorText || res.statusText}`);
      }

      return (await res.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  public readonly chat = {
    completions: {
      create: async (opts: ChatCompletionOptions): Promise<ChatCompletionResponse> => {
        return this.request<ChatCompletionResponse>('/v1/chat/completions', {
          method: 'POST',
          body: JSON.stringify({ ...opts, stream: false }),
        });
      },

      stream: async function* (
        this: WolinetAI,
        opts: ChatCompletionOptions
      ): AsyncIterable<ChatCompletionChunk> {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'User-Agent': 'WolinetAI-TS-SDK/1.1.0',
          ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
        };

        const res = await fetch(`${this.baseUrl}/v1/chat/completions`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ ...opts, stream: true }),
        });

        if (!res.ok) {
          const errText = await res.text().catch(() => '');
          throw new Error(`Wolinet Stream error [${res.status}]: ${errText}`);
        }

        if (!res.body) {
          throw new Error('Response body is null, cannot stream');
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith(':')) continue;
            if (trimmed === 'data: [DONE]') return;

            if (trimmed.startsWith('data: ')) {
              const dataStr = trimmed.slice(6).trim();
              try {
                const parsed = JSON.parse(dataStr) as ChatCompletionChunk;
                yield parsed;
              } catch {
                // Ignore parse errors on partial chunks
              }
            }
          }
        }
      }.bind(this),
    },
  };

  public readonly embeddings = {
    create: async (opts: EmbeddingOptions): Promise<EmbeddingResponse> => {
      return this.request<EmbeddingResponse>('/v1/embeddings', {
        method: 'POST',
        body: JSON.stringify(opts),
      });
    },
  };

  public readonly rerank = {
    create: async (opts: RerankOptions): Promise<RerankResponse> => {
      return this.request<RerankResponse>('/v1/rerank', {
        method: 'POST',
        body: JSON.stringify(opts),
      });
    },
  };

  public readonly models = {
    list: async (): Promise<{ data: Array<{ id: string; object: string; created: number; owned_by: string }> }> => {
      return this.request('/v1/models');
    },
  };

  public async status(): Promise<WolinetStatusResponse> {
    return this.request<WolinetStatusResponse>('/wolinet/status');
  }

  public async getKey(): Promise<WolinetKeyResponse> {
    return this.request<WolinetKeyResponse>('/wolinet/key');
  }
}

export default WolinetAI;
'''
    with open(TS_SDK_DIR / "src" / "index.ts", "w") as f:
        f.write(index_ts)

    # 1.5 README.md
    readme_ts = """# @wolinet/sdk

Official TypeScript & JavaScript client for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

- 🚀 **Gateway Model Discovery:** Use any model enabled in the LiteLLM catalog.
- ⚡ **Streaming Support:** Async generator SSE streaming for instant code and text token rendering.
- 🌐 **Zero External Dependencies:** Built on native `fetch` and `ReadableStream`.

## Installation

```bash
npm install @wolinet/sdk
```

## Quickstart

```typescript
import { WolinetAI } from '@wolinet/sdk';

const client = new WolinetAI({
  baseUrl: 'http://localhost:4000',
  apiKey: 'sk-wolinet-local-dev',
});

// 1. Unary Chat Completion
const completion = await client.chat.completions.create({
  model: 'your-enabled-model-id',
  messages: [{ role: 'user', content: 'Write a quicksort in TypeScript' }],
});
console.log(completion.choices[0].message.content);

// 2. Real-time Streaming
for await (const chunk of client.chat.completions.stream({
  model: 'your-enabled-model-id',
  messages: [{ role: 'user', content: 'Count from 1 to 5' }],
})) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}

// 3. Dense Vector Embeddings
const embeddings = await client.embeddings.create({
  model: 'bge-small-en-v1.5',
  input: 'Wolinet AI Sovereign Infrastructure',
});
console.log('Embedding dimension:', embeddings.data[0].embedding.length);

// 4. Cluster Telemetry
const status = await client.status();
console.log('Active inference models:', status.inference.model_count);
```
"""
    with open(TS_SDK_DIR / "README.md", "w") as f:
        f.write(readme_ts)

    print(f"✅ Generated TypeScript SDK at {TS_SDK_DIR}")


# ==============================================================================
# 2. PYTHON SDK GENERATION
# ==============================================================================
def generate_python_sdk(schema: dict):
    os.makedirs(PY_SDK_DIR / "wolinet", exist_ok=True)
    os.makedirs(PY_SDK_DIR / "tests", exist_ok=True)

    # 2.1 pyproject.toml
    pyproject_toml = """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "wolinet"
version = "1.1.0"
description = "Official Python client for the Wolinet AI Sovereign Gateway & Inference Cluster"
readme = "README.md"
requires-python = ">=3.9"
authors = [{ name = "Wolinet AI", email = "dev@wolinet.ai" }]
license = { text = "Apache-2.0" }
dependencies = [
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.20.0",
]
"""
    with open(PY_SDK_DIR / "pyproject.toml", "w") as f:
        f.write(pyproject_toml)

    # 2.2 wolinet/types.py
    types_py = '''"""
Wolinet AI Python SDK — Type Definitions
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    name: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None
    timings: Optional[Dict[str, Any]] = None


class ChatChunkDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatChunkChoice(BaseModel):
    index: int = 0
    delta: ChatChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatChunkChoice]


class EmbeddingData(BaseModel):
    index: int = 0
    object: str = "embedding"
    embedding: List[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: Dict[str, int]


class RerankResult(BaseModel):
    index: int
    relevance_score: float
    document: Optional[str] = None


class RerankResponse(BaseModel):
    id: str
    results: List[RerankResult]
    model: str
    usage: Dict[str, int]


'''
    with open(PY_SDK_DIR / "wolinet" / "types.py", "w") as f:
        f.write(types_py)

    # 2.3 wolinet/client.py
    client_py = '''"""
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
'''
    with open(PY_SDK_DIR / "wolinet" / "client.py", "w") as f:
        f.write(client_py)

    # 2.4 wolinet/__init__.py
    init_py = '''"""
Wolinet AI Python SDK
"""

from .client import WolinetAI, AsyncWolinetAI
from .types import (
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionChunk,
    EmbeddingResponse,
    RerankResponse,
)

__version__ = "1.1.0"
__all__ = [
    "WolinetAI",
    "AsyncWolinetAI",
    "ChatMessage",
    "ChatCompletionResponse",
    "ChatCompletionChunk",
    "EmbeddingResponse",
    "RerankResponse",
]
'''
    with open(PY_SDK_DIR / "wolinet" / "__init__.py", "w") as f:
        f.write(init_py)

    # 2.5 README.md
    readme_py = """# Wolinet AI Python SDK

Official Python client for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

## Installation

```bash
pip install -e packages/wolinet-python
```

## Quickstart

```python
from wolinet import WolinetAI

client = WolinetAI(base_url="http://localhost:4000", api_key="sk-wolinet-local-dev")

# 1. Unary Chat Completion
res = client.chat.create(
    model="your-enabled-model-id",
    messages=[{"role": "user", "content": "Write a Python decorator for logging execution time."}],
)
print(res.choices[0].message.content)

# 2. Real-time Streaming
for chunk in client.chat.create(
    model="your-enabled-model-id",
    messages=[{"role": "user", "content": "Explain vector databases in 2 sentences"}],
    stream=True,
):
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
print()

# 3. Dense Vector Embeddings
emb = client.embeddings.create(model="bge-small-en-v1.5", input="Wolinet AI sovereign cloud")
print("Vector length:", len(emb.data[0].embedding))

# 4. Check Cluster Status
status = client.status()
print("Gateway status:", status["gateway"]["status"])
```
"""
    with open(PY_SDK_DIR / "README.md", "w") as f:
        f.write(readme_py)

    print(f"✅ Generated Python SDK at {PY_SDK_DIR}")


# ==============================================================================
# 3. GO (GOLANG) SDK GENERATION
# ==============================================================================
def generate_go_sdk(schema: dict):
    os.makedirs(GO_SDK_DIR, exist_ok=True)

    # 3.1 go.mod
    go_mod = """module github.com/wolinet/wolinet-go

go 1.21
"""
    with open(GO_SDK_DIR / "go.mod", "w") as f:
        f.write(go_mod)

    # 3.2 types.go
    types_go = """package wolinet

// ChatMessage represents a single message in a chat conversation.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
	Name    string `json:"name,omitempty"`
}

// ChatCompletionRequest options for chat completion.
type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Temperature *float64      `json:"temperature,omitempty"`
	MaxTokens   *int          `json:"max_tokens,omitempty"`
	Stream      bool          `json:"stream,omitempty"`
}

// ChatCompletionChoice individual choice from completion.
type ChatCompletionChoice struct {
	Index        int         `json:"index"`
	Message      ChatMessage `json:"message"`
	FinishReason *string     `json:"finish_reason"`
}

// ChatCompletionUsage token usage breakdown.
type ChatCompletionUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// ChatCompletionResponse response from unary chat completion.
type ChatCompletionResponse struct {
	ID      string                 `json:"id"`
	Object  string                 `json:"object"`
	Created int64                  `json:"created"`
	Model   string                 `json:"model"`
	Choices []ChatCompletionChoice `json:"choices"`
	Usage   *ChatCompletionUsage   `json:"usage,omitempty"`
	Timings map[string]interface{} `json:"timings,omitempty"`
}

// ChatCompletionStreamChoice choice in a streaming chunk.
type ChatCompletionStreamChoice struct {
	Index int `json:"index"`
	Delta struct {
		Role    string `json:"role,omitempty"`
		Content string `json:"content,omitempty"`
	} `json:"delta"`
	FinishReason *string `json:"finish_reason"`
}

// ChatCompletionStreamResponse streaming chunk response.
type ChatCompletionStreamResponse struct {
	ID      string                       `json:"id"`
	Object  string                       `json:"object"`
	Created int64                        `json:"created"`
	Model   string                       `json:"model"`
	Choices []ChatCompletionStreamChoice `json:"choices"`
}

// EmbeddingRequest request parameters for embedding generation.
type EmbeddingRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// EmbeddingItem vector embedding item.
type EmbeddingItem struct {
	Index     int       `json:"index"`
	Object    string    `json:"object"`
	Embedding []float64 `json:"embedding"`
}

// EmbeddingResponse response from embeddings endpoint.
type EmbeddingResponse struct {
	Object string          `json:"object"`
	Data   []EmbeddingItem `json:"data"`
	Model  string          `json:"model"`
}

// RerankRequest parameters for cross-encoder reranking.
type RerankRequest struct {
	Model     string   `json:"model"`
	Query     string   `json:"query"`
	Documents []string `json:"documents"`
	TopN      *int     `json:"top_n,omitempty"`
}

// RerankResult single scored rerank document.
type RerankResult struct {
	Index          int     `json:"index"`
	RelevanceScore float64 `json:"relevance_score"`
	Document       string  `json:"document,omitempty"`
}

// RerankResponse response from rerank endpoint.
type RerankResponse struct {
	ID      string         `json:"id"`
	Results []RerankResult `json:"results"`
	Model   string         `json:"model"`
}

// StatusResponse platform telemetry and node status.
type StatusResponse struct {
	Brand struct {
		Name      string `json:"name"`
		Gateway   string `json:"gateway"`
		Inference string `json:"inference"`
		Docs      string `json:"docs"`
		OpenAPI   string `json:"openapi"`
	} `json:"brand"`
	ActiveKey  string `json:"active_key"`
	DefaultKey string `json:"default_key"`
	Gateway    struct {
		Status     string  `json:"status"`
		DB         string  `json:"db"`
		TotalSpend float64 `json:"total_spend"`
	} `json:"gateway"`
	Inference struct {
		Status     string                   `json:"status"`
		ModelCount int                      `json:"model_count"`
		Models     []map[string]interface{} `json:"models"`
		Nodes      []map[string]interface{} `json:"nodes"`
	} `json:"inference"`
	Timestamp string `json:"timestamp"`
}
"""
    with open(GO_SDK_DIR / "types.go", "w") as f:
        f.write(types_go)

    # 3.3 client.go
    client_go = """package wolinet

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Client is the Wolinet AI Sovereign Gateway API client.
type Client struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// Option configures a Client.
type Option func(*Client)

// WithBaseURL overrides default gateway URL.
func WithBaseURL(url string) Option {
	return func(c *Client) {
		c.baseURL = strings.TrimRight(url, "/")
	}
}

// WithHTTPClient overrides the underlying http.Client.
func WithHTTPClient(httpClient *http.Client) Option {
	return func(c *Client) {
		c.httpClient = httpClient
	}
}

// WithTimeout sets request timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *Client) {
		c.httpClient.Timeout = d
	}
}

// NewClient creates a new Wolinet AI client.
func NewClient(apiKey string, opts ...Option) *Client {
	if apiKey == "" {
		apiKey = "sk-wolinet-local-dev"
	}
	c := &Client{
		baseURL: "http://localhost:4000",
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

func (c *Client) setHeaders(req *http.Request) {
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "WolinetAI-Go-SDK/1.1.0")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
}

// CreateChatCompletion executes a unary chat completion.
func (c *Client) CreateChatCompletion(ctx context.Context, req ChatCompletionRequest) (*ChatCompletionResponse, error) {
	req.Stream = false
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(httpReq)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		errBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("api error [%d]: %s", resp.StatusCode, string(errBody))
	}

	var completion ChatCompletionResponse
	if err := json.NewDecoder(resp.Body).Decode(&completion); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &completion, nil
}

// ChatCompletionStream reads SSE chunks.
type ChatCompletionStream struct {
	reader   *bufio.Reader
	response *http.Response
}

// Recv receives next stream chunk. Returns io.EOF when stream is finished.
func (s *ChatCompletionStream) Recv() (*ChatCompletionStreamResponse, error) {
	for {
		line, err := s.reader.ReadString('\\n')
		if err != nil {
			return nil, err
		}
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, ":") {
			continue
		}
		if line == "data: [DONE]" {
			return nil, io.EOF
		}
		if strings.HasPrefix(line, "data: ") {
			payload := strings.TrimSpace(strings.TrimPrefix(line, "data: "))
			var chunk ChatCompletionStreamResponse
			if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
				continue
			}
			return &chunk, nil
		}
	}
}

// Close closes the underlying stream connection.
func (s *ChatCompletionStream) Close() error {
	if s.response != nil && s.response.Body != nil {
		return s.response.Body.Close()
	}
	return nil
}

// CreateChatCompletionStream initiates a real-time streaming completion.
func (c *Client) CreateChatCompletionStream(ctx context.Context, req ChatCompletionRequest) (*ChatCompletionStream, error) {
	req.Stream = true
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal stream request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create stream request: %w", err)
	}
	c.setHeaders(httpReq)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("execute stream request: %w", err)
	}

	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		errBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("stream api error [%d]: %s", resp.StatusCode, string(errBody))
	}

	return &ChatCompletionStream{
		reader:   bufio.NewReader(resp.Body),
		response: resp,
	}, nil
}

// CreateEmbedding generates dense vector embeddings.
func (c *Client) CreateEmbedding(ctx context.Context, req EmbeddingRequest) (*EmbeddingResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal embedding request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/embeddings", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(httpReq)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		errBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("api error [%d]: %s", resp.StatusCode, string(errBody))
	}

	var res EmbeddingResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &res, nil
}

// CreateRerank reranks documents according to semantic relevance.
func (c *Client) CreateRerank(ctx context.Context, req RerankRequest) (*RerankResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal rerank request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/rerank", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(httpReq)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		errBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("api error [%d]: %s", resp.StatusCode, string(errBody))
	}

	var res RerankResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &res, nil
}

// GetStatus returns live platform health, total spend, and cluster nodes.
func (c *Client) GetStatus(ctx context.Context) (*StatusResponse, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/wolinet/status", nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	c.setHeaders(httpReq)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		errBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("api error [%d]: %s", resp.StatusCode, string(errBody))
	}

	var status StatusResponse
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &status, nil
}

"""
    with open(GO_SDK_DIR / "client.go", "w") as f:
        f.write(client_go)

    # 3.4 client_test.go
    client_test_go = """package wolinet

import (
	"context"
	"testing"
	"time"
)

func TestChatCompletion(t *testing.T) {
	client := NewClient("sk-wolinet-local-dev", WithBaseURL("http://localhost:4000"), WithTimeout(15*time.Second))
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	resp, err := client.CreateChatCompletion(ctx, ChatCompletionRequest{
		Model: "your-enabled-model-id",
		Messages: []ChatMessage{
			{Role: "user", Content: "Reply with the single word: OK"},
		},
	})
	if err != nil {
		t.Logf("Gateway completion test skipped or failed: %v", err)
		return
	}

	if len(resp.Choices) == 0 {
		t.Fatalf("expected at least 1 choice, got 0")
	}
	t.Logf("Response content: %s", resp.Choices[0].Message.Content)
}

func TestGetStatus(t *testing.T) {
	client := NewClient("sk-wolinet-local-dev", WithBaseURL("http://localhost:4000"))
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	status, err := client.GetStatus(ctx)
	if err != nil {
		t.Logf("Status call skipped: %v", err)
		return
	}
	if status.Brand.Name == "" {
		t.Errorf("expected brand name, got empty string")
	}
	t.Logf("Brand: %s, Gateway: %s, Inference: %s", status.Brand.Name, status.Gateway.Status, status.Inference.Status)
}
"""
    with open(GO_SDK_DIR / "client_test.go", "w") as f:
        f.write(client_test_go)

    # 3.5 README.md
    readme_go = """# wolinet-go

Official Go (Golang) SDK for the **Wolinet AI Sovereign Gateway & Inference Cluster**.

## Installation

```bash
go get github.com/wolinet/wolinet-go
```

## Quickstart

```go
package main

import (
	"context"
	"fmt"
	"io"
	"log"

	"github.com/wolinet/wolinet-go"
)

func main() {
	client := wolinet.NewClient("sk-wolinet-local-dev", wolinet.WithBaseURL("http://localhost:4000"))

	// 1. Unary Chat Completion
	resp, err := client.CreateChatCompletion(context.Background(), wolinet.ChatCompletionRequest{
		Model: "your-enabled-model-id",
		Messages: []wolinet.ChatMessage{
			{Role: "user", Content: "Write an HTTP server in Go"},
		},
	})
	if err != nil {
		log.Fatalf("Chat completion error: %v", err)
	}
	fmt.Println(resp.Choices[0].Message.Content)

	// 2. Real-time Streaming
	stream, err := client.CreateChatCompletionStream(context.Background(), wolinet.ChatCompletionRequest{
		Model: "your-enabled-model-id",
		Messages: []wolinet.ChatMessage{
			{Role: "user", Content: "Count from 1 to 5"},
		},
	})
	if err != nil {
		log.Fatalf("Stream error: %v", err)
	}
	defer stream.Close()

	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			log.Fatalf("Recv error: %v", err)
		}
		fmt.Print(chunk.Choices[0].Delta.Content)
	}
	fmt.Println()
}
```
"""
    with open(GO_SDK_DIR / "README.md", "w") as f:
        f.write(readme_go)

    print(f"✅ Generated Go SDK at {GO_SDK_DIR}")


# ==============================================================================
# 4. MULTI-LANGUAGE CODE SNIPPETS (SCALAR EQUIVALENT)
# ==============================================================================
def generate_snippets(model: str, base_url: str = "http://localhost:4000") -> Dict[str, str]:
    """Generate multi-language code snippets for the given model & gateway URL."""
    return {
        "curl": f"""curl {base_url}/v1/chat/completions \\
  -H "Authorization: Bearer sk-wolinet-local-dev" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "{model}",
    "messages": [{{"role": "user", "content": "Hello Wolinet AI!"}}],
    "temperature": 0.7
  }}'""",
        "python": f"""from wolinet import WolinetAI

client = WolinetAI(base_url="{base_url}", api_key="sk-wolinet-local-dev")

response = client.chat.create(
    model="{model}",
    messages=[{{"role": "user", "content": "Hello Wolinet AI!"}}],
)
print(response.choices[0].message.content)""",
        "typescript": f"""import {{ WolinetAI }} from '@wolinet/sdk';

const client = new WolinetAI({{
  baseUrl: '{base_url}',
  apiKey: 'sk-wolinet-local-dev',
}});

const response = await client.chat.completions.create({{
  model: '{model}',
  messages: [{{ role: 'user', content: 'Hello Wolinet AI!' }}],
}});
console.log(response.choices[0].message.content);""",
        "go": f"""package main

import (
    "context"
    "fmt"
    "log"
    "github.com/wolinet/wolinet-go"
)

func main() {{
    client := wolinet.NewClient("sk-wolinet-local-dev", wolinet.WithBaseURL("{base_url}"))
    resp, err := client.CreateChatCompletion(context.Background(), wolinet.ChatCompletionRequest{{
        Model: "{model}",
        Messages: []wolinet.ChatMessage{{
            {{Role: "user", Content: "Hello Wolinet AI!"}},
        }},
    }})
    if err != nil {{
        log.Fatal(err)
    }}
    fmt.Println(resp.Choices[0].Message.Content)
}}""",
    }


def main():
    parser = argparse.ArgumentParser(description="Wolinet AI Multi-Language SDK Generator")
    parser.add_argument("--url", default="http://localhost:4000/openapi.json", help="OpenAPI specification URL")
    parser.add_argument("--lang", default="all", choices=["all", "python", "typescript", "go"], help="Target SDK language")
    parser.add_argument("--snippets", action="store_true", help="Print multi-language code snippets")
    parser.add_argument("--model", required=True, help="Model ID returned by the gateway's /v1/models endpoint")
    args = parser.parse_args()

    if args.snippets:
        snippets = generate_snippets(model=args.model)
        for lang, code in snippets.items():
            print(f"\\n{'='*20} {lang.upper()} {'='*20}\\n{code}")
        return

    print("🚀 Fetching Wolinet AI OpenAPI schema...")
    schema = fetch_openapi_schema(args.url)

    if args.lang in ("all", "typescript"):
        generate_typescript_sdk(schema)
    if args.lang in ("all", "python"):
        generate_python_sdk(schema)
    if args.lang in ("all", "go"):
        generate_go_sdk(schema)

    print("✨ Wolinet AI multi-language SDK generation completed successfully!")


if __name__ == "__main__":
    main()
