"""Add artifact scanner tables for supplemental data source ingestion.

Revision ID: f2a3b4c5d6e7
Revises: e7f8a9b0c1d2
Create Date: 2026-03-29 19:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "f2a3b4c5d6e7"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # artifact_snapshots — current state per scanned file
    op.create_table(
        "artifact_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "file_size_bytes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("file_mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "scan_status", sa.String(20), nullable=False, server_default="ok"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "source_type",
            "source_path",
            name="uq_artifact_snapshot_ws_type_path",
        ),
    )
    op.create_index(
        "ix_artifact_snapshots_workspace_id",
        "artifact_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        "ix_artifact_snapshots_source_type",
        "artifact_snapshots",
        ["source_type"],
    )
    op.create_index(
        "ix_artifact_snapshots_scanned_at",
        "artifact_snapshots",
        ["scanned_at"],
    )

    # artifact_history — append-only change log
    op.create_table(
        "artifact_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artifact_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("diff_summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("prev_content_hash", sa.String(64), nullable=True),
        sa.Column("new_content_hash", sa.String(64), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_artifact_history_workspace_id",
        "artifact_history",
        ["workspace_id"],
    )
    op.create_index(
        "ix_artifact_history_snapshot_id",
        "artifact_history",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_artifact_history_source_type",
        "artifact_history",
        ["source_type"],
    )
    op.create_index(
        "ix_artifact_history_ws_type_detected",
        "artifact_history",
        ["workspace_id", "source_type", "detected_at"],
    )


def downgrade() -> None:
    op.drop_table("artifact_history")
    op.drop_table("artifact_snapshots")
