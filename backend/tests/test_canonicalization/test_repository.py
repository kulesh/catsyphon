"""Integration tests for CanonicalRepository."""

import pytest
from datetime import datetime
from uuid import uuid4

from catsyphon.canonicalization import CanonicalType, Canonicalizer
from catsyphon.canonicalization.version import CANONICAL_VERSION
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.models.db import Conversation, ConversationCanonical, Epoch, Message, Workspace, Organization


def test_get_cached_returns_none_when_no_cache(test_session):
    """Test get_cached returns None when no cached canonical exists."""
    repo = CanonicalRepository(test_session)
    conversation_id = uuid4()

    cached = repo.get_cached(
        conversation_id=conversation_id,
        canonical_type="tagging",
    )

    assert cached is None


def test_save_and_get_canonical(test_session, sample_conversation):
    """Test saving and retrieving canonical representation."""
    from catsyphon.canonicalization.models import CanonicalConversation

    repo = CanonicalRepository(test_session)

    # Create canonical
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(sample_conversation.id),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=1,
        files_count=0,
        tool_calls_count=0,
        narrative="Test narrative for tagging",
        token_count=100,
        tools_used=["Bash", "Read"],
        has_errors=False,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    # Save
    saved = repo.save_canonical(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
        canonical=canonical,
    )

    assert saved.id is not None
    assert saved.conversation_id == sample_conversation.id
    assert saved.canonical_type == "tagging"
    assert saved.narrative == "Test narrative for tagging"
    assert saved.token_count == 100
    assert saved.version == CANONICAL_VERSION

    # Retrieve
    cached = repo.get_cached(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
    )

    assert cached is not None
    assert cached.id == saved.id
    assert cached.narrative == "Test narrative for tagging"


def test_should_regenerate_version_mismatch(test_session, sample_conversation):
    """Test should_regenerate returns True on version mismatch."""
    from catsyphon.canonicalization.models import CanonicalConversation

    repo = CanonicalRepository(test_session)

    # Create cached canonical with old version
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(sample_conversation.id),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=1,
        files_count=0,
        tool_calls_count=0,
        narrative="Old version",
        token_count=100,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    saved = repo.save_canonical(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
        canonical=canonical,
    )

    # Manually change version to simulate old cache
    saved.version = CANONICAL_VERSION - 1
    test_session.flush()

    # Check should_regenerate
    should_regen = repo.should_regenerate(
        conversation=sample_conversation,
        cached=saved,
        threshold_tokens=2000,
    )

    assert should_regen is True


def test_should_regenerate_token_growth(test_session, sample_conversation):
    """Test should_regenerate returns True when token growth exceeds threshold."""
    from catsyphon.canonicalization.models import CanonicalConversation

    repo = CanonicalRepository(test_session)

    # Create cached canonical
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(sample_conversation.id),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,  # Cached had 10 messages
        epoch_count=1,
        files_count=0,
        tool_calls_count=0,
        narrative="Cached narrative",
        token_count=1000,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    saved = repo.save_canonical(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
        canonical=canonical,
    )

    # Simulate conversation growth (increase message count)
    sample_conversation.message_count = 50  # Now has 50 messages (40 more)

    # With default estimate of 100 tokens/message, growth = 40 * 100 = 4000 tokens
    # This exceeds threshold of 2000, so should regenerate
    should_regen = repo.should_regenerate(
        conversation=sample_conversation,
        cached=saved,
        threshold_tokens=2000,
    )

    assert should_regen is True


def test_should_not_regenerate_when_fresh(test_session, sample_conversation):
    """Test should_regenerate returns False when cache is fresh."""
    from catsyphon.canonicalization.models import CanonicalConversation

    repo = CanonicalRepository(test_session)

    # Create cached canonical
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(sample_conversation.id),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=1,
        files_count=0,
        tool_calls_count=0,
        narrative="Fresh cache",
        token_count=1000,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    saved = repo.save_canonical(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
        canonical=canonical,
    )

    # Conversation hasn't changed
    sample_conversation.message_count = 10  # Same as cached

    should_regen = repo.should_regenerate(
        conversation=sample_conversation,
        cached=saved,
        threshold_tokens=2000,
    )

    assert should_regen is False


def test_invalidate_by_conversation(test_session, sample_conversation):
    """Test invalidate deletes canonical for specific conversation."""
    from catsyphon.canonicalization.models import CanonicalConversation

    repo = CanonicalRepository(test_session)

    # Create canonical
    canonical = CanonicalConversation(
        session_id="test-session",
        conversation_id=str(sample_conversation.id),
        agent_type="claude-code",
        agent_version="2.0",
        conversation_type="main",
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None,
        message_count=10,
        epoch_count=1,
        files_count=0,
        tool_calls_count=0,
        narrative="To be invalidated",
        token_count=100,
        canonical_version=CANONICAL_VERSION,
        generated_at=datetime.now(),
    )

    repo.save_canonical(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
        canonical=canonical,
    )

    # Verify it exists
    cached = repo.get_cached(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
    )
    assert cached is not None

    # Invalidate
    count = repo.invalidate(conversation_id=sample_conversation.id)
    assert count == 1

    # Verify it's gone
    cached = repo.get_cached(
        conversation_id=sample_conversation.id,
        canonical_type="tagging",
    )
    assert cached is None
