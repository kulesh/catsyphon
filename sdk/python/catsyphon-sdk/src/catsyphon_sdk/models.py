"""
Event models for the CatSyphon Collector API.

These models define the structure of events that can be sent to CatSyphon.
They are designed to be independent of any CatSyphon internal types.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events that can be sent to the collector."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"


class SessionStartData(BaseModel):
    """Data for session_start events."""

    agent_type: str = Field(..., description="Type of AI agent (e.g., 'claude-code')")
    agent_version: Optional[str] = Field(None, description="Agent version string")
    working_directory: Optional[str] = Field(None, description="Working directory path")
    git_branch: Optional[str] = Field(None, description="Current git branch")
    parent_session_id: Optional[str] = Field(
        None, description="Parent session ID for sub-agent conversations"
    )
    context_semantics: Optional[str] = Field(
        None, description="Context semantics (e.g., 'new', 'continue')"
    )
    slug: Optional[str] = Field(None, description="Human-readable session name")
    summaries: Optional[list[dict[str, Any]]] = Field(
        None, description="Session summaries from context compaction"
    )
    compaction_events: Optional[list[dict[str, Any]]] = Field(
        None, description="Context compaction events"
    )

    model_config = {"extra": "allow"}  # Allow additional metadata fields


class SessionEndData(BaseModel):
    """Data for session_end events."""

    outcome: str = Field(
        ..., description="Session outcome (success, partial, failed, abandoned)"
    )
    summary: Optional[str] = Field(None, description="Session summary text")
    total_messages: Optional[int] = Field(None, description="Total message count")
    plans: Optional[list[dict[str, Any]]] = Field(
        None, description="Plan mode data from the session"
    )
    files_touched: Optional[list[str]] = Field(
        None, description="Files modified during the session"
    )


class MessageData(BaseModel):
    """Data for message events."""

    author_role: str = Field(
        ..., description="Role of the message author (human, assistant, system, tool)"
    )
    message_type: str = Field(
        ..., description="Type of message (prompt, response, tool_result)"
    )
    content: str = Field(..., description="Message content")
    model: Optional[str] = Field(None, description="Model that generated this message")
    token_usage: Optional[dict[str, int]] = Field(
        None, description="Token usage stats (input, output, cache_read, etc.)"
    )
    thinking_content: Optional[str] = Field(
        None, description="Extended thinking content"
    )
    stop_reason: Optional[str] = Field(
        None, description="Reason the model stopped generating"
    )
    thinking_metadata: Optional[dict[str, Any]] = Field(
        None, description="Metadata about thinking process"
    )


class ToolCallData(BaseModel):
    """Data for tool_call events."""

    tool_name: str = Field(..., description="Name of the tool being called")
    tool_use_id: str = Field(..., description="Unique ID for this tool invocation")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Tool parameters"
    )


class ToolResultData(BaseModel):
    """Data for tool_result events."""

    tool_use_id: str = Field(..., description="ID of the tool call this responds to")
    success: bool = Field(..., description="Whether the tool call succeeded")
    result: str = Field(..., description="Tool result content")


class ThinkingData(BaseModel):
    """Data for thinking events."""

    content: str = Field(..., description="Thinking content")
    thinking_id: Optional[str] = Field(None, description="Unique ID for this thinking")


class ErrorData(BaseModel):
    """Data for error events."""

    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    details: Optional[dict[str, Any]] = Field(None, description="Additional details")


# Union of all event data types
EventData = Union[
    SessionStartData,
    SessionEndData,
    MessageData,
    ToolCallData,
    ToolResultData,
    ThinkingData,
    ErrorData,
    dict[str, Any],  # Fallback for extensibility
]


class Event(BaseModel):
    """A single event to send to the collector."""

    sequence: int = Field(..., description="Sequence number (1-indexed, monotonic)")
    type: EventType = Field(..., description="Event type")
    emitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event occurred in the agent",
    )
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event was observed by the collector",
    )
    data: EventData = Field(..., description="Event-specific data")

    def model_dump_json_safe(self) -> dict[str, Any]:
        """Dump to a JSON-serializable dict with ISO timestamps."""
        d = self.model_dump()
        d["emitted_at"] = self.emitted_at.isoformat()
        d["observed_at"] = self.observed_at.isoformat()
        return d


# API Response Models


class RegisterResponse(BaseModel):
    """Response from collector registration."""

    collector_id: UUID
    api_key: str = Field(..., description="API key (only shown once)")
    api_key_prefix: str = Field(..., description="API key prefix for identification")
    created_at: datetime


class EventsResponse(BaseModel):
    """Response from event submission."""

    accepted: int = Field(..., description="Number of events accepted")
    last_sequence: int = Field(..., description="Last sequence number received")
    conversation_id: UUID = Field(..., description="CatSyphon conversation ID")
    warnings: list[str] = Field(default_factory=list)


class SessionStatusResponse(BaseModel):
    """Response from session status check."""

    session_id: str
    conversation_id: UUID
    last_sequence: int
    event_count: int
    first_event_at: datetime
    last_event_at: datetime
    status: str


class SessionCompleteResponse(BaseModel):
    """Response from session completion."""

    session_id: str
    conversation_id: UUID
    status: str
    total_events: int
