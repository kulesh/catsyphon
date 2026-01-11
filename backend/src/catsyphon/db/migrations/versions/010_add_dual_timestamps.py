"""Add dual timestamps (emitted_at, observed_at) to messages

Revision ID: 010_dual_timestamps
Revises: 009_backing_models
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adds emitted_at (when message was produced) and observed_at (when parsed)
for accurate timeline reconstruction.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_dual_timestamps"
down_revision: Union[str, None] = "009_backing_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns as nullable first
    op.add_column(
        "messages",
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill: use timestamp for emitted, created_at for observed
    op.execute(
        """
        UPDATE messages SET
            emitted_at = COALESCE(timestamp, created_at),
            observed_at = created_at
    """
    )

    # Make columns NOT NULL after backfill
    op.alter_column("messages", "emitted_at", nullable=False)
    op.alter_column("messages", "observed_at", nullable=False)


def downgrade() -> None:
    op.drop_column("messages", "observed_at")
    op.drop_column("messages", "emitted_at")
