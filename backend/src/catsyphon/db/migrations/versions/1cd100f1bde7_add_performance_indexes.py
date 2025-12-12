"""add performance indexes

Revision ID: 1cd100f1bde7
Revises: ac65054bb848
Create Date: 2025-11-14 22:59:26.501489

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1cd100f1bde7"
down_revision: Union[str, None] = "ac65054bb848"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Conversations table indexes ===

    # Single-column indexes
    op.create_index(
        "idx_conversations_success", "conversations", ["success"], unique=False
    )
    op.create_index(
        "idx_conversations_updated_at", "conversations", ["updated_at"], unique=False
    )

    # Composite indexes for common query patterns
    op.create_index(
        "idx_conversations_project_time",
        "conversations",
        ["project_id", sa.text("start_time DESC")],
        unique=False,
    )
    op.create_index(
        "idx_conversations_developer_time",
        "conversations",
        ["developer_id", sa.text("start_time DESC")],
        unique=False,
    )
    op.create_index(
        "idx_conversations_agent_time",
        "conversations",
        ["agent_type", sa.text("start_time DESC")],
        unique=False,
    )
    op.create_index(
        "idx_conversations_status_time",
        "conversations",
        ["status", sa.text("start_time DESC")],
        unique=False,
    )

    # Partial index for success rate calculations
    op.execute(
        "CREATE INDEX idx_conversations_success_nonnull ON conversations (success) "
        "WHERE success IS NOT NULL"
    )

    # === Raw Logs table indexes ===

    # Note: idx_raw_logs_file_hash already exists (created by unique=True constraint)
    op.create_index("idx_raw_logs_file_path", "raw_logs", ["file_path"], unique=False)
    op.create_index("idx_raw_logs_agent_type", "raw_logs", ["agent_type"], unique=False)
    op.create_index(
        "idx_raw_logs_conversation", "raw_logs", ["conversation_id"], unique=False
    )

    # === Ingestion Jobs table indexes ===

    # Single-column indexes
    op.create_index(
        "idx_ingestion_jobs_source_type",
        "ingestion_jobs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_jobs_status", "ingestion_jobs", ["status"], unique=False
    )
    op.create_index(
        "idx_ingestion_jobs_started_at",
        "ingestion_jobs",
        [sa.text("started_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_jobs_source_config",
        "ingestion_jobs",
        ["source_config_id"],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_jobs_conversation",
        "ingestion_jobs",
        ["conversation_id"],
        unique=False,
    )

    # Composite indexes
    op.create_index(
        "idx_ingestion_jobs_source_time",
        "ingestion_jobs",
        ["source_type", sa.text("started_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_ingestion_jobs_status_time",
        "ingestion_jobs",
        ["status", sa.text("started_at DESC")],
        unique=False,
    )

    # Partial index for failed jobs
    op.execute(
        "CREATE INDEX idx_ingestion_jobs_failed ON ingestion_jobs (started_at DESC) "
        "WHERE status = 'failed'"
    )

    # === Watch Configurations table indexes ===

    op.create_index(
        "idx_watch_configs_is_active",
        "watch_configurations",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "idx_watch_configs_project",
        "watch_configurations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_watch_configs_directory",
        "watch_configurations",
        ["directory"],
        unique=False,
    )

    # === Messages table indexes ===

    # Composite index for role-based filtering
    op.create_index(
        "idx_messages_conversation_role",
        "messages",
        ["conversation_id", "role"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes in reverse order

    # Messages table
    op.drop_index("idx_messages_conversation_role", table_name="messages")

    # Watch Configurations table
    op.drop_index("idx_watch_configs_directory", table_name="watch_configurations")
    op.drop_index("idx_watch_configs_project", table_name="watch_configurations")
    op.drop_index("idx_watch_configs_is_active", table_name="watch_configurations")

    # Ingestion Jobs table
    op.execute("DROP INDEX IF EXISTS idx_ingestion_jobs_failed")
    op.drop_index("idx_ingestion_jobs_status_time", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_source_time", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_conversation", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_source_config", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_started_at", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("idx_ingestion_jobs_source_type", table_name="ingestion_jobs")

    # Raw Logs table
    op.drop_index("idx_raw_logs_conversation", table_name="raw_logs")
    op.drop_index("idx_raw_logs_agent_type", table_name="raw_logs")
    op.drop_index("idx_raw_logs_file_path", table_name="raw_logs")
    # Note: idx_raw_logs_file_hash managed by unique=True constraint, not dropped here

    # Conversations table
    op.execute("DROP INDEX IF EXISTS idx_conversations_success_nonnull")
    op.drop_index("idx_conversations_status_time", table_name="conversations")
    op.drop_index("idx_conversations_agent_time", table_name="conversations")
    op.drop_index("idx_conversations_developer_time", table_name="conversations")
    op.drop_index("idx_conversations_project_time", table_name="conversations")
    op.drop_index("idx_conversations_updated_at", table_name="conversations")
    op.drop_index("idx_conversations_success", table_name="conversations")
