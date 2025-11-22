"""add metrics JSONB column to ingestion_jobs

Revision ID: a3a7fe2f4377
Revises: e5adc1b6ec84
Create Date: 2025-11-22 15:58:25.574132

Adds metrics JSONB column to ingestion_jobs table for storing
stage-level performance metrics:
- parse: {duration_ms, method, lines_read}
- canonical: {duration_ms, tokens, cache_hit}
- llm: {duration_ms, prompt_tokens, completion_tokens, cost_usd, cache_hit, error}
- db: {duration_ms, queries_count}
- total: {duration_ms}
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "a3a7fe2f4377"
down_revision: Union[str, None] = "e5adc1b6ec84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add metrics JSONB column with empty dict default
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "metrics",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    # Remove metrics column
    op.drop_column("ingestion_jobs", "metrics")
