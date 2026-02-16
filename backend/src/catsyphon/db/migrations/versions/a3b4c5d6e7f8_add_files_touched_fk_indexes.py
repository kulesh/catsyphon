"""add_files_touched_fk_indexes

Add indexes on files_touched FK columns (conversation_id, epoch_id,
message_id) to eliminate full table scans on queries filtering by
these columns.

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-02-15 00:00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_files_touched_conversation_id",
        "files_touched",
        ["conversation_id"],
    )
    op.create_index(
        "ix_files_touched_epoch_id",
        "files_touched",
        ["epoch_id"],
    )
    op.create_index(
        "ix_files_touched_message_id",
        "files_touched",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_files_touched_message_id", table_name="files_touched")
    op.drop_index("ix_files_touched_epoch_id", table_name="files_touched")
    op.drop_index("ix_files_touched_conversation_id", table_name="files_touched")
