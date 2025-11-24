"""
SQLAlchemy database models for CatSyphon.

These models represent the database schema for storing parsed and tagged
conversation data.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class ConversationType(str, enum.Enum):
    """Type of conversation - main, agent, or other tool/context."""

    MAIN = "main"  # Primary human conversation thread
    AGENT = "agent"  # Subagent/delegated task conversation
    METADATA = "metadata"  # Session with only metadata entries (no messages)
    MCP = "mcp"  # MCP server conversation
    SKILL = "skill"  # Skill invocation conversation
    COMMAND = "command"  # Slash command conversation
    OTHER = "other"  # Other types of sub-conversations


class Organization(Base):
    """Organization entity for multi-workspace companies."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # URL-friendly identifier

    # Organization settings
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name!r}, slug={self.slug!r})>"


class Workspace(Base):
    """Workspace for multi-tenancy data isolation."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # URL-friendly identifier

    # Workspace settings
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="workspaces")
    collectors: Mapped[list["CollectorConfig"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="workspace"
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="workspace")
    developers: Mapped[list["Developer"]] = relationship(back_populates="workspace")
    watch_configurations: Mapped[list["WatchConfiguration"]] = relationship(
        back_populates="workspace"
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name!r}, slug={self.slug!r})>"


class CollectorConfig(Base):
    """Configuration for remote collector agents."""

    __tablename__ = "collector_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Collector identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    collector_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'agent', 'ci-server', 'developer-laptop', etc.

    # Authentication (single API key per collector)
    api_key_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # bcrypt hash
    api_key_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # First 8 chars for display (e.g., "cs_abc123...")

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Collector metadata
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )  # OS, Python version, location, etc.

    # Denormalized statistics for performance
    total_uploads: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_conversations: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_upload_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="collectors")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="collector"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="collector"
    )

    def __repr__(self) -> str:
        return (
            f"<CollectorConfig(id={self.id}, "
            f"name={self.name!r}, "
            f"type={self.collector_type!r})>"
        )


class Project(Base):
    """Project grouping for conversations."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    directory_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint('workspace_id', 'directory_path', name='uq_workspace_directory'),
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name!r})>"


class Developer(Base):
    """Developer/user information."""

    __tablename__ = "developers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint('workspace_id', 'username', name='uq_workspace_developer'),
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="developers")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="developer"
    )

    def __repr__(self) -> str:
        return f"<Developer(id={self.id}, username={self.username!r})>"


class Conversation(Base):
    """Main conversation record."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collector_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    developer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("developers.id"), nullable=True
    )

    # Hierarchy fields for agents, MCP servers, skills, commands, etc.
    parent_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    conversation_type: Mapped[str] = mapped_column(
        Enum(ConversationType, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=ConversationType.MAIN.value,
        index=True,
    )

    # Semantic metadata for context sharing behavior
    # Example: {"shares_parent_context": false, "can_use_parent_tools": true,
    #           "isolated_context": true, "max_context_window": 100000}
    context_semantics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Agent-specific metadata (for conversation_type='agent')
    # Example: {"agent_id": "88b5221b", "agent_type": "Explore",
    #           "delegation_reason": "Find error handling code",
    #           "parent_message_id": "msg-123", "specialized_prompt": "..."}
    agent_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'claude-code', 'copilot', etc.
    agent_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="open"
    )  # 'open', 'completed', 'abandoned'
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    iteration_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    # Denormalized counts for performance (avoid Cartesian product joins)
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    epoch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    files_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Metadata (flexible storage for additional fields)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    __table_args__ = (
        Index(
            "uq_conversation_ws_type_session",
            "workspace_id",
            "conversation_type",
            extra_data["session_id"].as_string(),
            unique=True,
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="conversations")
    collector: Mapped[Optional["CollectorConfig"]] = relationship(
        back_populates="conversations"
    )
    project: Mapped[Optional["Project"]] = relationship(back_populates="conversations")
    developer: Mapped[Optional["Developer"]] = relationship(
        back_populates="conversations"
    )

    # Hierarchical relationship for agents, MCP, skills, etc.
    parent_conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
        remote_side="Conversation.id",
        foreign_keys=[parent_conversation_id],
        back_populates="children",
    )
    children: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="parent_conversation",
        foreign_keys="Conversation.parent_conversation_id",
        cascade="all, delete-orphan",
    )

    epochs: Mapped[list["Epoch"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    files_touched: Mapped[list["FileTouched"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    raw_logs: Mapped[list["RawLog"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(id={self.id}, "
            f"agent_type={self.agent_type!r}, "
            f"start_time={self.start_time})>"
        )


class Epoch(Base):
    """Conversation segment/turn within a conversation."""

    __tablename__ = "epochs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # order within conversation

    # Classification
    intent: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # 'feature_add', 'bug_fix', 'refactor', etc.
    outcome: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # 'success', 'failure', 'partial', 'blocked'

    # Sentiment analysis
    sentiment: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'positive', 'neutral', 'negative', etc.
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # -1.0 to 1.0

    # Timing
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Additional metadata
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="epochs")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="epoch", cascade="all, delete-orphan"
    )
    files_touched: Mapped[list["FileTouched"]] = relationship(
        back_populates="epoch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Epoch(id={self.id}, "
            f"conversation_id={self.conversation_id}, "
            f"sequence={self.sequence})>"
        )


class Message(Base):
    """Individual message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    epoch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epochs.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Claude's extended thinking (internal reasoning)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # order within epoch

    # Tool usage
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    tool_results: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # Code changes
    code_changes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # Extracted entities
    entities: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    epoch: Mapped["Epoch"] = relationship(back_populates="messages")
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, role={self.role!r}, timestamp={self.timestamp})>"
        )


