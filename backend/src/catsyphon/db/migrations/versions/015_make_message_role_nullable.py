"""Make message role column nullable for non-conversational messages

Revision ID: 015_make_message_role_nullable
Revises: 014_widen_api_key_prefix
Create Date: 2025-12-29

Supports storing non-conversational message types (summaries, file snapshots,
system events, errors) that don't have a traditional user/assistant role.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_make_message_role_nullable"
down_revision: Union[str, None] = "014_widen_api_key_prefix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make role column nullable to support non-conversational messages
    op.alter_column(
        "messages",
        "role",
        existing_type=sa.String(50),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill NULL roles with "system" before making NOT NULL
    op.execute("""
        UPDATE messages SET role = 'system'
        WHERE role IS NULL
    """)

    op.alter_column(
        "messages",
        "role",
        existing_type=sa.String(50),
        nullable=False,
    )
