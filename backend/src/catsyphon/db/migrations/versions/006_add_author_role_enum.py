"""Add author_role enum to messages table

Revision ID: 006_author_role
Revises: 4c258c30a4b8
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adopts aiobscura's AuthorRole enum with 6 values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_author_role"
down_revision: Union[str, None] = "4c258c30a4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    author_role_enum = sa.Enum(
        "human",
        "caller",
        "assistant",
        "agent",
        "tool",
        "system",
        name="author_role",
        create_type=True,
    )
    author_role_enum.create(op.get_bind(), checkfirst=True)

    # Add column as nullable first
    op.add_column(
        "messages",
        sa.Column(
            "author_role",
            sa.Enum(
                "human",
                "caller",
                "assistant",
                "agent",
                "tool",
                "system",
                name="author_role",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # Backfill from existing role column
    # Map: user -> human, system -> system, assistant -> assistant
    op.execute(
        """
        UPDATE messages SET author_role = CASE role
            WHEN 'user' THEN 'human'::author_role
            WHEN 'system' THEN 'system'::author_role
            WHEN 'assistant' THEN 'assistant'::author_role
            ELSE 'assistant'::author_role
        END
    """
    )

    # Make column NOT NULL after backfill
    op.alter_column("messages", "author_role", nullable=False)


def downgrade() -> None:
    op.drop_column("messages", "author_role")
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS author_role")