class FileTouched(Base):
    """Files touched during conversations."""

    __tablename__ = "files_touched"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    epoch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epochs.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'created', 'modified', 'deleted', 'read'
    lines_added: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    lines_deleted: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    lines_modified: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="files_touched")
    epoch: Mapped["Epoch"] = relationship(back_populates="files_touched")

    def __repr__(self) -> str:
        return (
            f"<FileTouched(id={self.id}, "
            f"file_path={self.file_path!r}, "
            f"change_type={self.change_type})>"
        )


class RawLog(Base):
    """Raw logs (preserve originals for reprocessing)."""

    __tablename__ = "raw_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    log_format: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'json', 'markdown', 'xml', etc.
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )  # SHA-256 hash for deduplication

    # Incremental parsing state (Phase 2)
    last_processed_offset: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Byte offset in file where we last stopped parsing
    last_processed_line: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Line number for debugging/human readability
    file_size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # File size at last parse (detect truncation)
    partial_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # Hash of content up to last_processed_offset (detect mid-file changes)
    last_message_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp of last processed message (validation)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="raw_logs")

    def __repr__(self) -> str:
        return (
            f"<RawLog(id={self.id}, "
            f"agent_type={self.agent_type!r}, "
            f"log_format={self.log_format!r})>"
        )


class WatchConfiguration(Base):
    """Watch directory configuration for real-time ingestion."""

    __tablename__ = "watch_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    directory: Mapped[str] = mapped_column(
        Text, nullable=False, index=True
    )  # Path to watch directory
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    developer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("developers.id"), nullable=True
    )
    enable_tagging: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )  # Currently being watched
    daemon_pid: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )  # Process ID of running daemon (None if stopped)

    # Statistics snapshot (from WatcherStats)
    stats: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )  # files_processed, files_skipped, etc.

    # Configuration options (poll_interval, retry settings, etc.)
    extra_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    created_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Username who created this config
    last_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="watch_configurations")
    project: Mapped[Optional["Project"]] = relationship()
    developer: Mapped[Optional["Developer"]] = relationship()
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="watch_config", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<WatchConfiguration(id={self.id}, "
            f"directory={self.directory!r}, "
            f"is_active={self.is_active})>"
        )


class IngestionJob(Base):
    """Audit trail for all ingestion operations."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'watch', 'upload', 'cli', 'collector'
    source_config_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("watch_configurations.id"),
        nullable=True,
    )  # FK to watch_configurations if source_type='watch'
    collector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collector_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # FK to collector_configs if source_type='collector'

    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_logs.id"), nullable=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'success', 'failed', 'duplicate', 'skipped'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance metrics
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    incremental: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )  # Was incremental parsing used?
    messages_added: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )  # Stage-level performance metrics: {parse, canonical, llm, db, total}

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Username (for manual uploads)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    watch_config: Mapped[Optional["WatchConfiguration"]] = relationship(
        back_populates="ingestion_jobs"
    )
    collector: Mapped[Optional["CollectorConfig"]] = relationship(
        back_populates="ingestion_jobs"
    )
    raw_log: Mapped[Optional["RawLog"]] = relationship()
    conversation: Mapped[Optional["Conversation"]] = relationship()

    def __repr__(self) -> str:
        return (
            f"<IngestionJob(id={self.id}, "
            f"source_type={self.source_type!r}, "
            f"status={self.status!r})>"
        )


class ConversationCanonical(Base):
    """Canonical representation of conversations for analysis.

    Stores pre-computed narrative forms optimized for different analysis types.
    Supports multiple versions per conversation and window-based regeneration.
    """

    __tablename__ = "conversation_canonical"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Canonical type and version
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # Canonicalization algorithm version
    canonical_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'tagging', 'insights', 'export'

    # Narrative content
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Actual tokens in narrative

    # Structured metadata (JSONB for flexible storage)
    canonical_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )  # Tools used, files touched, etc.
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )  # CanonicalConfig settings used

    # Source tracking (for window-based regeneration)
    source_message_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Messages at generation time
    source_token_estimate: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Estimated tokens in source conversation

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "version", "canonical_type", name="uq_conversation_version_type"
        ),
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ConversationCanonical(id={self.id}, "
            f"conversation_id={self.conversation_id}, "
            f"type={self.canonical_type!r}, "
            f"version={self.version})>"
        )
