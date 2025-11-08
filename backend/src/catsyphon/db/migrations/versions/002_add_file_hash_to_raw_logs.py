"""Add file_hash column to raw_logs for deduplication

Revision ID: 002_file_hash
Revises: 001_initial
Create Date: 2025-11-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_file_hash"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add file_hash column with unique constraint for deduplication."""
    # Add file_hash column (64-char hex string for SHA-256)
    op.add_column(
        "raw_logs",
        sa.Column(
            "file_hash",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
    )

    # Create index for fast hash lookups
    op.create_index(
        "idx_raw_logs_file_hash",
        "raw_logs",
        ["file_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Remove file_hash column and index."""
    op.drop_index("idx_raw_logs_file_hash", table_name="raw_logs")
    op.drop_column("raw_logs", "file_hash")
