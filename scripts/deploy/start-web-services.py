#!/usr/bin/env python3
"""
Wolinet AI — Local Web Portals Service Daemon
=============================================
Runs dedicated HTTP servers for each distinct service:
  1. Port 3000: Wolinet AI Home & Marketing Website (apps/website/)
  2. Port 8082: Developer Portal & Studio (apps/dev-portal/)
     - Proxies /v1/ to Lango Gateway (port 4000)
     - Proxies /docs to Gateway API Docs (port 4000/docs)
     - Proxies /api/wolinet/ to WolinEx AI Studio (port 8080)
"""

import os
import sys
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WEBSITE_DIR = BASE_DIR / "apps" / "website"
DEVPORTAL_DIR = BASE_DIR / "apps" / "dev-portal"
DOCS_DIR = BASE_DIR / "apps" / "docs"

LANGO_UPSTREAM = os.getenv("LANGO_UPSTREAM", "http://127.0.0.1:4000")
WOLINEX_UPSTREAM = os.getenv("WOLINEX_UPSTREAM", "http://127.0.0.1:8080")


class BaseProxyHandler(SimpleHTTPRequestHandler):
    """Base HTTP handler with upstream reverse-proxy capabilities."""

    def _proxy(self, target_url, method="GET"):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(target_url, data=body, method=method)
        for key, val in self.headers.items():
            if key.lower() not in ("host", "content-length"):
                req.add_header(key, val)

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "content-encoding"):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ("transfer-encoding", "content-encoding"):
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"Proxy error: {e}")

    def do_HEAD(self):
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            return
        return super().do_HEAD()

    def log_message(self, format, *args):
        if os.getenv("DEBUG"):
            super().log_message(format, *args)


class WebsiteHandler(BaseProxyHandler):
    """Handler for Wolinet Home / Marketing Website (Port 3000)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEBSITE_DIR), **kwargs)

    def do_GET(self):
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path)

        if self.path.startswith("/docs"):
            return self._proxy(LANGO_UPSTREAM + self.path)

        # Single page application / static fallback
        requested = WEBSITE_DIR / self.path.lstrip("/").split("?")[0]
        if not requested.exists() and not self.path.startswith("/assets"):
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path, method="POST")

        self.send_error(404, "Not Found")


class DevPortalHandler(BaseProxyHandler):
    """Handler for Wolinet Developer Portal & Studio (Port 8082)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEVPORTAL_DIR), **kwargs)

    def do_GET(self):
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        if self.path.startswith("/docs"):
            return self._proxy(LANGO_UPSTREAM + self.path)

        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path)

        if self.path.startswith("/api/wolinet/"):
            sub_path = self.path.replace("/api/wolinet", "/api/v1")
            return self._proxy(WOLINEX_UPSTREAM + sub_path)

        # Fallback to index.html for virtual routes
        requested = DEVPORTAL_DIR / self.path.lstrip("/").split("?")[0]
        if not requested.exists() and "." not in self.path:
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path, method="POST")

        if self.path.startswith("/api/wolinet/"):
            sub_path = self.path.replace("/api/wolinet", "/api/v1")
            return self._proxy(WOLINEX_UPSTREAM + sub_path, method="POST")

        self.send_error(404, "Not Found")


class DocsHandler(BaseProxyHandler):
    """Handler for Wolinet Scalar API Documentation & Copilot (Port 8083)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def do_GET(self):
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        if self.path.startswith("/openapi.json"):
            return self._proxy(LANGO_UPSTREAM + "/openapi.json")

        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path)

        if self.path.startswith("/api/wolinet/"):
            sub_path = self.path.replace("/api/wolinet", "/api/v1")
            return self._proxy(WOLINEX_UPSTREAM + sub_path)

        # Fallback to index.html for virtual routes
        requested = DOCS_DIR / self.path.lstrip("/").split("?")[0]
        if not requested.exists() and "." not in self.path:
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            return self._proxy(LANGO_UPSTREAM + self.path, method="POST")

        if self.path.startswith("/api/wolinet/"):
            sub_path = self.path.replace("/api/wolinet", "/api/v1")
            return self._proxy(WOLINEX_UPSTREAM + sub_path, method="POST")

        self.send_error(404, "Not Found")


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_server(port, handler_class, name):
    server = ReusableHTTPServer(("0.0.0.0", port), handler_class)
    print(f"[Wolinet Web Services] {name} listening on http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except Exception as e:
        print(f"[Wolinet Web Services] {name} stopped: {e}")


def main():
    print("============================================================")
    print("Wolinet AI — Dedicated Web Services Engine")
    print("============================================================")
    print(f" - Home / Marketing Website: http://localhost:3000")
    print(f" - WolinEx AI Studio:        http://localhost:8080")
    print(f" - Developer Portal Studio:  http://localhost:8082")
    print(f" - Scalar API Documentation: http://localhost:8083")
    print(f" - API Gateway Raw Specs:    http://localhost:4000/docs")
    print("============================================================")

    t1 = threading.Thread(target=run_server, args=(3000, WebsiteHandler, "Home Website"), daemon=True)
    t2 = threading.Thread(target=run_server, args=(8082, DevPortalHandler, "Developer Portal"), daemon=True)
    t3 = threading.Thread(target=run_server, args=(8083, DocsHandler, "Docs Studio"), daemon=True)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()


if __name__ == "__main__":
    main()
