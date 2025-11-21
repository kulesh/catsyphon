"""Data models for conversation canonicalization."""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class CanonicalType(str, enum.Enum):
    """Type of canonical representation (determines token budget and sampling)."""

    TAGGING = "tagging"  # For LLM/rule-based tagging (8K tokens)
    INSIGHTS = "insights"  # For Epic 8 analytics (12K tokens)
    EXPORT = "export"  # For debugging/export (20K tokens)


@dataclass
class CanonicalConfig:
    """Configuration for canonicalization process."""

    # Token budget
    token_budget: int = 8000

    # Sampling strategy
    include_thinking: bool = True  # Include thinking_content
    include_tool_details: bool = True  # Include tool parameters and results
    include_code_changes: bool = True  # Include code change summaries
    include_children: bool = True  # Include child conversations (agents, MCP, etc.)

    # Hierarchical limits
    max_child_depth: int = 3  # Maximum nesting depth for children
    child_token_budget: int = 3000  # Total token budget for all children

    # Sampling parameters
    always_include_first_n: int = 10  # Always include first N messages
    always_include_last_n: int = 10  # Always include last N messages
    error_context_messages: int = 2  # Messages before/after errors
    tool_call_context_messages: int = 1  # Messages before/after tool calls

    # Content truncation
    max_message_chars: int = 1000  # Truncate long messages
    max_thinking_chars: int = 500  # Truncate long thinking blocks
    max_tool_param_chars: int = 200  # Truncate tool parameters

    @classmethod
    def for_type(cls, canonical_type: CanonicalType) -> "CanonicalConfig":
        """Create config for specific canonical type."""
        if canonical_type == CanonicalType.TAGGING:
            return cls(
                token_budget=8000,
                include_thinking=True,
                include_tool_details=True,
                include_code_changes=False,  # Not needed for tagging
                child_token_budget=2000,
            )
        elif canonical_type == CanonicalType.INSIGHTS:
            return cls(
                token_budget=12000,
                include_thinking=True,
                include_tool_details=True,
                include_code_changes=True,
                child_token_budget=3000,
            )
        elif canonical_type == CanonicalType.EXPORT:
            return cls(
                token_budget=20000,
                include_thinking=True,
                include_tool_details=True,
                include_code_changes=True,
                child_token_budget=5000,
                max_message_chars=2000,  # More content for export
                max_thinking_chars=1000,
            )
        else:
            return cls()  # Default

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "token_budget": self.token_budget,
            "include_thinking": self.include_thinking,
            "include_tool_details": self.include_tool_details,
            "include_code_changes": self.include_code_changes,
            "include_children": self.include_children,
            "max_child_depth": self.max_child_depth,
            "child_token_budget": self.child_token_budget,
            "always_include_first_n": self.always_include_first_n,
            "always_include_last_n": self.always_include_last_n,
            "error_context_messages": self.error_context_messages,
            "tool_call_context_messages": self.tool_call_context_messages,
            "max_message_chars": self.max_message_chars,
            "max_thinking_chars": self.max_thinking_chars,
            "max_tool_param_chars": self.max_tool_param_chars,
        }


@dataclass
class CanonicalConversation:
    """Unified canonical representation of a conversation."""

    # Identity
    session_id: str
    conversation_id: str  # UUID as string

    # Metadata
    agent_type: str
    agent_version: Optional[str]
    conversation_type: str  # 'main', 'agent', 'mcp', 'skill', 'command', 'other'
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]

    # Statistics
    message_count: int
    epoch_count: int
    files_count: int
    tool_calls_count: int

    # Narrative (the "play" format)
    narrative: str
    token_count: int  # Actual token count of narrative

    # Hierarchy
    parent_id: Optional[str] = None  # Parent conversation ID
    children: list["CanonicalConversation"] = field(default_factory=list)

    # Structured metadata (for efficient querying without parsing narrative)
    tools_used: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    has_errors: bool = False
    code_changes_summary: dict = field(
        default_factory=dict
    )  # {added: N, deleted: M, modified: K}

    # Generation metadata
    config: Optional[CanonicalConfig] = None
    canonical_version: int = 1
    generated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "agent_type": self.agent_type,
            "agent_version": self.agent_version,
            "conversation_type": self.conversation_type,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "message_count": self.message_count,
            "epoch_count": self.epoch_count,
            "files_count": self.files_count,
            "tool_calls_count": self.tool_calls_count,
            "narrative": self.narrative,
            "token_count": self.token_count,
            "parent_id": self.parent_id,
            "children": [child.to_dict() for child in self.children],
            "tools_used": self.tools_used,
            "files_touched": self.files_touched,
            "has_errors": self.has_errors,
            "code_changes_summary": self.code_changes_summary,
            "canonical_version": self.canonical_version,
            "generated_at": (
                self.generated_at.isoformat() if self.generated_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CanonicalConversation":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            conversation_id=data["conversation_id"],
            agent_type=data["agent_type"],
            agent_version=data.get("agent_version"),
            conversation_type=data["conversation_type"],
            start_time=(
                datetime.fromisoformat(data["start_time"])
                if data.get("start_time")
                else datetime.now()
            ),
            end_time=(
                datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None
            ),
            duration_seconds=data.get("duration_seconds"),
            message_count=data["message_count"],
            epoch_count=data["epoch_count"],
            files_count=data["files_count"],
            tool_calls_count=data["tool_calls_count"],
            narrative=data["narrative"],
            token_count=data["token_count"],
            parent_id=data.get("parent_id"),
            children=[
                cls.from_dict(child) for child in data.get("children", [])
            ],
            tools_used=data.get("tools_used", []),
            files_touched=data.get("files_touched", []),
            has_errors=data.get("has_errors", False),
            code_changes_summary=data.get("code_changes_summary", {}),
            canonical_version=data.get("canonical_version", 1),
            generated_at=(
                datetime.fromisoformat(data["generated_at"])
                if data.get("generated_at")
                else None
            ),
        )
