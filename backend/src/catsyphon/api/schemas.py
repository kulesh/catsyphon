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
    directory_path: str
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Response schema for Project."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListItem(ProjectResponse):
    """Extended project info for list view with session counts."""

    session_count: int = 0
    last_session_at: Optional[datetime] = None


class SentimentTimelinePoint(BaseModel):
    """Single data point in sentiment timeline."""

    date: str  # ISO date string (YYYY-MM-DD)
    avg_sentiment: float  # Average sentiment score (-1.0 to 1.0)
    session_count: int  # Number of sessions on this date


class ProjectStats(BaseModel):
    """Statistics for a single project."""

    project_id: UUID
    session_count: int
    total_messages: int
    total_files_changed: int
    success_rate: Optional[float] = None
    avg_session_duration_seconds: Optional[float] = None
    first_session_at: Optional[datetime] = None
    last_session_at: Optional[datetime] = None

    # Aggregated tags
    top_features: list[str] = Field(default_factory=list)
    top_problems: list[str] = Field(default_factory=list)
    tool_usage: dict[str, int] = Field(default_factory=dict)

    # Developer participation
    developer_count: int = 0
    developers: list[str] = Field(default_factory=list)

    # Sentiment timeline
    sentiment_timeline: list[SentimentTimelinePoint] = Field(default_factory=list)


class ProjectSession(BaseModel):
    """Lightweight session info for project session list."""

    id: UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    status: str
    success: Optional[bool] = None
    message_count: int = 0
    files_count: int = 0
    developer: Optional[str] = None  # Developer username
    agent_type: str


class ProjectFileAggregation(BaseModel):
    """Aggregated file modification data across project sessions."""

    file_path: str
    modification_count: int
    total_lines_added: int
    total_lines_deleted: int
    last_modified_at: datetime
    session_ids: list[UUID] = Field(default_factory=list)


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
    thinking_content: Optional[str] = None
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

    # Hierarchy fields (Phase 2: Epic 7u2)
    parent_conversation_id: Optional[UUID] = None
    conversation_type: str = "main"
    context_semantics: dict[str, Any] = Field(default_factory=dict)
    agent_metadata: dict[str, Any] = Field(default_factory=dict)

    # Related counts
    message_count: int = 0
    epoch_count: int = 0
    files_count: int = 0
    children_count: int = 0  # Number of child conversations (agents, etc.)

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

    # Hierarchical relationships (Phase 2: Epic 7u2)
    children: list["ConversationListItem"] = Field(default_factory=list)
    parent: Optional["ConversationListItem"] = None

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

    # Hierarchical conversation stats (Phase 2: Epic 7u2)
    total_main_conversations: int = 0  # Main human conversations
    total_agent_conversations: int = 0  # Agent/subagent conversations
    conversations_by_type: dict[str, int] = Field(default_factory=dict)  # main, agent, mcp, etc.


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
    status: str  # "success", "duplicate", "skipped", or "error"
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


# ===== Watch Configuration Schemas =====


class WatchConfigurationCreate(BaseModel):
    """Request schema for creating a watch configuration."""

    directory: str
    project_id: Optional[UUID] = None
    developer_id: Optional[UUID] = None
    enable_tagging: bool = False
    extra_config: dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None


class WatchConfigurationUpdate(BaseModel):
    """Request schema for updating a watch configuration."""

    directory: Optional[str] = None
    project_id: Optional[UUID] = None
    developer_id: Optional[UUID] = None
    enable_tagging: Optional[bool] = None
    extra_config: Optional[dict[str, Any]] = None


class WatchConfigurationResponse(BaseModel):
    """Response schema for watch configuration."""

    id: UUID
    directory: str
    project_id: Optional[UUID] = None
    developer_id: Optional[UUID] = None
    enable_tagging: bool
    is_active: bool
    stats: dict[str, Any]
    extra_config: dict[str, Any]
    created_by: Optional[str] = None
    last_started_at: Optional[datetime] = None
    last_stopped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== Ingestion Job Schemas =====


class IngestionJobResponse(BaseModel):
    """Response schema for ingestion job."""

    id: UUID
    source_type: str
    source_config_id: Optional[UUID] = None
    file_path: Optional[str] = None
    raw_log_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    status: str
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    incremental: bool
    messages_added: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IngestionJobFilters(BaseModel):
    """Query parameters for filtering ingestion jobs."""

    source_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class IngestionStatsResponse(BaseModel):
    """Response schema for ingestion statistics."""

    total_jobs: int
    by_status: dict[str, int]
    by_source_type: dict[str, int]
    avg_processing_time_ms: Optional[float] = None
    incremental_jobs: int
    incremental_percentage: float


# ===== Setup / Onboarding Schemas =====


class OrganizationCreate(BaseModel):
    """Request schema for creating an organization."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organization name (e.g., 'ACME Corporation', 'My Company')",
    )
    slug: Optional[str] = Field(
        None,
        pattern=r"^[a-z0-9-]+$",
        max_length=255,
        description="URL-friendly identifier (auto-generated if not provided)",
    )


class OrganizationResponse(BaseModel):
    """Response schema for Organization."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class WorkspaceCreate(BaseModel):
    """Request schema for creating a workspace."""

    organization_id: UUID = Field(..., description="Parent organization ID")
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Workspace name (e.g., 'Engineering', 'Personal Projects', 'Default')",
    )
    slug: Optional[str] = Field(
        None,
        pattern=r"^[a-z0-9-]+$",
        max_length=255,
        description="URL-friendly identifier (auto-generated if not provided)",
    )


