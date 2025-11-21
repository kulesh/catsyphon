"""add conversation_canonical table

Revision ID: 005
Revises: a3438217bff2
Create Date: 2025-11-19 23:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "a3438217bff2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create conversation_canonical table for caching canonicalized conversations."""
    op.create_table(
        "conversation_canonical",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("canonical_type", sa.String(length=50), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("source_message_count", sa.Integer(), nullable=False),
        sa.Column("source_token_estimate", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "version",
            "canonical_type",
            name="uq_conversation_version_type",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_conversation_canonical_conversation_id",
        "conversation_canonical",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conversation_canonical_version",
        "conversation_canonical",
        ["version"],
    )
    op.create_index(
        "ix_conversation_canonical_canonical_type",
        "conversation_canonical",
        ["canonical_type"],
    )
    op.create_index(
        "ix_conversation_canonical_generated_at",
        "conversation_canonical",
        ["generated_at"],
    )


def downgrade() -> None:
    """Drop conversation_canonical table."""
    op.drop_index("ix_conversation_canonical_generated_at", table_name="conversation_canonical")
    op.drop_index("ix_conversation_canonical_canonical_type", table_name="conversation_canonical")
    op.drop_index("ix_conversation_canonical_version", table_name="conversation_canonical")
    op.drop_index("ix_conversation_canonical_conversation_id", table_name="conversation_canonical")
    op.drop_table("conversation_canonical")
