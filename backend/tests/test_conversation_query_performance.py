"""
Tests for conversation list query performance fix.

Verifies:
1. Conversations list orders by end_time (not message subquery)
2. count_by_filters excludes children (parent-only semantics)
3. Orphan linking respects max_linking_attempts
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from catsyphon.db.repositories.conversation import ConversationRepository
from catsyphon.models.db import Conversation, Epoch, Message
from catsyphon.pipeline.ingestion import link_orphaned_agents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conversation(
    db_session,
    workspace_id,
    *,
    start_time=None,
    end_time=None,
    parent_id=None,
    conversation_type="main",
    agent_metadata=None,
    extra_data=None,
    message_count=0,
):
    """Create a conversation with minimal boilerplate."""
    now = datetime.now(UTC)
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        agent_type="claude-code",
        start_time=start_time or now,
        end_time=end_time,
        status="completed" if end_time else "open",
        conversation_type=conversation_type,
        parent_conversation_id=parent_id,
        agent_metadata=agent_metadata or {},
        extra_data=extra_data or {"session_id": str(uuid.uuid4())},
        message_count=message_count,
        epoch_count=0,
        files_count=0,
    )
    db_session.add(conv)
    db_session.flush()
    return conv


# ---------------------------------------------------------------------------
# Phase 1: Conversations list uses end_time, not message subquery
# ---------------------------------------------------------------------------


class TestConversationListOrdering:
    """Verify ordering uses Conversation.end_time, not a message subquery."""

    def test_orders_by_end_time_desc(self, db_session, sample_workspace):
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations with specific end_times
        old = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=2),
        )
        recent = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )
        db_session.flush()

        results = repo.get_with_counts_hierarchical(
            workspace_id=sample_workspace.id,
            order_by="last_activity",
            order_dir="desc",
        )

        # Extract parent conversations (depth_level=0)
        parents = [r for r in results if r[-1] == 0]
        assert len(parents) >= 2

        # Most recent end_time should come first
        first_conv = parents[0][0]
        second_conv = parents[1][0]
        assert first_conv.id == recent.id
        assert second_conv.id == old.id

    def test_last_activity_column_is_end_time(self, db_session, sample_workspace):
        """The last_activity column in the result tuple should be end_time."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)
        end = now - timedelta(minutes=5)

        conv = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now - timedelta(hours=1),
            end_time=end,
        )
        db_session.flush()

        results = repo.get_with_counts_hierarchical(
            workspace_id=sample_workspace.id,
        )

        # Find our conversation
        for r in results:
            if r[0].id == conv.id:
                last_activity = r[5]  # Index 5 is last_activity
                # Compare without timezone (SQLite strips tzinfo)
                assert last_activity.replace(tzinfo=None) == end.replace(tzinfo=None)
                break
        else:
            pytest.fail("Conversation not found in results")

    def test_null_end_time_falls_back_to_start_time(
        self, db_session, sample_workspace
    ):
        """Conversations with null end_time should sort by start_time."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Conversation with no end_time (still open)
        open_conv = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now,
            end_time=None,
        )
        # Older completed conversation
        old_conv = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )
        db_session.flush()

        results = repo.get_with_counts_hierarchical(
            workspace_id=sample_workspace.id,
            order_by="last_activity",
            order_dir="desc",
        )

        parents = [r for r in results if r[-1] == 0]
        # Open conv with start_time=now should come before old_conv with end_time=now-1h
        conv_ids = [r[0].id for r in parents]
        assert conv_ids.index(open_conv.id) < conv_ids.index(old_conv.id)


# ---------------------------------------------------------------------------
# Phase 1: count_by_filters excludes children
# ---------------------------------------------------------------------------


class TestCountByFiltersExcludesChildren:
    """Verify count_by_filters only counts parent conversations."""

    def test_excludes_child_conversations(self, db_session, sample_workspace):
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        parent = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now,
            end_time=now,
        )
        # Create child conversations
        _make_conversation(
            db_session,
            sample_workspace.id,
            parent_id=parent.id,
            conversation_type="agent",
            start_time=now,
            end_time=now,
        )
        _make_conversation(
            db_session,
            sample_workspace.id,
            parent_id=parent.id,
            conversation_type="agent",
            start_time=now,
            end_time=now,
        )
        db_session.flush()

        count = repo.count_by_filters(workspace_id=sample_workspace.id)

        # Should count only parents, not children
        # The sample_workspace may have the autouse fixture conversation too,
        # but children should NOT be counted
        all_count = (
            db_session.query(Conversation)
            .filter(Conversation.workspace_id == sample_workspace.id)
            .count()
        )
        parent_only_count = (
            db_session.query(Conversation)
            .filter(
                Conversation.workspace_id == sample_workspace.id,
                Conversation.parent_conversation_id.is_(None),
            )
            .count()
        )

        assert count == parent_only_count
        assert count < all_count  # Children exist but aren't counted

    def test_count_matches_hierarchical_parent_count(
        self, db_session, sample_workspace
    ):
        """count_by_filters should match the number of parents in get_with_counts_hierarchical."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        for i in range(3):
            parent = _make_conversation(
                db_session,
                sample_workspace.id,
                start_time=now - timedelta(hours=i),
                end_time=now - timedelta(hours=i),
            )
            # Each parent gets a child
            _make_conversation(
                db_session,
                sample_workspace.id,
                parent_id=parent.id,
                conversation_type="agent",
                start_time=now,
                end_time=now,
            )
        db_session.flush()

        count = repo.count_by_filters(workspace_id=sample_workspace.id)
        results = repo.get_with_counts_hierarchical(
            workspace_id=sample_workspace.id,
        )
        parent_results = [r for r in results if r[-1] == 0]

        assert count == len(parent_results)


