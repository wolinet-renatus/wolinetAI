"""Update user table

Revision ID: b10670c03dd5
Revises: 2f1211949ecc
Create Date: 2025-11-28 04:55:31.737538

"""

import json
import time
from typing import Sequence, Union

import open_webui.internal.db
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'b10670c03dd5'
down_revision: Union[str, None] = '2f1211949ecc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Ad-hoc table references for Core DML ─────────────────────────────────
# These are lightweight table() / column() references used only inside this
# migration for SELECT / UPDATE / INSERT — they do NOT create or alter
# anything on disk.

_user = sa.table(
    'user',
    sa.column('id', sa.Text),
    sa.column('oauth_sub', sa.Text),
    sa.column('oauth', JSONB),
    sa.column('api_key', sa.Text),
    sa.column('info', sa.Text),
    sa.column('settings', sa.Text),
)

_api_key = sa.table(
    'api_key',
    sa.column('id', sa.Text),
    sa.column('user_id', sa.Text),
    sa.column('key', sa.Text),
    sa.column('created_at', sa.BigInteger),
    sa.column('updated_at', sa.BigInteger),
)


def _convert_column_to_json(table: str, column: str):
    op.alter_column(
        table,
        column,
        type_=JSONB(),
        postgresql_using=f'NULLIF({column}, \'\')::jsonb',
    )


def _convert_column_to_text(table: str, column: str):
    op.alter_column(
        table,
        column,
        type_=sa.Text(),
        postgresql_using=f'{column}::text',
    )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    user_columns = {c['name'] for c in inspector.get_columns('user')}

    # ── Add new columns (idempotent) ──────────────────────────────────
    for col_name, col_type in [
        ('profile_banner_image_url', sa.Text()),
        ('timezone', sa.String()),
        ('presence_state', sa.String()),
        ('status_emoji', sa.String()),
        ('status_message', sa.Text()),
        ('status_expires_at', sa.BigInteger()),
        ('oauth', JSONB()),
    ]:
        if col_name not in user_columns:
            op.add_column('user', sa.Column(col_name, col_type, nullable=True))

    # Convert info (TEXT/JSONField) → JSON (skip if already JSON)
    user_col_types = {c['name']: c['type'] for c in inspector.get_columns('user')}
    if isinstance(user_col_types.get('info'), sa.Text):
        _convert_column_to_json('user', 'info')
    # Convert settings (TEXT/JSONField) → JSON (skip if already JSON)
    if isinstance(user_col_types.get('settings'), sa.Text):
        _convert_column_to_json('user', 'settings')

    # ── Create api_key table (idempotent) ─────────────────────────────
    if 'api_key' not in existing_tables:
        op.create_table(
            'api_key',
            sa.Column('id', sa.Text(), primary_key=True, unique=True),
            sa.Column('user_id', sa.Text(), sa.ForeignKey('user.id', ondelete='CASCADE')),
            sa.Column('key', sa.Text(), unique=True, nullable=False),
            sa.Column('data', JSONB(), nullable=True),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('last_used_at', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('updated_at', sa.BigInteger(), nullable=False),
        )

    # ── Migrate oauth_sub → oauth JSON (only if old column still exists)
    if 'oauth_sub' in user_columns:
        rows = conn.execute(sa.select(_user.c.id, _user.c.oauth_sub).where(_user.c.oauth_sub.is_not(None))).fetchall()

        for uid, oauth_sub in rows:
            if oauth_sub:
                provider, sub = oauth_sub.split('@', 1) if '@' in oauth_sub else ('oidc', oauth_sub)
                conn.execute(
                    sa.update(_user).where(_user.c.id == uid).values(oauth=json.dumps({provider: {'sub': sub}}))
                )

    # ── Migrate api_key column → api_key table (only if old column still exists)
    if 'api_key' in user_columns:
        rows = conn.execute(sa.select(_user.c.id, _user.c.api_key).where(_user.c.api_key.is_not(None))).fetchall()
        now = int(time.time())

        for uid, key_val in rows:
            if key_val:
                conn.execute(
                    sa.insert(_api_key).values(
                        id=f'key_{uid}',
                        user_id=uid,
                        key=key_val,
                        created_at=now,
                        updated_at=now,
                    )
                )

    # ── Drop legacy columns (idempotent) ──────────────────────────────
    cols_to_drop = {'api_key', 'oauth_sub'} & user_columns
    if cols_to_drop:
        with op.batch_alter_table('user') as batch_op:
            for col in cols_to_drop:
                batch_op.drop_column(col)


def downgrade() -> None:
    op.add_column('user', sa.Column('oauth_sub', sa.Text(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.select(_user.c.id, _user.c.oauth).where(_user.c.oauth.is_not(None))).fetchall()

    for uid, oauth in rows:
        try:
            data = json.loads(oauth)
            provider = list(data.keys())[0]
            sub = data[provider].get('sub')
            oauth_sub = f'{provider}@{sub}'
        except Exception:
            oauth_sub = None

        conn.execute(sa.update(_user).where(_user.c.id == uid).values(oauth_sub=oauth_sub))

    op.drop_column('user', 'oauth')

    # --- Restore api_key field ---
    op.add_column('user', sa.Column('api_key', sa.String(), nullable=True))

    keys = conn.execute(sa.select(_api_key.c.user_id, _api_key.c.key)).fetchall()
    for uid, key in keys:
        conn.execute(sa.update(_user).where(_user.c.id == uid).values(api_key=key))

    op.drop_table('api_key')

    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('profile_banner_image_url')
        batch_op.drop_column('timezone')

        batch_op.drop_column('presence_state')
        batch_op.drop_column('status_emoji')
        batch_op.drop_column('status_message')
        batch_op.drop_column('status_expires_at')

    # Convert info (JSON) → TEXT
    _convert_column_to_text('user', 'info')
    # Convert settings (JSON) → TEXT
    _convert_column_to_text('user', 'settings')
