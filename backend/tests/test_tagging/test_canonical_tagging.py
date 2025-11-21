"""Tests for canonical-based tagging pipeline."""

import pytest
from datetime import datetime
from uuid import uuid4

from catsyphon.canonicalization.models import CanonicalConversation, CanonicalType
from catsyphon.canonicalization.version import CANONICAL_VERSION
from catsyphon.tagging import RuleTagger


def test_rule_tagger_from_canonical_basic():
    """Test that rule tagger extracts metadata from canonical correctly."""
    # Create a canonical conversation with known metadata
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=2,
        files_count=3,
        tool_calls_count=5,
        narrative="User asked to run pytest. Assistant ran tests using Bash tool. Error occurred: test failed.",
        token_count=1000,
        tools_used=["Bash", "Read", "Write"],
        has_errors=True,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    # Extract tags using rule tagger
    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Verify extracted metadata
    assert tags.has_errors is True
    assert "Bash" in tags.tools_used
    assert "Read" in tags.tools_used
    assert "Write" in tags.tools_used
    assert tags.iterations == 2  # Should match epoch_count
    assert tags.patterns is not None
    assert len(tags.patterns) > 0


def test_rule_tagger_pattern_detection_from_tools():
    """Test that rule tagger detects patterns from tool usage."""
    # Create canonical with testing tools
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=5,
        epoch_count=1,
        files_count=0,
        tool_calls_count=2,
        narrative="User asked to run tests. Assistant ran pytest.",
        token_count=500,
        tools_used=["pytest", "Bash"],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Should detect testing pattern from pytest tool
    assert "testing" in tags.patterns


def test_rule_tagger_git_pattern_detection():
    """Test that rule tagger detects git operations from tools."""
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=3,
        epoch_count=1,
        files_count=0,
        tool_calls_count=1,
        narrative="User asked to commit changes. Assistant ran git commit.",
        token_count=300,
        tools_used=["git"],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Should detect git operations pattern
    assert "git_operations" in tags.patterns


def test_rule_tagger_refactoring_pattern():
    """Test that rule tagger detects refactoring from narrative."""
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=8,
        epoch_count=1,
        files_count=2,
        tool_calls_count=3,
        narrative="User asked to refactor the authentication module to improve code structure.",
        token_count=800,
        tools_used=["Read", "Edit"],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Should detect refactoring pattern from narrative
    assert "refactoring" in tags.patterns


def test_rule_tagger_conversation_length_patterns():
    """Test that rule tagger detects length-based patterns."""
    # Test quick resolution
    canonical_short = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=3,
        epoch_count=1,
        files_count=0,
        tool_calls_count=1,
        narrative="Quick fix applied.",
        token_count=200,
        tools_used=[],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    rule_tagger = RuleTagger()
    tags_short = rule_tagger.tag_from_canonical(canonical_short)
    assert "quick_resolution" in tags_short.patterns

    # Test long conversation
    canonical_long = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=60,
        epoch_count=5,
        files_count=10,
        tool_calls_count=20,
        narrative="Very long conversation with many iterations.",
        token_count=5000,
        tools_used=["Bash", "Read", "Write", "Edit"],
        has_errors=True,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    tags_long = rule_tagger.tag_from_canonical(canonical_long)
    assert "long_conversation" in tags_long.patterns


def test_rule_tagger_error_handling_pattern():
    """Test that rule tagger adds error_handling pattern when errors present."""
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=2,
        files_count=1,
        tool_calls_count=3,
        narrative="Debugging error in code.",
        token_count=1000,
        tools_used=["Read", "Edit"],
        has_errors=True,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Should add error_handling pattern when has_errors is True
    assert "error_handling" in tags.patterns


def test_rule_tagger_agent_delegation_pattern():
    """Test that rule tagger detects agent delegation from child conversations."""
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(uuid4()),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=1,
        files_count=0,
        tool_calls_count=2,
        narrative="Main conversation with agent delegation.",
        token_count=1000,
        tools_used=[],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
        children=[
            {
                "conversation_id": str(uuid4()),
                "agent_type": "task-agent",
                "message_count": 5,
            }
        ],
    )

    rule_tagger = RuleTagger()
    tags = rule_tagger.tag_from_canonical(canonical)

    # Should detect agent delegation when children present
    assert "agent_delegation" in tags.patterns
