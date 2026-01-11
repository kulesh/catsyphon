"""add_recaps_and_weekly_digests

Revision ID: 98a9f0c2b4d1
Revises: 78d25cb250a8
Create Date: 2026-01-02 18:26:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "98a9f0c2b4d1"
down_revision: Union[str, None] = "78d25cb250a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_recaps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "key_files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "blockers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "next_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "canonical_version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("conversation_recaps_conversation_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("conversation_recaps_pkey")),
        sa.UniqueConstraint(
            "conversation_id",
            "version",
            name="uq_conversation_recaps_version",
        ),
    )
    op.create_index(
        op.f("ix_conversation_recaps_conversation_id"),
        "conversation_recaps",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_recaps_generated_at"),
        "conversation_recaps",
        ["generated_at"],
        unique=False,
    )

    op.create_table(
        "weekly_digests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "wins",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "blockers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "highlights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("weekly_digests_workspace_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("weekly_digests_pkey")),
        sa.UniqueConstraint(
            "workspace_id",
            "period_start",
            "period_end",
            "version",
            name="uq_weekly_digest_workspace_period",
        ),
    )
    op.create_index(
        op.f("ix_weekly_digests_workspace_id"),
        "weekly_digests",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_weekly_digests_period_start"),
        "weekly_digests",
        ["period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_weekly_digests_period_end"),
        "weekly_digests",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_weekly_digests_generated_at"),
        "weekly_digests",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_weekly_digests_generated_at"), table_name="weekly_digests")
    op.drop_index(op.f("ix_weekly_digests_period_end"), table_name="weekly_digests")
    op.drop_index(op.f("ix_weekly_digests_period_start"), table_name="weekly_digests")
    op.drop_index(op.f("ix_weekly_digests_workspace_id"), table_name="weekly_digests")
    op.drop_table("weekly_digests")

    op.drop_index(
        op.f("ix_conversation_recaps_generated_at"), table_name="conversation_recaps"
    )
    op.drop_index(
        op.f("ix_conversation_recaps_conversation_id"), table_name="conversation_recaps"
    )
    op.drop_table("conversation_recaps")
