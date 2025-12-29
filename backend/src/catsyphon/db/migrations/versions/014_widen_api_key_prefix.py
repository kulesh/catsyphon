"""Widen api_key_prefix column

Revision ID: 014_widen_api_key_prefix
Revises: 013_is_builtin_collector
Create Date: 2025-12-28

Widens api_key_prefix from VARCHAR(10) to VARCHAR(16) to accommodate
the cs_live_xxxx format (12 characters).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_widen_api_key_prefix"
down_revision: Union[str, None] = "013_is_builtin_collector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen api_key_prefix from VARCHAR(10) to VARCHAR(16)
    op.alter_column(
        "collector_configs",
        "api_key_prefix",
        type_=sa.String(16),
        existing_type=sa.String(10),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert to VARCHAR(10) - may truncate data
    op.alter_column(
        "collector_configs",
        "api_key_prefix",
        type_=sa.String(10),
        existing_type=sa.String(16),
        existing_nullable=False,
    )
