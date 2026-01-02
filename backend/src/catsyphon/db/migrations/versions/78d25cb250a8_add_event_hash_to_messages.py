"""add_event_hash_to_messages

Revision ID: 78d25cb250a8
Revises: 97643190a1a5
Create Date: 2026-01-02 00:20:25.540375

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "78d25cb250a8"
down_revision: Union[str, None] = "97643190a1a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add event_hash column for content-based deduplication."""
    op.add_column(
        "messages", sa.Column("event_hash", sa.String(length=32), nullable=True)
    )
    op.create_index(
        op.f("ix_messages_event_hash"), "messages", ["event_hash"], unique=False
    )


def downgrade() -> None:
    """Remove event_hash column."""
    op.drop_index(op.f("ix_messages_event_hash"), table_name="messages")
    op.drop_column("messages", "event_hash")
