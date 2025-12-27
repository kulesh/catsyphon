"""Add collector session tracking fields to conversations

Revision ID: 012_collector_session
Revises: 011_raw_data
Create Date: 2025-12-27

Adds fields for the collector events protocol to track session state
and enable resumption after disconnect:
- collector_session_id: Original session_id from collector (unique)
- last_event_sequence: Last received sequence number for deduplication
- server_received_at: When last event was received
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_collector_session"
down_revision: Union[str, None] = "011_raw_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add collector_session_id - unique identifier from collector
    op.add_column(
        "conversations",
        sa.Column("collector_session_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_conversations_collector_session_id",
        "conversations",
        ["collector_session_id"],
        unique=True,
    )

    # Add last_event_sequence - for resumption tracking
    op.add_column(
        "conversations",
        sa.Column(
            "last_event_sequence",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )

    # Add server_received_at - when last event was received
    op.add_column(
        "conversations",
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "server_received_at")
    op.drop_column("conversations", "last_event_sequence")
    op.drop_index("ix_conversations_collector_session_id", table_name="conversations")
    op.drop_column("conversations", "collector_session_id")
