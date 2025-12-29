"""
Session context managers for CatSyphon SDK.

Provides high-level APIs for streaming events to a session with
automatic batching and lifecycle management.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from catsyphon_sdk.models import (
    Event,
    EventType,
    MessageData,
    SessionEndData,
    SessionStartData,
    ThinkingData,
    ToolCallData,
    ToolResultData,
)

if TYPE_CHECKING:
    from catsyphon_sdk.client import AsyncCollectorClient, CollectorClient

logger = logging.getLogger(__name__)


class Session:
    """
    Synchronous session context manager for streaming events.

    Usage:
        with client.session("session-123") as session:
            session.start(agent_type="my-agent")
            session.message(role="user", content="Hello")
            session.message(role="assistant", content="Hi there!")
            session.tool_call(name="Read", parameters={"file_path": "/foo"})
            session.tool_result(success=True, result="file contents...")
            session.complete(outcome="success")
    """

    def __init__(
        self,
        client: "CollectorClient",
        session_id: str,
        batch_size: int = 20,
        auto_flush: bool = True,
    ):
        """
        Initialize a session.

        Args:
            client: CollectorClient instance
            session_id: Unique session identifier
            batch_size: Maximum events before auto-flush
            auto_flush: Whether to auto-flush on batch size
        """
        self.client = client
        self.session_id = session_id
        self.batch_size = batch_size
        self.auto_flush = auto_flush

        self._sequence = 0
        self._events: list[Event] = []
        self._started = False
        self._completed = False
        self._conversation_id: Optional[str] = None

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Flush any remaining events
        if self._events:
            self.flush()

        # Auto-complete if started but not completed
        if self._started and not self._completed:
            outcome = "failed" if exc_type is not None else "success"
            self.complete(outcome=outcome)

    def _next_sequence(self) -> int:
        """Get the next sequence number."""
        self._sequence += 1
        return self._sequence

    def _add_event(self, event_type: EventType, data: Any) -> None:
        """Add an event to the batch."""
        event = Event(
            sequence=self._next_sequence(),
            type=event_type,
            emitted_at=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            data=data,
        )
        self._events.append(event)

        if self.auto_flush and len(self._events) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """Send all pending events to the server."""
        if not self._events:
            return

        response = self.client.send_events(self.session_id, self._events)
        self._conversation_id = str(response.conversation_id)

        logger.debug(
            f"Flushed {len(self._events)} events, accepted={response.accepted}"
        )
        self._events.clear()

    def start(
        self,
        agent_type: str,
        agent_version: Optional[str] = None,
        working_directory: Optional[str] = None,
        git_branch: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        **metadata: Any,
    ) -> None:
        """
        Start the session.

        Args:
            agent_type: Type of AI agent (e.g., 'claude-code', 'my-agent')
            agent_version: Agent version string
            working_directory: Working directory path
            git_branch: Current git branch
            parent_session_id: Parent session ID for sub-agents
            **metadata: Additional metadata fields
        """
        if self._started:
            logger.warning("Session already started")
            return

        data = SessionStartData(
            agent_type=agent_type,
            agent_version=agent_version,
            working_directory=working_directory,
            git_branch=git_branch,
            parent_session_id=parent_session_id,
            **metadata,
        )
        self._add_event(EventType.SESSION_START, data.model_dump(exclude_none=True))
        self._started = True

    def message(
        self,
        role: str,
        content: str,
        message_type: Optional[str] = None,
        model: Optional[str] = None,
        token_usage: Optional[dict[str, int]] = None,
        thinking_content: Optional[str] = None,
        stop_reason: Optional[str] = None,
    ) -> None:
        """
        Add a message event.

        Args:
            role: Author role (human, assistant, system, tool)
            content: Message content
            message_type: Type of message (prompt, response, tool_result)
            model: Model that generated this message
            token_usage: Token usage statistics
            thinking_content: Extended thinking content
            stop_reason: Reason the model stopped
        """
        # Map common role names
        author_role = {
            "user": "human",
            "human": "human",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
        }.get(role, role)

        # Default message type based on role
        if message_type is None:
            message_type = "prompt" if author_role == "human" else "response"

        data = MessageData(
            author_role=author_role,
            message_type=message_type,
            content=content,
            model=model,
            token_usage=token_usage,
            thinking_content=thinking_content,
            stop_reason=stop_reason,
        )
        self._add_event(EventType.MESSAGE, data.model_dump(exclude_none=True))

    def tool_call(
        self,
        name: str,
        parameters: Optional[dict[str, Any]] = None,
        tool_use_id: Optional[str] = None,
    ) -> str:
        """
        Add a tool call event.

        Args:
            name: Tool name
            parameters: Tool parameters
            tool_use_id: Unique ID for this tool call (auto-generated if not provided)

        Returns:
            The tool_use_id (for matching with tool_result)
        """
        if tool_use_id is None:
            tool_use_id = f"tool_{self._sequence + 1}"

        data = ToolCallData(
            tool_name=name,
            tool_use_id=tool_use_id,
            parameters=parameters or {},
        )
        self._add_event(EventType.TOOL_CALL, data.model_dump())
        return tool_use_id

    def tool_result(
        self,
        tool_use_id: str,
        success: bool,
        result: str,
    ) -> None:
        """
        Add a tool result event.

        Args:
            tool_use_id: ID of the corresponding tool call
            success: Whether the tool succeeded
            result: Tool result content
        """
        data = ToolResultData(
            tool_use_id=tool_use_id,
            success=success,
            result=result,
        )
        self._add_event(EventType.TOOL_RESULT, data.model_dump())

    def thinking(
        self,
        content: str,
        thinking_id: Optional[str] = None,
    ) -> None:
        """
        Add a thinking event.

        Args:
            content: Thinking content
            thinking_id: Unique ID for this thinking block
        """
        data = ThinkingData(
            content=content,
            thinking_id=thinking_id,
        )
        self._add_event(EventType.THINKING, data.model_dump(exclude_none=True))

    def error(
        self,
        error_type: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Add an error event.

        Args:
            error_type: Type of error
            message: Error message
            details: Additional error details
        """
        data = {
            "error_type": error_type,
            "message": message,
        }
        if details:
            data["details"] = details

        self._add_event(EventType.ERROR, data)

    def complete(
        self,
        outcome: str = "success",
        summary: Optional[str] = None,
        plans: Optional[list[dict[str, Any]]] = None,
        files_touched: Optional[list[str]] = None,
    ) -> None:
        """
        Complete the session.

        Args:
            outcome: Session outcome (success, partial, failed, abandoned)
            summary: Session summary text
            plans: Plan mode data
            files_touched: Files modified during the session
        """
        if self._completed:
            logger.warning("Session already completed")
            return

        # Flush pending events first
        self.flush()

        data = SessionEndData(
            outcome=outcome,
            summary=summary,
            total_messages=self._sequence,
            plans=plans,
            files_touched=files_touched,
        )
        self._add_event(EventType.SESSION_END, data.model_dump(exclude_none=True))
        self.flush()

        # Call complete endpoint
        self.client.complete_session(
            session_id=self.session_id,
            final_sequence=self._sequence,
            outcome=outcome,
            summary=summary,
        )

        self._completed = True


