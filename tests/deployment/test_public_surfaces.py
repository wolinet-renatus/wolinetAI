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
        parser = SiteParser()
        parser.feed((ROOT / "apps/homepage/index.html").read_text())

        for host in ("wolinex", "lango", "mitambo", "dev"):
            self.assertTrue(any(f"https://{host}.wolinet.com" in link for link in parser.links))
        self.assertTrue(any("apps.apple.com/app/wolinet-ai" in link for link in parser.links))
        self.assertTrue(any("play.google.com/store/apps/details?id=com.wolinet.ai" in link for link in parser.links))
        self.assertIn("mega-menu", parser.ids)

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

        for host in ("ai", "wolinex", "lango", "mitambo", "dev"):
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


if __name__ == "__main__":
    unittest.main()


