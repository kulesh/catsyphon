"""Fix conversation_type enum values to lowercase

Revision ID: a3438217bff2
Revises: 22bc7db34fe9
Create Date: 2025-11-18 18:51:15.262075

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3438217bff2"
down_revision: Union[str, None] = "22bc7db34fe9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing conversation_type values from uppercase to lowercase
    # The migration created enum with uppercase values (MAIN, AGENT) but the model expects lowercase (main, agent)
    op.execute(
        """
        UPDATE conversations
        SET conversation_type = LOWER(conversation_type)
        WHERE conversation_type IN ('MAIN', 'AGENT', 'MCP', 'SKILL', 'COMMAND', 'OTHER')
        """
    )

    # Recreate the enum column with lowercase values
    op.alter_column(
        "conversations",
        "conversation_type",
        type_=sa.Enum(
            "main",
            "agent",
            "mcp",
            "skill",
            "command",
            "other",
            name="conversationtype",
            native_enum=False,
        ),
        existing_type=sa.Enum(
            "MAIN",
            "AGENT",
            "MCP",
            "SKILL",
            "COMMAND",
            "OTHER",
            name="conversationtype",
            native_enum=False,
        ),
        existing_nullable=False,
        existing_server_default="main",
    )


def downgrade() -> None:
    # Revert to uppercase values
    op.execute(
        """
        UPDATE conversations
        SET conversation_type = UPPER(conversation_type)
        WHERE conversation_type IN ('main', 'agent', 'mcp', 'skill', 'command', 'other')
        """
    )

    # Recreate the enum column with uppercase values
    op.alter_column(
        "conversations",
        "conversation_type",
        type_=sa.Enum(
            "MAIN",
            "AGENT",
            "MCP",
            "SKILL",
            "COMMAND",
            "OTHER",
            name="conversationtype",
            native_enum=False,
        ),
        existing_type=sa.Enum(
            "main",
            "agent",
            "mcp",
            "skill",
            "command",
            "other",
            name="conversationtype",
            native_enum=False,
        ),
        existing_nullable=False,
        existing_server_default="main",
    )