class WorkspaceResponse(BaseModel):
    """Response schema for Workspace."""

    model_config = {"from_attributes": True}

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class SetupStatusResponse(BaseModel):
    """Response schema for setup status check."""

    needs_onboarding: bool = Field(
        ..., description="Whether the system requires initial setup"
    )
    organization_count: int = Field(..., description="Number of organizations")
    workspace_count: int = Field(..., description="Number of workspaces")


# ===== Canonical Schemas =====


class CanonicalMetadata(BaseModel):
    """Metadata extracted from canonical conversation."""

    tools_used: list[str] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    errors_encountered: list[str] = Field(default_factory=list)
    has_errors: bool = False


class CanonicalConfig(BaseModel):
    """Configuration used to generate canonical representation."""

    canonical_type: str = Field(..., description="Type of canonical (tagging, insights, export)")
    max_tokens: int = Field(..., description="Maximum tokens allowed")
    sampling_strategy: str = Field(..., description="Sampling strategy used")


class CanonicalResponse(BaseModel):
    """Response schema for canonical conversation representation."""

    id: UUID
    conversation_id: UUID
    version: int = Field(..., description="Canonical version for cache invalidation")
    canonical_type: str = Field(..., description="Type of canonical (tagging, insights, export)")
    narrative: str = Field(..., description="Play-format narrative of conversation")
    token_count: int = Field(..., description="Number of tokens in narrative")
    metadata: CanonicalMetadata = Field(..., description="Extracted metadata")
    config: CanonicalConfig = Field(..., description="Configuration used")

    # Source conversation metadata
    source_message_count: int = Field(..., description="Total messages in source conversation")
    source_token_estimate: int = Field(..., description="Estimated tokens in source")

    # Generation metadata
    generated_at: datetime = Field(..., description="When this canonical was generated")

    class Config:
        from_attributes = True


class CanonicalNarrativeResponse(BaseModel):
    """Simplified response containing only the narrative text."""

    narrative: str = Field(..., description="Play-format narrative")
    token_count: int = Field(..., description="Number of tokens")
    canonical_type: str = Field(..., description="Type of canonical")
    version: int = Field(..., description="Canonical version")


class RegenerateCanonicalRequest(BaseModel):
    """Request schema for forcing canonical regeneration."""

    canonical_type: str = Field(
        default="tagging",
        description="Type of canonical to regenerate (tagging, insights, export)"
    )
    sampling_strategy: str = Field(
        default="semantic",
        description="Sampling strategy (semantic, epoch, chronological)"
    )


# ===== Insights Schemas =====


class KeyMoment(BaseModel):
    """A key moment in the conversation."""

    timestamp: str = Field(..., description="Relative timestamp (early, mid, late)")
    event: str = Field(..., description="Description of the event")
    impact: str = Field(..., description="Impact (positive, negative, neutral)")


class QuantitativeMetrics(BaseModel):
    """Quantitative metrics from conversation analysis."""

    message_count: int = Field(..., description="Total messages")
    epoch_count: int = Field(..., description="Number of epochs/iterations")
    files_touched_count: int = Field(..., description="Files modified")
    tool_calls_count: int = Field(..., description="Tool invocations")
    token_count: int = Field(..., description="Tokens in canonical")
    has_errors: bool = Field(..., description="Whether errors occurred")
    tools_used: list[str] = Field(default_factory=list, description="Tools used")
    child_conversations_count: int = Field(..., description="Child conversations")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")


class InsightsResponse(BaseModel):
    """Response schema for conversation insights."""

    conversation_id: UUID = Field(..., description="Conversation UUID")

    # Qualitative insights from LLM
    workflow_patterns: list[str] = Field(
        default_factory=list,
        description="Observable workflow patterns"
    )
    productivity_indicators: list[str] = Field(
        default_factory=list,
        description="Productivity signals"
    )
    collaboration_quality: int = Field(
        ...,
        ge=1,
        le=10,
        description="Human-AI collaboration quality (1-10)"
    )
    key_moments: list[KeyMoment] = Field(
        default_factory=list,
        description="Critical turning points"
    )
    learning_opportunities: list[str] = Field(
        default_factory=list,
        description="Areas for improvement"
    )
    agent_effectiveness: int = Field(
        ...,
        ge=1,
        le=10,
        description="Agent helpfulness (1-10)"
    )
    scope_clarity: int = Field(
        ...,
        ge=1,
        le=10,
        description="Goal definition quality (1-10)"
    )
    technical_debt_indicators: list[str] = Field(
        default_factory=list,
        description="Technical debt signals"
    )
    testing_behavior: str = Field(..., description="Testing practices observed")
    summary: str = Field(..., description="2-3 sentence summary")

    # Quantitative metrics
    quantitative_metrics: QuantitativeMetrics = Field(
        ...,
        description="Numerical metrics"
    )

    # Metadata
    canonical_version: int = Field(..., description="Canonical algorithm version")
    analysis_timestamp: float = Field(..., description="Unix timestamp of analysis")
