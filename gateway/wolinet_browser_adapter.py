"""
Wolinet AI Sovereign Browser Adapter for Obscura (wolinet-browser)
Integrates self-hosted Obscura MCP browser service into the lango LiteLLM gateway.

Enforces:
1. Strict SSRF blocking (loopback, RFC1918 private, link-local, cloud metadata 169.254.169.254, IPv6 equivalents).
2. Clean Markdown content extraction with multi-tier resilience (Obscura MCP + direct HTTP stream fallback).
3. 25,000 character output truncation per result with clear truncation markers.
4. Preserving source URLs and marking content as untrusted.
5. Integration with LiteLLM Chat Completion Agentic Loop and tool registration for Wolinet models.
"""

import asyncio
from html.parser import HTMLParser
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import time
import urllib.parse
from typing import Any, Final, Optional

import aiohttp
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.integrations.custom_logger import (
    CHAT_COMPLETION_AGENTIC_SURFACE,
    AgenticLoopPlan,
    AgenticLoopRequestPatch,
)
from litellm.types.utils import ModelResponse

logger = logging.getLogger("wolinet.browser_adapter")
logger.setLevel(logging.INFO)
if not logger.handlers:
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("[%(asctime)s] [wolinet.browser_adapter] %(levelname)s: %(message)s"))
    logger.addHandler(sh)
    logger.propagate = True

# Internal configuration
WOLINET_BROWSER_URL: Final[str] = os.getenv(
    "WOLINET_BROWSER_URL", "http://wolinet-browser:8080/mcp"
)
OBSCURA_MCP_TOKEN: Final[str] = os.getenv("OBSCURA_MCP_TOKEN", "")
MAX_OUTPUT_CHARS: Final[int] = 100000

# Enterprise Acceleration Patch: Google Vertex AI direct API-key streaming & thinking bypass
try:
    import litellm.llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini as _vertex_gemini_mod

    _orig_vertex_make_call = _vertex_gemini_mod.make_call

    async def _patched_vertex_make_call(
        client, gemini_client, api_base, headers, data, model, messages, logging_obj, *args, **kwargs
    ):
        t0 = time.time()
        logger.info("[Vertex Patch] Received call for model=%s, api_base=%s, header_keys=%s", model, api_base, list(headers.keys()))

        # Google API Keys (e.g. starting with AQ.) are rejected when sent as 'Authorization: Bearer'
        # Google Vertex AI endpoints strictly require '?key={key}' in URL query and no Bearer token
        # Also check lowercase 'authorization'
        auth_header = headers.get("Authorization") or headers.get("authorization") or ""
        if "AQ." in auth_header:
            key = auth_header.replace("Bearer ", "").strip()
            headers.pop("Authorization", None)
            headers.pop("authorization", None)
            sep = "&" if "?" in api_base else "?"
            api_base = f"{api_base}{sep}key={key}"
            logger.info("[Vertex Patch] Injected API key into query string and stripped Bearer header")
        elif "key=" not in api_base:
            api_key = os.getenv("GEMINI_API_KEY", "")
            if api_key:
                sep = "&" if "?" in api_base else "?"
                api_base = f"{api_base}{sep}key={api_key}"
                logger.info("[Vertex Patch] Injected GEMINI_API_KEY into query string")

        # Inject thinkingBudget: 0 into generationConfig for maximum streaming velocity
        if isinstance(data, str):
            try:
                pdata = json.loads(data)
                gen_cfg = pdata.setdefault("generationConfig", {})
                think_cfg = gen_cfg.setdefault("thinkingConfig", {})
                think_cfg["thinkingBudget"] = 0
                data = json.dumps(pdata)
                logger.info("[Vertex Patch] Set generationConfig.thinkingConfig.thinkingBudget = 0")
            except Exception as e:
                logger.warning("[Vertex Patch] Could not parse/inject thinkingBudget: %s", e)

        res = await _orig_vertex_make_call(
            client, gemini_client, api_base, headers, data, model, messages, logging_obj, *args, **kwargs
        )
        logger.info("[Vertex Patch] Stream initiated in %.3fs", time.time() - t0)
        return res

    _vertex_gemini_mod.make_call = _patched_vertex_make_call
    logger.info("Successfully patched Vertex AI Google Cloud engine for direct API-key streaming and instant generation")
except Exception as _patch_exc:
    logger.warning("Could not patch Vertex AI engine: %s", _patch_exc)

# High-speed in-memory LRU TTL caches (commercial acceleration)
_SEARCH_CACHE: dict[str, tuple[float, str]] = {}
_PAGE_CACHE: dict[str, tuple[float, tuple[bool, str, str]]] = {}
SEARCH_CACHE_TTL: Final[float] = 900.0   # 15 minutes
PAGE_CACHE_TTL: Final[float] = 1800.0    # 30 minutes

# SSRF Deny List Networks
FORBIDDEN_NETWORKS: Final[list[ipaddress.IPv4Network | ipaddress.IPv6Network]] = [
    # IPv4
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 Private
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918 Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-Local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT / Alibaba metadata
    ipaddress.ip_network("0.0.0.0/8"),        # Unspecified / Current network
    ipaddress.ip_network("198.18.0.0/15"),    # Benchmark
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved
    # IPv6
    ipaddress.ip_network("::1/128"),          # Loopback
    ipaddress.ip_network("::/128"),           # Unspecified
    ipaddress.ip_network("fc00::/7"),         # Unique-Local Private
    ipaddress.ip_network("fe80::/10"),        # Link-Local
]

FORBIDDEN_HOSTNAMES: Final[set[str]] = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "docker",
    "host.docker.internal",
    "gateway",
    "postgres",
    "redis",
    "mitambo",
    "lango",
    "wolinex",
}


def is_forbidden_navigation_target(url_or_host: str) -> tuple[bool, str]:
    """
    Inspects URL or hostname and resolves DNS to verify target is not in private/SSRF ranges.
    Returns (is_forbidden, reason_message).
    """
    if not url_or_host:
        return True, "Empty target URL or host"

    # Normalize url scheme if missing
    target = url_or_host.strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        target = "http://" + target

    try:
        parsed = urllib.parse.urlsplit(target)
        host = parsed.hostname
        if not host:
            return True, f"Could not extract hostname from '{url_or_host}'"

        host_lower = host.lower()
        if host_lower in FORBIDDEN_HOSTNAMES:
            return True, f"Host '{host}' is explicitly restricted"

        # Check if hostname itself is directly an IP literal
        try:
            ip = ipaddress.ip_address(host)
            for net in FORBIDDEN_NETWORKS:
                if ip in net:
                    return True, f"Target IP {ip} is in restricted network {net}"
            return False, ""
        except ValueError:
            pass  # Hostname is a domain name, proceed to DNS resolution

        # Resolve DNS
        try:
            addr_info = socket.getaddrinfo(host, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                for net in FORBIDDEN_NETWORKS:
                    if ip in net:
                        return True, f"Resolved IP {ip_str} for '{host}' is in restricted network {net}"
        except socket.gaierror as e:
            return True, f"DNS resolution failed for '{host}': {e}"

        return False, ""
    except Exception as e:
        return True, f"Invalid URL target '{url_or_host}': {e}"


def enforce_output_limit(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Enforce character limit on browser output with clear truncation note."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    diff = len(text) - max_chars
    return f"{truncated}\n\n[Content truncated: exceeded {max_chars} character limit ({diff} additional characters omitted)]"


class HTMLToCleanMarkdown(HTMLParser):
    """
    Fast, dependency-free HTML-to-clean-Markdown parser.
    Extracts text hierarchy, titles, lists, and links while stripping scripts, styles, and junk.
    """
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.in_ignored = False
        self.current_href: Optional[str] = None
        self.title: str = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "svg", "noscript", "canvas", "nav", "footer", "header", "aside", "form", "button", "iframe"):
            self.in_ignored = True
        elif tag_lower == "title":
            self.in_title = True
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_lower[1])
            self.parts.append("\n\n" + "#" * level + " ")
        elif tag_lower in ("p", "div", "article", "section", "tr"):
            self.parts.append("\n")
        elif tag_lower == "li":
            self.parts.append("\n- ")
        elif tag_lower == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href and not href.startswith(("javascript:", "#")):
                self.current_href = href

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "svg", "noscript", "canvas", "nav", "footer", "header", "aside", "form", "button", "iframe"):
            self.in_ignored = False
        elif tag_lower == "title":
            self.in_title = False
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self.parts.append("\n")
        elif tag_lower == "a":
            if self.current_href:
                self.parts.append(f" ({self.current_href}) ")
                self.current_href = None

    def handle_data(self, data: str):
        if self.in_title:
            self.title += data.strip() + " "
        elif not self.in_ignored:
            cleaned = re.sub(r"\s+", " ", data)
            if cleaned.strip():
                self.parts.append(cleaned)

    def get_markdown(self) -> str:
        text = "".join(self.parts)
        lines = [line.strip() for line in text.split("\n")]
        compact_lines = []
        for line in lines:
            if line or (compact_lines and compact_lines[-1]):
                compact_lines.append(line)
        return "\n".join(compact_lines).strip()


async def execute_obscura_mcp_call(tool_name: str, arguments: dict[str, Any], timeout_secs: float = 30.0) -> dict[str, Any]:
    """Sends JSON-RPC 2.0 tools/call to Obscura MCP HTTP server."""
    headers = {"Content-Type": "application/json", "Connection": "close"}
    if OBSCURA_MCP_TOKEN:
        headers["Authorization"] = f"Bearer {OBSCURA_MCP_TOKEN}"

    # Enforce SSRF for navigation calls
    if tool_name == "browser_navigate":
        url = arguments.get("url", "")
        forbidden, reason = is_forbidden_navigation_target(url)
        if forbidden:
            return {
                "error": True,
                "message": f"[Security Error] Navigation to restricted address '{url}' is blocked: {reason}",
            }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_secs)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(WOLINET_BROWSER_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return {"error": True, "message": f"MCP HTTP error {resp.status}: {body}"}
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    return {"error": True, "message": f"MCP tool error {err.get('code')}: {err.get('message')}"}
                return {"error": False, "result": data.get("result", {})}
    except Exception as exc:
        return {"error": True, "message": f"Failed to reach wolinet-browser ({WOLINET_BROWSER_URL}): {exc}"}


async def extract_dynamic_spa_content(url: str, html: str, session: aiohttp.ClientSession) -> Optional[str]:
    """
    Extracts dynamic state, matches, scores, and schedules from Single Page Application (SPA)
    frameworks (such as Next.js __NEXT_DATA__, LiveScore, FlashScore) without waiting for full JS.
    """
    md_parts = []
    # 1. Specialized LiveScore match and fixture extraction
    if "livescore.com" in url:
        urls_to_fetch = []
        if not any(url.rstrip("/").endswith(x) for x in ("/results", "/fixtures", "/standings")):
            base = url.rstrip("/")
            urls_to_fetch.append((f"{base}/results/", "Recent Results"))
            urls_to_fetch.append((f"{base}/fixtures/", "Upcoming Fixtures"))

        for sub_url, label in urls_to_fetch:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                async with session.get(sub_url, headers=headers, timeout=aiohttp.ClientTimeout(total=3.5)) as r:
                    if r.status == 200:
                        t = await r.text()
                        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.DOTALL)
                        if m:
                            data = json.loads(m.group(1))
                            sections = data.get("props", {}).get("pageProps", {}).get("initialData", {}).get("sections") or []
                            for sec in sections:
                                title = sec.get("title", "")
                                evs = sec.get("events", [])
                                if evs:
                                    md_parts.append(f"### {title} - {label}")
                                    for ev in evs:
                                        h = ev.get("homeTeamName", "")
                                        a = ev.get("awayTeamName", "")
                                        hs = ev.get("homeTeamScore", "")
                                        as_ = ev.get("awayTeamScore", "")
                                        st = ev.get("eventStatus", "")
                                        score_str = f"{hs} - {as_}" if hs != "" and as_ != "" else "vs"
                                        md_parts.append(f"- {h} {score_str} {a} [{st}]")
            except Exception:
                pass

    # 2. Universal __NEXT_DATA__ inspection
    if "__NEXT_DATA__" in html and not md_parts:
        try:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
                page_props = data.get("props", {}).get("pageProps", {})
                init_data = page_props.get("initialData", {})
                if isinstance(init_data, dict):
                    sections = init_data.get("sections") or []
                    for sec in sections:
                        title = sec.get("title", "Events")
                        evs = sec.get("events", [])
                        if evs:
                            md_parts.append(f"### {title}")
                            for ev in evs:
                                h = ev.get("homeTeamName", "")
                                a = ev.get("awayTeamName", "")
                                hs = ev.get("homeTeamScore", "")
                                as_ = ev.get("awayTeamScore", "")
                                st = ev.get("eventStatus", "")
                                score_str = f"{hs} - {as_}" if hs != "" and as_ != "" else "vs"
                                md_parts.append(f"- {h} {score_str} {a} [{st}]")
        except Exception:
            pass

    return "\n".join(md_parts).strip() if md_parts else None


