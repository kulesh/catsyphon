"""Add analysis run provenance tracking and artifact links.

Revision ID: d4c3b2a1f0e9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-06 22:30:00.000000
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4c3b2a1f0e9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | None = None
depends_on: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_backing_model_id(
    connection: sa.Connection,
    provider: str,
    model_id: str,
) -> uuid.UUID:
    existing = connection.execute(
        sa.text(
            """
            SELECT id
            FROM backing_models
            WHERE provider = :provider AND model_id = :model_id
            LIMIT 1
            """
        ),
        {"provider": provider, "model_id": model_id},
    ).scalar_one_or_none()
    if existing:
        return existing

    backing_id = uuid.uuid4()
    connection.execute(
        sa.text(
            """
            INSERT INTO backing_models (id, provider, model_id, display_name, first_seen_at, metadata)
            VALUES (:id, :provider, :model_id, :display_name, :first_seen_at, CAST(:metadata AS jsonb))
            """
        ),
        {
            "id": backing_id,
            "provider": provider,
            "model_id": model_id,
            "display_name": model_id,
            "first_seen_at": _utc_now(),
            "metadata": json.dumps({}),
        },
    )
    return backing_id


def _insert_run(
    connection: sa.Connection,
    *,
    capability: str,
    artifact_type: str,
    artifact_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
    provider: str,
    model_id: str,
    started_at: datetime,
    completed_at: datetime | None,
) -> uuid.UUID:
    backing_model_id = _get_or_create_backing_model_id(connection, provider, model_id)
    run_id = uuid.uuid4()
    connection.execute(
        sa.text(
            """
            INSERT INTO analysis_runs (
                id, capability, artifact_type, artifact_id, conversation_id,
                backing_model_id, provider, model_id,
                prompt_version, prompt_hash, input_hash, input_canonical_version,
                temperature, max_tokens,
                prompt_tokens, completion_tokens, total_tokens,
                cost_usd, latency_ms, finish_reason,
                status, error_message, source, started_at, completed_at, metadata
            ) VALUES (
                :id, :capability, :artifact_type, :artifact_id, :conversation_id,
                :backing_model_id, :provider, :model_id,
                :prompt_version, NULL, NULL, NULL,
                NULL, NULL,
                NULL, NULL, NULL,
                NULL, NULL, NULL,
                :status, NULL, :source, :started_at, :completed_at, CAST(:metadata AS jsonb)
            )
            """
        ),
        {
            "id": run_id,
            "capability": capability,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "conversation_id": conversation_id,
            "backing_model_id": backing_model_id,
            "provider": provider,
            "model_id": model_id,
            "prompt_version": "legacy-unknown",
            "status": "succeeded",
            "source": "backfill",
            "started_at": started_at,
            "completed_at": completed_at,
            "metadata": json.dumps({}),
        },
    )
    return run_id


def _backfill_insights(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT id, conversation_id, generated_at
            FROM conversation_insights
            """
        )
    ).mappings()

    for row in rows:
        run_id = _insert_run(
            connection,
            capability="insights",
            artifact_type="conversation_insight",
            artifact_id=row["id"],
            conversation_id=row["conversation_id"],
            provider="openai",
            model_id="unknown",
            started_at=row["generated_at"] or _utc_now(),
            completed_at=row["generated_at"] or _utc_now(),
        )
        connection.execute(
            sa.text(
                """
                UPDATE conversation_insights
                SET latest_run_id = :run_id
                WHERE id = :insight_id
                """
            ),
            {"run_id": run_id, "insight_id": row["id"]},
        )


def _backfill_recaps(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT id, conversation_id, generated_at, metadata
            FROM conversation_recaps
            """
        )
    ).mappings()

    for row in rows:
        metadata = row["metadata"] or {}
        llm_metrics: dict[str, Any] = metadata.get("llm_metrics", {}) if metadata else {}
        model_id = llm_metrics.get("llm_model", "unknown") or "unknown"
        run_id = _insert_run(
            connection,
            capability="recap",
            artifact_type="conversation_recap",
            artifact_id=row["id"],
            conversation_id=row["conversation_id"],
            provider="openai",
            model_id=model_id,
            started_at=row["generated_at"] or _utc_now(),
            completed_at=row["generated_at"] or _utc_now(),
        )
        connection.execute(
            sa.text(
                """
                UPDATE conversation_recaps
                SET latest_run_id = :run_id
                WHERE id = :recap_id
                """
            ),
            {"run_id": run_id, "recap_id": row["id"]},
        )


def _backfill_recommendations(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT id, conversation_id, recommendation_type, created_at
            FROM automation_recommendations
            """
        )
    ).mappings()

    for row in rows:
        run_id = _insert_run(
            connection,
            capability=f"recommendation_{row['recommendation_type']}",
            artifact_type="automation_recommendation",
            artifact_id=row["id"],
            conversation_id=row["conversation_id"],
            provider="openai",
            model_id="unknown",
            started_at=row["created_at"] or _utc_now(),
            completed_at=row["created_at"] or _utc_now(),
        )
        connection.execute(
            sa.text(
                """
                UPDATE automation_recommendations
                SET run_id = :run_id
                WHERE id = :rec_id
                """
            ),
            {"run_id": run_id, "rec_id": row["id"]},
        )


