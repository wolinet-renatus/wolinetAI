#!/usr/bin/env python3
"""
Wolinet AI — Mock Gateway Server (Phase 3)
A lightweight, zero-dependency mock server implementing the Wolinet AI OpenAPI
specification for local frontend development, testing, and CI pipelines without GPUs.

Features:
- OpenAI-compatible /v1/chat/completions (streaming SSE + non-streaming)
- /v1/models endpoint listing local sovereign models (wolinex-coder, etc.)
- /wolinet/status live health aggregator endpoint
- Embedded Scalar API Reference pointing to mock endpoints
- Full CORS support for dashboard and web-client testing
"""

import argparse
import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

MOCK_MODELS = [
    {
        "id": "wolinex-coder",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "wolinet-ai",
        "type": "LLM",
        "size_b": 14,
        "context_length": 32768,
        "description": "Sovereign coding assistant fine-tuned on Qwen2.5-Coder-14B",
    },
    {
        "id": "qwen2.5-omni",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "wolinet-ai",
        "type": "audio",
        "size_b": 7,
        "context_length": 16384,
        "description": "Multimodal voice & omni perception model",
    },
    {
        "id": "FLUX.1-Kontext-dev",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "wolinet-ai",
        "type": "image",
        "size_b": 12,
        "context_length": 4096,
        "description": "Sovereign high-fidelity text-to-image synthesis",
    },
    {
        "id": "bge-m3",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "wolinet-ai",
        "type": "embedding",
        "size_b": 0.5,
        "context_length": 8192,
        "description": "Multi-lingual semantic embedding engine",
    },
    {
        "id": "bge-reranker-large",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "wolinet-ai",
        "type": "rerank",
        "size_b": 0.5,
        "context_length": 8192,
        "description": "Cross-encoder semantic reranking engine",
    },
]

