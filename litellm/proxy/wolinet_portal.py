"""
Wolinet AI — Sovereign Developer Portal & Unified Authentication Engine
========================================================================
Provides self-hosted, offline-resilient authentication, API key governance,
developer dashboard panels (Overview, API Keys, Models, Status, Reference),
and self-hosted AI Assistant powered by the default sovereign model.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from typing import Any

log = logging.getLogger("litellm.proxy.wolinet_portal")


def get_default_model() -> str:
    """Return the configured sovereign default model (defaulting to wolinex-coder)."""
    return (
        os.getenv("DEFAULT_MODEL")
        or os.getenv("DEFAULT_MODELS", "wolinex-coder").split(",")[0].strip()
        or "wolinex-coder"
    )


import psycopg  # PostgreSQL adapter — do NOT reintroduce sqlite3
from psycopg.rows import dict_row


class WolinetPortalDB:
    """
    Unified PostgreSQL storage for sovereign portal users, keys, and sessions.
    Stores all data directly in PostgreSQL (DATABASE_URL), avoiding local SQLite files.
    """

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise RuntimeError("DATABASE_URL must point to the PostgreSQL cluster")
        if self.db_url.startswith("postgres://"):
            self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
        self.conn_str = self.db_url.replace("postgresql+psycopg://", "postgresql://")
        self._init_db()

    def _get_conn(self):
        return psycopg.connect(self.conn_str, row_factory=dict_row)

    def _init_db(self) -> None:
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS portal_users (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            email TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            salt TEXT NOT NULL,
                            role TEXT NOT NULL DEFAULT 'developer',
                            api_key TEXT NOT NULL,
                            created_at DOUBLE PRECISION NOT NULL
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS portal_keys (
                            id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            key TEXT UNIQUE NOT NULL,
                            key_alias TEXT,
                            max_budget DOUBLE PRECISION DEFAULT 25.0,
                            spend DOUBLE PRECISION DEFAULT 0.0,
                            duration TEXT,
                            expires_at DOUBLE PRECISION,
                            status TEXT DEFAULT 'active',
                            created_at DOUBLE PRECISION NOT NULL
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS portal_sessions (
                            token TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            expires_at DOUBLE PRECISION NOT NULL,
                            created_at DOUBLE PRECISION NOT NULL
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_portal_users_email ON portal_users(email)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_portal_keys_user ON portal_keys(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_portal_keys_key ON portal_keys(key)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_portal_sessions_token ON portal_sessions(token)")
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to initialize PostgreSQL portal DB: %s", exc)

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        if not salt:
            salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return pw_hash, salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        test_hash, _ = WolinetPortalDB.hash_password(password, salt)
        return secrets.compare_digest(test_hash, password_hash)

    def register_user(self, name: str, email: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
        email = email.strip().lower()
        name = name.strip()
        if not email or not password or not name:
            return None, "Name, email, and password are required."
        if len(password) < 6:
            return None, "Password must be at least 6 characters long."

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM portal_users WHERE email = %s", (email,))
                existing = cur.fetchone()
                if existing:
                    return None, "Account already exists. Please sign in."

                user_id = f"usr_{secrets.token_hex(8)}"
                pw_hash, salt = self.hash_password(password)
                api_key = f"sk-wolinet-{secrets.token_hex(16)}"
                now = time.time()

                cur.execute(
                    "INSERT INTO portal_users (id, name, email, password_hash, salt, role, api_key, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (user_id, name, email, pw_hash, salt, "developer", api_key, now)
                )

                key_id = f"key_{secrets.token_hex(8)}"
                cur.execute(
                    "INSERT INTO portal_keys (id, user_id, key, key_alias, max_budget, spend, status, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (key_id, user_id, api_key, "Primary Sovereign Key", 25.0, 0.0, "active", now)
                )

                session_token = f"wlst_{secrets.token_urlsafe(32)}"
                cur.execute(
                    "INSERT INTO portal_sessions (token, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                    (session_token, user_id, now + 30 * 86400, now)
                )
            conn.commit()

            return {
                "id": user_id,
                "name": name,
                "email": email,
                "role": "developer",
                "api_key": api_key,
                "token": session_token,
                "credits": {"allocated": 25.0, "spent": 0.0, "remaining": 25.0, "currency": "USD"}
            }, None

    def authenticate_user(self, email: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
        email = email.strip().lower()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM portal_users WHERE email = %s", (email,))
                row = cur.fetchone()
                if not row or not self.verify_password(password, row["password_hash"], row["salt"]):
                    return None, "Invalid email or password."

                user_id = row["id"]
                now = time.time()
                session_token = f"wlst_{secrets.token_urlsafe(32)}"
                cur.execute(
                    "INSERT INTO portal_sessions (token, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                    (session_token, user_id, now + 30 * 86400, now)
                )

                cur.execute("SELECT max_budget, spend FROM portal_keys WHERE user_id = %s", (user_id,))
                keys = cur.fetchall()
            conn.commit()

            alloc = sum(k["max_budget"] or 0.0 for k in keys) if keys else 25.0
            spent = sum(k["spend"] or 0.0 for k in keys) if keys else 0.0
            rem = max(0.0, round(alloc - spent, 4))

            return {
                "id": user_id,
                "name": row["name"],
                "email": row["email"],
                "role": row["role"],
                "api_key": row["api_key"],
                "token": session_token,
                "credits": {"allocated": alloc, "spent": spent, "remaining": rem, "currency": "USD"}
            }, None

    def get_session_user(self, token_or_key: str) -> dict[str, Any] | None:
        if not token_or_key:
            return None
        token_or_key = token_or_key.strip()

        master_keys = [
            k for k in [os.getenv("LITELLM_MASTER_KEY"), os.getenv("WOLINET_GATEWAY_MASTER_KEY"), os.getenv("OPENAI_API_KEY")]
            if k
        ]
        if token_or_key in master_keys:
            return {
                "id": "admin",
                "name": "Cluster Administrator",
                "email": "admin@wolinet.local",
                "role": "admin",
                "api_key": token_or_key,
                "token": token_or_key,
                "credits": {"allocated": 1000.0, "spent": 0.0, "remaining": 1000.0, "currency": "USD"}
            }

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                now = time.time()
                user_id = None
                if token_or_key.startswith("wlst_"):
                    cur.execute("SELECT user_id, expires_at FROM portal_sessions WHERE token = %s", (token_or_key,))
                    s = cur.fetchone()
                    if s and s["expires_at"] > now:
                        user_id = s["user_id"]
                elif token_or_key.startswith("sk-"):
                    cur.execute("SELECT user_id FROM portal_keys WHERE key = %s AND status = 'active'", (token_or_key,))
                    k = cur.fetchone()
                    if k:
                        user_id = k["user_id"]
                    else:
                        cur.execute("SELECT id FROM portal_users WHERE api_key = %s", (token_or_key,))
                        u = cur.fetchone()
                        if u:
                            user_id = u["id"]

                if not user_id:
                    return None

                cur.execute("SELECT * FROM portal_users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                if not user:
                    return None

                cur.execute("SELECT max_budget, spend FROM portal_keys WHERE user_id = %s", (user_id,))
                keys = cur.fetchall()

            alloc = sum(k["max_budget"] or 0.0 for k in keys) if keys else 25.0
            spent = sum(k["spend"] or 0.0 for k in keys) if keys else 0.0

            return {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "api_key": user["api_key"],
                "token": token_or_key if token_or_key.startswith("wlst_") else None,
                "credits": {"allocated": alloc, "spent": spent, "remaining": max(0.0, round(alloc - spent, 4)), "currency": "USD"}
            }

    def regenerate_key(self, user_id: str) -> str | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                new_key = f"sk-wolinet-{secrets.token_hex(16)}"
                now = time.time()
                cur.execute("UPDATE portal_users SET api_key = %s WHERE id = %s", (new_key, user_id))
                key_id = f"key_{secrets.token_hex(8)}"
                cur.execute(
                    "INSERT INTO portal_keys (id, user_id, key, key_alias, max_budget, spend, status, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (key_id, user_id, new_key, "Regenerated Key", 25.0, 0.0, "active", now)
                )
            conn.commit()
            return new_key

    def create_key(self, user_id: str, alias: str = "", max_budget: float = 25.0, duration: str = "30d") -> dict[str, Any]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                new_key = f"sk-wolinet-{secrets.token_hex(16)}"
                key_id = f"key_{secrets.token_hex(8)}"
                now = time.time()
                cur.execute(
                    "INSERT INTO portal_keys (id, user_id, key, key_alias, max_budget, spend, duration, status, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (key_id, user_id, new_key, alias or "Developer Key", max_budget, 0.0, duration, "active", now)
                )
            conn.commit()
            return {
                "key": new_key,
                "key_alias": alias or "Developer Key",
                "max_budget": max_budget,
                "spend": 0.0,
                "status": "active",
                "created_at": now
            }

    def list_keys(self, user_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM portal_keys WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
                rows = cur.fetchall()
            res = []
            for r in rows:
                k_str = r["key"]
                masked = k_str[:7] + "..." + k_str[-4:] if len(k_str) > 11 else k_str
                res.append({
                    "token": masked,
                    "key": masked,
                    "full_key": k_str,
                    "key_alias": r["key_alias"] or "Sovereign Key",
                    "max_budget": r["max_budget"],
                    "spend": r["spend"],
                    "status": r["status"],
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["created_at"]))
                })
            return res

    def logout_session(self, token: str) -> None:
        if not token:
            return
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM portal_sessions WHERE token = %s", (token,))
            conn.commit()


# Global portal DB instance
portal_db = WolinetPortalDB()


def build_developer_portal_html(
    title: str,
    openapi_url: str = "/openapi.json",
    scalar_js_url: str = "/swagger/scalar.js",
    favicon_url: str = "/swagger/favicon.png",
    default_model: str | None = None,
) -> str:
    """
    Renders the unified, state-of-the-art Wolinet AI Developer Portal.
    Includes sidebar menu navigation (Overview, API Keys, Models, Status, Reference),
    key generation and budget management, live OpenAPI docs, and self-hosted AI Assistant.
    """
    def_model = default_model or get_default_model()

    html_path = os.path.join(os.path.dirname(__file__), "wolinet_portal.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as ex:  # noqa: BLE001
        log.error("Failed to load portal HTML template from %s: %s", html_path, ex)
        return "<html><body><h1>Developer Portal Error</h1><p>Template file missing.</p></body></html>"

    return (
        template
        .replace("__TITLE__", title)
        .replace("__OPENAPI_URL__", openapi_url)
        .replace("__SCALAR_JS_URL__", scalar_js_url)
        .replace("__FAVICON_URL__", favicon_url)
        .replace("__DEFAULT_MODEL__", def_model)
    )
