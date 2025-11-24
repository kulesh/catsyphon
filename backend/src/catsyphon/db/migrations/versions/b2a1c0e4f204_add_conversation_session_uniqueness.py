"""Add unique index on (workspace, conversation_type, session_id)

Revision ID: b2a1c0e4f204
Revises: 4c0e1dddfaab
Create Date: 2025-11-24 04:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2a1c0e4f204"
down_revision: Union[str, None] = "4c0e1dddfaab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_conversation_ws_type_session"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect == "postgresql":
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
            ON conversations (
                workspace_id,
                conversation_type,
                (metadata ->> 'session_id')
            )
            """
        )
    else:
        # SQLite/other: use json_extract for session_id from metadata
        op.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
            ON conversations (
                workspace_id,
                conversation_type,
                json_extract(metadata, '$.session_id')
            )
            """
        )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
