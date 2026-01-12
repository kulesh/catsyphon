"""Add message_type enum to messages table

Revision ID: 007_message_type
Revises: 006_author_role
Create Date: 2025-12-26

Phase 0 of collector integration: Type system alignment.
Adopts aiobscura's MessageType enum with 8 values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_message_type"
down_revision: Union[str, None] = "006_author_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    message_type_enum = sa.Enum(
        "prompt",
        "response",
        "tool_call",
        "tool_result",
        "plan",
        "summary",
        "context",
        "error",
        name="message_type",
        create_type=True,
    )
    message_type_enum.create(op.get_bind(), checkfirst=True)

    # Add column as nullable first
    op.add_column(
        "messages",
        sa.Column(
            "message_type",
            sa.Enum(
                "prompt",
                "response",
                "tool_call",
                "tool_result",
                "plan",
                "summary",
                "context",
                "error",
                name="message_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # Backfill based on role and content analysis
    # Note: tool_calls and tool_results columns are JSONB arrays
    op.execute(
        """
        UPDATE messages SET message_type = CASE
            WHEN role = 'user' THEN 'prompt'::message_type
            WHEN role = 'system' THEN 'context'::message_type
            WHEN tool_calls IS NOT NULL AND tool_calls::text != '[]' THEN 'tool_call'::message_type
            WHEN tool_results IS NOT NULL AND tool_results::text != '[]' THEN 'tool_result'::message_type
            ELSE 'response'::message_type
        END
    """
    )

    # Make column NOT NULL after backfill
    op.alter_column("messages", "message_type", nullable=False)


def downgrade() -> None:
    op.drop_column("messages", "message_type")
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS message_type")
