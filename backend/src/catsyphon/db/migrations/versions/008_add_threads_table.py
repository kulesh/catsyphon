"""Add threads table for conversation flow hierarchy

Revision ID: 008_threads
Revises: 007_message_type
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adds Thread table with parent-child hierarchy for tracking main,
agent, and background threads within a session/conversation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008_threads"
down_revision: Union[str, None] = "007_message_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the thread_type enum using raw SQL with IF NOT EXISTS
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE thread_type AS ENUM ('main', 'agent', 'background'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # Create threads table using existing enum
    op.create_table(
        "threads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parent_thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "thread_type",
            postgresql.ENUM(
                "main", "agent", "background", name="thread_type", create_type=False
            ),
            nullable=False,
            server_default="main",
        ),
        sa.Column(
            "spawned_by_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Add thread_id FK to messages table
    op.add_column(
        "messages",
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("threads.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    # Remove thread_id from messages
    op.drop_column("messages", "thread_id")

    # Drop threads table
    op.drop_table("threads")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS thread_type")
