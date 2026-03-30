"""Add permanently_orphaned column to conversations.

Marks agent conversations whose parent will never be found, so the
linking loop can exclude them at the query level instead of loading
and skipping them every cycle.

Revision ID: e7f8a9b0c1d2
Revises: d4c3b2a1f0e9
Create Date: 2026-03-29 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d4c3b2a1f0e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add column
    op.add_column(
        "conversations",
        sa.Column(
            "permanently_orphaned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # 2. Partial index: efficient lookup of linkable orphans
    op.create_index(
        "ix_conversations_linkable_orphans",
        "conversations",
        ["workspace_id"],
        postgresql_where=sa.text(
            "parent_conversation_id IS NULL AND permanently_orphaned IS NOT TRUE"
        ),
    )

    # 3. Backfill: mark existing maxed-out orphans as permanently orphaned.
    #    These have been retried 10+ times over weeks — parents will never appear.
    op.execute(
        sa.text("""
            UPDATE conversations
            SET permanently_orphaned = true
            WHERE parent_conversation_id IS NULL
              AND conversation_type = 'agent'
              AND agent_metadata ? '_linking_attempts'
              AND (agent_metadata->>'_linking_attempts')::int >= 10
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_linkable_orphans", table_name="conversations")
    op.drop_column("conversations", "permanently_orphaned")
