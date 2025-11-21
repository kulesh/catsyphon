"""Tests for canonicalization models."""

from datetime import datetime

import pytest

from catsyphon.canonicalization.models import (
    CanonicalConfig,
    CanonicalConversation,
    CanonicalType,
)


class TestCanonicalType:
    """Test CanonicalType enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert CanonicalType.TAGGING == "tagging"
        assert CanonicalType.INSIGHTS == "insights"
        assert CanonicalType.EXPORT == "export"


class TestCanonicalConfig:
    """Test CanonicalConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CanonicalConfig()

        assert config.token_budget == 8000
        assert config.include_thinking is True
        assert config.include_tool_details is True
        assert config.include_children is True
        assert config.max_child_depth == 3

    def test_for_type_tagging(self):
        """Test configuration for tagging type."""
        config = CanonicalConfig.for_type(CanonicalType.TAGGING)

        assert config.token_budget == 8000
        assert config.include_code_changes is False  # Not needed for tagging
        assert config.child_token_budget == 2000

    def test_for_type_insights(self):
        """Test configuration for insights type."""
        config = CanonicalConfig.for_type(CanonicalType.INSIGHTS)

        assert config.token_budget == 12000
        assert config.include_code_changes is True
        assert config.child_token_budget == 3000

    def test_for_type_export(self):
        """Test configuration for export type."""
        config = CanonicalConfig.for_type(CanonicalType.EXPORT)

        assert config.token_budget == 20000
        assert config.max_message_chars == 2000  # More content for export
        assert config.max_thinking_chars == 1000
        assert config.child_token_budget == 5000

    def test_custom_config(self):
        """Test custom configuration."""
        config = CanonicalConfig(
            token_budget=15000,
            include_thinking=False,
            max_message_chars=500,
        )

        assert config.token_budget == 15000
        assert config.include_thinking is False
        assert config.max_message_chars == 500


class TestCanonicalConversation:
    """Test CanonicalConversation dataclass."""

    def test_create_conversation(self):
        """Test creating canonical conversation."""
        now = datetime.now()

        canonical = CanonicalConversation(
            session_id="test-session-123",
            conversation_id="conv-456",
            agent_type="claude-code",
            agent_version="2.0.28",
            conversation_type="main",
            start_time=now,
            end_time=None,
            duration_seconds=None,
            message_count=10,
            epoch_count=2,
            files_count=3,
            tool_calls_count=5,
            narrative="Test narrative",
            token_count=100,
        )

        assert canonical.session_id == "test-session-123"
        assert canonical.conversation_id == "conv-456"
        assert canonical.agent_type == "claude-code"
        assert canonical.message_count == 10
        assert canonical.narrative == "Test narrative"
        assert canonical.token_count == 100

    def test_to_dict(self):
        """Test converting to dictionary."""
        now = datetime.now()

        canonical = CanonicalConversation(
            session_id="test-session",
            conversation_id="conv-123",
            agent_type="claude-code",
            agent_version="2.0.28",
            conversation_type="main",
            start_time=now,
            end_time=now,
            duration_seconds=600,
            message_count=5,
            epoch_count=1,
            files_count=2,
            tool_calls_count=3,
            narrative="Test",
            token_count=50,
            tools_used=["Bash", "Read"],
            files_touched=["file1.py", "file2.py"],
            has_errors=True,
            code_changes_summary={"added": 10, "deleted": 5, "modified": 1},
        )

        data = canonical.to_dict()

        assert data["session_id"] == "test-session"
        assert data["conversation_id"] == "conv-123"
        assert data["message_count"] == 5
        assert data["tools_used"] == ["Bash", "Read"]
        assert data["files_touched"] == ["file1.py", "file2.py"]
        assert data["has_errors"] is True
        assert data["code_changes_summary"]["added"] == 10

    def test_from_dict(self):
        """Test creating from dictionary."""
        now = datetime.now()
        data = {
            "session_id": "test-session",
            "conversation_id": "conv-123",
            "agent_type": "claude-code",
            "agent_version": "2.0.28",
            "conversation_type": "main",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "duration_seconds": 600,
            "message_count": 5,
            "epoch_count": 1,
            "files_count": 2,
            "tool_calls_count": 3,
            "narrative": "Test narrative",
            "token_count": 50,
            "tools_used": ["Bash"],
            "files_touched": ["file1.py"],
            "has_errors": False,
            "code_changes_summary": {},
            "canonical_version": 1,
        }

        canonical = CanonicalConversation.from_dict(data)

        assert canonical.session_id == "test-session"
        assert canonical.message_count == 5
        assert canonical.tools_used == ["Bash"]
        assert canonical.has_errors is False

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        now = datetime.now()

        original = CanonicalConversation(
            session_id="test",
            conversation_id="conv-1",
            agent_type="claude-code",
            agent_version="2.0",
            conversation_type="main",
            start_time=now,
            end_time=None,
            duration_seconds=None,
            message_count=10,
            epoch_count=2,
            files_count=3,
            tool_calls_count=5,
            narrative="Test",
            token_count=100,
            tools_used=["Bash", "Read"],
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = CanonicalConversation.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.conversation_id == original.conversation_id
        assert restored.message_count == original.message_count
        assert restored.tools_used == original.tools_used
        assert restored.token_count == original.token_count

    def test_with_children(self):
        """Test canonical conversation with children."""
        now = datetime.now()

        child = CanonicalConversation(
            session_id="child-session",
            conversation_id="child-conv",
            agent_type="claude-code",
            agent_version="2.0",
            conversation_type="agent",
            start_time=now,
            end_time=now,
            duration_seconds=60,
            message_count=3,
            epoch_count=1,
            files_count=1,
            tool_calls_count=2,
            narrative="Child narrative",
            token_count=30,
            parent_id="parent-conv",
        )

        parent = CanonicalConversation(
            session_id="parent-session",
            conversation_id="parent-conv",
            agent_type="claude-code",
            agent_version="2.0",
            conversation_type="main",
            start_time=now,
            end_time=now,
            duration_seconds=120,
            message_count=10,
            epoch_count=2,
            files_count=3,
            tool_calls_count=5,
            narrative="Parent narrative",
            token_count=100,
            children=[child],
        )

        assert len(parent.children) == 1
        assert parent.children[0].conversation_id == "child-conv"
        assert parent.children[0].parent_id == "parent-conv"

        # Test serialization with children
        data = parent.to_dict()
        assert len(data["children"]) == 1
        assert data["children"][0]["conversation_id"] == "child-conv"
