"""Add backing_models table for LLM tracking

Revision ID: 009_backing_models
Revises: 008_threads
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adds BackingModel table for tracking LLM provider/model information
and links it to conversations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009_backing_models"
down_revision: Union[str, None] = "008_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create backing_models table
    op.create_table(
        "backing_models",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        # Unique constraint on provider + model_id
        sa.UniqueConstraint(
            "provider", "model_id", name="uq_backing_model_provider_model"
        ),
    )

    # Add backing_model_id FK to conversations table
    op.add_column(
        "conversations",
        sa.Column(
            "backing_model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backing_models.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    # Remove backing_model_id from conversations
    op.drop_column("conversations", "backing_model_id")

    # Drop backing_models table
    op.drop_table("backing_models")
