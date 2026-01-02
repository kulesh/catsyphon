"""
API schemas for CatSyphon.

Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    model_config = ConfigDict(from_attributes=True)


class ProjectListItem(ProjectResponse):
    """Extended project info for list view with session counts."""

    session_count: int = 0
    last_session_at: Optional[datetime] = None


class SentimentTimelinePoint(BaseModel):
    """Single data point in sentiment timeline."""

    date: str  # ISO date string (YYYY-MM-DD)
    avg_sentiment: float  # Average sentiment score (-1.0 to 1.0)
    session_count: int  # Number of sessions on this date


class PairingEffectivenessPair(BaseModel):
    """Pair-level effectiveness metrics."""

    developer: Optional[str]
    agent_type: str
    score: float
    success_rate: Optional[float] = None
    lines_per_hour: Optional[float] = None
    first_change_minutes: Optional[float] = None
    sessions: int


class RoleDynamicsSummary(BaseModel):
    """Aggregate role balance across sessions."""

    agent_led: int = 0
    dev_led: int = 0
    co_pilot: int = 0


class HandoffStats(BaseModel):
    """Metrics for parent→agent handoffs."""

    handoff_count: int = 0
    avg_response_minutes: Optional[float] = None
    success_rate: Optional[float] = None
    clarifications_avg: Optional[float] = None


class ImpactMetrics(BaseModel):
    """Impact and latency metrics."""

    avg_lines_per_hour: Optional[float] = None
    median_first_change_minutes: Optional[float] = None
    total_lines_changed: int = 0
    sessions_measured: int = 0


class SentimentByAgent(BaseModel):
    """Sentiment rollup per agent type."""

    agent_type: str
    avg_sentiment: Optional[float] = None
    sessions: int = 0


class InfluenceFlow(BaseModel):
    """Adoption/influence flows between actors."""

    source: str
    target: str
    count: int


class ErrorBucket(BaseModel):
    """Error counts by agent and category."""

    agent_type: str
    category: str
    count: int


class ThinkingTimeStats(BaseModel):
    """Approximate thinking-time metrics derived from user→assistant latency."""

    pair_count: int = 0
    median_latency_seconds: Optional[float] = None
    p95_latency_seconds: Optional[float] = None
    max_latency_seconds: Optional[float] = None
    pct_with_thinking: Optional[float] = None
    pct_with_tool_calls: Optional[float] = None


class ProjectAnalytics(BaseModel):
    """Advanced analytics for a project."""

    project_id: UUID
    date_range: Optional[str] = None
    pairing_top: list[PairingEffectivenessPair] = Field(default_factory=list)
    pairing_bottom: list[PairingEffectivenessPair] = Field(default_factory=list)
    role_dynamics: RoleDynamicsSummary = RoleDynamicsSummary()
    handoffs: HandoffStats = HandoffStats()
    impact: ImpactMetrics = ImpactMetrics()
    sentiment_by_agent: list[SentimentByAgent] = Field(default_factory=list)
    influence_flows: list[InfluenceFlow] = Field(default_factory=list)
    error_heatmap: list[ErrorBucket] = Field(default_factory=list)
    thinking_time: Optional[ThinkingTimeStats] = None


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
    last_activity: Optional[datetime] = None  # Actual last message timestamp
    duration_seconds: Optional[int] = None
    status: str
    success: Optional[bool] = None
    message_count: int = 0
    files_count: int = 0
    developer: Optional[str] = None  # Developer username
    agent_type: str

    # Hierarchy fields (for hierarchical display)
    children_count: int = 0
    depth_level: int = 0
    parent_conversation_id: Optional[UUID] = None

    # Plan fields
    plan_count: int = 0
    plan_status: Optional[str] = None  # 'approved', 'active', or 'abandoned'


class ProjectSessionsResponse(BaseModel):
    """Response schema for paginated project sessions list."""

    items: list[ProjectSession]
    total: int
    page: int
    page_size: int
    pages: int


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

    model_config = ConfigDict(from_attributes=True)


# ===== Conversation Schemas =====


class MessageResponse(BaseModel):
    """Response schema for Message."""

    id: UUID
    role: Optional[str] = None  # None for non-conversational messages
    content: str
    thinking_content: Optional[str] = None
    timestamp: datetime
    sequence: int
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    code_changes: list[dict[str, Any]] = Field(default_factory=list)
    entities: dict[str, Any] = Field(default_factory=dict)
    extra_data: dict[str, Any] = Field(default_factory=dict)

    # Extracted from extra_data for convenience
    model: Optional[str] = None  # Claude model used (e.g., "claude-opus-4-5")
    token_usage: Optional[dict[str, Any]] = (
        None  # {input_tokens, output_tokens, cache_*}
    )
    stop_reason: Optional[str] = None  # end_turn, max_tokens, tool_use

    # Phase 0: Type system alignment with aiobscura
    author_role: Optional[str] = Field(
        None,
        description="AuthorRole: human, caller, assistant, agent, tool, system",
    )
    message_type: Optional[str] = Field(
        None,
        description="MessageType: prompt, response, tool_call, tool_result, plan, summary, context, error",
    )
    emitted_at: Optional[datetime] = Field(
        None,
        description="When message was produced by source (original timestamp)",
    )
    observed_at: Optional[datetime] = Field(
        None,
        description="When message was parsed/ingested into CatSyphon",
    )
    thread_id: Optional[UUID] = Field(
        None,
        description="Thread this message belongs to (for multi-thread conversations)",
    )

    model_config = ConfigDict(from_attributes=True)


class ThreadResponse(BaseModel):
    """Response schema for Thread (Phase 0: Type system alignment)."""

    id: UUID
    conversation_id: UUID
    parent_thread_id: Optional[UUID] = Field(
        None,
        description="Parent thread for nested agent conversations",
    )
    thread_type: str = Field(
        "main",
        description="ThreadType: main, agent, background",
    )
    spawned_by_message_id: Optional[UUID] = Field(
        None,
        description="Message that spawned this thread (for agent threads)",
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackingModelResponse(BaseModel):
    """Response schema for BackingModel (Phase 0: Type system alignment)."""

    id: UUID
    provider: str = Field(..., description="LLM provider (e.g., 'anthropic', 'openai')")
    model_id: str = Field(..., description="Model identifier (e.g., 'claude-opus-4-5')")
    display_name: Optional[str] = Field(
        None,
        description="Human-readable model name",
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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
    depth_level: int = 0  # Hierarchy depth: 0 for parent, 1 for child
    plan_count: int = 0  # Number of plans in this conversation

    # Extracted from extra_data for convenience
    slug: Optional[str] = (
        None  # Human-readable session name (e.g., "sprightly-dancing-liskov")
    )
    git_branch: Optional[str] = None  # Git branch active during session
    total_tokens: Optional[int] = None  # Sum of all message token usage

    # Phase 0: Type system alignment with aiobscura
    backing_model_id: Optional[UUID] = Field(
        None,
        description="ID of the LLM model used for this conversation",
    )

    # Related objects (optional, for joins)
    project: Optional[ProjectResponse] = None
    developer: Optional[DeveloperResponse] = None

    model_config = ConfigDict(from_attributes=True)


class RawLogInfo(BaseModel):
    """Minimal raw log information for display."""

    id: UUID
    file_path: Optional[str] = None
    file_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationListItem):
    """Schema for detailed conversation view (with messages)."""

    messages: list[MessageResponse] = Field(default_factory=list)
    epochs: list[EpochResponse] = Field(default_factory=list)
    files_touched: list[FileTouchedResponse] = Field(default_factory=list)
    raw_logs: list[RawLogInfo] = Field(default_factory=list)

    # Hierarchical relationships (Phase 2: Epic 7u2)
    children: list["ConversationListItem"] = Field(default_factory=list)
    parent: Optional["ConversationListItem"] = None

    # Plan data (extracted from extra_data["plans"])
    plans: list["PlanResponse"] = Field(default_factory=list)

    # Extracted from extra_data for convenience
    summaries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Auto-generated session checkpoints [{text, leaf_uuid}]",
    )
    compaction_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Context compaction events [{timestamp, trigger, pre_tokens}]",
    )

    # Phase 0: Type system alignment with aiobscura
    threads: list[ThreadResponse] = Field(
        default_factory=list,
        description="Threads within this conversation (main, agent, background)",
    )
    backing_model: Optional[BackingModelResponse] = Field(
        None,
        description="LLM model used for this conversation",
    )

    model_config = ConfigDict(from_attributes=True)


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
    conversations_by_type: dict[str, int] = Field(
        default_factory=dict
    )  # main, agent, mcp, etc.

    # Plan statistics
    total_plans: int = 0  # Total number of plans across all conversations
    plans_by_status: dict[str, int] = Field(
        default_factory=dict
    )  # approved, active, abandoned
    conversations_with_plans: int = 0  # Conversations that have at least one plan


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
    skipped_count: int = 0
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

    model_config = ConfigDict(from_attributes=True)


class SuggestedPath(BaseModel):
    """A suggested watch directory path."""

    path: str
    name: str
    description: str
    project_count: Optional[int] = None


class PathValidationRequest(BaseModel):
    """Request schema for validating a directory path."""

    path: str


class PathValidationResponse(BaseModel):
    """Response schema for path validation."""

    valid: bool
    expanded_path: str
    exists: bool
    is_directory: bool
    is_readable: bool


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
    ingest_mode: Optional[str] = Field(
        default=None,
        description="Ingestion mode used for this job (replace/append/skip)",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-level performance metrics (deduplication_check_ms, database_operations_ms, total_ms)",
    )
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def inject_ingest_mode(cls, values: Any) -> Any:
        """
        Pull ingest_mode from metrics if not present on the model.
        """
        if isinstance(values, dict):
            if values.get("ingest_mode") is None and isinstance(
                values.get("metrics"), dict
            ):
                metrics = values.get("metrics") or {}
                if "ingest_mode" in metrics:
                    values["ingest_mode"] = metrics["ingest_mode"]
        return values


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
    peak_processing_time_ms: Optional[float] = Field(
        default=None,
        description="Peak (maximum) processing time for any single job",
    )
    processing_time_percentiles: dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Processing time percentiles (p50, p75, p90, p99) in milliseconds",
    )
    incremental_jobs: int
    incremental_percentage: float
    incremental_speedup: Optional[float] = Field(
        default=None,
        description="Speedup factor of incremental parsing (avg_full / avg_incremental)",
    )

    # Recent activity metrics
    jobs_last_hour: int = Field(
        default=0,
        description="Number of jobs processed in the last hour",
    )
    jobs_last_24h: int = Field(
        default=0,
        description="Number of jobs processed in the last 24 hours",
    )
    processing_rate_per_minute: float = Field(
        default=0.0,
        description="Average processing rate (jobs per minute over last hour)",
    )

    # Success/failure metrics
    success_rate: Optional[float] = Field(
        default=None,
        description="Success rate as percentage (0-100)",
    )
    failure_rate: Optional[float] = Field(
        default=None,
        description="Failure rate as percentage (0-100)",
    )
    time_since_last_failure_minutes: Optional[float] = Field(
        default=None,
        description="Minutes since the last failed ingestion job",
    )

    # Time-series data for sparklines
    timeseries_24h: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Hourly time-series data for last 24 hours (for sparklines)",
    )

    # Stage-level aggregate metrics
    avg_parse_duration_ms: Optional[float] = Field(
        default=None,
        description="Average parsing time (file reading + JSONL parsing)",
    )
    avg_deduplication_check_ms: Optional[float] = Field(
        default=None,
        description="Average deduplication check time (file hash + DB lookup)",
    )
    avg_database_operations_ms: Optional[float] = Field(
        default=None,
        description="Average database operations time (inserts, updates, queries)",
    )

    # Tagging aggregate metrics
    avg_tagging_duration_ms: Optional[float] = Field(
        default=None,
        description="Average total tagging duration (rule-based + LLM + merging)",
    )
    avg_llm_tagging_ms: Optional[float] = Field(
        default=None,
        description="Average LLM tagging duration (OpenAI API call time only)",
    )
    avg_llm_prompt_tokens: Optional[float] = Field(
        default=None,
        description="Average LLM prompt tokens per tagging operation",
    )
    avg_llm_completion_tokens: Optional[float] = Field(
        default=None,
        description="Average LLM completion tokens per tagging operation",
    )
    avg_llm_total_tokens: Optional[float] = Field(
        default=None,
        description="Average total LLM tokens per tagging operation",
    )
    avg_llm_cost_usd: Optional[float] = Field(
        default=None,
        description="Average LLM cost per tagging operation (USD)",
    )
    total_llm_cost_usd: Optional[float] = Field(
        default=None,
        description="Total LLM cost across all tagged jobs (USD)",
    )
    llm_cache_hit_rate: Optional[float] = Field(
        default=None,
        description="Percentage of LLM cache hits (0.0 to 1.0)",
    )

    error_rates_by_stage: dict[str, int] = Field(
        default_factory=dict,
        description="Count of errors by stage (if tracked in future)",
    )

    # Parser/change-type aggregates
    parser_usage: dict[str, int] = Field(
        default_factory=dict, description="Count of jobs per parser_name"
    )
    parser_version_usage: dict[str, int] = Field(
        default_factory=dict, description="Count of jobs per parser@version"
    )
    parse_methods: dict[str, int] = Field(
        default_factory=dict,
        description="Count of jobs per parse_method (full, incremental, etc.)",
    )
    parse_change_types: dict[str, int] = Field(
        default_factory=dict, description="Count of jobs per parse_change_type"
    )
    avg_parse_warning_count: Optional[float] = Field(
        default=None, description="Average number of parser warnings per job"
    )
    parse_warning_rate: Optional[float] = Field(
        default=None, description="Percentage of jobs with parser warnings (0-100)"
    )


class TaggingQueueStatsResponse(BaseModel):
    """Response schema for tagging queue statistics."""

    # Worker status
    worker_running: bool = Field(
        description="Whether the background tagging worker is currently running"
    )

    # Queue counts
    pending: int = Field(default=0, description="Jobs waiting to be processed")
    processing: int = Field(default=0, description="Jobs currently being processed")
    completed: int = Field(default=0, description="Successfully completed jobs")
    failed: int = Field(default=0, description="Jobs that failed after max retries")
    total: int = Field(default=0, description="Total jobs in queue (all statuses)")

    # Worker stats (if available)
    jobs_processed: int = Field(
        default=0, description="Total jobs processed by worker since startup"
    )
    jobs_succeeded: int = Field(
        default=0, description="Jobs that succeeded since startup"
    )
    jobs_failed: int = Field(
        default=0, description="Jobs that failed since startup"
    )


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

    canonical_type: str = Field(
        ..., description="Type of canonical (tagging, insights, export)"
    )
    max_tokens: int = Field(..., description="Maximum tokens allowed")
    sampling_strategy: str = Field(..., description="Sampling strategy used")


class CanonicalResponse(BaseModel):
    """Response schema for canonical conversation representation."""

    id: UUID
    conversation_id: UUID
    version: int = Field(..., description="Canonical version for cache invalidation")
    canonical_type: str = Field(
        ..., description="Type of canonical (tagging, insights, export)"
    )
    narrative: str = Field(..., description="Play-format narrative of conversation")
    token_count: int = Field(..., description="Number of tokens in narrative")
    metadata: CanonicalMetadata = Field(..., description="Extracted metadata")
    config: CanonicalConfig = Field(..., description="Configuration used")

    # Source conversation metadata
    source_message_count: int = Field(
        ..., description="Total messages in source conversation"
    )
    source_token_estimate: int = Field(..., description="Estimated tokens in source")

    # Generation metadata
    generated_at: datetime = Field(..., description="When this canonical was generated")

    model_config = ConfigDict(from_attributes=True)


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
        description="Type of canonical to regenerate (tagging, insights, export)",
    )
    sampling_strategy: str = Field(
        default="semantic",
        description="Sampling strategy (semantic, epoch, chronological)",
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
        default_factory=list, description="Observable workflow patterns"
    )
    productivity_indicators: list[str] = Field(
        default_factory=list, description="Productivity signals"
    )
    collaboration_quality: int = Field(
        ..., ge=1, le=10, description="Human-AI collaboration quality (1-10)"
    )
    key_moments: list[KeyMoment] = Field(
        default_factory=list, description="Critical turning points"
    )
    learning_opportunities: list[str] = Field(
        default_factory=list, description="Areas for improvement"
    )
    agent_effectiveness: int = Field(
        ..., ge=1, le=10, description="Agent helpfulness (1-10)"
    )
    scope_clarity: int = Field(
        ..., ge=1, le=10, description="Goal definition quality (1-10)"
    )
    technical_debt_indicators: list[str] = Field(
        default_factory=list, description="Technical debt signals"
    )
    testing_behavior: str = Field(..., description="Testing practices observed")
    summary: str = Field(..., description="2-3 sentence summary")

    # Quantitative metrics
    quantitative_metrics: QuantitativeMetrics = Field(
        ..., description="Numerical metrics"
    )

    # Metadata
    canonical_version: int = Field(..., description="Canonical algorithm version")
    analysis_timestamp: float = Field(..., description="Unix timestamp of analysis")


# ===== Health Report Schemas =====


class SessionEvidence(BaseModel):
    """A session example used as evidence in health report."""

    session_id: str
    title: str
    date: str  # ISO date string
    duration_minutes: int
    explanation: str
    outcome: str = ""  # LLM-generated description of what happened and why


class PatternEvidence(BaseModel):
    """A cross-session pattern detected."""

    description: str
    data: dict[str, Any] = Field(default_factory=dict)


class HealthReportDiagnosis(BaseModel):
    """Diagnosis section of health report."""

    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    primary_issue: Optional[str] = None
    primary_issue_detail: Optional[str] = None


class HealthReportEvidence(BaseModel):
    """Evidence section with real session examples."""

    success_example: Optional[SessionEvidence] = None
    failure_example: Optional[SessionEvidence] = None
    patterns: list[PatternEvidence] = Field(default_factory=list)


class HealthReportRecommendation(BaseModel):
    """A recommendation backed by evidence."""

    advice: str
    evidence: str
    filter_link: Optional[str] = None


# ===== Plan Schemas =====


class PlanOperationResponse(BaseModel):
    """Response schema for a single plan operation."""

    operation_type: str = Field(..., description="Operation type: create, edit, read")
    file_path: str = Field(..., description="Path to the plan file")
    content: Optional[str] = Field(
        None, description="Full content for create operations"
    )
    old_content: Optional[str] = Field(
        None, description="Old content for edit operations"
    )
    new_content: Optional[str] = Field(
        None, description="New content for edit operations"
    )
    timestamp: Optional[datetime] = Field(
        None, description="When the operation occurred"
    )
    message_index: int = Field(
        0, description="Index of the message containing this operation"
    )


class PlanResponse(BaseModel):
    """Response schema for extracted plan data."""

    plan_file_path: str = Field(..., description="Path to the plan file")
    initial_content: Optional[str] = Field(
        None, description="First version of the plan content"
    )
    final_content: Optional[str] = Field(
        None, description="Latest version after all edits"
    )
    status: str = Field(
        "active", description="Plan status: active, approved, abandoned"
    )
    iteration_count: int = Field(1, description="Number of edits to the plan")
    operations: list[PlanOperationResponse] = Field(
        default_factory=list, description="List of operations on this plan"
    )
    entry_message_index: Optional[int] = Field(
        None, description="Message index where plan mode started"
    )
    exit_message_index: Optional[int] = Field(
        None, description="Message index where plan mode exited"
    )
    related_agent_session_ids: list[str] = Field(
        default_factory=list, description="Session IDs of related Plan agents"
    )


class PlanListItem(BaseModel):
    """Lightweight plan info for list view."""

    plan_file_path: str
    status: str
    iteration_count: int
    conversation_id: UUID
    conversation_start_time: datetime
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None


class PlanListResponse(BaseModel):
    """Paginated list of plans."""

    items: list[PlanListItem]
    total: int
    page: int
    page_size: int
    pages: int


class PlanDetailResponse(PlanResponse):
    """Detailed plan view with full content and conversation context."""

    conversation_id: UUID
    conversation_start_time: datetime
    project_id: Optional[UUID] = None
    project_name: Optional[str] = None

    # Execution tracking (future enhancement)
    executed_steps: list[dict[str, Any]] = Field(
        default_factory=list, description="Plan steps matched to execution"
    )
    execution_progress: Optional[float] = Field(
        None, description="Execution progress 0.0 to 1.0"
    )


class HealthReportResponse(BaseModel):
    """Response schema for project health report."""

    # Hero section
    score: float = Field(..., description="Overall health score (0-1)")
    label: str = Field(
        ..., description="Quality label (Excellent/Good/Developing/Needs Attention)"
    )
    summary: str = Field(..., description="Plain English summary")

    # Diagnosis
    diagnosis: HealthReportDiagnosis

    # Evidence
    evidence: HealthReportEvidence

    # Recommendations
    recommendations: list[HealthReportRecommendation] = Field(default_factory=list)

    # Session links for drill-down
    session_links: dict[str, str] = Field(default_factory=dict)

    # Metadata
    sessions_analyzed: int = 0
    generated_at: float = Field(..., description="Unix timestamp of generation")
    cached: bool = Field(
        default=False, description="Whether this was served from cache"
    )


# ===== Collector Events API Schemas =====


class CollectorRegisterRequest(BaseModel):
    """Request schema for registering a new collector."""

    collector_type: str = Field(
        ..., description="Type of collector (aiobscura, watcher, sdk)"
    )
    collector_version: str = Field(..., description="Version of the collector")
    hostname: str = Field(..., description="Hostname of the collector machine")
    workspace_id: UUID = Field(..., description="Workspace ID for multi-tenancy")
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata (os, user, etc.)"
    )


class CollectorRegisterResponse(BaseModel):
    """Response schema for collector registration."""

    collector_id: UUID
    api_key: str = Field(..., description="API key (only returned once)")
    api_key_prefix: str = Field(..., description="API key prefix for identification")
    created_at: datetime


class EventData(BaseModel):
    """Base event data - type-specific payload."""

    # Common fields that may appear in various event types
    # Message events
    author_role: Optional[str] = Field(
        None, description="Who produced the message (human, assistant, agent, tool, system)"
    )
    message_type: Optional[str] = Field(
        None, description="Semantic type (prompt, response, tool_call, tool_result, context, error)"
    )
    content: Optional[str] = Field(None, description="Message content")
    model: Optional[str] = Field(None, description="LLM model used")
    token_usage: Optional[dict[str, int]] = Field(None, description="Token consumption stats")
    thinking_content: Optional[str] = Field(None, description="Extended thinking blocks")
    thinking_metadata: Optional[dict[str, Any]] = Field(None, description="Thinking level settings")
    stop_reason: Optional[str] = Field(None, description="Why generation stopped")
    raw_data: Optional[dict[str, Any]] = Field(None, description="Original message data")

    # Tool call events
    tool_name: Optional[str] = Field(None, description="Name of the tool")
    tool_use_id: Optional[str] = Field(None, description="Tool use identifier")
    parameters: Optional[dict[str, Any]] = Field(None, description="Tool parameters")

    # Tool result events
    success: Optional[bool] = Field(None, description="Whether tool succeeded")
    result: Optional[str] = Field(None, description="Tool result content")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Session start events
    agent_type: Optional[str] = Field(None, description="Type of agent")
    agent_version: Optional[str] = Field(None, description="Agent version")
    working_directory: Optional[str] = Field(None, description="Working directory")
    git_branch: Optional[str] = Field(None, description="Git branch")
    parent_session_id: Optional[str] = Field(None, description="Parent session ID")
    context_semantics: Optional[dict[str, Any]] = Field(None, description="Context sharing settings")

    # Session start events - metadata for semantic parity
    slug: Optional[str] = Field(None, description="Human-readable session name")
    summaries: Optional[list[dict[str, Any]]] = Field(
        None, description="Session checkpoint summaries"
    )
    compaction_events: Optional[list[dict[str, Any]]] = Field(
        None, description="Context compaction events"
    )

    # Session end events
    outcome: Optional[str] = Field(
        None, description="Session outcome (success, partial, failed, abandoned)"
    )
    summary: Optional[str] = Field(None, description="Session summary")
    total_messages: Optional[int] = Field(None, description="Total message count")
    total_tool_calls: Optional[int] = Field(None, description="Total tool calls")

    # Session end events - data for semantic parity
    plans: Optional[list[dict[str, Any]]] = Field(
        None, description="Plan data from session (list of PlanInfo dicts)"
    )
    files_touched: Optional[list[str]] = Field(
        None, description="All files touched during session"
    )

    model_config = ConfigDict(extra="allow")


class CollectorEvent(BaseModel):
    """Single event in an event batch."""

    type: str = Field(
        ...,
        description="Event type (session_start, session_end, message, tool_call, tool_result, thinking, error, metadata)",
    )
    emitted_at: datetime = Field(
        ..., description="When the event was originally produced by the source"
    )
    observed_at: datetime = Field(
        ..., description="When the collector observed the event"
    )
    event_hash: Optional[str] = Field(
        None, max_length=32, description="Content-based hash for deduplication"
    )
    data: EventData = Field(..., description="Type-specific payload")

    @model_validator(mode="after")
    def validate_event_data(self) -> "CollectorEvent":
        """Validate that required fields are present based on event type."""
        event_type = self.type
        data = self.data

        if event_type == "session_start":
            if not data.agent_type:
                raise ValueError("session_start events require agent_type in data")
        elif event_type == "message":
            if not data.author_role:
                raise ValueError("message events require author_role in data")
            if not data.message_type:
                raise ValueError("message events require message_type in data")
        elif event_type == "tool_call":
            if not data.tool_name:
                raise ValueError("tool_call events require tool_name in data")
            if not data.tool_use_id:
                raise ValueError("tool_call events require tool_use_id in data")
        elif event_type == "tool_result":
            if not data.tool_use_id:
                raise ValueError("tool_result events require tool_use_id in data")
        elif event_type == "session_end":
            if not data.outcome:
                raise ValueError("session_end events require outcome in data")

        return self


class CollectorEventsRequest(BaseModel):
    """Request schema for submitting event batch."""

    session_id: str = Field(..., description="Unique session identifier from the agent")
    events: list[CollectorEvent] = Field(
        ..., min_length=1, max_length=50, description="Batch of events to submit"
    )


class CollectorEventsResponse(BaseModel):
    """Response schema for event batch submission."""

    accepted: int = Field(..., description="Number of events accepted")
    last_sequence: Optional[int] = Field(
        None, description="Last sequence number (deprecated, use event_count)"
    )
    conversation_id: UUID = Field(..., description="CatSyphon's internal conversation ID")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal issues")


class CollectorSessionStatusResponse(BaseModel):
    """Response schema for session status check."""

    session_id: str
    conversation_id: UUID
    last_sequence: int = Field(..., description="Last received sequence number")
    event_count: int = Field(..., description="Total events received")
    first_event_at: datetime
    last_event_at: datetime
    status: str = Field(..., description="Session status (active, completed)")


class CollectorSessionCompleteRequest(BaseModel):
    """Request schema for marking session complete."""

    event_count: Optional[int] = Field(
        None, description="Total events in session (informational)"
    )
    outcome: str = Field(
        ..., description="Session outcome (success, partial, failed, abandoned)"
    )
    summary: Optional[str] = Field(None, description="Optional session summary")


class CollectorSessionCompleteResponse(BaseModel):
    """Response schema for session completion."""

    session_id: str
    conversation_id: UUID
    status: str = Field(default="completed")
    total_events: int


class CollectorSequenceGapError(BaseModel):
    """Error response for sequence gap."""

    error: str = Field(default="sequence_gap")
    message: str
    last_received_sequence: int
    expected_sequence: int


# ===== Automation Recommendation Schemas =====


class RecommendationEvidence(BaseModel):
    """Evidence supporting a recommendation."""

    quotes: list[str] = Field(
        default_factory=list, description="Relevant quotes from conversation"
    )
    pattern_count: int = Field(
        default=0, description="Number of times pattern was detected"
    )
    # MCP-specific evidence fields
    matched_signals: list[str] = Field(
        default_factory=list, description="Signal patterns that matched (MCP)"
    )
    workarounds_detected: list[str] = Field(
        default_factory=list, description="Workarounds the developer used (MCP)"
    )
    friction_indicators: list[str] = Field(
        default_factory=list, description="Friction signs like errors/retries (MCP)"
    )


class SuggestedImplementation(BaseModel):
    """Suggested implementation details for a slash command or MCP."""

    # Slash command fields
    command_name: Optional[str] = Field(None, description="Suggested /command name")
    trigger_phrases: list[str] = Field(
        default_factory=list, description="Example phrases that would invoke this"
    )
    template: Optional[str] = Field(
        None, description="Suggested command template/prompt"
    )
    # MCP-specific fields
    category: Optional[str] = Field(
        None, description="MCP category (browser-automation, database, etc.)"
    )
    suggested_mcps: list[str] = Field(
        default_factory=list, description="Suggested MCP servers to install"
    )
    use_cases: list[str] = Field(
        default_factory=list, description="Use cases this MCP would enable"
    )
    friction_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Friction score without this MCP"
    )


class RecommendationResponse(BaseModel):
    """Response schema for a single automation recommendation."""

    id: UUID
    conversation_id: UUID
    recommendation_type: str = Field(
        ..., description="Type: slash_command, mcp_server, sub_agent"
    )
    title: str = Field(..., description="Brief title for the recommendation")
    description: str = Field(..., description="Detailed explanation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    priority: int = Field(..., ge=0, le=4, description="Priority (0=critical, 4=low)")
    evidence: RecommendationEvidence = Field(
        default_factory=RecommendationEvidence, description="Supporting evidence"
    )
    suggested_implementation: Optional[SuggestedImplementation] = Field(
        None, description="Implementation details for slash commands"
    )
    status: str = Field(
        default="pending",
        description="Status: pending, accepted, dismissed, implemented",
    )
    user_feedback: Optional[str] = Field(None, description="User feedback if provided")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationUpdate(BaseModel):
    """Request schema for updating a recommendation."""

    status: Optional[str] = Field(
        None, description="New status: pending, accepted, dismissed, implemented"
    )
    user_feedback: Optional[str] = Field(None, description="User feedback")


class RecommendationListResponse(BaseModel):
    """Response schema for list of recommendations."""

    items: list[RecommendationResponse]
    total: int
    conversation_id: UUID


class RecommendationSummaryStats(BaseModel):
    """Summary statistics for recommendations."""

    total: int = Field(..., description="Total recommendations")
    by_status: dict[str, int] = Field(
        default_factory=dict, description="Count by status"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count by recommendation type"
    )
    average_confidence: float = Field(..., description="Average confidence score")


class DetectionRequest(BaseModel):
    """Request schema for triggering recommendation detection."""

    force_regenerate: bool = Field(
        default=False,
        description="Force regeneration even if recommendations exist",
    )


class DetectionResponse(BaseModel):
    """Response schema for detection result."""

    conversation_id: UUID
    recommendations_count: int = Field(
        ..., description="Number of recommendations detected"
    )
    tokens_analyzed: int = Field(
        ..., description="Tokens in the analyzed narrative"
    )
    detection_model: str = Field(..., description="Model used for detection")
    recommendations: list[RecommendationResponse] = Field(
        default_factory=list, description="Detected recommendations"
    )


# ===== Benchmark Schemas =====


class BenchmarkItem(BaseModel):
    """Single benchmark result entry."""

    name: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BenchmarkResultResponse(BaseModel):
    """Response schema for benchmark run results."""

    run_id: str
    started_at: datetime
    completed_at: datetime
    benchmarks: list[BenchmarkItem]
    environment: dict[str, Any] = Field(default_factory=dict)


class BenchmarkStatusResponse(BaseModel):
    """Response schema for benchmark runner status."""

    status: str
    run_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
