"""Tests for message sampling strategies."""

import pytest
from datetime import datetime

from catsyphon.canonicalization.models import CanonicalConfig
from catsyphon.canonicalization.samplers import (
    ChronologicalSampler,
    EpochSampler,
    SampledMessage,
    SemanticSampler,
)
from catsyphon.canonicalization.tokens import TokenCounter
from catsyphon.models.db import Epoch, Message


# ===== ChronologicalSampler Tests =====


def test_chronological_sampler_empty_messages():
    """Test ChronologicalSampler with empty message list."""
    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(messages=[], epochs=[], token_budget=1000)

    assert result == []


def test_chronological_sampler_single_message(sample_message):
    """Test ChronologicalSampler with single message."""
    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=[sample_message],
        epochs=[],
        token_budget=1000
    )

    assert len(result) == 1
    assert result[0].message == sample_message
    assert result[0].priority == 1000
    assert result[0].reason == "chronological"
    assert result[0].estimated_tokens > 0


def test_chronological_sampler_multiple_messages(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with multiple messages."""
    # Create multiple messages with different sequence numbers
    messages = []
    for i in range(10):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Test message {i}",
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages
    assert len(result) == 10

    # All should have same priority and reason
    for sm in result:
        assert sm.priority == 1000
        assert sm.reason == "chronological"
        assert sm.estimated_tokens > 0

    # Should be in chronological order (by sequence)
    for i, sm in enumerate(result):
        assert sm.message.sequence == i


def test_chronological_sampler_chronological_ordering(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test that ChronologicalSampler maintains chronological order."""
    # Create messages in non-sequential order
    messages = []
    sequences = [5, 1, 8, 3, 9, 2, 7, 4, 6, 0]  # Random order

    for seq in sequences:
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="user",
            content=f"Message {seq}",
            timestamp=datetime.now(),
            sequence=seq,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should be sorted by sequence despite input order
    assert len(result) == 10
    for i, sm in enumerate(result):
        assert sm.message.sequence == i


def test_chronological_sampler_ignores_budget(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test that ChronologicalSampler ignores token budget."""
    # Create messages that will exceed budget
    messages = []
    for i in range(50):  # Many messages
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content="This is a longer message with more content that will consume more tokens " * 10,
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    # Use small budget
    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=100  # Very small budget
    )

    # Should still include all messages despite small budget
    assert len(result) == 50

    # Calculate total tokens
    total_tokens = sum(sm.estimated_tokens for sm in result)
    assert total_tokens > 100  # Should exceed budget


def test_chronological_sampler_with_tool_calls(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with messages containing tool calls."""
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content=f"Running tool {i}",
            tool_calls=[
                {"tool_name": "Read", "parameters": {"file_path": f"/file{i}.py"}}
            ],
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages with tool calls
    assert len(result) == 5
    for sm in result:
        assert sm.message.tool_calls is not None
        assert len(sm.message.tool_calls) > 0


def test_chronological_sampler_with_thinking_content(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with messages containing thinking content."""
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content=f"Response {i}",
            thinking_content=f"Thinking about {i}..." * 20,  # Long thinking
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig(include_thinking=True)
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages with thinking content
    assert len(result) == 5
    for sm in result:
        assert sm.message.thinking_content is not None
        assert len(sm.message.thinking_content) > 0


def test_chronological_sampler_with_code_changes(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with messages containing code changes."""
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content=f"Modified file {i}",
            code_changes=[
                {
                    "file_path": f"/file{i}.py",
                    "lines_added": 10 + i,
                    "lines_deleted": i,
                }
            ],
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig(include_code_changes=True)
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages with code changes
    assert len(result) == 5
    for sm in result:
        assert sm.message.code_changes is not None
        assert len(sm.message.code_changes) > 0


def test_chronological_sampler_mixed_message_types(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with mixed message types."""
    messages = []

    # User message
    msg1 = Message(
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        role="user",
        content="Please read the file",
        timestamp=datetime.now(),
        sequence=0,
    )

    # Assistant with tool call
    msg2 = Message(
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        role="assistant",
        content="Reading file...",
        tool_calls=[{"tool_name": "Read", "parameters": {}}],
        thinking_content="I should read the file...",
        timestamp=datetime.now(),
        sequence=1,
    )

    # Assistant with code change
    msg3 = Message(
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        role="assistant",
        content="Modified the file",
        code_changes=[{"file_path": "/file.py", "lines_added": 5, "lines_deleted": 2}],
        timestamp=datetime.now(),
        sequence=2,
    )

    # User error message
    msg4 = Message(
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        role="user",
        content="Error: File not found",
        timestamp=datetime.now(),
        sequence=3,
    )

    messages = [msg1, msg2, msg3, msg4]
    for msg in messages:
        test_session.add(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages regardless of type
    assert len(result) == 4

    # Verify chronological order
    assert result[0].message.sequence == 0
    assert result[1].message.sequence == 1
    assert result[2].message.sequence == 2
    assert result[3].message.sequence == 3


# ===== Comparison Tests =====


def test_chronological_vs_semantic_coverage(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test that ChronologicalSampler includes more messages than SemanticSampler."""
    # Create many messages with longer content to exceed budget
    messages = []
    for i in range(100):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content=f"This is a longer regular message number {i} with more content " * 20,  # Much longer
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")

    chronological_sampler = ChronologicalSampler(config, token_counter)
    semantic_sampler = SemanticSampler(config, token_counter)

    budget = 2000  # Smaller budget to force semantic to exclude messages

    chronological_result = chronological_sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=budget
    )

    semantic_result = semantic_sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=budget
    )

    # Chronological should include all messages
    assert len(chronological_result) == 100

    # Semantic should be limited by budget
    assert len(semantic_result) < 100

    # Chronological should have significantly more messages than semantic
    assert len(chronological_result) > len(semantic_result)


# ===== Token Estimation Tests =====


def test_chronological_sampler_token_estimation(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test that ChronologicalSampler correctly estimates tokens."""
    # Create messages with known content lengths
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="user",
            content="word " * 100,  # Predictable content
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=10000
    )

    # All messages should have similar token estimates
    token_estimates = [sm.estimated_tokens for sm in result]
    assert len(set(token_estimates)) == 1  # All should be same

    # Should be reasonable estimate (not zero, not huge)
    for sm in result:
        assert sm.estimated_tokens > 0
        assert sm.estimated_tokens < 10000


# ===== Edge Cases =====


def test_chronological_sampler_with_empty_content(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with messages that have empty content."""
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="system",
            content="",  # Empty content (not None, as DB may not allow None)
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    # Should not crash with empty content
    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    assert len(result) == 5
    for sm in result:
        assert sm.estimated_tokens >= 0  # Should handle empty content gracefully
        assert sm.priority == 1000
        assert sm.reason == "chronological"


def test_chronological_sampler_with_very_long_messages(
    test_session,
    sample_conversation,
    sample_epoch
):
    """Test ChronologicalSampler with very long messages."""
    messages = []
    for i in range(5):
        msg = Message(
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            role="assistant",
            content="This is a very long message. " * 1000,  # Very long
            timestamp=datetime.now(),
            sequence=i,
        )
        test_session.add(msg)
        messages.append(msg)
    test_session.flush()

    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=messages,
        epochs=[sample_epoch],
        token_budget=1000
    )

    # Should include all messages even if very long
    assert len(result) == 5

    # Should have reasonable token estimates (respecting max_message_chars)
    for sm in result:
        assert sm.estimated_tokens > 0
        # Token estimate should be bounded by max_message_chars config
        # (default 1000 chars ~= 250 tokens)
        assert sm.estimated_tokens < 500  # Reasonable upper bound


def test_chronological_sampler_returns_sampled_message_objects(sample_message):
    """Test that ChronologicalSampler returns SampledMessage objects."""
    config = CanonicalConfig()
    token_counter = TokenCounter(model="gpt-4o-mini")
    sampler = ChronologicalSampler(config, token_counter)

    result = sampler.sample(
        messages=[sample_message],
        epochs=[],
        token_budget=1000
    )

    assert len(result) == 1
    assert isinstance(result[0], SampledMessage)
    assert hasattr(result[0], 'message')
    assert hasattr(result[0], 'priority')
    assert hasattr(result[0], 'reason')
    assert hasattr(result[0], 'estimated_tokens')
