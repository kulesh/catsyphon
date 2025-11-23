"""Extend conversation_type to support metadata

Revision ID: 4c0e1dddfaab
Revises: 0a3f6f60bde8
Create Date: 2025-11-23 17:14:14.496282

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c0e1dddfaab"
down_revision: Union[str, None] = "0a3f6f60bde8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend conversation_type VARCHAR from 7 to 10 characters to support "metadata" (8 chars)
    op.alter_column(
        "conversations",
        "conversation_type",
        type_=sa.String(length=10),
        existing_type=sa.String(length=7),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert back to VARCHAR(7)
    # WARNING: This will fail if there are "metadata" type conversations in the database
    op.alter_column(
        "conversations",
        "conversation_type",
        type_=sa.String(length=7),
        existing_type=sa.String(length=10),
        existing_nullable=False,
    )
