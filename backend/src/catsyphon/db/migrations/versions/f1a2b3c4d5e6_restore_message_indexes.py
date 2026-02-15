"""restore_message_indexes

Restore indexes on messages table that were accidentally dropped by
migration c7103d6e90ac (collector multi-tenancy). Also add a functional
index on conversations for the COALESCE(end_time, start_time) ORDER BY
expression used by the conversations list query.

Revision ID: f1a2b3c4d5e6
Revises: b7f2c5d8e901
Create Date: 2026-02-15 00:00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "b7f2c5d8e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Restore indexes dropped by c7103d6e90ac
    op.create_index(
        "idx_messages_conversation_id",
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "idx_messages_epoch_id",
        "messages",
        ["epoch_id"],
        unique=False,
    )
    op.create_index(
        "idx_messages_timestamp",
        "messages",
        ["timestamp"],
        unique=False,
    )
    # Composite covering index for conversation detail page queries
    op.create_index(
        "idx_messages_conversation_timestamp",
        "messages",
        ["conversation_id", "timestamp"],
        unique=False,
        postgresql_ops={"timestamp": "DESC"},
    )
    # Functional index on conversations for ORDER BY COALESCE(end_time, start_time)
    op.execute(
        "CREATE INDEX idx_conversations_last_activity "
        "ON conversations (COALESCE(end_time, start_time) DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_conversations_last_activity")
    op.drop_index("idx_messages_conversation_timestamp", table_name="messages")
    op.drop_index("idx_messages_timestamp", table_name="messages")
    op.drop_index("idx_messages_epoch_id", table_name="messages")
    op.drop_index("idx_messages_conversation_id", table_name="messages")
