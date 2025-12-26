"""Add raw_data JSONB column to messages

Revision ID: 011_raw_data
Revises: 010_dual_timestamps
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adds raw_data column for lossless message capture, enabling
reprocessing without losing original data.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011_raw_data"
down_revision: Union[str, None] = "010_dual_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add raw_data column - nullable since historical messages won't have it
    op.add_column(
        "messages",
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "raw_data")
