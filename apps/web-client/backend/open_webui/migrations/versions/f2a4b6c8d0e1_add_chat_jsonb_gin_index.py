"""add PostgreSQL GIN index for chat payload search

Revision ID: f2a4b6c8d0e1
Revises: 461111b60977
"""

from typing import Sequence, Union

from alembic import op

revision: str = 'f2a4b6c8d0e1'
down_revision: Union[str, None] = '461111b60977'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_content_gin ON chat USING GIN (chat)')


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute('DROP INDEX CONCURRENTLY IF EXISTS idx_chat_content_gin')
