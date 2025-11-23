"""Tests for canonicalization builders."""

from datetime import datetime, timedelta

import pytest

from catsyphon.canonicalization.builders import PlayFormatBuilder
from catsyphon.canonicalization.models import (
    CanonicalConfig,
    CanonicalConversation,
    CanonicalType,
)
from catsyphon.canonicalization.samplers import SampledMessage
from catsyphon.models.db import Conversation, Epoch, Message


class TestPlayFormatBuilder:
    """Test PlayFormatBuilder class."""

    def test_child_not_duplicated_when_multiple_messages_match(
        self, test_session, sample_workspace
    ):
        """Test that children are inserted exactly once after closest preceding message.

        With the new logic, children are inserted after the chronologically
        closest parent message that occurred before the child started, ensuring
        deterministic placement even when multiple messages are temporally close.
        """
        # Create parent conversation with multiple messages in a short timeframe
        base_time = datetime(2024, 11, 22, 14, 35, 0)

        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=10),
            status="completed",
            message_count=3,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        # Create epoch
        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        # Create three parent messages, two within 60 seconds
        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="First message",
            timestamp=base_time,  # 14:35:00
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Second message",
            timestamp=base_time + timedelta(seconds=30),  # 14:35:30
            sequence=1,
        )
        msg3 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Third message",
            timestamp=base_time + timedelta(minutes=5),  # 14:40:00
            sequence=2,
        )
        test_session.add_all([msg1, msg2, msg3])
        test_session.flush()
        test_session.refresh(conversation)

        # Create child conversation that spawned at 14:35:20
        # This is within 60 seconds of both msg1 (14:35:00) and msg2 (14:35:30)
        child_start = base_time + timedelta(seconds=20)  # 14:35:20
        child = CanonicalConversation(
            session_id="child-session",
            conversation_id="child-uuid",
            agent_type="claude-code",
            agent_version="2.0.28",
            conversation_type="agent",
            start_time=child_start,
            end_time=child_start + timedelta(minutes=3),
            duration_seconds=180,
            message_count=5,
            epoch_count=1,
            files_count=2,
            tool_calls_count=3,
            narrative="Child narrative content here",
            token_count=100,
            parent_id=str(conversation.id),
            children=[],
            tools_used=["Read", "Grep"],
            files_touched=["file1.py", "file2.py"],
            has_errors=False,
            code_changes_summary={},
            config=CanonicalConfig.for_type(CanonicalType.TAGGING),
            canonical_version=1,
            generated_at=datetime.now(),
        )

        # Create sampled messages for the builder
        sampled_messages = [
            SampledMessage(
                message=msg1,
                priority=1000,
                reason="chronological",
                estimated_tokens=10,
            ),
            SampledMessage(
                message=msg2,
                priority=1000,
                reason="chronological",
                estimated_tokens=10,
            ),
            SampledMessage(
                message=msg3,
                priority=1000,
                reason="chronological",
                estimated_tokens=10,
            ),
        ]

        # Build narrative with the child
        config = CanonicalConfig.for_type(CanonicalType.TAGGING)
        builder = PlayFormatBuilder(config)
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=[child],
        )

        # Assert child narrative appears exactly once
        child_count = narrative.count("AGENT DELEGATION: child-uuid")
        assert child_count == 1, (
            f"Expected child to appear exactly once, but found {child_count} occurrences. "
            f"This indicates the child was inserted multiple times."
        )

        # Also verify the child narrative content is present
        assert "Child narrative content here" in narrative

    def test_child_inserted_at_correct_position(
        self, test_session, sample_workspace
    ):
        """Test that children are inserted after the chronologically correct message."""
        base_time = datetime(2024, 11, 22, 14, 0, 0)

        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=10),
            status="completed",
            message_count=3,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        # Create messages
        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Message before child",
            timestamp=base_time,
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Message after child",
            timestamp=base_time + timedelta(minutes=5),
            sequence=1,
        )
        test_session.add_all([msg1, msg2])
        test_session.flush()
        test_session.refresh(conversation)

        # Child spawned shortly after msg1
        child_start = base_time + timedelta(seconds=10)
        child = CanonicalConversation(
            session_id="child-session",
            conversation_id="child-xyz",
            agent_type="claude-code",
            agent_version="2.0.28",
            conversation_type="agent",
            start_time=child_start,
            end_time=child_start + timedelta(minutes=2),
            duration_seconds=120,
            message_count=3,
            epoch_count=1,
            files_count=0,
            tool_calls_count=2,
            narrative="Child worked on task",
            token_count=50,
            parent_id=str(conversation.id),
            children=[],
            tools_used=["Read"],
            files_touched=[],
            has_errors=False,
            code_changes_summary={},
            config=CanonicalConfig.for_type(CanonicalType.TAGGING),
            canonical_version=1,
            generated_at=datetime.now(),
        )

        sampled_messages = [
            SampledMessage(msg1, 1000, "chronological", 10),
            SampledMessage(msg2, 1000, "chronological", 10),
        ]

        config = CanonicalConfig.for_type(CanonicalType.TAGGING)
        builder = PlayFormatBuilder(config)
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=[child],
        )

        # Find positions in narrative
        msg_before_pos = narrative.find("Message before child")
        child_pos = narrative.find("AGENT DELEGATION: child-xyz")
        msg_after_pos = narrative.find("Message after child")

        # Assert correct ordering
        assert msg_before_pos < child_pos < msg_after_pos, (
            "Child should be inserted between the two messages chronologically"
        )

    def test_multiple_children_all_inserted_once(
        self, test_session, sample_workspace
    ):
        """Test that multiple children are each inserted exactly once."""
        base_time = datetime(2024, 11, 22, 15, 0, 0)

        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=15),
            status="completed",
            message_count=4,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        # Create messages spread out
        messages = []
        for i in range(4):
            msg = Message(
                conversation_id=conversation.id,
                epoch_id=epoch.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                timestamp=base_time + timedelta(minutes=i * 3),
                sequence=i,
            )
            messages.append(msg)
        test_session.add_all(messages)
        test_session.flush()
        test_session.refresh(conversation)

        # Create three children at different times
        # Each within 60 seconds of a message to ensure they get inserted
        children = []
        for i in range(3):
            # Child i spawns 30 seconds after message i
            child_start = base_time + timedelta(minutes=i * 3, seconds=30)
            child = CanonicalConversation(
                session_id=f"child-{i}",
                conversation_id=f"child-id-{i}",
                agent_type="claude-code",
                agent_version="2.0.28",
                conversation_type="agent",
                start_time=child_start,
                end_time=child_start + timedelta(minutes=1),
                duration_seconds=60,
                message_count=2,
                epoch_count=1,
                files_count=0,
                tool_calls_count=1,
                narrative=f"Child {i} narrative",
                token_count=30,
                parent_id=str(conversation.id),
                children=[],
                tools_used=[],
                files_touched=[],
                has_errors=False,
                code_changes_summary={},
                config=CanonicalConfig.for_type(CanonicalType.TAGGING),
                canonical_version=1,
                generated_at=datetime.now(),
            )
            children.append(child)

        sampled_messages = [
            SampledMessage(msg, 1000, "chronological", 10)
            for msg in messages
        ]

        config = CanonicalConfig.for_type(CanonicalType.TAGGING)
        builder = PlayFormatBuilder(config)
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=children,
        )

        # Assert each child appears exactly once
        for i in range(3):
            child_count = narrative.count(f"AGENT DELEGATION: child-id-{i}")
            assert child_count == 1, (
                f"Child {i} should appear exactly once, found {child_count} times"
            )

    def test_child_before_any_message_not_inserted(
        self, test_session, sample_workspace
    ):
        """Test that child spawned before any parent message is not inserted."""
        base_time = datetime(2024, 11, 22, 14, 0, 0)

        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time + timedelta(minutes=5),  # Conversation starts later
            end_time=base_time + timedelta(minutes=10),
            status="completed",
            message_count=2,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time + timedelta(minutes=5),
        )
        test_session.add(epoch)
        test_session.flush()

        # Messages start at 5 minutes
        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="First message",
            timestamp=base_time + timedelta(minutes=5),
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Second message",
            timestamp=base_time + timedelta(minutes=6),
            sequence=1,
        )
        test_session.add_all([msg1, msg2])
        test_session.flush()
        test_session.refresh(conversation)

        # Child spawned BEFORE any parent message (at time 0)
        child = CanonicalConversation(
            session_id="early-child",
            conversation_id="early-child-uuid",
            agent_type="claude-code",
            agent_version="2.0.28",
            conversation_type="agent",
            start_time=base_time,  # Before first message!
            end_time=base_time + timedelta(minutes=1),
            duration_seconds=60,
            message_count=2,
            epoch_count=1,
            files_count=0,
            tool_calls_count=1,
            narrative="Early child narrative",
            token_count=30,
            parent_id=str(conversation.id),
            children=[],
            tools_used=[],
            files_touched=[],
            has_errors=False,
            code_changes_summary={},
            config=CanonicalConfig.for_type(CanonicalType.TAGGING),
            canonical_version=1,
            generated_at=datetime.now(),
        )

        sampled_messages = [
            SampledMessage(msg1, 1000, "chronological", 10),
            SampledMessage(msg2, 1000, "chronological", 10),
        ]

        config = CanonicalConfig.for_type(CanonicalType.TAGGING)
        builder = PlayFormatBuilder(config)
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=[child],
        )

        # Child should NOT appear (no valid insertion point)
        assert "AGENT DELEGATION: early-child-uuid" not in narrative
        assert "Early child narrative" not in narrative

    def test_multiple_children_with_same_insertion_point(
        self, test_session, sample_workspace
    ):
        """Test that multiple children spawned after same message all get inserted."""
        base_time = datetime(2024, 11, 22, 16, 0, 0)

        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=10),
            status="completed",
            message_count=2,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Spawn agents",
            timestamp=base_time,
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Done",
            timestamp=base_time + timedelta(minutes=8),
            sequence=1,
        )
        test_session.add_all([msg1, msg2])
        test_session.flush()
        test_session.refresh(conversation)

        # Three children all spawn shortly after msg1
        children = []
        for i in range(3):
            child = CanonicalConversation(
                session_id=f"child-{i}",
                conversation_id=f"child-same-point-{i}",
                agent_type="claude-code",
                agent_version="2.0.28",
                conversation_type="agent",
                start_time=base_time + timedelta(seconds=10 + i),  # All after msg1
                end_time=base_time + timedelta(minutes=1),
                duration_seconds=50,
                message_count=1,
                epoch_count=1,
                files_count=0,
                tool_calls_count=0,
                narrative=f"Child {i} narrative",
                token_count=20,
                parent_id=str(conversation.id),
                children=[],
                tools_used=[],
                files_touched=[],
                has_errors=False,
                code_changes_summary={},
                config=CanonicalConfig.for_type(CanonicalType.TAGGING),
                canonical_version=1,
                generated_at=datetime.now(),
            )
            children.append(child)

        sampled_messages = [
            SampledMessage(msg1, 1000, "chronological", 10),
            SampledMessage(msg2, 1000, "chronological", 10),
        ]

        config = CanonicalConfig.for_type(CanonicalType.TAGGING)
        builder = PlayFormatBuilder(config)
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=children,
        )

        # All three children should appear after msg1
        for i in range(3):
            assert f"AGENT DELEGATION: child-same-point-{i}" in narrative
            assert f"Child {i} narrative" in narrative

        # Verify they all appear AFTER msg1 and BEFORE msg2
        msg1_pos = narrative.find("Spawn agents")
        msg2_pos = narrative.find("Done")
        for i in range(3):
            child_pos = narrative.find(f"AGENT DELEGATION: child-same-point-{i}")
            assert msg1_pos < child_pos < msg2_pos, (
                f"Child {i} should appear between msg1 and msg2"
            )

    def test_exact_parent_message_id_match(
        self, test_session, sample_workspace
    ):
        """Test that child with parent_message_id is inserted after exact message."""
        base_time = datetime(2025, 11, 22, 10, 0, 0)

        # Create parent conversation
        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=10),
            status="completed",
            message_count=5,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        # Create epoch
        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        # Create five parent messages
        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="First message",
            timestamp=base_time,
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Second message",
            timestamp=base_time + timedelta(minutes=1),
            sequence=1,
        )
        target_message = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Third message with Task",
            timestamp=base_time + timedelta(minutes=2),
            sequence=2,
        )
        msg4 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Fourth message",
            timestamp=base_time + timedelta(minutes=3),
            sequence=3,
        )
        msg5 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Fifth message",
            timestamp=base_time + timedelta(minutes=4),
            sequence=4,
        )
        test_session.add_all([msg1, msg2, target_message, msg4, msg5])
        test_session.flush()
        test_session.refresh(conversation)

        # Create child with exact parent_message_id
        child = CanonicalConversation(
            session_id="child-exact-id",
            conversation_id="child-exact-uuid",
            agent_type="claude-code",
            agent_version="2.0",
            conversation_type="agent",
            start_time=base_time + timedelta(minutes=2, seconds=30),
            end_time=base_time + timedelta(minutes=2, seconds=45),
            duration_seconds=15,
            message_count=5,
            epoch_count=1,
            files_count=0,
            tool_calls_count=2,
            narrative="Child narrative content",
            token_count=100,
            agent_metadata={"parent_message_id": str(target_message.id)},
        )

        # Create sampled messages for the builder
        sampled_messages = [
            SampledMessage(message=msg1, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=msg2, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=target_message, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=msg4, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=msg5, priority=1000, reason="chronological", estimated_tokens=10),
        ]

        # Build narrative with exact ID matching
        builder = PlayFormatBuilder(CanonicalConfig())
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=[child],
        )

        # Verify child appears exactly after the third message
        third_msg_pos = narrative.find("Third message with Task")
        fourth_msg_pos = narrative.find("Fourth message")
        child_pos = narrative.find("AGENT DELEGATION: child-exact-uuid")

        assert third_msg_pos < child_pos < fourth_msg_pos, (
            "Child should appear between third and fourth messages "
            "(after the exact parent_message_id)"
        )

    def test_fallback_to_timestamp_when_parent_message_id_not_found(
        self, test_session, sample_workspace
    ):
        """Test that builder falls back to timestamp matching when parent_message_id not in sampled messages."""
        base_time = datetime(2025, 11, 22, 10, 0, 0)

        # Create parent conversation
        conversation = Conversation(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=5),
            status="completed",
            message_count=3,
            epoch_count=1,
        )
        test_session.add(conversation)
        test_session.flush()

        # Create epoch
        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=base_time,
        )
        test_session.add(epoch)
        test_session.flush()

        # Create three parent messages
        msg1 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="First message",
            timestamp=base_time,
            sequence=0,
        )
        msg2 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="assistant",
            content="Second message",
            timestamp=base_time + timedelta(minutes=1),
            sequence=1,
        )
        msg3 = Message(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            role="user",
            content="Third message",
            timestamp=base_time + timedelta(minutes=2),
            sequence=2,
        )
        test_session.add_all([msg1, msg2, msg3])
        test_session.flush()
        test_session.refresh(conversation)

        # Create child with INVALID parent_message_id (UUID that doesn't exist)
        # Should fall back to timestamp matching
        child = CanonicalConversation(
            session_id="child-fallback",
            conversation_id="child-fallback-uuid",
            agent_type="claude-code",
            agent_version="2.0",
            conversation_type="agent",
            start_time=base_time + timedelta(minutes=1, seconds=30),
            end_time=base_time + timedelta(minutes=1, seconds=45),
            duration_seconds=15,
            message_count=3,
            epoch_count=1,
            files_count=0,
            tool_calls_count=1,
            narrative="Child narrative content",
            token_count=50,
            agent_metadata={"parent_message_id": "00000000-0000-0000-0000-000000000000"},  # Invalid ID
        )

        # Create sampled messages for the builder
        sampled_messages = [
            SampledMessage(message=msg1, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=msg2, priority=1000, reason="chronological", estimated_tokens=10),
            SampledMessage(message=msg3, priority=1000, reason="chronological", estimated_tokens=10),
        ]

        # Build narrative - should use timestamp fallback
        builder = PlayFormatBuilder(CanonicalConfig())
        narrative = builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=[],
            children=[child],
        )

        # Child starts at minute 1:30, so should be inserted after second message (minute 1)
        second_msg_pos = narrative.find("Second message")
        third_msg_pos = narrative.find("Third message")
        child_pos = narrative.find("AGENT DELEGATION: child-fallback-uuid")

        assert second_msg_pos < child_pos < third_msg_pos, (
            "Child should appear between second and third messages "
            "(fallback to timestamp-based matching)"
        )