class AsyncSession:
    """
    Asynchronous session context manager for streaming events.

    Usage:
        async with client.session("session-123") as session:
            await session.start(agent_type="my-agent")
            await session.message(role="user", content="Hello")
            await session.complete(outcome="success")
    """

    def __init__(
        self,
        client: "AsyncCollectorClient",
        session_id: str,
        batch_size: int = 20,
        auto_flush: bool = True,
    ):
        """Initialize an async session."""
        self.client = client
        self.session_id = session_id
        self.batch_size = batch_size
        self.auto_flush = auto_flush

        self._sequence = 0
        self._events: list[Event] = []
        self._started = False
        self._completed = False
        self._conversation_id: Optional[str] = None

    async def __aenter__(self) -> "AsyncSession":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._events:
            await self.flush()

        if self._started and not self._completed:
            outcome = "failed" if exc_type is not None else "success"
            await self.complete(outcome=outcome)

    def _next_sequence(self) -> int:
        """Get the next sequence number."""
        self._sequence += 1
        return self._sequence

    async def _add_event(self, event_type: EventType, data: Any) -> None:
        """Add an event to the batch."""
        event = Event(
            sequence=self._next_sequence(),
            type=event_type,
            emitted_at=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            data=data,
        )
        self._events.append(event)

        if self.auto_flush and len(self._events) >= self.batch_size:
            await self.flush()

    async def flush(self) -> None:
        """Send all pending events to the server."""
        if not self._events:
            return

        response = await self.client.send_events(self.session_id, self._events)
        self._conversation_id = str(response.conversation_id)

        logger.debug(
            f"Flushed {len(self._events)} events, accepted={response.accepted}"
        )
        self._events.clear()

    async def start(
        self,
        agent_type: str,
        agent_version: Optional[str] = None,
        working_directory: Optional[str] = None,
        git_branch: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        **metadata: Any,
    ) -> None:
        """Start the session."""
        if self._started:
            logger.warning("Session already started")
            return

        data = SessionStartData(
            agent_type=agent_type,
            agent_version=agent_version,
            working_directory=working_directory,
            git_branch=git_branch,
            parent_session_id=parent_session_id,
            **metadata,
        )
        await self._add_event(
            EventType.SESSION_START, data.model_dump(exclude_none=True)
        )
        self._started = True

    async def message(
        self,
        role: str,
        content: str,
        message_type: Optional[str] = None,
        model: Optional[str] = None,
        token_usage: Optional[dict[str, int]] = None,
        thinking_content: Optional[str] = None,
        stop_reason: Optional[str] = None,
    ) -> None:
        """Add a message event."""
        author_role = {
            "user": "human",
            "human": "human",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
        }.get(role, role)

        if message_type is None:
            message_type = "prompt" if author_role == "human" else "response"

        data = MessageData(
            author_role=author_role,
            message_type=message_type,
            content=content,
            model=model,
            token_usage=token_usage,
            thinking_content=thinking_content,
            stop_reason=stop_reason,
        )
        await self._add_event(EventType.MESSAGE, data.model_dump(exclude_none=True))

    async def tool_call(
        self,
        name: str,
        parameters: Optional[dict[str, Any]] = None,
        tool_use_id: Optional[str] = None,
    ) -> str:
        """Add a tool call event."""
        if tool_use_id is None:
            tool_use_id = f"tool_{self._sequence + 1}"

        data = ToolCallData(
            tool_name=name,
            tool_use_id=tool_use_id,
            parameters=parameters or {},
        )
        await self._add_event(EventType.TOOL_CALL, data.model_dump())
        return tool_use_id

    async def tool_result(
        self,
        tool_use_id: str,
        success: bool,
        result: str,
    ) -> None:
        """Add a tool result event."""
        data = ToolResultData(
            tool_use_id=tool_use_id,
            success=success,
            result=result,
        )
        await self._add_event(EventType.TOOL_RESULT, data.model_dump())

    async def thinking(
        self,
        content: str,
        thinking_id: Optional[str] = None,
    ) -> None:
        """Add a thinking event."""
        data = ThinkingData(
            content=content,
            thinking_id=thinking_id,
        )
        await self._add_event(EventType.THINKING, data.model_dump(exclude_none=True))

    async def error(
        self,
        error_type: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an error event."""
        data = {
            "error_type": error_type,
            "message": message,
        }
        if details:
            data["details"] = details

        await self._add_event(EventType.ERROR, data)

    async def complete(
        self,
        outcome: str = "success",
        summary: Optional[str] = None,
        plans: Optional[list[dict[str, Any]]] = None,
        files_touched: Optional[list[str]] = None,
    ) -> None:
        """Complete the session."""
        if self._completed:
            logger.warning("Session already completed")
            return

        await self.flush()

        data = SessionEndData(
            outcome=outcome,
            summary=summary,
            total_messages=self._sequence,
            plans=plans,
            files_touched=files_touched,
        )
        await self._add_event(
            EventType.SESSION_END, data.model_dump(exclude_none=True)
        )
        await self.flush()

        await self.client.complete_session(
            session_id=self.session_id,
            final_sequence=self._sequence,
            outcome=outcome,
            summary=summary,
        )

        self._completed = True
