from __future__ import annotations

# Alembic environment configuration runner.
# Coordinates database migrations in both offline and online execution modes.
import logging.config
import logging
import alembic.context
from open_webui.env import DATABASE_URL, LOG_FORMAT
from open_webui.internal.db import extract_ssl_params_from_url, reattach_ssl_params_to_url
from open_webui.models.auths import Auth
from open_webui.models.calendar import Calendar, CalendarEvent, CalendarEventAttendee  # noqa: F401
from sqlalchemy import engine_from_config, pool

alembic_config = alembic.context.config
if alembic_config.config_file_name:
    logging.config.fileConfig(alembic_config.config_file_name, disable_existing_loggers=False)
if LOG_FORMAT == 'json':
    from open_webui.env import JSONFormatter

    for log_handler in logging.root.handlers:
        log_handler.setFormatter(JSONFormatter())
migration_metadata = Auth.metadata
target_db_url = DATABASE_URL
base_url, ssl_query_params = extract_ssl_params_from_url(target_db_url)
if ssl_query_params:
    target_db_url = reattach_ssl_params_to_url(base_url, ssl_query_params)
try:
    import psycopg  # noqa: F401
except ImportError as exc:
    raise RuntimeError('The PostgreSQL psycopg driver is required for Alembic migrations') from exc

if target_db_url.startswith('postgresql://'):
    target_db_url = target_db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
elif target_db_url.startswith('postgres://'):
    target_db_url = target_db_url.replace('postgres://', 'postgresql+psycopg://', 1)
alembic_config.set_main_option('sqlalchemy.url', target_db_url.replace('%', '%%'))


def run_migrations_offline() -> None:
    """Execute Alembic migrations in offline mode (outputs raw SQL DDL)."""
    db_connection_url = alembic_config.get_main_option('sqlalchemy.url')
    alembic.context.configure(
        url=db_connection_url,
        target_metadata=migration_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with alembic.context.begin_transaction():
        alembic.context.run_migrations()


def _get_engine_connectable():
    """Build the database engine based on target URL and authentication credentials."""
    return engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )


def _sanitize_alembic_version(connection) -> None:
    """Ensure alembic_version only holds known local migration revisions.
    If a foreign/unrecognized revision (e.g. 'd4c1a8e37b62') exists, reset it to head."""
    try:
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect, text

        inspector = inspect(connection)
        if not inspector.has_table('alembic_version'):
            return

        script_dir = ScriptDirectory.from_config(alembic_config)
        known_revisions = {rev.revision for rev in script_dir.walk_revisions()}
        heads = script_dir.get_heads()
        head_rev = heads[0] if heads else None
        if not head_rev:
            return

        rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        for row in rows:
            rev_in_db = row[0]
            if rev_in_db and rev_in_db not in known_revisions:
                logging.getLogger("alembic.env").warning(
                    f"Orphan Alembic revision '{rev_in_db}' detected in database. Resetting to head '{head_rev}'."
                )
                connection.execute(
                    text("UPDATE alembic_version SET version_num = :head WHERE version_num = :old"),
                    {"head": head_rev, "old": rev_in_db},
                )
                if hasattr(connection, 'commit'):
                    connection.commit()
    except Exception as exc:
        logging.getLogger("alembic.env").warning(f"Could not verify alembic_version: {exc}")


def run_migrations_online() -> None:
    """Execute migrations against a live database connection."""
    live_connectable = _get_engine_connectable()
    with live_connectable.connect() as live_connection:
        _sanitize_alembic_version(live_connection)
        alembic.context.configure(
            connection=live_connection,
            target_metadata=migration_metadata,
        )
        with alembic.context.begin_transaction():
            alembic.context.run_migrations()


# Alembic execution entrypoint branch
if alembic.context.is_offline_mode():
    run_migrations_offline()  # run in offline mode
if not alembic.context.is_offline_mode():
    run_migrations_online()  # run in online mode