# ---------------------------------------------------------------------------
# Phase 3: Orphan linking respects max_linking_attempts
# ---------------------------------------------------------------------------


class TestOrphanLinkingMaxAttempts:
    """Verify link_orphaned_agents tracks and respects attempt limits."""

    def test_increments_linking_attempts_on_failure(
        self, db_session, sample_workspace
    ):
        """Failed linking should increment _linking_attempts in agent_metadata."""
        now = datetime.now(UTC)

        # Agent with no matching parent
        agent = _make_conversation(
            db_session,
            sample_workspace.id,
            conversation_type="agent",
            start_time=now,
            agent_metadata={
                "parent_session_id": "nonexistent-session-id",
            },
            extra_data={"session_id": str(uuid.uuid4())},
        )
        db_session.flush()

        # First attempt
        linked = link_orphaned_agents(db_session, sample_workspace.id)
        assert linked == 0

        db_session.refresh(agent)
        assert agent.agent_metadata.get("_linking_attempts") == 1

        # Second attempt
        linked = link_orphaned_agents(db_session, sample_workspace.id)
        assert linked == 0

        db_session.refresh(agent)
        assert agent.agent_metadata.get("_linking_attempts") == 2

    def test_skips_after_max_attempts(self, db_session, sample_workspace):
        """Agents exceeding max_linking_attempts should be skipped entirely."""
        now = datetime.now(UTC)

        agent = _make_conversation(
            db_session,
            sample_workspace.id,
            conversation_type="agent",
            start_time=now,
            agent_metadata={
                "parent_session_id": "nonexistent-session-id",
                "_linking_attempts": 10,  # Already at max
            },
            extra_data={"session_id": str(uuid.uuid4())},
        )
        db_session.flush()

        linked = link_orphaned_agents(
            db_session, sample_workspace.id, max_linking_attempts=10
        )
        assert linked == 0

        # Attempts counter should NOT be incremented (skipped entirely)
        db_session.refresh(agent)
        assert agent.agent_metadata.get("_linking_attempts") == 10

    def test_custom_max_attempts(self, db_session, sample_workspace):
        """max_linking_attempts parameter controls the threshold."""
        now = datetime.now(UTC)

        agent = _make_conversation(
            db_session,
            sample_workspace.id,
            conversation_type="agent",
            start_time=now,
            agent_metadata={
                "parent_session_id": "nonexistent-session-id",
                "_linking_attempts": 2,
            },
            extra_data={"session_id": str(uuid.uuid4())},
        )
        db_session.flush()

        # With max_attempts=3, attempt 2 is below threshold → should try
        linked = link_orphaned_agents(
            db_session, sample_workspace.id, max_linking_attempts=3
        )
        assert linked == 0

        db_session.refresh(agent)
        assert agent.agent_metadata.get("_linking_attempts") == 3

        # Now at max → should be skipped
        linked = link_orphaned_agents(
            db_session, sample_workspace.id, max_linking_attempts=3
        )
        assert linked == 0

        db_session.refresh(agent)
        assert agent.agent_metadata.get("_linking_attempts") == 3  # unchanged

    def test_successful_link_does_not_increment(
        self, db_session, sample_workspace
    ):
        """Successfully linked agents should not have their counter incremented."""
        now = datetime.now(UTC)
        parent_session_id = str(uuid.uuid4())

        # Create the parent first
        parent = _make_conversation(
            db_session,
            sample_workspace.id,
            start_time=now,
            extra_data={"session_id": parent_session_id},
        )

        # Create orphaned agent pointing to that parent
        agent = _make_conversation(
            db_session,
            sample_workspace.id,
            conversation_type="agent",
            start_time=now,
            agent_metadata={
                "parent_session_id": parent_session_id,
                "_linking_attempts": 0,
            },
            extra_data={"session_id": str(uuid.uuid4())},
        )
        db_session.flush()

        linked = link_orphaned_agents(db_session, sample_workspace.id)
        assert linked == 1

        db_session.refresh(agent)
        assert agent.parent_conversation_id == parent.id
        # Counter should still be 0 (not incremented on success)
        assert agent.agent_metadata.get("_linking_attempts") == 0