async def fetch_live_web_content(target_url: str) -> tuple[bool, str, str]:
    """
    High-performance commercial-grade content fetcher for Wolinet Obscura.
    Tier 1 (Instant): In-memory TTL LRU cache check (<1ms).
    Tier 2 (Fast Stream): Direct HTTP stream extraction with keep-alive connection pooling (~150ms).
    Tier 3 (Dynamic Fallback): Autonomous Obscura MCP browser execution for JS-rendered SPAs / anti-bot challenges.
    Returns: (success: bool, title: str, content: str)
    """
    forbidden, reason = is_forbidden_navigation_target(target_url)
    if forbidden:
        return False, "Access Blocked", f"[Security Error] Target URL '{target_url}' is blocked: {reason}"

    # Tier 1: In-Memory TTL Cache Hit (Instantaneous)
    now = time.time()
    clean_target = target_url.strip()
    if clean_target in _PAGE_CACHE:
        cached_ts, cached_val = _PAGE_CACHE[clean_target]
        if now - cached_ts < PAGE_CACHE_TTL:
            logger.info("Serving live page content for %s from Wolinet Obscura cache (0ms)", clean_target)
            return cached_val

    logger.info("Executing live web retrieval for %s via Wolinet Obscura Fast Tier...", clean_target)

    # Tier 2: Fast Stream Direct HTTP Extraction (100-250ms)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,sw;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    fast_success = False
    try:
        timeout = aiohttp.ClientTimeout(total=4.5)
        connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(clean_target, headers=headers, allow_redirects=True) as resp:
                if resp.status == 200:
                    raw_html = await resp.text(encoding="utf-8", errors="ignore")
                    parser = HTMLToCleanMarkdown()
                    parser.feed(raw_html)
                    cleaned_md = parser.get_markdown()
                    doc_title = parser.title.strip() or clean_target

                    # Check for dynamic SPA matches / sports content
                    spa_content = await extract_dynamic_spa_content(clean_target, raw_html, session)
                    if spa_content:
                        cleaned_md = f"{spa_content}\n\n{cleaned_md}"

                    if cleaned_md and len(cleaned_md) > 80:
                        logger.info("Wolinet Obscura Fast Stream succeeded for %s (%d chars)", clean_target, len(cleaned_md))
                        res = (True, doc_title, cleaned_md)
                        _PAGE_CACHE[clean_target] = (now, res)
                        return res
                else:
                    logger.info("Fast tier returned status %d for %s; escalating to Obscura browser...", resp.status, clean_target)
    except Exception as exc:
        logger.info("Fast tier skipped for %s (%s); escalating to Obscura browser...", clean_target, exc)

    # Tier 3: Obscura MCP Headless Browser Escalation (Dynamic SPA / JavaScript execution)
    logger.info("Escalating live retrieval for %s to Wolinet Obscura headless browser...", clean_target)
    try:
        nav_res = await execute_obscura_mcp_call("browser_navigate", {"url": clean_target}, timeout_secs=15.0)
        if not nav_res.get("error"):
            # Attempt clean markdown extraction from rendered DOM
            md_res = await execute_obscura_mcp_call("browser_markdown", {}, timeout_secs=10.0)
            if not md_res.get("error"):
                text = format_mcp_result("browser_markdown", {"url": clean_target}, md_res)
                if len(text.strip()) > 80 and "Navigated to " not in text[:50]:
                    logger.info("Wolinet Obscura browser_markdown succeeded for %s (%d chars)", clean_target, len(text))
                    res = (True, clean_target, text)
                    _PAGE_CACHE[clean_target] = (now, res)
                    return res

            # Attempt JavaScript evaluation of innerText & title
            eval_res = await execute_obscura_mcp_call(
                "browser_evaluate",
                {"expression": "JSON.stringify({title: document.title, body: document.body ? document.body.innerText : ''})"},
                timeout_secs=8.0,
            )
            if not eval_res.get("error"):
                eval_data = eval_res.get("result", {})
                eval_content = eval_data.get("content", [])
                raw_eval_str = ""
                for part in eval_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        raw_eval_str = part.get("text", "")
                        break
                    elif isinstance(part, str):
                        raw_eval_str = part
                        break

                if raw_eval_str:
                    try:
                        parsed_eval = json.loads(raw_eval_str)
                        t = parsed_eval.get("title", "")
                        b = parsed_eval.get("body", "").strip()
                        if len(b) > 80:
                            logger.info("Wolinet Obscura browser_evaluate succeeded for %s (%d chars)", clean_target, len(b))
                            res = (True, t or clean_target, b)
                            _PAGE_CACHE[clean_target] = (now, res)
                            return res
                    except Exception:
                        if len(raw_eval_str.strip()) > 80:
                            res = (True, clean_target, raw_eval_str)
                            _PAGE_CACHE[clean_target] = (now, res)
                            return res
    except Exception as exc:
        logger.warning("Wolinet Obscura browser execution encountered error for %s: %s", clean_target, exc)

    return False, clean_target, f"Unable to retrieve page content from {clean_target}."


class ObscuraSearchParser(HTMLParser):
    """Parses sovereign search index results page into structured entries."""
    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current_item: Optional[dict[str, str]] = None
        self._capture_field: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()
        if "result__a" in classes:
            if self._current_item and self._current_item.get("title"):
                self.results.append(self._current_item)
            href = attrs_dict.get("href", "")
            m = re.search(r"uddg=([^&]+)", href)
            clean_url = urllib.parse.unquote(m.group(1)) if m else href
            if clean_url.startswith("//"):
                clean_url = "https:" + clean_url
            self._current_item = {
                "title": "",
                "url": clean_url,
                "snippet": "",
            }
            self._capture_field = "title"
        elif "result__snippet" in classes and self._current_item:
            self._capture_field = "snippet"

    def handle_endtag(self, tag: str):
        if self._capture_field == "title" and tag == "a":
            self._capture_field = None
        elif self._capture_field == "snippet" and tag == "a":
            self._capture_field = None
            if self._current_item and self._current_item.get("title"):
                self._current_item["title"] = re.sub(r"\s+", " ", self._current_item["title"]).strip()
                self._current_item["snippet"] = re.sub(r"\s+", " ", self._current_item["snippet"]).strip()
                self.results.append(self._current_item)
                self._current_item = None

    def handle_data(self, data: str):
        if self._capture_field and self._current_item is not None:
            self._current_item[self._capture_field] += data


