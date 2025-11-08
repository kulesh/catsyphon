"""
API schemas for CatSyphon.

Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ===== Base Schemas =====


class ProjectBase(BaseModel):
    """Base schema for Project."""

    name: str
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Response schema for Project."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeveloperBase(BaseModel):
    """Base schema for Developer."""

    username: str
    email: Optional[str] = None


class DeveloperResponse(DeveloperBase):
    """Response schema for Developer."""

    id: UUID
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Conversation Schemas =====


class MessageResponse(BaseModel):
    """Response schema for Message."""

    id: UUID
    role: str
    content: str
    timestamp: datetime
    sequence: int
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    code_changes: list[dict[str, Any]] = Field(default_factory=list)
    entities: dict[str, Any] = Field(default_factory=dict)
    extra_data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class EpochResponse(BaseModel):
    """Response schema for Epoch."""

    id: UUID
    sequence: int
    intent: Optional[str] = None
    outcome: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    message_count: int = 0  # Will be populated from messages

    class Config:
        from_attributes = True


class FileTouchedResponse(BaseModel):
    """Response schema for FilesTouched."""

    id: UUID
    file_path: str
    change_type: Optional[str] = None
    lines_added: int = 0
    lines_deleted: int = 0
    lines_modified: int = 0
    timestamp: datetime
    extra_data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ConversationTagResponse(BaseModel):
    """Response schema for ConversationTag."""

    id: UUID
    tag_type: str
    tag_value: str
    confidence: Optional[float] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    """Schema for conversation in list view (without messages)."""

    id: UUID
    project_id: Optional[UUID] = None
    developer_id: Optional[UUID] = None
    agent_type: str
    agent_version: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "open"
    success: Optional[bool] = None
    iteration_count: int = 1
    tags: dict[str, Any] = Field(default_factory=dict)
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    # Related counts
    message_count: int = 0
    epoch_count: int = 0
    files_count: int = 0

    # Related objects (optional, for joins)
    project: Optional[ProjectResponse] = None
    developer: Optional[DeveloperResponse] = None

    class Config:
        from_attributes = True


class ConversationDetail(ConversationListItem):
    """Schema for detailed conversation view (with messages)."""

    messages: list[MessageResponse] = Field(default_factory=list)
    epochs: list[EpochResponse] = Field(default_factory=list)
    files_touched: list[FileTouchedResponse] = Field(default_factory=list)
    conversation_tags: list[ConversationTagResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response schema for paginated conversation list."""

    items: list[ConversationListItem]
    total: int
    page: int
    page_size: int
    pages: int


# ===== Stats Schemas =====


class OverviewStats(BaseModel):
    """Response schema for overview statistics."""

    total_conversations: int
    total_messages: int
    total_projects: int
    total_developers: int
    conversations_by_status: dict[str, int] = Field(default_factory=dict)
    conversations_by_agent: dict[str, int] = Field(default_factory=dict)
    recent_conversations: int  # Last 7 days
    success_rate: Optional[float] = None  # Percentage of successful conversations


class AgentPerformanceStats(BaseModel):
    """Response schema for agent performance statistics."""

    agent_type: str
    total_conversations: int
    successful_conversations: int
    failed_conversations: int
    success_rate: float
    avg_iteration_count: float
    avg_duration_minutes: Optional[float] = None


class DeveloperActivityStats(BaseModel):
    """Response schema for developer activity statistics."""

    developer_id: UUID
    developer_username: str
    total_conversations: int
    successful_conversations: int
    total_messages: int
    total_files_touched: int
    avg_conversation_duration: Optional[float] = None
    most_used_agent: Optional[str] = None


# ===== Query Parameters =====


class ConversationFilters(BaseModel):
    """Query parameters for filtering conversations."""

    project_id: Optional[UUID] = None
    developer_id: Optional[UUID] = None
    agent_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    success: Optional[bool] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


# ===== Upload Schemas =====


class UploadResult(BaseModel):
    """Result for a single uploaded file."""

    filename: str
    status: str  # "success" or "error"
    conversation_id: Optional[UUID] = None
    message_count: int = 0
    epoch_count: int = 0
    files_count: int = 0
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Response schema for batch file upload."""

    success_count: int
    failed_count: int
    results: list[UploadResult]
