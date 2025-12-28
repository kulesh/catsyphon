"""Add is_builtin flag to collector_configs

Revision ID: 013_is_builtin_collector
Revises: 012_collector_session
Create Date: 2025-12-28

Adds is_builtin column to identify the auto-created local watcher collector.
This enables simpler UX where watch directories just toggle "Use API Mode"
without needing to manually enter collector credentials.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_is_builtin_collector"
down_revision: Union[str, None] = "012_collector_session"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_builtin flag - identifies auto-created local watcher collector
    op.add_column(
        "collector_configs",
        sa.Column(
            "is_builtin",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )
    op.create_index(
        "ix_collector_configs_is_builtin",
        "collector_configs",
        ["is_builtin"],
    )


def downgrade() -> None:
    op.drop_index("ix_collector_configs_is_builtin", table_name="collector_configs")
    op.drop_column("collector_configs", "is_builtin")
