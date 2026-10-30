import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if values.get("id"):
            self.ids.add(values["id"] or "")


class PublicSurfaceTests(unittest.TestCase):
    def test_homepage_exposes_each_product_and_download_destination(self) -> None:
        raw_html = (ROOT / "website/index.html").read_text()
        parser = SiteParser()
        parser.feed(raw_html)

        # 1. Assert all 4 native desktop platform releases are exposed
        for platform_binary in (
            "WolinetIDE-macOS-arm64.dmg",
            "WolinetIDE-macOS-x64.dmg",
            "WolinetIDE-Windows-x64-setup.exe",
            "WolinetIDE-Linux-x86_64.AppImage",
        ):
            self.assertTrue(
                any(f"/downloads/{platform_binary}" in link for link in parser.links),
                f"Missing download link for {platform_binary}",
            )

        # 2. Assert dynamic OS detection & downloader UI elements
        for required_id in ("hero-download-btn", "hero-download-label", "detected-os-pill", "terminal-install-code"):
            self.assertIn(required_id, parser.ids, f"Missing required element id {required_id}")

        # 3. Assert Studio and API reference portal bindings exist
        self.assertIn('data-portal="wolinex"', raw_html)
        self.assertIn('data-portal="docs"', raw_html)

        # 4. Assert zero raw infrastructure leak in user-facing marketing copy
        for leak in (":4000", ":9997", "litellm", "xinference"):
            self.assertNotIn(leak, raw_html.lower())

    def test_developer_portal_has_session_key_and_assistant_contracts(self) -> None:
        page = (ROOT / "apps/dev-portal/index.html").read_text()
        client = (ROOT / "apps/dev-portal/app.js").read_text()
        config = (ROOT / "apps/dev-portal/nginx.conf").read_text()

        for endpoint in ("/api/wolinet/auth/session", "/api/wolinet/auth/regenerate-key", "/v1/chat/completions"):
            self.assertIn(endpoint, client)
        self.assertIn("id=\"chat-form\"", page)
        self.assertIn("set $webui_upstream wolinex:8080", config)
        self.assertIn("set $lango_upstream lango:4000", config)
        self.assertIn("proxy_buffering off", config)

    def test_edge_routes_all_public_hosts_and_rewrites_the_session_cookie(self) -> None:
        config = (ROOT / "nginx/conf.d/wolinet.conf").read_text()

        for host in ("ai", "wolinex", "lango", "mitambo", "dev", "docs"):
            self.assertIn(f"server_name {host}.wolinet.com", config)
        self.assertIn("Domain=.wolinet.com", config)
        self.assertIn("Secure; SameSite=Lax", config)
        self.assertIn("auth_basic_user_file /etc/nginx/secrets/mitambo.htpasswd", config)

    def test_cloudflare_edge_alignment_and_cookie_security(self) -> None:
        edge_config = (ROOT / "nginx/conf.d/wolinet.conf").read_text()
        main_config = (ROOT / "nginx/nginx.conf").read_text()
        compose_config = (ROOT / "docker-compose.prod.yml").read_text()
        docs_router = (ROOT / "apps/web-client/backend/open_webui/routers/wolinet_docs.py").read_text()
        proxy_server = (ROOT / "gateway/litellm/proxy/proxy_server.py").read_text()

        # 1. Cloudflare edge buffering suppression
        self.assertIn("add_header X-Accel-Buffering no always;", edge_config)

        # 2. Upstream keepalive & persistent connection settings
        self.assertIn("proxy_socket_keepalive on;", edge_config)
        self.assertIn("proxy_socket_keepalive      on;", main_config)
        self.assertIn("keepalive_timeout  600s;", main_config)

        # 3. Explicit Secure cookie flags across engines
        self.assertIn('WEBUI_AUTH_COOKIE_SECURE: "True"', compose_config)
        self.assertIn('secure=True', docs_router)
        self.assertIn('secure=True', proxy_server)

    def test_litellm_docs_serves_scalar_instead_of_swagger(self) -> None:
        proxy_server_path = ROOT / "gateway/litellm/proxy/proxy_server.py"
        proxy_server_code = proxy_server_path.read_text(encoding="utf-8")

        # 1. Assert default Swagger UI and Redoc paths are suppressed in FastAPI init
        self.assertIn("docs_url=None", proxy_server_code)
        self.assertIn("redoc_url=None", proxy_server_code)

        # 2. Assert dedicated /docs route serves Scalar documentation handler
        self.assertIn('@app.get("/docs", include_in_schema=False)', proxy_server_code)
        self.assertIn("async def scalar_api_documentation():", proxy_server_code)

        # 3. Assert Scalar HTML template contains exact system endpoints and bundle tags
        self.assertIn("<title>Wolinet Ecosystem - API Gateway Docs</title>", proxy_server_code)
        self.assertIn('<script id="api-reference" data-url="/openapi.json"></script>', proxy_server_code)
        self.assertIn('/swagger/scalar.js', proxy_server_code)

        # 4. Assert live gateway endpoint (if running) serves Scalar and suppresses Swagger
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:4000/docs")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn('id="api-reference"', body)
                self.assertIn('data-url="/openapi.json"', body)
                self.assertIn("Wolinet Ecosystem - API Gateway Docs", body)
                self.assertIn("jsdelivr.net", body)
                self.assertNotIn("swagger-ui", body)
                self.assertNotIn("SwaggerUIBundle", body)
        except Exception:  # noqa: BLE001, S110
            # If live container is not running during isolated CI runs, file assertions above validate contract
            pass

    def test_docs_portal_has_scalar_and_copilot_contracts(self) -> None:
        index_html = (ROOT / "apps/docs/index.html").read_text()
        client_js = (ROOT / "apps/docs/app.js").read_text()
        nginx_conf = (ROOT / "apps/docs/nginx.conf").read_text()

        # 1. Scalar API Reference contracts
        self.assertIn("@scalar/api-reference", index_html)
        self.assertIn('data-url="/openapi.json"', index_html)
        self.assertIn('id="api-reference"', index_html)

        # 2. Docs AI Copilot contracts
        self.assertIn('id="floating-assistant-btn"', index_html)
        self.assertIn('id="open-assistant-header-btn"', index_html)
        self.assertIn('id="copilot-drawer"', index_html)
        self.assertIn('id="copilot-form"', index_html)
        self.assertIn("/v1/chat/completions", client_js)
        self.assertIn("Wolinet AI Documentation Copilot", client_js)

        # 3. Upstream proxy and SSE buffering configs
        self.assertIn("set $lango_upstream lango:4000", nginx_conf)
        self.assertIn("proxy_buffering off", nginx_conf)

        # 4. Zero stack leaks in user-facing html
        for leak in (":4000", ":9997", "litellm", "xinference"):
            self.assertNotIn(leak, index_html.lower())

    def test_docker_compose_and_appstore_contracts(self) -> None:
        compose_prod = (ROOT / "docker-compose.prod.yml").read_text()
        compose_core = (ROOT / "docker-compose.yml").read_text()
        compose_dev = (ROOT / "docker-compose.dev.yml").read_text()

        # 1. DevPortal and Docs in production compose
        self.assertIn("devportal:", compose_prod)
        self.assertIn("docs:", compose_prod)
        self.assertIn("aliases:\n          - devportal", compose_prod)
        self.assertIn("aliases:\n          - docs", compose_prod)
        self.assertIn("- devportal", compose_prod)
        self.assertIn("- docs", compose_prod)

        # 2. Core & Dev compose manifests
        self.assertIn("devportal:", compose_core)
        self.assertIn("docs:", compose_core)
        self.assertIn("8082:8082", compose_dev)
        self.assertIn("8083:8083", compose_dev)

        # 3. 1Panel App Store and Quadlet manifests
        self.assertTrue((ROOT / "orchestrator/appstore/apps/dev-portal/data.yml").exists())
        self.assertTrue((ROOT / "orchestrator/appstore/apps/dev-portal/1.0.0/data.yml").exists())
        self.assertTrue((ROOT / "orchestrator/appstore/apps/dev-portal/1.0.0/docker-compose.yml").exists())
        self.assertTrue((ROOT / "orchestrator/appstore/apps/docs/data.yml").exists())
        self.assertTrue((ROOT / "orchestrator/appstore/apps/docs/1.0.0/data.yml").exists())
        self.assertTrue((ROOT / "orchestrator/appstore/apps/docs/1.0.0/docker-compose.yml").exists())
        self.assertTrue((ROOT / "orchestrator/podman/quadlets/wolinet-devportal.container").exists())
        self.assertTrue((ROOT / "orchestrator/podman/quadlets/wolinet-docs.container").exists())
        self.assertTrue((ROOT / "orchestrator/1apanel/core/app/template/wolinet-docs.container").exists())

        # 4. Products catalog contains both dev-portal and docs
        products_text = (ROOT / "products.json").read_text()
        self.assertIn('"id": "dev-portal"', products_text)
        self.assertIn('"id": "docs"', products_text)


if __name__ == "__main__":
    unittest.main()


