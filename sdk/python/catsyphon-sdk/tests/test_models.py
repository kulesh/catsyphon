"""Tests for event models."""

from datetime import datetime, timezone

import pytest

from catsyphon_sdk.models import (
    Event,
    EventType,
    MessageData,
    SessionEndData,
    SessionStartData,
    ToolCallData,
    ToolResultData,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_are_strings(self):
        """Event types should be string values."""
        assert EventType.SESSION_START.value == "session_start"
        assert EventType.SESSION_END.value == "session_end"
        assert EventType.MESSAGE.value == "message"
        assert EventType.TOOL_CALL.value == "tool_call"
        assert EventType.TOOL_RESULT.value == "tool_result"


class TestSessionStartData:
    """Tests for SessionStartData model."""

    def test_minimal_session_start(self):
        """Should create with just agent_type."""
        data = SessionStartData(agent_type="my-agent")
        assert data.agent_type == "my-agent"
        assert data.agent_version is None
        assert data.working_directory is None

    def test_full_session_start(self):
        """Should create with all fields."""
        data = SessionStartData(
            agent_type="claude-code",
            agent_version="1.0.0",
            working_directory="/home/user/project",
            git_branch="main",
            parent_session_id="parent-123",
            context_semantics="new",
        )
        assert data.agent_type == "claude-code"
        assert data.agent_version == "1.0.0"
        assert data.git_branch == "main"

    def test_extra_fields_allowed(self):
        """Should allow extra metadata fields."""
        data = SessionStartData(
            agent_type="my-agent",
            custom_field="custom_value",
        )
        assert data.agent_type == "my-agent"
        # Extra fields should be accessible via model_dump
        dumped = data.model_dump()
        assert dumped["custom_field"] == "custom_value"


class TestMessageData:
    """Tests for MessageData model."""

    def test_message_creation(self):
        """Should create a message with required fields."""
        data = MessageData(
            author_role="human",
            message_type="prompt",
            content="Hello, world!",
        )
        assert data.author_role == "human"
        assert data.message_type == "prompt"
        assert data.content == "Hello, world!"

    def test_message_with_optional_fields(self):
        """Should include optional fields."""
        data = MessageData(
            author_role="assistant",
            message_type="response",
            content="Hello!",
            model="claude-3-opus",
            token_usage={"input": 10, "output": 5},
            stop_reason="end_turn",
        )
        assert data.model == "claude-3-opus"
        assert data.token_usage == {"input": 10, "output": 5}
        assert data.stop_reason == "end_turn"


class TestToolCallData:
    """Tests for ToolCallData model."""

    def test_tool_call_creation(self):
        """Should create a tool call event."""
        data = ToolCallData(
            tool_name="Read",
            tool_use_id="tool_123",
            parameters={"file_path": "/src/main.py"},
        )
        assert data.tool_name == "Read"
        assert data.tool_use_id == "tool_123"
        assert data.parameters["file_path"] == "/src/main.py"

    def test_empty_parameters(self):
        """Should allow empty parameters."""
        data = ToolCallData(
            tool_name="ListFiles",
            tool_use_id="tool_456",
        )
        assert data.parameters == {}


class TestToolResultData:
    """Tests for ToolResultData model."""

    def test_successful_result(self):
        """Should create a successful tool result."""
        data = ToolResultData(
            tool_use_id="tool_123",
            success=True,
            result="File contents here...",
        )
        assert data.success is True
        assert data.result == "File contents here..."

    def test_failed_result(self):
        """Should create a failed tool result."""
        data = ToolResultData(
            tool_use_id="tool_123",
            success=False,
            result="Error: File not found",
        )
        assert data.success is False


class TestSessionEndData:
    """Tests for SessionEndData model."""

    def test_minimal_session_end(self):
        """Should create with just outcome."""
        data = SessionEndData(outcome="success")
        assert data.outcome == "success"
        assert data.summary is None

    def test_full_session_end(self):
        """Should include all fields."""
        data = SessionEndData(
            outcome="partial",
            summary="Fixed 2 of 3 bugs",
            total_messages=15,
            files_touched=["/src/auth.py", "/src/login.py"],
        )
        assert data.outcome == "partial"
        assert data.summary == "Fixed 2 of 3 bugs"
        assert len(data.files_touched) == 2


class TestEvent:
    """Tests for Event model."""

    def test_event_creation(self):
        """Should create an event with all fields."""
        now = datetime.now(timezone.utc)
        event = Event(
            sequence=1,
            type=EventType.MESSAGE,
            emitted_at=now,
            observed_at=now,
            data={"author_role": "human", "message_type": "prompt", "content": "Hi"},
        )
        assert event.sequence == 1
        assert event.type == EventType.MESSAGE
        assert event.emitted_at == now

    def test_event_json_safe_dump(self):
        """Should produce JSON-serializable dict."""
        now = datetime.now(timezone.utc)
        event = Event(
            sequence=1,
            type=EventType.SESSION_START,
            emitted_at=now,
            observed_at=now,
            data={"agent_type": "test"},
        )
        dumped = event.model_dump_json_safe()

        assert isinstance(dumped["emitted_at"], str)
        assert isinstance(dumped["observed_at"], str)
        assert dumped["sequence"] == 1
        assert dumped["type"] == "session_start"

    def test_default_timestamps(self):
        """Should set default timestamps if not provided."""
        event = Event(
            sequence=1,
            type=EventType.MESSAGE,
            data={"author_role": "human", "message_type": "prompt", "content": "Hi"},
        )
        assert event.emitted_at is not None
        assert event.observed_at is not None
