from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Literal, Self, overload
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from open_webui.env import (
    DATABASE_ENABLE_SESSION_SHARING,
    DATABASE_POOL_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
    DATABASE_SCHEMA,
    DATABASE_URL,
)
from sqlalchemy import Dialect, Engine, MetaData, create_engine, types
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

log = logging.getLogger(__name__)


def _pop_first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.pop(key, None)
    return values[0] if values else None


def _is_postgres_url(url: str) -> bool:
    return bool(url) and any(url.startswith(p) for p in ('postgresql://', 'postgresql+', 'postgres://'))


def extract_ssl_params_from_url(url: str) -> tuple[str, dict[str, str]]:
    if not _is_postgres_url(url):
        return url, {}

    parsed = urlparse(url)
    qp = parse_qs(parsed.query, keep_blank_values=True)

    sslmode_val = _pop_first(qp, 'sslmode')
    ssl_val = _pop_first(qp, 'ssl')
    ssl_mode = sslmode_val or ssl_val

    ssl_dict: dict[str, str] = {}
    if ssl_mode:
        ssl_dict['sslmode'] = ssl_mode
    for key in ('sslrootcert', 'sslcert', 'sslkey', 'sslcrl'):
        val = _pop_first(qp, key)
        if val:
            ssl_dict[key] = val

    if not ssl_dict:
        return url, ssl_dict

    cleaned_query = urlencode(qp, doseq=True)
    return urlunparse(parsed._replace(query=cleaned_query)), ssl_dict


def reattach_ssl_params_to_url(url_without_ssl: str, ssl_dict: dict[str, str]) -> str:
    if not ssl_dict:
        return url_without_ssl

    parts = [f'{k}={v}' for k, v in ssl_dict.items() if v]
    if not parts:
        return url_without_ssl

    sep = '&' if '?' in url_without_ssl else '?'
    return f'{url_without_ssl}{sep}{"&".join(parts)}'


extract_ssl_mode_from_url = extract_ssl_params_from_url
reattach_ssl_mode_to_url = reattach_ssl_params_to_url


class JSONField(types.TypeDecorator):
    """PostgreSQL JSONB storage for structured columns.

    PostgreSQL JSONB columns are returned by psycopg as native Python dict/list
    objects — NO json.loads() call is required.  The only case where we need to
    parse is if a legacy row somehow contains a raw JSON *string* value (this
    should not happen after the JSONB migration, but we keep a narrow guard so
    old data doesn't crash on read).
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        # Pass dicts/lists straight through; SQLAlchemy + psycopg handles serialization.
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        # JSONB columns already arrive as Python objects from the driver.
        # Only parse if we receive a raw string (shouldn't happen post-migration).
        if isinstance(value, str):
            stripped = value.lstrip()
            if stripped.startswith(('{', '[')):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    log.warning(
                        'Malformed legacy JSON string returned from PostgreSQL JSONB column; '
                        'returning raw string value to avoid data loss.'
                    )
        return value

    def copy(self, **kwargs: Any) -> Self:
        return JSONField()


def _require_postgres_url(url: str) -> str:
    if not url or 'sqlite' in url.lower():
        raise RuntimeError(
            'SQLite is not supported. Set WEBUI_DATABASE_URL or DATABASE_URL to a PostgreSQL '
            'connection string.'
        )
    if not _is_postgres_url(url):
        raise RuntimeError(
            f'Unsupported DATABASE_URL scheme. PostgreSQL is required, got: {url.split(":", 1)[0]}'
        )
    return url


_require_postgres_url(DATABASE_URL)

_url_without_ssl, _ssl_dict = extract_ssl_params_from_url(DATABASE_URL)
SQLALCHEMY_DATABASE_URL = reattach_ssl_params_to_url(_url_without_ssl, _ssl_dict) if _ssl_dict else DATABASE_URL

try:
    import psycopg  # noqa: F401
except ImportError as exc:
    raise RuntimeError('The PostgreSQL psycopg driver is required') from exc

if SQLALCHEMY_DATABASE_URL.startswith('postgresql://'):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
elif SQLALCHEMY_DATABASE_URL.startswith('postgres://'):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)


def _make_async_url(url: str) -> str:
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)
    return url


@overload
def _build_engine(url: str, *, async_mode: Literal[True]) -> AsyncEngine: ...
@overload
def _build_engine(url: str, *, async_mode: Literal[False]) -> Engine: ...
def _build_engine(url: str, *, async_mode: bool) -> AsyncEngine | Engine:
    pool_size = DATABASE_POOL_SIZE if isinstance(DATABASE_POOL_SIZE, int) else 10
    max_overflow = DATABASE_POOL_MAX_OVERFLOW if isinstance(DATABASE_POOL_MAX_OVERFLOW, int) else 20
    timeout = DATABASE_POOL_TIMEOUT if isinstance(DATABASE_POOL_TIMEOUT, int) else 30
    recycle = DATABASE_POOL_RECYCLE if isinstance(DATABASE_POOL_RECYCLE, int) else 3600

    kwargs: dict[str, Any] = {
        'pool_pre_ping': True,
    }
    if pool_size > 0:
        kwargs.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=timeout,
            pool_recycle=recycle,
        )
        if not async_mode:
            kwargs['poolclass'] = QueuePool
    else:
        kwargs['poolclass'] = NullPool

    if async_mode:
        return create_async_engine(url, **kwargs)
    return create_engine(url, **kwargs)


if sys.platform == 'win32':
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

engine = _build_engine(SQLALCHEMY_DATABASE_URL, async_mode=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
metadata_obj = MetaData(schema=DATABASE_SCHEMA)
Base = declarative_base(metadata=metadata_obj)
ScopedSession = scoped_session(SessionLocal)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)

ASYNC_SQLALCHEMY_DATABASE_URL = _make_async_url(SQLALCHEMY_DATABASE_URL)
async_engine = _build_engine(ASYNC_SQLALCHEMY_DATABASE_URL, async_mode=True)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_session():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


@asynccontextmanager
async def get_async_db_context(db: AsyncSession | None = None) -> AsyncGenerator[AsyncSession, None]:
    if isinstance(db, AsyncSession) and DATABASE_ENABLE_SESSION_SHARING:
        yield db
    else:
        async with get_async_db() as session:
            yield session