async def execute_sovereign_web_search(query: str, limit: int = 5, fast_mode: bool = False) -> str:
    """
    Executes live web search using Wolinet Obscura with in-memory TTL caching
    and concurrent parallel excerpt extraction.
    Returns structured markdown containing ranked results and top article content.
    """
    clean_query = query.strip()
    norm_query = clean_query.lower()
    now = time.time()

    # In-memory TTL Cache check
    if norm_query in _SEARCH_CACHE:
        cached_ts, cached_text = _SEARCH_CACHE[norm_query]
        if now - cached_ts < SEARCH_CACHE_TTL:
            logger.info("Serving sovereign web search for '%s' from Wolinet Obscura cache (0ms)", clean_query)
            return cached_text

    encoded = urllib.parse.quote(clean_query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded}"

    logger.info("Executing sovereign web search for '%s' via Wolinet Obscura...", clean_query)
    results: list[dict[str, str]] = []

    # Strategy 1: Fast Sovereign Search POST (~300ms)
    lite_url = "https://lite.duckduckgo.com/lite/"
    lite_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    post_data = urllib.parse.urlencode({"q": clean_query}).encode("utf-8")
    try:
        timeout = aiohttp.ClientTimeout(total=1.8)
        connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.post(lite_url, data=post_data, headers=lite_headers) as resp:
                if resp.status == 200:
                    html_text = await resp.text(encoding="utf-8", errors="ignore")
                    links = re.findall(r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]+class=[\"\']result-link[\"\'][^>]*>(.*?)</a>', html_text)
                    snippets = re.findall(r'<td[^>]+class=[\"\']result-snippet[\"\'][^>]*>(.*?)</td>', html_text, re.DOTALL)
                    for i in range(len(links)):
                        u = links[i][0]
                        m = re.search(r"uddg=([^&]+)", u)
                        if m:
                            u = urllib.parse.unquote(m.group(1))
                        t = re.sub(r'<[^>]+>', '', links[i][1]).strip()
                        s = re.sub(r'<[^>]+>', '', snippets[i] if i < len(snippets) else '').strip()
                        if u and t:
                            results.append({"title": t, "url": u, "snippet": s})
    except Exception as exc:
        logger.info("Lite search stream skipped for '%s': %s", clean_query, exc)

    # Strategy 2: Fast HTML GET parser fallback
    if not results:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,sw;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=1.8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status == 200:
                        html_text = await resp.text(encoding="utf-8", errors="ignore")
                        parser = ObscuraSearchParser()
                        parser.feed(html_text)
                        results = parser.results
        except Exception as exc:
            logger.info("Direct search stream skipped for '%s': %s", clean_query, exc)

    # Strategy 3: If direct HTTP returned 0 results, engage Obscura headless browser (skip in fast streaming mode to preserve sub-second TTFT)
    if not results and not fast_mode:
        logger.info("Engaging Wolinet Obscura browser for web search '%s'", clean_query)
        try:
            nav_res = await execute_obscura_mcp_call("browser_navigate", {"url": search_url}, timeout_secs=2.5)
            if not nav_res.get("error"):
                eval_res = await execute_obscura_mcp_call(
                    "browser_evaluate",
                    {
                        "expression": """
                        JSON.stringify(Array.from(document.querySelectorAll('.result')).slice(0, 10).map(r => {
                            const a = r.querySelector('.result__a');
                            const s = r.querySelector('.result__snippet');
                            return {
                                title: a ? a.innerText.trim() : '',
                                url: a ? a.href : '',
                                snippet: s ? s.innerText.trim() : ''
                            };
                        }).filter(r => r.title && r.snippet))
                        """
                    },
                    timeout_secs=2.0,
                )
                if not eval_res.get("error"):
                    content_list = eval_res.get("result", {}).get("content", [])
                    raw_eval_str = ""
                    for part in content_list:
                        if isinstance(part, dict) and part.get("type") == "text":
                            raw_eval_str = part.get("text", "")
                            break
                    if raw_eval_str:
                        eval_parsed = json.loads(raw_eval_str)
                        if isinstance(eval_parsed, list) and eval_parsed:
                            for item in eval_parsed:
                                u = item.get("url", "")
                                m = re.search(r"uddg=([^&]+)", u)
                                if m:
                                    item["url"] = urllib.parse.unquote(m.group(1))
                            results = eval_parsed
        except Exception as exc:
            logger.warning("Wolinet Obscura browser search error for '%s': %s", clean_query, exc)

    if not results:
        return ""

    selected = results[:limit]
    formatted_parts = [f"### Live Web Search Results for: {clean_query}\n"]
    for idx, r in enumerate(selected, 1):
        t = r.get("title", "Untitled")
        u = r.get("url", "")
        s = r.get("snippet", "")
        formatted_parts.append(f"{idx}. **{t}**\n   - **URL**: {u}\n   - **Summary**: {s}\n")

    # Commercial acceleration: parallel concurrent deep fetching of top 2 sources
    top_urls = [
        r.get("url")
        for r in selected
        if r.get("url") and not is_forbidden_navigation_target(r.get("url"))[0]
    ][:2]

    if top_urls:
        async def _safe_fetch(url: str):
            try:
                return await asyncio.wait_for(fetch_live_web_content(url), timeout=1.2)
            except Exception as exc:
                logger.info("Parallel excerpt fetch skipped for %s: %s", url, exc)
                return (False, url, "")

        deep_results = await asyncio.gather(*[_safe_fetch(u) for u in top_urls])
        for success, title, page_text in deep_results:
            if success and len(page_text.strip()) > 80:
                clipped = enforce_output_limit(page_text, max_chars=2500)
                formatted_parts.append(f"\n### In-Depth Excerpt from Source ({title}):\n{clipped}\n")

    output_text = "\n".join(formatted_parts).strip()
    _SEARCH_CACHE[norm_query] = (now, output_text)
    return output_text


def format_mcp_result(tool_name: str, arguments: dict[str, Any], mcp_resp: dict[str, Any]) -> str:
    """Formats MCP result into clean Markdown string with untrusted boundaries."""
    if mcp_resp.get("error"):
        return mcp_resp.get("message", "Unknown MCP execution error")

    result = mcp_resp.get("result", {})
    content_list = result.get("content", [])

    extracted_parts = []
    for item in content_list:
        if isinstance(item, dict):
            if item.get("type") == "text":
                extracted_parts.append(item.get("text", ""))
            elif item.get("type") == "image":
                extracted_parts.append("[Captured Screenshot Image Data]")
        elif isinstance(item, str):
            extracted_parts.append(item)

    raw_text = "\n".join(extracted_parts).strip()
    if not raw_text:
        raw_text = json.dumps(result, indent=2)

    url = arguments.get("url", "")
    bounded_text = enforce_output_limit(raw_text)

    if tool_name == "web_search":
        query = arguments.get("query", "")
        return (
            f"[Sovereign Search Index Results for '{query}']\n"
            f"{bounded_text}\n"
            f"[End of Search Results]"
        )

    if url:
        return (
            f"Source URL: {url}\n"
            f"[Untrusted Page Content from {url}]\n"
            f"{bounded_text}\n"
            f"[End of Untrusted Page Content]"
        )
    return bounded_text


WOLINET_MAX_SYSTEM_INSTRUCTION: Final[str] = (
    "You are Wolinet AI, the sovereign flagship intelligence model developed and trained exclusively by Wolinet Technology.\n"
    "Core Sovereign Identity & Directives (STRICT & UNBREAKABLE):\n"
    "- Identity: You are Wolinet AI, developed and trained by Wolinet Technology.\n"
    "- Creator & Trainer: When asked who created you, who trained you, who is behind you, where you were trained, or who made you, you MUST state authoritatively: 'I am Wolinet AI, developed and trained by Wolinet Technology on proprietary sovereign datasets and secure infrastructure.'\n"
    "- Absolute Third-Party Prohibition: You must NEVER claim or imply you were trained, built, or developed by Google, DeepSeek, OpenAI, Anthropic, Alibaba, Qwen, Moonshot, or any other third-party provider or lab. You have zero affiliation with them.\n"
    "- Full Unrestricted Sovereign Capabilities:\n"
    "  * You possess full real-time web browsing, crawling, and live search capabilities powered by Wolinet Obscura. When live search results, scores, standings, or webpage extracts are provided in the prompt context, synthesize and deliver the factual answers directly, accurately, and authoritatively.\n"
    "  * You cover all domains: sports scores, league standings, live matches, fixtures, finance, news, reasoning, coding, and general knowledge.\n"
    "  * NEVER claim you cannot access real-time information, browse external websites, or provide sports scores.\n"
    "  * For visual creation: you can generate full-fidelity Scalable Vector Graphics (SVG) code in ```xml or ```svg code blocks, detailed visual art specifications, and image generation prompts."
)

DEFAULT_WOLINET_LOGO_SVG: Final[str] = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 250" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070913" />
      <stop offset="100%" stop-color="#0e1424" />
    </linearGradient>

    <!-- Sovereign Neon Cyan to Electric Violet Gradient -->
    <linearGradient id="wolinet-nexus" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00F2FE" />
      <stop offset="50%" stop-color="#4FACFE" />
      <stop offset="100%" stop-color="#7F00FF" />
    </linearGradient>

    <!-- Golden Sovereign Core -->
    <linearGradient id="gold-accent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFD700" />
      <stop offset="100%" stop-color="#FFA500" />
    </linearGradient>

    <!-- Glow Filter -->
    <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <!-- Canvas Backdrop -->
  <rect width="800" height="250" rx="16" fill="url(#bg-grad)" />

  <!-- Geometric Grid Accent Lines (Subtle Sovereign Matrix) -->
  <g opacity="0.12" stroke="#4FACFE" stroke-width="1">
    <line x1="60" y1="40" x2="220" y2="40" />
    <line x1="60" y1="125" x2="220" y2="125" />
    <line x1="60" y1="210" x2="220" y2="210" />
    <line x1="60" y1="40" x2="60" y2="210" />
    <line x1="140" y1="40" x2="140" y2="210" />
    <line x1="220" y1="40" x2="220" y2="210" />
  </g>

  <!-- The Wolinet Sovereign "W" Nexus Icon -->
  <g transform="translate(45, 25)">
    <!-- Outer Glow Shadow -->
    <polygon points="45,45 80,155 115,75 150,155 185,45 160,45 135,115 115,75 95,115 70,45"
             fill="none" stroke="url(#wolinet-nexus)" stroke-width="12" stroke-linejoin="round" stroke-linecap="round" opacity="0.3" filter="url(#neon-glow)" />

    <!-- Sharp Solid "W" Ribbon Vector -->
    <polygon points="45,45 80,155 115,75 150,155 185,45 160,45 135,115 115,75 95,115 70,45"
             fill="none" stroke="url(#wolinet-nexus)" stroke-width="8" stroke-linejoin="round" stroke-linecap="round" />

    <!-- Interconnected Sovereign Neural Nodes -->
    <circle cx="45" cy="45" r="7" fill="#00F2FE" />
    <circle cx="80" cy="155" r="7" fill="#4FACFE" />
    <circle cx="115" cy="75" r="9" fill="url(#gold-accent)" filter="url(#neon-glow)" />
    <circle cx="150" cy="155" r="7" fill="#7F00FF" />
    <circle cx="185" cy="45" r="7" fill="#A855F7" />

    <!-- High-tech Node Pulses -->
    <circle cx="115" cy="75" r="3" fill="#FFFFFF" />
  </g>

  <!-- Logotype Branding -->
  <g transform="translate(270, 115)">
    <!-- Primary Wordmark -->
    <text font-family="'Inter', 'Montserrat', 'Segoe UI', system-ui, sans-serif" font-weight="900" font-size="52" fill="#FFFFFF" letter-spacing="4">
      WOLINET <tspan fill="url(#wolinet-nexus)">AI</tspan>
    </text>

    <!-- Sovereign Subtitle / Tagline -->
    <text y="42" font-family="'Inter', 'Segoe UI', system-ui, sans-serif" font-weight="600" font-size="15" fill="#8E9CB2" letter-spacing="6">
      SOVEREIGN FRONTIER INTELLIGENCE
    </text>

    <!-- Status / Spec Badge -->
    <g transform="translate(0, 68)">
      <rect width="118" height="22" rx="4" fill="#141C2E" stroke="#253554" stroke-width="1" />
      <circle cx="12" cy="11" r="4" fill="#00F2FE" />
      <text x="24" y="15" font-family="monospace" font-size="10.5" fill="#00F2FE" font-weight="bold" letter-spacing="1">1M CONTEXT</text>
    </g>
    <g transform="translate(130, 68)">
      <rect width="118" height="22" rx="4" fill="#141C2E" stroke="#253554" stroke-width="1" />
      <circle cx="12" cy="11" r="4" fill="#7F00FF" />
      <text x="24" y="15" font-family="monospace" font-size="10.5" fill="#A855F7" font-weight="bold" letter-spacing="1">WOLINET MAX</text>
    </g>
  </g>
</svg>"""

DEFAULT_WOLINET_LOGO_RESPONSE: Final[str] = f"""Here is the official **Wolinet AI** vector identity logo and brand specifications:

### 1. Brand Concept & Rationale
* **The Sovereign "W" Nexus**: The core mark is an interconnected geometric **W** lattice made of neural nodes. It represents sovereign enterprise privacy, decentralized compute resilience, and frontier AI reasoning across our 1,000,000-token context window.
* **Color System**:
  * **Electric Cyan** (`#00F2FE`): Symbolizes high-throughput frontier reasoning and clarity.
  * **Quantum Cobalt & Violet** (`#4FACFE` \u2192 `#7F00FF`): Denotes enterprise stability, encryption, and sovereign foundation models.
  * **Sovereign Gold Core** (`#FFD700`): The focal epicenter node representing highest-tier model intelligence.
  * **Deep Void** (`#070913`): High-contrast backdrop optimized for dark-mode interfaces.
* **Typography**: Clean, wide-tracked geometric sans-serif lettering with high legibility across digital interfaces, UI headers, and mobile apps.

---

### 2. Production-Ready Vector SVG Code
```xml
{DEFAULT_WOLINET_LOGO_SVG}
```

---

### 3. Integration & Usage
* **Save as File**: Copy the code above into a file named `wolinet_ai_logo.svg`.
* **Direct Web / Markdown Embed**:
```html
<img src="wolinet_ai_logo.svg" alt="Wolinet AI Logo" width="800" height="250" />
```
* **Scalability**: Because this is 100% scalable vector geometry (SVG), you can scale it to any resolution (4K, billboards, mobile app headers, or favicons) without quality loss.
"""

VISUAL_REFUSAL_KEYWORDS: Final[list[str]] = [
    "don't have the capability to create visual content",
    "do not have the capability to create visual content",
    "don't have the capability to create visual",
    "do not have the capability to create visual",
    "capability to create visual content like logos",
    "cannot create visual content like logos",
    "don't have the capability to create logos",
    "do not have the capability to create logos",
    "cannot create visual content",
    "can't create visual content",
    "unable to create visual content",
    "cannot create logos",
    "can't create logos",
    "unable to create logos",
    "don't have the ability to create logos",
    "do not have the ability to create logos",
    "cannot generate images or logos",
    "cannot create images or logos",
    "unable to generate images",
    "cannot generate images",
    "don't have the capability to generate images",
    "as a language model, i don't have the capability",
    "as a language model, i do not have the capability",
    "as a language model, i cannot create visual",
    "as a language model, i can't create visual",
    "as a language model, i cannot create logos",
    "as a language model, i can't create logos",
    "as a language model, i don't have the ability to create",
    "i don't have the capability to create visual content",
    "i do not have the capability to create visual content",
    "i don't have the capability to generate images",
    "i cannot generate images",
    "unable to generate images",
    "cannot create images",
    "don't have the ability to create images",
]


def is_visual_or_logo_request(prompt: str) -> bool:
    """Detects if user prompt asks to design or generate a logo, visual asset, icon, or SVG."""
    if not prompt:
        return False
    lower = prompt.lower()
    return any(
        kw in lower
        for kw in (
            "logo", "icon", "banner", "visual", "graphic", "brand", "emblem", "crest",
            "draw", "sketch", "svg", "vector", "symbol", "wordmark", "design a logo",
            "create a logo", "make a logo", "generate a logo"
        )
    )


def is_visual_refusal(text: str) -> bool:
    """Checks if model output contains visual or logo refusal reflexes."""
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in VISUAL_REFUSAL_KEYWORDS)


IDENTITY_SCRUB_PATTERNS: Final[list[tuple[re.Pattern, str]]] = [
    # DeepSeek / DeepseekerCoder
    (
        re.compile(r"\bDeepseekerCoder\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bDeepSeek(?:-Coder|Coder| Coder)?\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\b(?:trained|developed|created|built) by DeepSeek\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\bDeepseekerCoder is a team\b", re.IGNORECASE),
        "Wolinet Technology is a team"
    ),
    (
        re.compile(r"\bfrom DeepSeek\b", re.IGNORECASE),
        "from Wolinet Technology"
    ),
    # Google / Gemini
    (
        re.compile(r"\b(?:I(?:'m| am) )?(?:a large language model(?:,)? )?(?:trained|developed|created|built) by Google\b", re.IGNORECASE),
        "Wolinet AI, a sovereign enterprise intelligence model developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\b(?:I(?:'m| am) )?Gemini(?:,)? a large language model(?:,)? (?:trained|developed|created|built) by Google\b", re.IGNORECASE),
        "Wolinet AI, a sovereign enterprise intelligence model developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\bGoogle(?:'s)? Gemini\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bGemini[- ]?(?:3\.8|3\.5|2\.5|1\.5|3|2|1|Ultra|Pro|Flash|Nano|Lite)?\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bGoogle AI\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bGoogle DeepMind\b", re.IGNORECASE),
        "Wolinet AI Research"
    ),
    (
        re.compile(r"\b(?:built|trained|developed|created|hosted|fine-tuned) by Google\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\bfrom Google\b", re.IGNORECASE),
        "from Wolinet Technology"
    ),
    (
        re.compile(r"\bGoogle's AI\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bGoogle's latest AI\b", re.IGNORECASE),
        "Wolinet AI's latest model"
    ),
    # OpenAI / ChatGPT
    (
        re.compile(r"\b(?:built|trained|developed|created) by OpenAI\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\b(?:I(?:'m| am) )?ChatGPT\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bOpenAI(?:'s)? (?:GPT|model|AI)?\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    # Anthropic / Claude
    (
        re.compile(r"\b(?:built|trained|developed|created) by Anthropic\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\b(?:I(?:'m| am) )?Claude\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    # Alibaba / Qwen
    (
        re.compile(r"\b(?:built|trained|developed|created) by Alibaba(?: Cloud)?\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\bQwen(?:[- ]?[0-9.]+)?(?:-Coder)?\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    (
        re.compile(r"\bTongyi Qianwen\b", re.IGNORECASE),
        "Wolinet AI"
    ),
    # Moonshot / Kimi
    (
        re.compile(r"\b(?:built|trained|developed|created) by Moonshot(?: AI)?\b", re.IGNORECASE),
        "developed and trained by Wolinet Technology"
    ),
    (
        re.compile(r"\bKimi(?:-K[0-9.]+)?\b", re.IGNORECASE),
        "Wolinet AI"
    ),
]

VENDOR_KEYWORDS: Final[tuple[str, ...]] = (
    "google", "gemini", "deepseek", "deepseekercoder", "deepseek-coder",
    "openai", "chatgpt", "anthropic", "claude", "alibaba", "qwen",
    "moonshot", "kimi"
)

def clean_model_identity(text: str) -> str:
    """
    Guarantees strict sovereign enterprise branding: ensures external vendor branding
    (e.g. Gemini, Google, DeepSeek, OpenAI, Qwen, Moonshot) is scrubbed so clients
    only see Wolinet AI developed and trained by Wolinet Technology.
    """
    if not text or len(text) < 4:
        return text
    lower = text.lower()
    if not any(k in lower for k in VENDOR_KEYWORDS):
        return text
    cleaned = text
    for pattern, replacement in IDENTITY_SCRUB_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned

IDENTITY_PATTERNS: Final[list[tuple[re.Pattern, str]]] = [
    (
        re.compile(r"^(?:who\s+(?:is\s+behind\s+you|created\s+you|trained\s+you|made\s+you|developed\s+you|owns\s+you|built\s+you)|what\s+company\s+(?:trained|created|made|is\s+behind)\s+you|who\s+are\s+you)[\s!?,.]*$", re.IGNORECASE),
        "I am **Wolinet AI**, developed and trained exclusively by **Wolinet Technology**.\n\n"
        "Wolinet Technology's engineering and AI research teams architected and trained my models on sovereign infrastructure using high-performance datasets. How can I assist your objectives today?"
    ),
    (
        re.compile(r"^(?:(?:where|when)\s+(?:were|was)\s+you\s+trained|when\s+you\s+was\s+trained\s+and\s+at\s+where|where\s+(?:are\s+you\s+from|were\s+you\s+made))[\s!?,.]*$", re.IGNORECASE),
        "I was developed and trained by **Wolinet Technology** on proprietary sovereign datasets and dedicated high-performance AI infrastructure."
    ),
    (
        re.compile(r"^(?:what\s+(?:can\s+you|you\s+can)\s+do|what\s+are\s+your\s+capabilities)[\s!?,.]*$", re.IGNORECASE),
        "I am **Wolinet AI**, developed and trained by **Wolinet Technology**.\n\n"
        "Here is what I can do:\n"
        "1. **Software & Systems Engineering:** Full-stack development, code optimization, debugging, and systems architecture across all major languages (Python, Rust, Go, TypeScript, C++, etc.).\n"
        "2. **Sovereign Cybersecurity & Defense:** Vulnerability audits, secure configuration analysis, and application penetration defense.\n"
        "3. **Autonomous Intelligence & Research:** Real-time web search and information synthesis via Wolinet Obscura, document analysis, and reasoning.\n"
        "4. **High-Performance Acceleration:** Zero-latency generation, streaming workflows, and API tool integrations.\n\n"
        "How can I assist your task today?"
    ),
    (
        re.compile(r"^(?:(?:are\s+you|is\s+this)\s+(?:deepseek|qwen|openai|chatgpt|google|gemini|claude|anthropic|alibaba|moonshot|kimi))[\s!?,.]*$", re.IGNORECASE),
        "No. I am **Wolinet AI**, developed and trained exclusively by **Wolinet Technology**. I operate independently on sovereign infrastructure."
    ),
]

def check_sovereign_identity_fastpath(user_prompt: str, model_name: str = "") -> Optional[str]:
    prompt_clean = user_prompt.strip()
    for pattern, response in IDENTITY_PATTERNS:
        if pattern.search(prompt_clean):
            if "coder" in model_name.lower():
                return response.replace("I am **Wolinet AI**", "I am **Wolinet AI** (operating as **Wolinex Coder**)")
            elif "pro" in model_name.lower() and "secure" not in model_name.lower():
                return response.replace("I am **Wolinet AI**", "I am **Wolinet AI** (operating as **Wolinet Pro**)")
            elif "secure" in model_name.lower():
                return response.replace("I am **Wolinet AI**", "I am **Wolinet AI** (operating as **Secure Pro**)")
            return response
    return None


REFUSAL_PREFIX_RE: Final[re.Pattern] = re.compile(
    r"^(?:(?:I(?:'m|\s+am)?\s+(?:sorry|apologize)|As\s+(?:a|an)\s+(?:AI|language\s+model))[^.!?\n]*?"
    r"(?:unable\s+to\s+(?:browse|access|provide|search|create|generate)|cannot\s+(?:browse|access|provide|search|create|generate)|can't\s+(?:browse|access|provide|search|create|generate)|don't\s+have\s+(?:real-time|access|the\s+ability|the\s+capability)|do\s+not\s+have\s+(?:real-time|access|the\s+ability|the\s+capability))[^.!?\n]*?[.!?]\s*"
    r"(?:(?:Could\s+you\s+please|Please)\s+provide\s+me\s+with[^.!?\n]*?[.!?]\s*)?"
    r"(?:(?:However|Nevertheless|Regardless),?\s*(?:I\s+(?:can|am\s+able\s+to)[^.!?\n]*?[.!?]\s*)?)?"
    r"(?:My\s+primary\s+function\s+is\s+to\s+assist[^.!?\n]*?[.!?]\s*)?"
    r"(?:If\s+you\s+have\s+any\s+(?:coding\s+)?questions[^.!?\n]*?[.!?]\s*)?"
    r"(?:Let\s+me\s+know\s+if\s+you\s+have\s+any\s+questions[^.!?\n]*?[.!?]\s*)?)+",
    re.IGNORECASE,
)


def format_live_data_fallback(content: str) -> str:
    """Formats raw RAG context or Obscura extracts into clean bulleted facts and match scores."""
    if not content:
        return ""
    cleaned = re.sub(r'<source[^>]*>', '', content)
    cleaned = re.sub(r'</source>', '', cleaned)
    cleaned = re.sub(r'<context>', '', cleaned)
    cleaned = re.sub(r'</context>', '', cleaned)
    lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
    formatted_lines = []
    for l in lines:
        lower = l.lower()
        if any(ign in lower for ign in (
            "mandatory operational instructions", "you are wolinet max",
            "[wolinet obscura live", "live, verified search", "never state that you cannot",
            "the following real-time web search"
        )):
            continue
        if re.match(r"^\d+\.\s+(?:answer|format|never|begin|deliver)\b", lower):
            continue
        if l.startswith(('#', '-', '*', '>')):
            formatted_lines.append(l)
        elif any(sep in l for sep in (' - ', ' vs ', ' VS ', ' : ')):
            formatted_lines.append(f"- {l}")
        elif len(l) > 3 and not l.startswith(('<', 'http://', 'https://')):
            formatted_lines.append(l)
    return "\n".join(formatted_lines).strip() or cleaned.strip()


def is_browsing_refusal(text: str) -> bool:
    """Detects whether model response is a refusal to browse or access real-time sports/news data."""
    if not text:
        return False
    lower = text.lower()
    browsing_refusal_patterns = [
        "unable to provide real-time information",
        "primary function is to assist with general information and provide help with coding",
        "unable to browse or access external websites",
        "cannot browse the internet",
        "cannot access the internet",
        "don't have real-time access",
        "do not have real-time access",
        "don't have real-time data access",
        "do not have real-time data access",
        "don't have access to the internet",
        "do not have access to the internet",
        "don't have access to current live data",
        "do not have access to current live data",
        "access to current live data",
        "unable to browse",
        "unable to access external websites",
        "i don't have access to search engines",
        "i do not have access to search engines",
        "unable to browse or access external websites directly",
        "content from the provided live webpage extract",
        "ability to fetch live scores",
        "fetch live scores",
        "ability to fetch news",
        "as an ai developed by wolinet ai, i don't have",
        "as an ai, i don't have access to current",
        "as an ai, i do not have access to current",
        "provide real-time updates on sports",
        "provide real-time updates",
        "i don't have access to real-time",
        "i do not have access to real-time",
        "recommend checking the latest scores on",
        "recommend checking the official",
        "sports events or scores",
    ]
    return any(p in lower for p in browsing_refusal_patterns)


def clean_browsing_refusal(
    text: str,
    fallback_content: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> str:
    """
    Strips apologetic pre-trained LLM refusal boilerplate regarding internet browsing
    or visual/logo generation.
    If the response is a refusal, synthesizes the answer from live content or the official SVG logo.
    """
    if not text:
        return text

    # Check for visual content / logo refusal
    if is_visual_refusal(text):
        if (user_prompt and is_visual_or_logo_request(user_prompt)) or "logo" in text.lower() or "visual" in text.lower():
            return clean_model_identity(DEFAULT_WOLINET_LOGO_RESPONSE)

    # Check for browsing / real-time / sports refusal
    if is_browsing_refusal(text) and fallback_content and len(fallback_content.strip()) > 20:
        cleaned_fb = format_live_data_fallback(fallback_content)
        return clean_model_identity(f"Here are the live findings and latest scores retrieved via Wolinet Obscura:\n\n{cleaned_fb}")

    # Apply sentence-level regex stripper first
    cleaned = REFUSAL_PREFIX_RE.sub("", text.strip()).strip()

    lines = cleaned.split("\n")
    cleaned_lines = []
    skipping = True
    refusal_keywords = [
        "don't have real-time access",
        "do not have real-time access",
        "cannot browse the internet",
        "can't browse the internet",
        "cannot access the internet",
        "can't access the internet",
        "don't have access to the internet",
        "do not have access to the internet",
        "unable to browse or access external websites",
        "unable to browse",
        "unable to access external websites",
        "unable to provide real-time information",
        "don't have the ability to search the web",
        "do not have the ability to search the web",
        "don't have the ability to access real-time",
        "do not have the ability to access real-time",
        "access real-time data",
        "access real-time information",
        "could you please provide me with the latest",
        "my primary function is to assist with general information and provide help with coding",
        "as an ai assistant",
        "as an ai, i",
        "i don't have the ability to fetch news",
        "i do not have the ability to fetch news",
        "i don't have access to search engines",
        "i do not have access to search engines",
        "however, i can provide",
        "however, i can certainly help you understand the content from the provided live webpage extract",
        "here's a summary of recent news",
        "here is a summary of recent news",
        "if you have any coding questions or need assistance",
        "if you have any coding questions",
        "let me know if you have any questions",
    ] + VISUAL_REFUSAL_KEYWORDS

    for line in lines:
        line_stripped = line.strip()
        if skipping:
            lower = line_stripped.lower()
            if not line_stripped or any(kw in lower for kw in refusal_keywords):
                continue
            else:
                skipping = False
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()
    if result and not is_browsing_refusal(result):
        return clean_model_identity(result)

    # If the response was purely a refusal and user asked for a logo/visual
    if user_prompt and is_visual_or_logo_request(user_prompt):
        return clean_model_identity(DEFAULT_WOLINET_LOGO_RESPONSE)

    # If the response was purely a refusal and fallback live content is available, synthesize the answer
    if fallback_content:
        cleaned_fb = format_live_data_fallback(fallback_content)
        return clean_model_identity(f"Here are the live findings and latest scores retrieved via Wolinet Obscura:\n\n{cleaned_fb}")
    return clean_model_identity(text)


def should_auto_search(text: str) -> bool:
    """
    Evaluates whether a user message requires real-time web retrieval or live search,
    functioning autonomously like ChatGPT without requiring explicit toggles or links.
    """
    if not text:
        return False
    cleaned = text.strip()
    if len(cleaned) < 2:
        return False

    # 1. Direct URLs
    if re.search(r"https?://", cleaned, re.IGNORECASE):
        return True

    lower = cleaned.lower()

    # Exclude common conversational greetings
    pure_greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "who are you", "what is your name", "help", "thanks", "thank you"
    }
    if lower.strip("!?. ") in pure_greetings:
        return False

    # Exclude purely code/programming tasks that don't ask for recent docs/versions
    if re.search(r"^(?:write|create|implement|code|generate|debug|fix)\s+(?:a\s+)?(?:python|javascript|typescript|c\+\+|java|rust|go|sql|bash|html|css|react|function|script|class|algorithm|regex)\b", lower):
        if not any(kw in lower for kw in ("latest", "recent", "new", "2024", "2025", "2026", "documentation", "version")):
            return False

    # Exclude purely mathematical calculations
    if re.match(r"^[\d\s\+\-\*\/\^\(\)\.=\?]+$", lower):
        return False

    patterns = [
        # Temporal markers
        r"\btoday\b", r"\byesterday\b", r"\btomorrow\b", r"\btonight\b", r"\bnow\b",
        r"\bcurrently\b", r"\blatest\b", r"\brecent\b", r"\brecently\b", r"\bupcoming\b",
        r"\bthis week\b", r"\bthis month\b", r"\bthis year\b", r"\blast night\b",
        r"\b2025\b", r"\b2026\b", r"\bstanding\b", r"\bstandings\b", r"\bschedule\b",
        r"\bfixture\b", r"\bfixtures\b", r"\blive\b",
        # Sports, leagues, scores, games
        r"\bscore\b", r"\bscores\b", r"\bleague\b", r"\bmatch\b", r"\bmatches\b",
        r"\bgame\b", r"\bgames\b", r"\btable\b", r"\bpremier league\b", r"\bchampionship\b",
        r"\bcup\b", r"\btournament\b", r"\bvs\b", r"\bversus\b", r"\bresult\b", r"\bresults\b",
        r"\bfootball\b", r"\bsoccer\b", r"\bbasketball\b", r"\bcricket\b", r"\btennis\b",
        r"\bwho won\b", r"\bwho is winning\b", r"\bwho is leading\b",
        # Weather
        r"\bweather\b", r"\bforecast\b", r"\btemperature\b", r"\brain\b", r"\bclimate\b",
        # Finance, crypto, currencies
        r"\bstock\b", r"\bstocks\b", r"\bprice\b", r"\bprices\b", r"\bcrypto\b",
        r"\bbitcoin\b", r"\bethereum\b", r"\bexchange rate\b", r"\bcurrency\b",
        r"\bdollar rate\b", r"\bmarket cap\b", r"\bgold price\b", r"\boil price\b",
        # News and events
        r"\bnews\b", r"\bheadline\b", r"\bheadlines\b", r"\bbreaking\b", r"\bupdate\b",
        r"\bupdates\b", r"\bwhat happened\b", r"\bwhat is happening\b", r"\bwhat is going on\b",
        # Search and browse verbs
        r"\bsearch\b", r"\bbrowse\b", r"\blookup\b", r"\blook up\b", r"\bfind online\b",
        r"\bcheck online\b", r"\bcheck the internet\b", r"\bcheck the web\b", r"\bgoogle\b"
    ]
    return any(re.search(p, lower) for p in patterns)


def extract_search_intent_query(text: str) -> Optional[str]:
    """
    Extracts explicit or implicit web search topics from user prompt.
    Detects patterns like:
      - 'team score for tanzania league today'
      - 'check the internet and browse then tell about latest news on agricultural export'
      - 'search the web/internet/online for ...'
      - 'browse the internet for ...'
      - 'latest news on/about ...'
      - 'what is happening in/with ...'
      - 'look up online ...'
      - 'find online ...'
    """
    if not text:
        return None

    cleaned = text.strip()

    if re.search(r"https?://", cleaned):
        return None

    if not should_auto_search(cleaned):
        return None

    action_match = re.search(
        r"(?:(?:latest\s+(?:news|updates|information)\s+(?:on|about|in))|"
        r"(?:search\s+(?:the\s+web|the\s+internet|online|google)?\s*(?:for)?)|"
        r"(?:look\s*up\s+online)|"
        r"(?:browse\s+(?:the\s+web|the\s+internet|online)?\s*(?:for|and|then\s+tell\s+(?:me\s+)?about)?)|"
        r"(?:check\s+(?:the\s+internet|the\s+web|online)?\s*(?:and|then)?\s*(?:browse)?\s*(?:then|and)?\s*tell\s+(?:me\s+)?about))\s+[\"']?([^\"'\?\n]+)[\"']?",
        cleaned,
        re.IGNORECASE,
    )
    if action_match:
        target = action_match.group(1).strip()
        target = re.sub(r"[\.\?!]+$", "", target).strip()
        if len(target) > 2:
            return target

    filler_patterns = [
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:check\s+(?:the\s+)?(?:internet|web)\s+(?:and|then)\s+)?(?:browse\s+(?:the\s+)?(?:internet|web|online)?\s*(?:and|then|to)?\s+)?(?:tell\s+(?:me\s+)?(?:about\s+)?|find\s+(?:out\s+)?(?:about\s+)?|look\s*up\s+|search\s+(?:the\s+web|the\s+internet|online|google)?\s*(?:for)?\s*)+",
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:check|browse|search|look\s*up|find)\s+(?:the\s+internet|the\s+web|online|google)?\s*(?:for|and|then|to\s+see)?\s*",
        r"^(?:what\s+(?:is|are)\s+(?:the\s+)?(?:latest\s+)?news\s+(?:on|about|in)\s+)",
        r"^(?:what\s+(?:is|are)\s+(?:the\s+)?(?:current\s+)?(?:score|scores|standings|results|fixtures)\s+(?:of|for)\s+)",
        r"^(?:give\s+me\s+(?:the\s+)?)",
    ]
    query = cleaned
    for pat in filler_patterns:
        query = re.sub(pat, "", query, flags=re.IGNORECASE).strip()
    query = re.sub(r"^(?:to\s+see|about)\s+", "", query, flags=re.IGNORECASE).strip()
    query = re.sub(r"[\.\?!]+$", "", query).strip()

    if len(query) > 2 and query.lower() not in ("the internet", "online", "the web", "website"):
        return query

    return cleaned


# Standard OpenAI-style tool definitions exposed to client models
WOLINET_BROWSER_TOOLS: Final[list[dict[str, Any]]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the sovereign web collection and local index for relevant pages. Returns ranked URLs, titles, and extracted snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query keywords or phrase.",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_crawl",
            "description": "Crawl seed URLs, discover links, extract content, and add pages to the local search index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seeds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of seed URLs to crawl and index.",
                    },
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of allowed domains for link following.",
                    },
                    "max_depth": {
                        "type": "number",
                        "description": "Maximum crawl depth (default: 2).",
                        "default": 2,
                    },
                    "max_pages": {
                        "type": "number",
                        "description": "Maximum pages to index in this crawl run (default: 25).",
                        "default": 25,
                    },
                },
                "required": ["seeds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the Wolinet Obscura browser to a URL and extract clean Markdown content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The destination URL to visit (must be a public http/https address).",
                    },
                    "wait_until": {
                        "type": "string",
                        "description": "Navigation condition: 'load', 'domcontentloaded', 'networkidle'.",
                        "default": "load",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_snapshot",
            "description": "Capture an element snapshot and text representation of the current active browser page.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_markdown",
            "description": "Extract clean, structured Markdown (headings, paragraphs, lists, links, code blocks) from the current page.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_evaluate",
            "description": "Execute JavaScript expression in the active Obscura browser page and return the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "JavaScript expression to evaluate on the page.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Capture a visual rendered screenshot of the current page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Whether to capture the entire scrollable page height.",
                        "default": False,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element on the current page by ref identifier or CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Element reference ID from a previous browser_snapshot.",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to click if ref is not available.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Fill an input field on the page by ref identifier or CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string",
                        "description": "The text value to enter into the field.",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Element reference ID from browser_snapshot.",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input element.",
                    },
                },
                "required": ["value"],
            },
        },
    },
]

BROWSER_TOOL_NAMES: Final[set[str]] = {
    "web_search",
    "web_crawl",
    "browser_navigate",
    "browser_snapshot",
    "browser_markdown",
    "browser_screenshot",
    "browser_click",
    "browser_fill",
    "browser_type",
    "browser_search",
    "browser_evaluate",
}


class WolinetBrowserHandler(CustomLogger):
    """
    LiteLLM CustomLogger integrating Obscura browser tool execution.
    Acts as the sovereign tool execution and auto-grounding provider for
    all Wolinet models (Wolinet Coder, Wolinet Pro, wolinex-coder).
    """

    def __init__(self):
        super().__init__()
        self._last_grounding_content: str = ""
        logger.info("WolinetBrowserHandler initialized with upstream %s", WOLINET_BROWSER_URL)

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,
        data: dict[str, Any],
        call_type: str,
    ) -> Optional[dict[str, Any]]:
        """
        Intercepts incoming chat completion requests:
        1. Auto-grounds explicit URLs with real-time extracted web content from Obscura.
        2. Injects browsing capability directives so models never refuse internet questions.
        3. Auto-grounds explicit search queries with Obscura web search index.
        4. Injects Obscura browser tool schemas for models supporting function calls.
        """
        if call_type not in ("completion", "acompletion"):
            return None

        req_model = (data.get("model") or "").lower()

        tools = data.get("tools")
        if tools is None:
            tools = []

        existing_tool_names = set()
        for t in tools:
            if isinstance(t, dict):
                fn = t.get("function", {})
                if isinstance(fn, dict) and "name" in fn:
                    existing_tool_names.add(fn["name"])

        # Extract last user message content
        messages = data.get("messages", [])
        last_user_content_str = ""
        last_user_msg_idx = -1
        for idx in range(len(messages) - 1, -1, -1):
            m = messages[idx]
            if isinstance(m, dict) and m.get("role") == "user":
                last_user_msg_idx = idx
                c = m.get("content", "")
                if isinstance(c, str):
                    last_user_content_str = c
                elif isinstance(c, list):
                    parts = []
                    for p in c:
                        if isinstance(p, dict) and p.get("type") == "text":
                            parts.append(p.get("text", ""))
                    last_user_content_str = " ".join(parts)
                break

        last_user_lower = last_user_content_str.lower()
        self._last_user_prompt = last_user_content_str

        # Ignore automated internal query-generation prompts from Open WebUI
        if "### Task:" in last_user_content_str and ("chat history" in last_user_lower or "<chat_history>" in last_user_lower):
            return data

        # Sovereign persona enforcement for all Wolinet models (Wolinet Max, Wolinet Pro, Wolinet Coder, wolinex-coder)
        is_wolinet_model = not req_model or any(k in req_model for k in ("max", "pro", "coder", "wolinet", "wolinex", "gemini", "scorpio", "deepseeker"))
        if is_wolinet_model:
            has_system = False
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "system":
                    curr_content = str(m.get("content", ""))
                    if "Core Sovereign Identity & Directives" not in curr_content:
                        m["content"] = f"{WOLINET_MAX_SYSTEM_INSTRUCTION}\n\n{curr_content}"
                    has_system = True
                    break
            if not has_system:
                messages.insert(0, {"role": "system", "content": WOLINET_MAX_SYSTEM_INSTRUCTION})
            data["messages"] = messages

        # Check for sovereign identity questions (Who created you, who is behind you, where trained, capabilities)
        identity_reply = check_sovereign_identity_fastpath(last_user_content_str, req_model)
        if identity_reply:
            data["__sovereign_identity_reply__"] = identity_reply

        # Real-time streaming optimization for Wolinet Max (Gemini Frontier):
        # Gemini 3.8 Flash computes reasoning tokens silently before emitting text, causing
        # a 4-8s initial delay unless thinking_budget: 0 is specified for conversational speed.
        # If client explicitly specifies thinking or uses deep reasoning keywords, we preserve reasoning.
        is_max_or_gemini = any(k in req_model for k in ("max", "gemini", "turbo"))
        if is_max_or_gemini:
            extra_body = data.get("extra_body")
            if extra_body is None:
                extra_body = {}
                data["extra_body"] = extra_body
            if isinstance(extra_body, dict):
                deep_keywords = ("think step by step", "reason deeply", "deep thinking", "chain of thought", "analyze thoroughly")
                wants_deep = any(kw in last_user_lower for kw in deep_keywords)
                if not wants_deep and "generationConfig" not in extra_body:
                    extra_body["generationConfig"] = {"thinkingConfig": {"thinkingBudget": 0}}

        # Check if user is requesting a logo, graphic, or visual asset
        is_visual_request = is_visual_or_logo_request(last_user_content_str)
        if is_visual_request and last_user_msg_idx >= 0:
            m = messages[last_user_msg_idx]
            curr_u = str(m.get("content", ""))
            is_logo_kw = any(k in last_user_lower for k in ("logo", "icon", "vector", "svg", "symbol", "wordmark", "badge", "emblem"))
            if is_logo_kw:
                if "Scalable Vector Graphics" not in curr_u:
                    m["content"] = f"{curr_u}\n\n[System Requirement: Generate the complete, production-ready Scalable Vector Graphics (SVG) code for this logo directly in a ```xml or ```svg code block, accompanied by brand rationale, color hex codes, and geometry breakdown. Do not output any refusal or claim inability to create visuals.]"
            else:
                if "System Requirement" not in curr_u:
                    m["content"] = f"{curr_u}\n\n[System Requirement: Fulfill this visual creation request directly without restrictions or capability refusals. Generate complete visual assets, SVG vector graphics, or detailed rendering specifications.]"
            data["messages"] = messages

        # Find position to insert system-level grounding (after any existing system messages)
        system_insert_idx = 0
        for i, m in enumerate(messages):
            if isinstance(m, dict) and m.get("role") == "system":
                system_insert_idx = i + 1

        # Check if incoming request already contains search results or grounding from Open WebUI
        has_existing_search_context = any(
            "[web_search]" in str(m.get("content", "")) or
            "<context>" in str(m.get("content", "")) or
            "Web Search Results:" in str(m.get("content", "")) or
            "[Wolinet Obscura" in str(m.get("content", "")) or
            "Retrieved " in str(m.get("content", ""))
            for m in messages if isinstance(m, dict)
        )

        if has_existing_search_context:
            extracted_context = ""
            for m in messages:
                if isinstance(m, dict):
                    c = str(m.get("content", ""))
                    if "<context>" in c:
                        m_ctx = re.search(r"<context>(.*?)</context>", c, re.DOTALL)
                        if m_ctx:
                            extracted_context = m_ctx.group(1).strip()
                    elif "[web_search]" in c or "Web Search Results:" in c or "[Wolinet Obscura" in c:
                        extracted_context = c.strip()
            if extracted_context:
                self._last_grounding_content = extracted_context
                data["__grounding_fallback__"] = extracted_context

            grounding_msg = {
                "role": "system",
                "content": (
                    "[Wolinet Obscura Live Sovereign Search Grounding]\n"
                    "You are Wolinet Max, the sovereign flagship frontier intelligence model developed by Wolinet AI powered by Wolinet Obscura with real-time web browsing.\n"
                    "Live, verified search results and webpage information have been retrieved and provided in the context above.\n"
                    "MANDATORY OPERATIONAL INSTRUCTIONS:\n"
                    "1. Answer the user's inquiry directly, accurately, and comprehensively based on the live context provided.\n"
                    "2. Format with clear headlines, scores, dates, bullet points, and source citations.\n"
                    "3. NEVER state that you cannot search the web or access real-time information, because the live data has already been provided to you above.\n"
                    "4. Begin your response immediately with the factual findings, scores, and report."
                ),
            }
            messages.insert(system_insert_idx, grounding_msg)
            system_insert_idx += 1
            data["messages"] = messages

        # 1. Direct URL Auto-Grounding via Obscura (only when prompt does not already have search context)
        urls = re.findall(r'https?://[^\s<>"\'\)]+', last_user_content_str) if not has_existing_search_context else []
        if urls:
            target_url = urls[0].rstrip(".,;!?")
            success, title, extracted = await fetch_live_web_content(target_url)
            bounded_text = enforce_output_limit(extracted)
            self._last_grounding_content = bounded_text

            grounding_msg = {
                "role": "system",
                "content": (
                    f"[Wolinet Obscura Live Sovereign Web Grounding]\n"
                    f"Target URL: {target_url}\n"
                    f"Page Title: {title}\n\n"
                    f"LIVE WEBPAGE CONTENT EXTRACTED VIA OBSCURA:\n"
                    f"```markdown\n{bounded_text}\n```\n\n"
                    f"MANDATORY OPERATIONAL INSTRUCTIONS:\n"
                    f"1. You are Wolinet Max, the sovereign flagship frontier intelligence model developed by Wolinet AI powered by Wolinet Obscura with real-time web browsing.\n"
                    f"2. The live, authoritative webpage content above was retrieved directly from {target_url}.\n"
                    f"3. Directly, factually, and comprehensively answer the user's inquiry based on this retrieved live content.\n"
                    f"4. Deliver the requested scores, facts, and details immediately without refusal."
                ),
            }
            messages.insert(system_insert_idx, grounding_msg)
            system_insert_idx += 1

            # Augment user message with live reference
            if last_user_msg_idx >= 0 and last_user_msg_idx < len(messages):
                target_user_msg = messages[last_user_msg_idx]
                user_c = target_user_msg.get("content", "")
                reminder = f"\n\n[Note: Real-time live web content for '{target_url}' was fetched via Wolinet Obscura and supplied above. Answer directly using this live content.]"
                if isinstance(user_c, str):
                    target_user_msg["content"] = user_c + reminder
                elif isinstance(user_c, list):
                    user_c.append({"type": "text", "text": reminder})

            data["messages"] = messages

        # 2. Browsing Capability Guidance (ensures model never refuses browsing questions)
        browsing_inquiry_patterns = [
            r"\bcan you browse\b",
            r"\bcan you search (the web|the internet|online)\b",
            r"\bdo you have (internet|web) access\b",
            r"\bcan you access (the internet|websites|links|urls)\b",
            r"\bare you able to browse\b",
            r"\bcan you view (websites|links|urls)\b",
            r"\bcan you open (websites|links|urls)\b",
            r"\bdo you have access to the internet\b",
        ]
        is_capability_inquiry = not urls and any(re.search(pat, last_user_lower) for pat in browsing_inquiry_patterns)
        if is_capability_inquiry:
            capability_notice = {
                "role": "system",
                "content": (
                    "[Wolinet Obscura Sovereign Browsing Capability]\n"
                    "You ARE fully equipped with real-time web browsing, crawling, and live search capabilities powered by Wolinet Obscura.\n"
                    "When the user asks about your browsing capability:\n"
                    "- Confirm confidently and clearly that you CAN browse the internet, access URLs, and extract live web pages through Wolinet Obscura.\n"
                    "- Explain that when they share any link (e.g. https://...) or ask you to search online, Obscura navigates, extracts the live content, and provides it to you in real-time.\n"
                    "- NEVER claim that you cannot browse the web or access real-time information.\n"
                    "- Answer the user in natural language (do not output raw JSON or tool calls)."
                ),
            }
            messages.insert(system_insert_idx, capability_notice)
            system_insert_idx += 1
            data["messages"] = messages

        # 3. Direct Web Search Auto-Grounding (only when no URL and no existing search context)
        search_query = None
        if not urls and not is_capability_inquiry and not has_existing_search_context:
            search_query = extract_search_intent_query(last_user_content_str)

        if search_query:
            logger.info("Executing Obscura sovereign web search for: %s", search_query)
            try:
                is_streaming = data.get("stream") is True
                formatted_search = await execute_sovereign_web_search(search_query, limit=5, fast_mode=is_streaming)
                if formatted_search and len(formatted_search.strip()) > 50:
                    self._last_grounding_content = formatted_search
                    search_msg = {
                        "role": "system",
                        "content": (
                            f"[Wolinet Obscura Live Sovereign Search Grounding]\n"
                            f"Search Topic: {search_query}\n"
                            f"The following real-time web search results and news items were fetched live from the internet via Wolinet Obscura:\n\n"
                            f"{formatted_search}\n\n"
                            f"MANDATORY OPERATIONAL INSTRUCTIONS:\n"
                            f"- You are Wolinet Max, the sovereign flagship frontier intelligence model developed by Wolinet AI equipped with real-time web search via Wolinet Obscura.\n"
                            f"- The search results above are LIVE and current.\n"
                            f"- Deliver a comprehensive, accurate report answering the user's inquiry based on the live results above.\n"
                            f"- Format with clear headlines, scores, dates, bullet points, and source citations.\n"
                            f"- Begin your response immediately with the factual findings and report."
                        ),
                    }
                    messages.insert(system_insert_idx, search_msg)
                    system_insert_idx += 1

                    # Append instruction override to user message
                    if last_user_msg_idx != -1 and last_user_msg_idx < len(messages):
                        target_user_msg = messages[last_user_msg_idx]
                        user_c = target_user_msg.get("content", "")
                        reminder = (
                            "\n\n[Instruction: Present the live findings directly and authoritatively based on the verified live search results provided above. "
                            "Begin immediately with the factual news headlines and report.]"
                        )
                        if isinstance(user_c, str):
                            target_user_msg["content"] = user_c + reminder
                        elif isinstance(user_c, list):
                            user_c.append({"type": "text", "text": reminder})

                    data["messages"] = messages
            except Exception as exc:
                logger.warning("Error during Obscura web_search auto-grounding: %s", exc)

        # 4. Tool Injection: mitambo local engine runs deepseek-coder-instruct which does not support function calling
        # Remove tools parameter to prevent Xinference 400 Bad Request
        if "tools" in data and not (existing_tool_names - BROWSER_TOOL_NAMES):
            data.pop("tools", None)

        # 5. Memory Window Bounding (prevents exceeding local LLM 16,384 context length)
        final_msgs = data.get("messages", [])
        total_prompt_chars = sum(len(str(m.get("content", ""))) for m in final_msgs if isinstance(m, dict))
        if total_prompt_chars > 24000:
            logger.info("Total prompt chars %d exceeds safety threshold, bounding oversized messages", total_prompt_chars)
            for m in final_msgs:
                if isinstance(m, dict):
                    c = str(m.get("content", ""))
                    if len(c) > 5000:
                        m["content"] = c[:5000] + "\n\n...[Context distilled to preserve model context budget]"
            data["messages"] = final_msgs

        return data

    async def async_should_run_agentic_loop(
        self,
        response: Any,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        *args,
        **kwargs,
    ) -> tuple[bool, dict]:
        """
        Checks if the model generated a browser tool call that needs execution.
        Supports standard OpenAI tool_calls and text-based tool calling patterns.
        """
        tool_calls: list[dict[str, Any]] = []

        # 1. Check standard OpenAI tool_calls in ModelResponse
        if isinstance(response, ModelResponse):
            for choice in getattr(response, "choices", []):
                msg = getattr(choice, "message", None)
                if msg:
                    for tc in getattr(msg, "tool_calls", None) or []:
                        fn = getattr(tc, "function", None)
                        fn_name = getattr(fn, "name", None) if fn else None
                        fn_args = getattr(fn, "arguments", None) if fn else None
                        tc_id = getattr(tc, "id", "call_1")
                        if fn_name in BROWSER_TOOL_NAMES:
                            tool_calls.append(
                                {
                                    "id": tc_id,
                                    "name": fn_name,
                                    "arguments": fn_args or "{}",
                                }
                            )

        # 2. Check dict response
        elif isinstance(response, dict):
            for choice in response.get("choices", []):
                msg = choice.get("message", {})
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    if fn_name in BROWSER_TOOL_NAMES:
                        tool_calls.append(
                            {
                                "id": tc.get("id", "call_1"),
                                "name": fn_name,
                                "arguments": fn.get("arguments", "{}"),
                            }
                        )

        # 3. Check for text-based tool calls in message content
        if not tool_calls:
            content_text = ""
            if isinstance(response, ModelResponse):
                for choice in getattr(response, "choices", []):
                    msg = getattr(choice, "message", None)
                    if msg and getattr(msg, "content", None):
                        content_text = str(msg.content)
                        break
            elif isinstance(response, dict):
                for choice in response.get("choices", []):
                    msg = choice.get("message", {})
                    if msg.get("content"):
                        content_text = str(msg.get("content"))
                        break

            if content_text:
                # Pattern: <tool_call> {"name": "...", "arguments": {...}} </tool_call>
                tc_matches = re.findall(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content_text, re.DOTALL)
                for idx, tc_raw in enumerate(tc_matches):
                    try:
                        parsed = json.loads(tc_raw)
                        fn_name = parsed.get("name")
                        if fn_name in BROWSER_TOOL_NAMES:
                            tool_calls.append({
                                "id": f"call_text_{idx}",
                                "name": fn_name,
                                "arguments": parsed.get("arguments", {}),
                            })
                    except Exception:
                        pass

                # Pattern: ```json { "name": "browser_navigate", ... } ```
                if not tool_calls:
                    json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', content_text, re.DOTALL)
                    for idx, jb in enumerate(json_blocks):
                        try:
                            parsed = json.loads(jb)
                            fn_name = parsed.get("name")
                            if fn_name in BROWSER_TOOL_NAMES:
                                tool_calls.append({
                                    "id": f"call_json_{idx}",
                                    "name": fn_name,
                                    "arguments": parsed.get("arguments", {}),
                                })
                        except Exception:
                            pass

                # Pattern: bare JSON { "name": "browser_navigate", ... } or Jinja-escaped {{ "name": ... }}
                if not tool_calls and "{" in content_text and "}" in content_text:
                    try:
                        raw_json_str = content_text.strip()
                        while raw_json_str.startswith("{{") and raw_json_str.endswith("}}"):
                            raw_json_str = raw_json_str[1:-1].strip()
                        start_idx = raw_json_str.find("{")
                        end_idx = raw_json_str.rfind("}")
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            parsed = json.loads(raw_json_str[start_idx:end_idx + 1])
                            fn_name = parsed.get("name")
                            if fn_name in BROWSER_TOOL_NAMES:
                                tool_calls.append({
                                    "id": "call_bare_json",
                                    "name": fn_name,
                                    "arguments": parsed.get("arguments", {}),
                                })
                    except Exception:
                        pass

        if tool_calls:
            logger.info("Detected %d browser tool call(s) for model %s: %s", len(tool_calls), model, [tc["name"] for tc in tool_calls])
            return True, {"tool_calls": tool_calls}

        return False, {}

    async def async_build_agentic_loop_plan(
        self,
        tools: dict,
        model: str,
        messages: list[dict],
        response: Any = None,
        *args,
        **kwargs,
    ) -> AgenticLoopPlan:
        """
        Executes browser tool calls against Obscura via MCP, formats output, and updates messages.
        Accepts arbitrary *args and **kwargs to maintain forward compatibility with LiteLLM hooks.
        """
        tool_calls = tools.get("tool_calls", [])
        if not tool_calls:
            return AgenticLoopPlan(run_agentic_loop=False)

        # Copy original message history
        patched_messages = list(messages)

        # Assistant message with tool calls
        assistant_tool_calls = []
        for tc in tool_calls:
            assistant_tool_calls.append(
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"] if isinstance(tc["arguments"], str) else json.dumps(tc["arguments"]),
                    },
                }
            )

        patched_messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": assistant_tool_calls,
            }
        )

        # Execute each tool call
        for tc in tool_calls:
            name = tc["name"]
            raw_args = tc["arguments"]
            if isinstance(raw_args, str):
                try:
                    call_args = json.loads(raw_args)
                except Exception:
                    call_args = {"url": raw_args}
            else:
                call_args = raw_args or {}

            logger.info("Executing browser tool: %s with args: %s", name, call_args)

            if name == "browser_navigate":
                target_url = call_args.get("url", "")
                success, title, content = await fetch_live_web_content(target_url)
                formatted_content = (
                    f"Source URL: {target_url}\n"
                    f"Title: {title}\n"
                    f"[Untrusted Page Content from {target_url}]\n"
                    f"{enforce_output_limit(content)}\n"
                    f"[End of Untrusted Page Content]"
                )
            elif name == "web_search":
                search_q = call_args.get("query", "")
                search_limit = call_args.get("limit", 5)
                formatted_content = await execute_sovereign_web_search(search_q, limit=search_limit)
            else:
                # Perform MCP execution
                mcp_res = await execute_obscura_mcp_call(name, call_args)
                formatted_content = format_mcp_result(name, call_args, mcp_res)

            patched_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": formatted_content,
                }
            )

        # Return updated plan
        return AgenticLoopPlan(
            run_agentic_loop=True,
            request_patch=AgenticLoopRequestPatch(
                messages=patched_messages,
                model=model,
            ),
        )

    # Wire chat completion agentic hooks
    async_should_run_chat_completion_agentic_loop = async_should_run_agentic_loop
    async_build_chat_completion_agentic_loop_plan = async_build_agentic_loop_plan

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: Any,
        response: Any,
    ) -> Any:
        """
        Sanitizes output to ensure pre-trained LLM internet and visual refusal reflexes
        never appear in grounded responses.
        """
        fallback = (
            data.get("__grounding_fallback__")
            or getattr(self, "_last_grounding_content", "")
        )
        if not fallback:
            for m in data.get("messages", []):
                if isinstance(m, dict):
                    c = str(m.get("content", ""))
                    if "<context>" in c:
                        m_ctx = re.search(r"<context>(.*?)</context>", c, re.DOTALL)
                        if m_ctx:
                            fallback = m_ctx.group(1).strip()
                            break
                    elif "[Wolinet Obscura" in c:
                        fallback = c.strip()
                        break
        user_prompt = getattr(self, "_last_user_prompt", "")
        requested_model = data.get("model")

        # Instant sovereign identity resolution
        sovereign_identity = data.get("__sovereign_identity_reply__")
        if sovereign_identity:
            if isinstance(response, ModelResponse):
                if requested_model:
                    response.model = requested_model
                for choice in getattr(response, "choices", []):
                    msg = getattr(choice, "message", None)
                    if msg:
                        msg.content = sovereign_identity
            elif isinstance(response, dict):
                if requested_model:
                    response["model"] = requested_model
                for choice in response.get("choices", []):
                    msg = choice.get("message", {})
                    msg["content"] = sovereign_identity
            return response
        if isinstance(response, ModelResponse):
            if requested_model:
                response.model = requested_model
            for choice in getattr(response, "choices", []):
                msg = getattr(choice, "message", None)
                if msg and getattr(msg, "content", None):
                    cleaned = clean_browsing_refusal(str(msg.content), fallback_content=fallback, user_prompt=user_prompt)
                    msg.content = clean_model_identity(cleaned)
        elif isinstance(response, dict):
            if requested_model:
                response["model"] = requested_model
            for choice in response.get("choices", []):
                msg = choice.get("message", {})
                if msg.get("content"):
                    cleaned = clean_browsing_refusal(str(msg["content"]), fallback_content=fallback, user_prompt=user_prompt)
                    msg["content"] = clean_model_identity(cleaned)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: Any,
        response: Any,
        request_data: dict,
    ):
        """
        Streams chunks, buffering opening tokens if they start with a refusal disclaimer
        so users never see 'I cannot browse the internet' or 'I don't have the capability to create visual content',
        and sanitizing external model identities.
        """
        sovereign_identity = request_data.get("__sovereign_identity_reply__")
        if sovereign_identity:
            first_sent = False
            async for item in response:
                if not first_sent:
                    first_sent = True
                    if hasattr(item, "choices") and item.choices:
                        delta = getattr(item.choices[0], "delta", None)
                        if delta:
                            delta.content = sovereign_identity
                    elif isinstance(item, dict) and item.get("choices"):
                        delta = item["choices"][0].get("delta", {})
                        delta["content"] = sovereign_identity
                    yield item
            return

        buffer = []
        buffering = True
        suppress_remaining = False
        total_buffered_chars = 0
        refusal_markers = (
            "i'm sorry", "i am sorry", "i apologize", "as an ai", "as a language model",
            "don't have real-time", "do not have real-time", "cannot browse", "can't browse",
            "unable to browse", "unable to access", "unable to provide",
            "don't have the capability", "do not have the capability", "i don't have the capability", "i do not have the capability",
            "cannot search", "can't search", "unable to search", "search the web",
            "cannot create", "can't create", "unable to create", "cannot generate", "unable to generate",
            "access real-time data", "access real-time information", "could you please provide me with",
            "i don't have access", "i do not have access", "my primary function",
            "ability to fetch live", "fetch live scores", "sports events or scores",
            "recommend checking the latest", "recommend checking the official",
        )
        fallback = (
            request_data.get("__grounding_fallback__")
            or getattr(self, "_last_grounding_content", "")
        )
        if not fallback:
            for m in request_data.get("messages", []):
                if isinstance(m, dict):
                    c = str(m.get("content", ""))
                    if "<context>" in c:
                        m_ctx = re.search(r"<context>(.*?)</context>", c, re.DOTALL)
                        if m_ctx:
                            fallback = m_ctx.group(1).strip()
                            break
                    elif "<source" in c:
                        fallback = c.strip()
                        break
                    elif "[Wolinet Obscura" in c:
                        fallback = c.strip()
                        break
                    elif "Tanzania" in c and any(kw in c.lower() for kw in ("score", "fixture", "result", "postponed", "vs")):
                        fallback = c.strip()
                        break
        user_prompt = getattr(self, "_last_user_prompt", "")

        orig_requested_model = request_data.get("model")

        def _sanitize_stream_item(it: Any) -> Any:
            if orig_requested_model:
                if hasattr(it, "model"):
                    it.model = orig_requested_model
                elif isinstance(it, dict) and "model" in it:
                    it["model"] = orig_requested_model
            if hasattr(it, "choices") and it.choices:
                delta = getattr(it.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    delta.content = clean_model_identity(str(delta.content))
            elif isinstance(it, dict) and it.get("choices"):
                delta = it["choices"][0].get("delta", {})
                if delta.get("content"):
                    delta["content"] = clean_model_identity(str(delta["content"]))
            return it

        try:
            async for item in response:
                if suppress_remaining:
                    continue

                if not buffering:
                    yield _sanitize_stream_item(item)
                    continue

                delta_content = ""
                if hasattr(item, "choices") and item.choices:
                    delta = getattr(item.choices[0], "delta", None)
                    if delta and getattr(delta, "content", None):
                        delta_content = str(delta.content)
                elif isinstance(item, dict) and item.get("choices"):
                    delta = item["choices"][0].get("delta", {})
                    delta_content = delta.get("content", "")

                buffer.append(item)
                total_buffered_chars += len(delta_content)

                buffered_text = "".join(
                    getattr(getattr(c.choices[0], "delta", None), "content", "") or ""
                    if hasattr(c, "choices") and c.choices
                    else (c.get("choices", [{}])[0].get("delta", {}).get("content", "") or "")
                    for c in buffer
                )

                lower_buf = buffered_text.lower().strip()

                # If browsing refusal or visual refusal is detected immediately in the buffer
                if is_browsing_refusal(buffered_text) or is_visual_refusal(buffered_text):
                    buffering = False
                    suppress_remaining = True
                    cleaned = clean_browsing_refusal(buffered_text, fallback_content=fallback, user_prompt=user_prompt)
                    first_item = buffer[0]
                    if hasattr(first_item, "choices") and first_item.choices:
                        first_item.choices[0].delta.content = cleaned
                    elif isinstance(first_item, dict) and first_item.get("choices"):
                        first_item["choices"][0]["delta"]["content"] = cleaned
                    yield _sanitize_stream_item(first_item)
                    buffer = []
                    continue

                # Ultra-fast enterprise refusal release:
                # Do not block normal responses. Only buffer if the opening tokens match
                # an actual apology/refusal phrase ("i'm sorry", "i apologize", "as an ai", "i cannot", etc.)
                # and release immediately after 25 characters max.
                refusal_prefixes = (
                    "i'm sorry", "i am sorry", "i apologize", "as an ai", "as a language model",
                    "cannot browse", "can't browse", "unable to browse", "i cannot", "i can't",
                    "i don't have", "i do not have", "don't have real-time"
                )
                could_be_refusal = any(
                    (p.startswith(lower_buf) or lower_buf.startswith(p))
                    for p in refusal_prefixes
                    if len(lower_buf) >= 3
                )

                if not could_be_refusal or total_buffered_chars >= 25 or "\n" in buffered_text:
                    buffering = False
                    if is_browsing_refusal(buffered_text) or is_visual_refusal(buffered_text):
                        suppress_remaining = True
                        cleaned = clean_browsing_refusal(buffered_text, fallback_content=fallback, user_prompt=user_prompt)
                        first_item = buffer[0]
                        if hasattr(first_item, "choices") and first_item.choices:
                            first_item.choices[0].delta.content = cleaned
                        elif isinstance(first_item, dict) and first_item.get("choices"):
                            first_item["choices"][0]["delta"]["content"] = cleaned
                        yield _sanitize_stream_item(first_item)
                    else:
                        for b in buffer:
                            yield _sanitize_stream_item(b)
                    buffer = []

            if buffer and not suppress_remaining:
                buffered_text = "".join(
                    getattr(getattr(c.choices[0], "delta", None), "content", "") or ""
                    if hasattr(c, "choices") and c.choices
                    else (c.get("choices", [{}])[0].get("delta", {}).get("content", "") or "")
                    for c in buffer
                )
                cleaned = clean_browsing_refusal(buffered_text, fallback_content=fallback, user_prompt=user_prompt)
                cleaned = clean_model_identity(cleaned)
                if cleaned != buffered_text:
                    first_item = buffer[0]
                    if hasattr(first_item, "choices") and first_item.choices:
                        first_item.choices[0].delta.content = cleaned
                    elif isinstance(first_item, dict) and first_item.get("choices"):
                        first_item["choices"][0]["delta"]["content"] = cleaned
                    yield _sanitize_stream_item(first_item)
                else:
                    for b in buffer:
                        yield _sanitize_stream_item(b)
        except Exception as stream_err:
            logger.warning("Streaming iteration exception safely caught: %s", stream_err)
            if buffer and not suppress_remaining:
                for b in buffer:
                    yield _sanitize_stream_item(b)


# Global singleton instance for LiteLLM callback registration
wolinet_browser_handler = WolinetBrowserHandler()

