"""Database-backed configuration with environment variable defaults."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import reduce
from typing import Any, Optional, Union

import redis
from open_webui.internal.db import Base, get_async_db, get_db
from open_webui.utils.redis import get_redis_connection
from sqlalchemy import JSON, Column, DateTime, Integer, func, select

log = logging.getLogger(__name__)


# ── Model ────────────────────────────────────────────────────────────────────


class ConfigTable(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


# ── Blob ─────────────────────────────────────────────────────────────────────


class ConfigState:
    """In-memory mirror of database configuration with dynamic schema adaptation."""

    __slots__ = ('_data',)

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @property
    def snapshot(self) -> dict:
        return self._data

    def read(self, path: str) -> Any:
        return reduce(
            lambda n, k: n.get(k) if isinstance(n, dict) else None,
            path.split('.'),
            self._data,
        )

    def write(self, path: str, value: Any) -> None:
        keys = path.split('.')
        reduce(lambda d, k: d.setdefault(k, {}), keys[:-1], self._data)[keys[-1]] = value

    def replace(self, data: dict) -> None:
        self._data = data

    @staticmethod
    def _walk_flat(data: dict, prefix: str = '') -> dict[str, Any]:
        result = {}
        for key, value in data.items():
            path = f'{prefix}.{key}' if prefix else str(key)
            if isinstance(value, dict) and value and not path.endswith('.api_configs'):
                result.update(ConfigState._walk_flat(value, path))
            else:
                result[path] = value
        return result

    def load(self) -> dict:
        data: dict[str, Any] = {}
        try:
            with get_db() as db:
                from sqlalchemy import inspect, text

                inspector = inspect(db.bind)
                table_names = set(inspector.get_table_names())

                # 1. Base from legacy config_old if present
                if 'config_old' in table_names:
                    try:
                        row = db.execute(text('SELECT data FROM config_old ORDER BY id DESC LIMIT 1')).first()
                        if row and row[0]:
                            raw = row[0]
                            data = raw if isinstance(raw, dict) else json.loads(raw)
                    except Exception as e:
                        log.debug('Could not read from config_old: %s', e)

                # 2. Overlay from config table (either per-key rows or single blob)
                if 'config' in table_names:
                    try:
                        cols = {c['name'] for c in inspector.get_columns('config')}
                        if {'key', 'value'}.issubset(cols):
                            rows = db.execute(text('SELECT key, value FROM config')).all()
                            for k, v in rows:
                                if isinstance(v, str):
                                    try:
                                        v = json.loads(v)
                                    except Exception:
                                        pass
                                keys = k.split('.')
                                reduce(lambda d, kp: d.setdefault(kp, {}), keys[:-1], data)[keys[-1]] = v
                        elif {'id', 'data'}.issubset(cols):
                            row = db.execute(text('SELECT data FROM config ORDER BY id DESC LIMIT 1')).first()
                            if row and row[0]:
                                raw = row[0]
                                data = raw if isinstance(raw, dict) else json.loads(raw)
                    except Exception as e:
                        log.warning('Could not read from config table: %s', e)

                if data:
                    self._data = data
                    return self._data
        except Exception as exc:
            log.warning('ConfigState.load encountered an exception: %s', exc)

        if not self._data:
            self._data = {'version': 0, 'ui': {}}
        return self._data

    def persist(self, data: dict | None = None) -> None:
        if data is not None:
            self._data = data
        try:
            with get_db() as db:
                import time
                from sqlalchemy import inspect, text

                inspector = inspect(db.bind)
                table_names = set(inspector.get_table_names())
                is_pg = getattr(db.bind.dialect, 'name', '') == 'postgresql'

                if 'config' in table_names:
                    cols = {c['name'] for c in inspector.get_columns('config')}
                    if {'key', 'value'}.issubset(cols):
                        now = int(time.time())
                        flat = self._walk_flat(self._data)
                        sql = (
                            'INSERT INTO config (key, value, updated_at) '
                            'VALUES (:k, CAST(:v AS JSONB), :t) '
                            'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at'
                            if is_pg
                            else 'INSERT INTO config (key, value, updated_at) '
                            'VALUES (:k, :v, :t) '
                            'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at'
                        )
                        for k, v in flat.items():
                            val_json = json.dumps(v)
                            try:
                                db.execute(text(sql), {'k': k, 'v': val_json, 't': now})
                            except Exception:
                                db.rollback()
                                updated = db.execute(
                                    text('UPDATE config SET value = :v, updated_at = :t WHERE key = :k'),
                                    {'k': k, 'v': val_json, 't': now},
                                )
                                if updated.rowcount == 0:
                                    db.execute(
                                        text('INSERT INTO config (key, value, updated_at) VALUES (:k, :v, :t)'),
                                        {'k': k, 'v': val_json, 't': now},
                                    )
                        db.commit()
                    elif {'id', 'data'}.issubset(cols):
                        row = db.query(ConfigTable).first()
                        if row is None:
                            db.add(ConfigTable(data=self._data, version=0))
                        else:
                            row.data, row.updated_at = self._data, datetime.now()
                            db.add(row)
                        db.commit()

                if 'config_old' in table_names:
                    try:
                        db.execute(
                            text(
                                'UPDATE config_old SET data = CAST(:d AS JSON), updated_at = now() '
                                'WHERE id = (SELECT id FROM config_old ORDER BY id DESC LIMIT 1)'
                                if is_pg
                                else 'UPDATE config_old SET data = :d WHERE id = (SELECT id FROM config_old ORDER BY id DESC LIMIT 1)'
                            ),
                            {'d': json.dumps(self._data)},
                        )
                        db.commit()
                    except Exception as e:
                        log.debug('config_old update skipped: %s', e)
        except Exception as exc:
            log.warning('ConfigState.persist encountered an exception: %s', exc)

    async def persist_async(self, data: dict | None = None) -> None:
        if data is not None:
            self._data = data
        try:
            async with get_async_db() as db:
                import time
                from sqlalchemy import inspect, text

                def _get_table_info(conn):
                    insp = inspect(conn)
                    tables = set(insp.get_table_names())
                    cols = {c['name'] for c in insp.get_columns('config')} if 'config' in tables else set()
                    is_pg = getattr(conn.dialect, 'name', '') == 'postgresql'
                    return tables, cols, is_pg

                tables, cols, is_pg = await db.run_sync(_get_table_info)

                if 'config' in tables:
                    if {'key', 'value'}.issubset(cols):
                        now = int(time.time())
                        flat = self._walk_flat(self._data)
                        sql = (
                            'INSERT INTO config (key, value, updated_at) '
                            'VALUES (:k, CAST(:v AS JSONB), :t) '
                            'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at'
                            if is_pg
                            else 'INSERT INTO config (key, value, updated_at) '
                            'VALUES (:k, :v, :t) '
                            'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at'
                        )
                        for k, v in flat.items():
                            val_json = json.dumps(v)
                            try:
                                await db.execute(text(sql), {'k': k, 'v': val_json, 't': now})
                            except Exception:
                                pass
                        await db.commit()
                    elif {'id', 'data'}.issubset(cols):
                        result = await db.execute(select(ConfigTable).limit(1))
                        row = result.scalars().first()
                        if row is None:
                            db.add(ConfigTable(data=self._data, version=0))
                        else:
                            row.data, row.updated_at = self._data, datetime.now()
                            db.add(row)
                        await db.commit()

                if 'config_old' in tables:
                    try:
                        await db.execute(
                            text(
                                'UPDATE config_old SET data = CAST(:d AS JSON), updated_at = now() '
                                'WHERE id = (SELECT id FROM config_old ORDER BY id DESC LIMIT 1)'
                                if is_pg
                                else 'UPDATE config_old SET data = :d WHERE id = (SELECT id FROM config_old ORDER BY id DESC LIMIT 1)'
                            ),
                            {'d': json.dumps(self._data)},
                        )
                        await db.commit()
                    except Exception:
                        pass
        except Exception as exc:
            log.warning('ConfigState.persist_async encountered an exception: %s', exc)

    def clear(self) -> None:
        try:
            with get_db() as db:
                from sqlalchemy import inspect, text

                inspector = inspect(db.bind)
                table_names = set(inspector.get_table_names())
                if 'config' in table_names:
                    db.execute(text('DELETE FROM config'))
                if 'config_old' in table_names:
                    db.execute(text('DELETE FROM config_old'))
                db.commit()
        except Exception as exc:
            log.warning('ConfigState.clear encountered an exception: %s', exc)

    async def clear_async(self) -> None:
        try:
            async with get_async_db() as db:
                from sqlalchemy import text

                await db.execute(text('DELETE FROM config'))
                await db.commit()
        except Exception as exc:
            log.warning('ConfigState.clear_async encountered an exception: %s', exc)


STATE = ConfigState()


# ── ConfigVar ──────────────────────────────────────────────────────────────────


_persist_enabled: bool = True
_oauth_persist_enabled: bool = False
_all_configs: list[ConfigVar] = []


def initialize(*, enable_persistent: bool = True, enable_oauth_persistent: bool = False) -> dict:
    global _persist_enabled, _oauth_persist_enabled
    _persist_enabled = enable_persistent
    _oauth_persist_enabled = enable_oauth_persistent
    return STATE.load()


class ConfigVar:
    __slots__ = ('env_name', 'config_path', 'env_value', 'config_value', 'value')

    def __init__(self, env_name: str, config_path: str, env_value: Any) -> None:
        self.env_name = env_name
        self.config_path = config_path
        self.env_value = env_value
        self.config_value = STATE.read(config_path)

        if self.config_value is not None and _persist_enabled:
            if config_path.startswith('oauth.') and not _oauth_persist_enabled:
                log.info("Skipping DB value for '%s' (OAuth persistence disabled)", env_name)
                self.value = env_value
            else:
                log.info("'%s' loaded from database", env_name)
                self.value = self.config_value
        else:
            self.value = env_value

        _all_configs.append(self)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f'<ConfigVar {self.env_name}={self.value!r}>'

    @property
    def __dict__(self):  # type: ignore[override]
        raise TypeError(f"ConfigVar('{self.env_name}') cannot be cast to dict; use .value")

    def __getattribute__(self, item: str):
        if item == '__dict__':
            raise TypeError('ConfigVar cannot be cast to dict; use .value')
        return super().__getattribute__(item)

    def refresh(self) -> None:
        current = STATE.read(self.config_path)
        if current is not None:
            self.value = current
            log.info('Refreshed %s → %s', self.env_name, self.value)

    def commit(self) -> None:
        log.info("Persisting '%s'", self.env_name)
        STATE.write(self.config_path, self.value)
        self.config_value = self.value
        STATE.persist()

    async def commit_async(self) -> None:
        log.info("Persisting '%s'", self.env_name)
        STATE.write(self.config_path, self.value)
        self.config_value = self.value
        await STATE.persist_async()


# ── AppConfig ──────────────────────────────────────────────────────────


class AppConfig:
    """Attribute-style container for ConfigVars with optional Redis sync."""

    def __init__(
        self,
        *,
        redis_url: Optional[str] = None,
        redis_sentinels: Optional[list] = None,
        redis_cluster: bool = False,
        redis_key_prefix: str = 'open-webui',
    ) -> None:
        super().__setattr__('_entries', {})
        super().__setattr__('_key_prefix', redis_key_prefix)

        # If sentinels weren't explicitly provided, read from env.
        if redis_sentinels is None:
            from open_webui.env import REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_PORT
            from open_webui.utils.redis import get_sentinels_from_env

            redis_sentinels = get_sentinels_from_env(REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_PORT)

        rc: Union[redis.Redis, redis.cluster.RedisCluster, None] = None
        if redis_url:
            rc = get_redis_connection(redis_url, redis_sentinels or [], redis_cluster, decode_responses=True)
        super().__setattr__('_rc', rc)

    def __setattr__(self, name: str, value: Any) -> None:
        entries: dict = super().__getattribute__('_entries')

        if isinstance(value, ConfigVar):
            entries[name] = value
            return

        if name not in entries:
            entries[name] = ConfigVar(name, f'app.{name.lower()}', value)
            return

        entries[name].value = value

        try:
            asyncio.get_running_loop().create_task(self._write_async(name))
        except RuntimeError:
            entries[name].commit()

        rc = super().__getattribute__('_rc')
        if rc and _persist_enabled:
            prefix = super().__getattribute__('_key_prefix')
            try:
                rc.set(f'{prefix}:config:{name}', json.dumps(entries[name].value))
            except Exception as exc:
                log.error("Redis write failed for '%s': %s", name, exc)

    async def _write_async(self, name: str) -> None:
        try:
            await self._entries[name].commit_async()
        except Exception as exc:
            log.error("Async persist failed for '%s': %s", name, exc)

    def __getattr__(self, name: str) -> Any:
        entries = super().__getattribute__('_entries')
        if name not in entries:
            raise AttributeError(f"No config key '{name}'")

        rc = super().__getattribute__('_rc')
        if rc and _persist_enabled:
            prefix = super().__getattribute__('_key_prefix')
            try:
                raw = rc.get(f'{prefix}:config:{name}')
                if raw is not None:
                    decoded = json.loads(raw)
                    if entries[name].value != decoded:
                        entries[name].value = decoded
                        log.info("Updated '%s' from Redis", name)
            except Exception as exc:
                log.error("Redis read failed for '%s': %s", name, exc)

        return entries[name].value

    def _sync_to_redis(self) -> None:
        rc = super().__getattribute__('_rc')
        if not rc or not _persist_enabled:
            return
        prefix = super().__getattribute__('_key_prefix')
        for name, s in super().__getattribute__('_entries').items():
            try:
                rc.set(f'{prefix}:config:{name}', json.dumps(s.value))
            except Exception as exc:
                log.error("Redis sync failed for '%s': %s", name, exc)
