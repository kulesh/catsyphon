"""
Parsed conversation data models.

These are intermediate Python dataclasses representing parsed conversations
before they are stored in the database. Used by parsers and the ingestion pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ToolCall:
    """Tool invocation by agent."""

    tool_name: str
    parameters: dict
    result: Optional[str] = None
    success: bool = True
    timestamp: Optional[datetime] = None


@dataclass
class CodeChange:
    """Code modification."""

    file_path: str
    change_type: str  # 'create', 'edit', 'delete'
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    lines_added: int = 0
    lines_deleted: int = 0


@dataclass
class PlanOperation:
    """A single operation on a plan file."""

    operation_type: str  # 'create', 'edit', 'read'
    file_path: str
    content: Optional[str] = None  # Full content for creates
    old_content: Optional[str] = None  # For edits
    new_content: Optional[str] = None  # For edits
    timestamp: Optional[datetime] = None
    message_index: int = 0  # Index in conversation messages

    def to_dict(self) -> dict:
        """Convert to dictionary for JSONB storage."""
        return {
            "operation_type": self.operation_type,
            "file_path": self.file_path,
            "content": self.content,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "message_index": self.message_index,
        }


@dataclass
class PlanInfo:
    """Extracted plan metadata from a conversation."""

    plan_file_path: str
    initial_content: Optional[str] = None  # First written version
    final_content: Optional[str] = None  # Latest version after edits
    status: str = "active"  # 'active', 'approved', 'abandoned'
    iteration_count: int = 1  # Number of edits to the plan
    operations: list[PlanOperation] = field(default_factory=list)
    entry_message_index: Optional[int] = None  # Message where plan mode started
    exit_message_index: Optional[int] = None  # Message where plan mode exited
    related_agent_session_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSONB storage."""
        return {
            "plan_file_path": self.plan_file_path,
            "initial_content": self.initial_content,
            "final_content": self.final_content,
            "status": self.status,
            "iteration_count": self.iteration_count,
            "operations": [op.to_dict() for op in self.operations],
            "entry_message_index": self.entry_message_index,
            "exit_message_index": self.exit_message_index,
            "related_agent_session_ids": self.related_agent_session_ids,
        }


@dataclass
class ParsedMessage:
    """Single message in a conversation."""

    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    tool_calls: list[ToolCall] = field(default_factory=list)
    code_changes: list[CodeChange] = field(default_factory=list)
    entities: dict = field(default_factory=dict)
    model: Optional[str] = None  # Claude model used (for assistant messages)
    token_usage: Optional[dict] = None  # Token usage statistics
    thinking_content: Optional[str] = None  # Extended thinking blocks (Claude)
    stop_reason: Optional[str] = None  # Why generation stopped (end_turn, max_tokens, tool_use)
    thinking_metadata: Optional[dict] = None  # Thinking level and settings


@dataclass
class ParsedConversation:
    """Unified format for all parsed conversations."""

    agent_type: str
    agent_version: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    messages: list[ParsedMessage]
    metadata: dict = field(default_factory=dict)
    session_id: Optional[str] = None  # Unique session identifier
    git_branch: Optional[str] = None  # Git branch during conversation
    working_directory: Optional[str] = None  # Working directory path
    files_touched: list[str] = field(default_factory=list)  # List of file paths
    code_changes: list[CodeChange] = field(default_factory=list)  # Code modifications

    # Hierarchy fields (Phase 2: Epic 7u2)
    conversation_type: str = "main"  # 'main', 'agent', 'mcp', 'skill', 'command', 'other'
    parent_session_id: Optional[str] = None  # Parent session ID for agent/tool conversations
    context_semantics: dict = field(default_factory=dict)  # Context sharing behavior
    agent_metadata: dict = field(default_factory=dict)  # Agent-specific metadata

    # Plan tracking
    plans: list[PlanInfo] = field(default_factory=list)  # Extracted plan data

    # Session identification
    slug: Optional[str] = None  # Human-readable session name (e.g., "sprightly-dancing-liskov")

    # Summaries (auto-generated session checkpoints)
    summaries: list[dict] = field(default_factory=list)

    # Context compaction events (when conversation was compacted)
    compaction_events: list[dict] = field(default_factory=list)


@dataclass
class ConversationTags:
    """Tags generated by the tagging engine."""

    # Sentiment
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None

    # Classification
    intent: Optional[str] = None
    outcome: Optional[str] = None

    # Iteration tracking
    iterations: int = 1

    # Extracted entities
    entities: dict = field(default_factory=dict)

    # Features and problems
    features: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)

    # Tools used
    tools_used: list[str] = field(default_factory=list)
    has_errors: bool = False

    # LLM reasoning (why these tags were assigned)
    reasoning: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage in JSONB."""
        return {
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "intent": self.intent,
            "outcome": self.outcome,
            "iterations": self.iterations,
            "entities": self.entities,
            "features": self.features,
            "problems": self.problems,
            "patterns": self.patterns,
            "tools_used": self.tools_used,
            "has_errors": self.has_errors,
            "reasoning": self.reasoning,
        }
