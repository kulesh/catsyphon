"""add_otel_events_table

Revision ID: b7f2c5d8e901
Revises: 98a9f0c2b4d1
Create Date: 2026-01-28 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7f2c5d8e901"
down_revision: Union[str, None] = "98a9f0c2b4d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "otel_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("source_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column("event_timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("severity_text", sa.String(length=64), nullable=True),
        sa.Column("severity_number", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(length=32), nullable=True),
        sa.Column("span_id", sa.String(length=16), nullable=True),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "resource_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "scope_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("otel_events_workspace_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("otel_events_pkey")),
    )
    op.create_index(
        op.f("ix_otel_events_event_name"),
        "otel_events",
        ["event_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_otel_events_event_timestamp"),
        "otel_events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_otel_events_source_conversation_id"),
        "otel_events",
        ["source_conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_otel_events_workspace_id"),
        "otel_events",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_otel_events_workspace_id"), table_name="otel_events")
    op.drop_index(op.f("ix_otel_events_source_conversation_id"), table_name="otel_events")
    op.drop_index(op.f("ix_otel_events_event_timestamp"), table_name="otel_events")
    op.drop_index(op.f("ix_otel_events_event_name"), table_name="otel_events")
    op.drop_table("otel_events")
