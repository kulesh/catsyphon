"""Add automation_recommendations table for AI Advisor

Revision ID: 016_add_automation_recommendations
Revises: 015_make_message_role_nullable
Create Date: 2025-12-29

Stores LLM-detected automation opportunities (slash commands, MCP servers, etc.)
that could help users optimize their coding workflows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_add_recs"
down_revision: Union[str, None] = "015_make_message_role_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("recommendation_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="2", nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "suggested_implementation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False),
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_automation_recommendations_confidence",
        ),
        sa.CheckConstraint(
            "priority >= 0 AND priority <= 4",
            name="ck_automation_recommendations_priority",
        ),
    )
    op.create_index(
        "ix_automation_recommendations_conversation_id",
        "automation_recommendations",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_recommendations_type",
        "automation_recommendations",
        ["recommendation_type"],
        unique=False,
    )
    op.create_index(
        "ix_automation_recommendations_status",
        "automation_recommendations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automation_recommendations_status",
        table_name="automation_recommendations",
    )
    op.drop_index(
        "ix_automation_recommendations_type",
        table_name="automation_recommendations",
    )
    op.drop_index(
        "ix_automation_recommendations_conversation_id",
        table_name="automation_recommendations",
    )
    op.drop_table("automation_recommendations")