MOCK_STATUS = {
    "brand": {
        "name": "Wolinet AI",
        "gateway": "http://localhost:4010",
        "inference": "http://localhost:9997 (Mock)",
        "docs": "http://localhost:4010/docs",
        "openapi": "http://localhost:4010/openapi.json",
    },
    "gateway": {
        "status": "healthy (mock)",
        "db": "connected (mock)",
        "total_spend": 0.0,
    },
    "inference": {
        "status": "healthy",
        "model_count": len(MOCK_MODELS),
        "models": MOCK_MODELS,
        "nodes": [
            {
                "role": "Supervisor / Worker (Mock)",
                "address": "127.0.0.1:9997",
                "gpus": 1,
            }
        ],
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


class MockGatewayHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-litellm-api-key")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/health", "/health/readiness", "/health/liveliness"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "wolinet-mock-gateway"}')
            return

        if path == "/wolinet/status":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_data = dict(MOCK_STATUS)
            status_data["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
            return

        if path in ("/v1/models", "/models"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "object": "list",
                "data": MOCK_MODELS,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if path == "/openapi.json":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            schema = {
                "openapi": "3.1.0",
                "info": {
                    "title": "Wolinet AI — Mock Gateway API",
                    "version": "1.102.1-mock",
                    "description": "Mock server for Wolinet AI local testing and CI/CD pipelines.",
                },
                "servers": [{"url": "http://localhost:4010", "description": "Mock Gateway"}],
                "paths": {
                    "/v1/chat/completions": {
                        "post": {
                            "summary": "Chat Completions",
                            "description": "Generate chat completions with local sovereign models.",
                            "responses": {"200": {"description": "Successful response"}},
                        }
                    },
                    "/v1/models": {
                        "get": {
                            "summary": "List Models",
                            "responses": {"200": {"description": "List of available models"}},
                        }
                    },
                    "/wolinet/status": {
                        "get": {
                            "summary": "Platform Status",
                            "responses": {"200": {"description": "Live health aggregator"}},
                        }
                    },
                },
            }
            self.wfile.write(json.dumps(schema).encode("utf-8"))
            return

        if path in ("/swagger/scalar.js", "/scalar.js"):
            local_scalar = Path(__file__).resolve().parent.parent / "gateway" / "litellm" / "proxy" / "swagger" / "scalar.js"
            if local_scalar.exists():
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.end_headers()
                with open(local_scalar, "rb") as sf:
                    self.wfile.write(sf.read())
                return

        if path in ("/docs", "/reference"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
  <title>Wolinet AI — Mock Reference (Scalar)</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --scalar-color-accent: #7c6dfa;
      --scalar-background-1: #0d0d12;
      --scalar-background-2: #13131c;
      --scalar-border-color: rgba(124,109,250,0.18);
    }
    a[href*="scalar.com"], .gitbook-show, .upgradeButton, .agent-upgrade-modal {
      display: none !important;
    }
  </style>
</head>
<body>
  <script id="api-reference" data-url="/openapi.json"></script>
  <script>
    document.getElementById('api-reference').dataset.configuration = JSON.stringify({
      theme: 'deepSpace',
      darkMode: true,
      agent: { key: 'wolinet-mock-key' },
      externalUrls: {
        dashboardUrl: '/ui',
        registryUrl: '/',
        proxyUrl: '',
        apiBaseUrl: '/',
      },
      authentication: {
        preferredSecurityScheme: 'bearerAuth',
        apiKey: { token: 'sk-wolinet-mock-dev' }
      }
    });
  </script>
  <script src="/swagger/scalar.js"></script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
            return

        # 404 fallback
        self.send_response(404)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error": "Endpoint not found on mock gateway"}')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body = {}

        if path in ("/v1/chat/completions", "/chat/completions"):
            model = body.get("model", "wolinex-coder")
            stream = body.get("stream", False)
            messages = body.get("messages", [])
            last_msg = messages[-1].get("content", "") if messages else "Hello"

            if stream:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                mock_tokens = [
                    f"Hello from Wolinet AI Mock Gateway! You requested model `{model}`.",
                    f" Processing prompt: \"{last_msg[:30]}...\"",
                    " All systems operational: 100% sovereign local inference.",
                ]

                req_id = f"chatcmpl-mock-{int(time.time())}"
                for i, token in enumerate(mock_tokens):
                    chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": "stop" if i == len(mock_tokens) - 1 else None,
                            }
                        ],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(0.05)

                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return

            # Non-streaming response
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            resp = {
                "id": f"chatcmpl-mock-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Hello from Wolinet AI Mock Gateway! You queried model `{model}` with prompt: \"{last_msg}\". System healthy.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(last_msg.split()),
                    "completion_tokens": 28,
                    "total_tokens": len(last_msg.split()) + 28,
                },
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if path in ("/v1/embeddings", "/embeddings"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.01] * 128}],
                "model": body.get("model", "bge-m3"),
                "usage": {"prompt_tokens": 8, "total_tokens": 8},
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Fallback
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "mock_accepted", "message": "Mock POST endpoint received request"}')

    def log_message(self, format, *args):
        # Clean logging format
        sys.stderr.write(f"[Wolinet Mock] {self.address_string()} - {format % args}\n")


def run(port=4010):
    server_address = ("", port)
    httpd = HTTPServer(server_address, MockGatewayHandler)
    print(f"\n🚀 Wolinet AI Mock Gateway running at http://localhost:{port}")
    print(f"📖 Scalar API Reference: http://localhost:{port}/docs")
    print(f"📡 Status Telemetry:     http://localhost:{port}/wolinet/status")
    print(f"⚡ OpenAI Compatible:    http://localhost:{port}/v1/chat/completions\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Stopping Wolinet Mock Server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wolinet AI Mock Gateway")
    parser.add_argument("--port", type=int, default=4010, help="Port to listen on (default: 4010)")
    args = parser.parse_args()
    run(port=args.port)