def _backfill_tagging(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT id, updated_at, tags
            FROM conversations
            WHERE tags IS NOT NULL
              AND tags::text <> '{}'::text
            """
        )
    ).mappings()

    for row in rows:
        metrics_row = connection.execute(
            sa.text(
                """
                SELECT metrics
                FROM ingestion_jobs
                WHERE conversation_id = :conversation_id
                  AND metrics ? 'llm_model'
                ORDER BY completed_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """
            ),
            {"conversation_id": row["id"]},
        ).mappings().first()

        model_id = "unknown"
        if metrics_row:
            metrics = metrics_row["metrics"] or {}
            model_id = metrics.get("llm_model", "unknown") or "unknown"

        run_id = _insert_run(
            connection,
            capability="tagging",
            artifact_type="conversation_tagging",
            artifact_id=row["id"],
            conversation_id=row["id"],
            provider="openai",
            model_id=model_id,
            started_at=row["updated_at"] or _utc_now(),
            completed_at=row["updated_at"] or _utc_now(),
        )
        connection.execute(
            sa.text(
                """
                UPDATE conversations
                SET last_tagging_run_id = :run_id
                WHERE id = :conversation_id
                """
            ),
            {"run_id": run_id, "conversation_id": row["id"]},
        )


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("backing_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("input_canonical_version", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("finish_reason", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "source", sa.String(length=20), server_default="live", nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["backing_model_id"], ["backing_models.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_runs_artifact_id"), "analysis_runs", ["artifact_id"])
    op.create_index(
        op.f("ix_analysis_runs_artifact_type"), "analysis_runs", ["artifact_type"]
    )
    op.create_index(op.f("ix_analysis_runs_capability"), "analysis_runs", ["capability"])
    op.create_index(
        op.f("ix_analysis_runs_conversation_id"), "analysis_runs", ["conversation_id"]
    )
    op.create_index(op.f("ix_analysis_runs_model_id"), "analysis_runs", ["model_id"])
    op.create_index(op.f("ix_analysis_runs_provider"), "analysis_runs", ["provider"])
    op.create_index(op.f("ix_analysis_runs_source"), "analysis_runs", ["source"])
    op.create_index(op.f("ix_analysis_runs_started_at"), "analysis_runs", ["started_at"])
    op.create_index(op.f("ix_analysis_runs_status"), "analysis_runs", ["status"])
    op.create_index(
        op.f("ix_analysis_runs_backing_model_id"), "analysis_runs", ["backing_model_id"]
    )

    op.add_column(
        "conversations",
        sa.Column("last_tagging_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_conversations_last_tagging_run_id"),
        "conversations",
        ["last_tagging_run_id"],
    )
    op.create_foreign_key(
        "fk_conversations_last_tagging_run_id_analysis_runs",
        "conversations",
        "analysis_runs",
        ["last_tagging_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "conversation_insights",
        sa.Column("latest_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_conversation_insights_latest_run_id"),
        "conversation_insights",
        ["latest_run_id"],
    )
    op.create_foreign_key(
        "fk_conversation_insights_latest_run_id_analysis_runs",
        "conversation_insights",
        "analysis_runs",
        ["latest_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "conversation_recaps",
        sa.Column("latest_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_conversation_recaps_latest_run_id"),
        "conversation_recaps",
        ["latest_run_id"],
    )
    op.create_foreign_key(
        "fk_conversation_recaps_latest_run_id_analysis_runs",
        "conversation_recaps",
        "analysis_runs",
        ["latest_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "automation_recommendations",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_automation_recommendations_run_id"),
        "automation_recommendations",
        ["run_id"],
    )
    op.create_foreign_key(
        "fk_automation_recommendations_run_id_analysis_runs",
        "automation_recommendations",
        "analysis_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()
    _backfill_insights(connection)
    _backfill_recaps(connection)
    _backfill_recommendations(connection)
    _backfill_tagging(connection)


def downgrade() -> None:
    op.drop_constraint(
        "fk_automation_recommendations_run_id_analysis_runs",
        "automation_recommendations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_automation_recommendations_run_id"),
        table_name="automation_recommendations",
    )
    op.drop_column("automation_recommendations", "run_id")

    op.drop_constraint(
        "fk_conversation_recaps_latest_run_id_analysis_runs",
        "conversation_recaps",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_conversation_recaps_latest_run_id"), table_name="conversation_recaps"
    )
    op.drop_column("conversation_recaps", "latest_run_id")

    op.drop_constraint(
        "fk_conversation_insights_latest_run_id_analysis_runs",
        "conversation_insights",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_conversation_insights_latest_run_id"),
        table_name="conversation_insights",
    )
    op.drop_column("conversation_insights", "latest_run_id")

    op.drop_constraint(
        "fk_conversations_last_tagging_run_id_analysis_runs",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_conversations_last_tagging_run_id"), table_name="conversations"
    )
    op.drop_column("conversations", "last_tagging_run_id")

    op.drop_index(op.f("ix_analysis_runs_backing_model_id"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_status"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_started_at"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_source"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_provider"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_model_id"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_conversation_id"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_capability"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_artifact_type"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_artifact_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
