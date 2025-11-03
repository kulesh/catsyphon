"""
Tests for parsed conversation data models.
"""

from datetime import UTC, datetime

from catsyphon.models.parsed import (
    CodeChange,
    ConversationTags,
    ParsedConversation,
    ParsedMessage,
    ToolCall,
)


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        """Test creating a tool call."""
        tool_call = ToolCall(
            tool_name="Read",
            parameters={"file_path": "/path/to/file.py"},
            result="File contents...",
            success=True,
            timestamp=datetime.now(UTC),
        )

        assert tool_call.tool_name == "Read"
        assert tool_call.parameters["file_path"] == "/path/to/file.py"
        assert tool_call.success is True

    def test_tool_call_defaults(self):
        """Test tool call default values."""
        tool_call = ToolCall(
            tool_name="Write",
            parameters={"content": "test"},
        )

        assert tool_call.result is None
        assert tool_call.success is True
        assert tool_call.timestamp is None


class TestCodeChange:
    """Tests for CodeChange dataclass."""

    def test_create_code_change(self):
        """Test creating a code change."""
        code_change = CodeChange(
            file_path="src/app.py",
            change_type="edit",
            old_content="def old():\n    pass",
            new_content="def new():\n    pass",
            lines_added=1,
            lines_deleted=1,
        )

        assert code_change.file_path == "src/app.py"
        assert code_change.change_type == "edit"
        assert code_change.lines_added == 1

    def test_code_change_defaults(self):
        """Test code change default values."""
        code_change = CodeChange(
            file_path="new_file.py",
            change_type="create",
        )

        assert code_change.old_content is None
        assert code_change.new_content is None
        assert code_change.lines_added == 0
        assert code_change.lines_deleted == 0


class TestParsedMessage:
    """Tests for ParsedMessage dataclass."""

    def test_create_parsed_message(self):
        """Test creating a parsed message."""
        timestamp = datetime.now(UTC)
        message = ParsedMessage(
            role="user",
            content="Please fix the bug in auth.py",
            timestamp=timestamp,
            tool_calls=[ToolCall(tool_name="Read", parameters={"file": "auth.py"})],
            code_changes=[
                CodeChange(file_path="auth.py", change_type="edit", lines_added=3)
            ],
            entities={"files": ["auth.py"], "intent": "bug_fix"},
        )

        assert message.role == "user"
        assert "bug" in message.content
        assert len(message.tool_calls) == 1
        assert len(message.code_changes) == 1
        assert message.entities["intent"] == "bug_fix"

    def test_parsed_message_defaults(self):
        """Test parsed message default values."""
        message = ParsedMessage(
            role="assistant",
            content="I'll help with that.",
            timestamp=datetime.now(UTC),
        )

        assert message.tool_calls == []
        assert message.code_changes == []
        assert message.entities == {}


class TestParsedConversation:
    """Tests for ParsedConversation dataclass."""

    def test_create_parsed_conversation(self):
        """Test creating a parsed conversation."""
        start_time = datetime.now(UTC)
        messages = [
            ParsedMessage(
                role="user",
                content="Add login feature",
                timestamp=start_time,
            ),
            ParsedMessage(
                role="assistant",
                content="I'll implement that.",
                timestamp=start_time,
            ),
        ]

        conversation = ParsedConversation(
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=start_time,
            end_time=start_time,
            messages=messages,
            metadata={"session_id": "test-123"},
        )

        assert conversation.agent_type == "claude-code"
        assert conversation.agent_version == "1.0.0"
        assert len(conversation.messages) == 2
        assert conversation.metadata["session_id"] == "test-123"

    def test_parsed_conversation_defaults(self):
        """Test parsed conversation default values."""
        conversation = ParsedConversation(
            agent_type="claude-code",
            agent_version=None,
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[],
        )

        assert conversation.agent_version is None
        assert conversation.end_time is None
        assert conversation.messages == []
        assert conversation.metadata == {}


class TestConversationTags:
    """Tests for ConversationTags dataclass."""

    def test_create_conversation_tags(self):
        """Test creating conversation tags."""
        tags = ConversationTags(
            sentiment="positive",
            sentiment_score=0.8,
            intent="feature_add",
            outcome="success",
            iterations=3,
            entities={"files": ["auth.py"], "technologies": ["Python"]},
            features=["authentication", "login"],
            problems=["missing dependencies"],
            patterns=["test-driven development"],
            tools_used=["Write", "Read", "Bash"],
            has_errors=False,
        )

        assert tags.sentiment == "positive"
        assert tags.sentiment_score == 0.8
        assert tags.intent == "feature_add"
        assert tags.iterations == 3
        assert len(tags.features) == 2
        assert "Write" in tags.tools_used

    def test_conversation_tags_defaults(self):
        """Test conversation tags default values."""
        tags = ConversationTags()

        assert tags.sentiment is None
        assert tags.sentiment_score is None
        assert tags.intent is None
        assert tags.outcome is None
        assert tags.iterations == 1
        assert tags.entities == {}
        assert tags.features == []
        assert tags.problems == []
        assert tags.has_errors is False

    def test_conversation_tags_to_dict(self):
        """Test converting conversation tags to dictionary."""
        tags = ConversationTags(
            sentiment="positive",
            sentiment_score=0.9,
            intent="refactor",
            outcome="partial",
            iterations=2,
            features=["code_cleanup"],
        )

        tag_dict = tags.to_dict()

        assert isinstance(tag_dict, dict)
        assert tag_dict["sentiment"] == "positive"
        assert tag_dict["sentiment_score"] == 0.9
        assert tag_dict["intent"] == "refactor"
        assert tag_dict["iterations"] == 2
        assert tag_dict["features"] == ["code_cleanup"]
        assert tag_dict["has_errors"] is False
