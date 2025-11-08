"""
SQLAlchemy database models for CatSyphon.

These models represent the database schema for storing parsed and tagged
conversation data.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Project(Base):
    """Project grouping for conversations."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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

    # Relationships
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
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
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
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    developer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("developers.id"), nullable=True
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
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    iteration_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    # Metadata (flexible storage for additional fields)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
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
    project: Mapped[Optional["Project"]] = relationship(back_populates="conversations")
    developer: Mapped[Optional["Developer"]] = relationship(
        back_populates="conversations"
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
    conversation_tags: Mapped[list["ConversationTag"]] = relationship(
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


class ConversationTag(Base):
    """Conversation tags (extracted insights)."""

    __tablename__ = "conversation_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    tag_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'feature', 'technology', 'problem', 'pattern'
    tag_value: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # 0.0 to 1.0

    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        back_populates="conversation_tags"
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationTag(id={self.id}, "
            f"tag_type={self.tag_type!r}, "
            f"tag_value={self.tag_value!r})>"
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

    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    log_format: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'json', 'markdown', 'xml', etc.
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # SHA-256 hash for deduplication

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
