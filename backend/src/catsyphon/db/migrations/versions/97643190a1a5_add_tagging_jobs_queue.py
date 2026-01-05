"""add_tagging_jobs_queue

Revision ID: 97643190a1a5
Revises: 016_add_recs
Create Date: 2026-01-01 22:48:10.587971

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97643190a1a5"
down_revision: Union[str, None] = "016_add_recs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tagging_jobs table for async tagging queue
    op.create_table(
        "tagging_jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
    )

    # Index for efficient queue polling: pending jobs ordered by priority and creation time
    op.create_index(
        "ix_tagging_jobs_pending",
        "tagging_jobs",
        ["status", "priority", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Index for looking up jobs by conversation
    op.create_index(
        "ix_tagging_jobs_conversation_id",
        "tagging_jobs",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tagging_jobs_conversation_id", table_name="tagging_jobs")
    op.drop_index("ix_tagging_jobs_pending", table_name="tagging_jobs")
    op.drop_table("tagging_jobs")
