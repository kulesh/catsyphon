"""
Tests for database repositories.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    EpochRepository,
    MessageRepository,
    ProjectRepository,
    RawLogRepository,
)
from catsyphon.models.db import Conversation, Developer, Epoch, Project


class TestProjectRepository:
    """Tests for ProjectRepository."""

    def test_create_project(self, db_session: Session):
        """Test creating a project via repository."""
        repo = ProjectRepository(db_session)
        project = repo.create(
            id=uuid.uuid4(),
            name="New Project",
            description="Project description",
        )

        assert project.id is not None
        assert project.name == "New Project"

    def test_get_project(self, db_session: Session, sample_project: Project):
        """Test getting a project by ID."""
        repo = ProjectRepository(db_session)
        project = repo.get(sample_project.id)

        assert project is not None
        assert project.id == sample_project.id
        assert project.name == sample_project.name

    def test_get_nonexistent_project(self, db_session: Session):
        """Test getting a non-existent project returns None."""
        repo = ProjectRepository(db_session)
        project = repo.get(uuid.uuid4())

        assert project is None

    def test_get_by_name(self, db_session: Session, sample_project: Project):
        """Test getting a project by name."""
        repo = ProjectRepository(db_session)
        project = repo.get_by_name("Test Project")

        assert project is not None
        assert project.id == sample_project.id

    def test_search_by_name(self, db_session: Session):
        """Test searching projects by name pattern."""
        repo = ProjectRepository(db_session)

        # Create multiple projects
        repo.create(id=uuid.uuid4(), name="Project Alpha")
        repo.create(id=uuid.uuid4(), name="Project Beta")
        repo.create(id=uuid.uuid4(), name="Other Thing")

        results = repo.search_by_name("%Project%")

        assert len(results) == 2
        assert all("Project" in p.name for p in results)

    def test_update_project(self, db_session: Session, sample_project: Project):
        """Test updating a project."""
        repo = ProjectRepository(db_session)
        updated = repo.update(
            sample_project.id,
            description="Updated description",
        )

        assert updated is not None
        assert updated.description == "Updated description"

    def test_delete_project(self, db_session: Session, sample_project: Project):
        """Test deleting a project."""
        repo = ProjectRepository(db_session)
        project_id = sample_project.id

        result = repo.delete(project_id)
        assert result is True

        # Verify it's gone
        project = repo.get(project_id)
        assert project is None

    def test_count_projects(self, db_session: Session):
        """Test counting projects."""
        repo = ProjectRepository(db_session)

        initial_count = repo.count()
        repo.create(id=uuid.uuid4(), name="Project 1")
        repo.create(id=uuid.uuid4(), name="Project 2")

        assert repo.count() == initial_count + 2

    def test_get_all_projects(self, db_session: Session):
        """Test getting all projects with pagination."""
        repo = ProjectRepository(db_session)

        # Create test data
        for i in range(5):
            repo.create(id=uuid.uuid4(), name=f"Project {i}")

        # Test limit
        results = repo.get_all(limit=3)
        assert len(results) <= 3

        # Test offset
        results_offset = repo.get_all(limit=3, offset=2)
        assert len(results_offset) <= 3


class TestDeveloperRepository:
    """Tests for DeveloperRepository."""

    def test_create_developer(self, db_session: Session):
        """Test creating a developer via repository."""
        repo = DeveloperRepository(db_session)
        developer = repo.create(
            id=uuid.uuid4(),
            username="john_doe",
            email="john@example.com",
        )

        assert developer.id is not None
        assert developer.username == "john_doe"

    def test_get_by_username(self, db_session: Session, sample_developer: Developer):
        """Test getting a developer by username."""
        repo = DeveloperRepository(db_session)
        developer = repo.get_by_username("test_developer")

        assert developer is not None
        assert developer.id == sample_developer.id

    def test_get_by_email(self, db_session: Session, sample_developer: Developer):
        """Test getting a developer by email."""
        repo = DeveloperRepository(db_session)
        developer = repo.get_by_email("test@example.com")

        assert developer is not None
        assert developer.id == sample_developer.id

    def test_get_or_create_existing(
        self, db_session: Session, sample_developer: Developer
    ):
        """Test get_or_create with existing developer."""
        repo = DeveloperRepository(db_session)
        developer = repo.get_or_create(username="test_developer")

        assert developer.id == sample_developer.id

    def test_get_or_create_new(self, db_session: Session):
        """Test get_or_create with new developer."""
        repo = DeveloperRepository(db_session)
        initial_count = repo.count()

        developer = repo.get_or_create(
            username="new_developer",
            email="new@example.com",
        )

        assert developer.id is not None
        assert developer.username == "new_developer"
        assert repo.count() == initial_count + 1


class TestConversationRepository:
    """Tests for ConversationRepository."""

    def test_create_conversation(
        self, db_session: Session, sample_project: Project, sample_developer: Developer
    ):
        """Test creating a conversation via repository."""
        repo = ConversationRepository(db_session)
        conversation = repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        assert conversation.id is not None
        assert conversation.agent_type == "claude-code"

    def test_get_with_relations(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test getting conversation with related data."""
        repo = ConversationRepository(db_session)
        conversation = repo.get_with_relations(sample_conversation.id)

        assert conversation is not None
        assert conversation.project is not None
        assert conversation.developer is not None

    def test_get_by_project(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting conversations by project."""
        repo = ConversationRepository(db_session)

        # Create multiple conversations
        for i in range(3):
            repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC),
            )

        conversations = repo.get_by_project(sample_project.id)
        assert len(conversations) >= 3

    def test_get_by_developer(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting conversations by developer."""
        repo = ConversationRepository(db_session)

        # Create conversations
        for i in range(2):
            repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC),
            )

        conversations = repo.get_by_developer(sample_developer.id)
        assert len(conversations) >= 2

    def test_get_by_agent_type(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting conversations by agent type."""
        repo = ConversationRepository(db_session)

        # Create conversations with different agent types
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="copilot",
            start_time=datetime.now(UTC),
        )

        claude_conversations = repo.get_by_agent_type("claude-code")
        assert len(claude_conversations) >= 1
        assert all(c.agent_type == "claude-code" for c in claude_conversations)

    def test_get_by_date_range(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting conversations by date range."""
        repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create conversation from yesterday
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=yesterday,
        )

        # Query for conversations in the last day
        conversations = repo.get_by_date_range(two_days_ago, now)
        assert len(conversations) >= 1

    def test_count_by_status(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test counting conversations by status."""
        repo = ConversationRepository(db_session)

        # Create conversations with different statuses
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            status="completed",
        )
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            status="open",
        )

        completed_count = repo.count_by_status("completed")
        assert completed_count >= 1

    def test_get_recent(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting recent conversations."""
        repo = ConversationRepository(db_session)

        # Create several conversations
        for i in range(5):
            repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC) - timedelta(minutes=i),
            )

        recent = repo.get_recent(limit=3)
        assert len(recent) <= 3

        # Should be ordered by start_time desc (most recent first)
        if len(recent) > 1:
            assert recent[0].start_time >= recent[1].start_time

    def test_pagination(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test repository pagination."""
        repo = ConversationRepository(db_session)

        # Create test data
        for i in range(10):
            repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC),
            )

        # Test limit and offset
        page1 = repo.get_by_project(sample_project.id, limit=5, offset=0)
        page2 = repo.get_by_project(sample_project.id, limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5
        # IDs should be different
        page1_ids = {c.id for c in page1}
        page2_ids = {c.id for c in page2}
        assert len(page1_ids & page2_ids) == 0  # No overlap

    def test_get_with_counts_returns_accurate_counts(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test get_with_counts returns accurate SQL-computed counts."""
        from catsyphon.models.db import FileTouched

        conv_repo = ConversationRepository(db_session)
        epoch_repo = EpochRepository(db_session)
        msg_repo = MessageRepository(db_session)

        # Create conversation with multiple messages, epochs, and files
        conv = conv_repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        # Create 3 epochs
        epochs = []
        for i in range(3):
            epoch = epoch_repo.create_epoch(
                conversation_id=conv.id,
                sequence=i,
                start_time=datetime.now(UTC),
            )
            epochs.append(epoch)

        # Create 5 messages
        for i in range(5):
            msg_repo.create_message(
                epoch_id=epochs[0].id,
                conversation_id=conv.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        # Create 2 files touched
        for i in range(2):
            file_touched = FileTouched(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                epoch_id=epochs[0].id,
                file_path=f"test{i}.py",
                change_type="modified",
                timestamp=datetime.now(UTC),
            )
            db_session.add(file_touched)
        db_session.commit()

        # Use get_with_counts
        results = conv_repo.get_with_counts(project_id=sample_project.id)

        # Find our conversation
        result = next(
            (r for r in results if r[0].id == conv.id),
            None,
        )
        assert result is not None

        conversation, msg_count, epoch_count, files_count = result

        # Verify counts are correct
        assert msg_count == 5
        assert epoch_count == 3
        assert files_count == 2

    def test_get_with_counts_uses_selectinload_not_joinedload(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that get_with_counts uses selectinload for relations."""
        conv_repo = ConversationRepository(db_session)

        _conv = conv_repo.create(  # noqa: F841 - Used for test setup
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        # This should not raise GROUP BY error
        results = conv_repo.get_with_counts()

        assert len(results) >= 1
        conversation, msg_count, epoch_count, files_count = results[0]

        # Project and developer should be loaded
        assert conversation.project is not None
        assert conversation.developer is not None

    def test_get_with_counts_filters_work(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that get_with_counts applies filters correctly."""
        conv_repo = ConversationRepository(db_session)

        # Create conversations with different attributes
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            success=True,
        )
        conv2 = conv_repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="copilot",
            start_time=datetime.now(UTC),
            success=False,
        )

        # Filter by agent_type (partial match)
        results = conv_repo.get_with_counts(agent_type="claude")
        conv_ids = [r[0].id for r in results]

        assert conv1.id in conv_ids
        assert conv2.id not in conv_ids

        # Filter by success
        results = conv_repo.get_with_counts(success=True)
        conv_ids = [r[0].id for r in results]

        assert conv1.id in conv_ids
        assert conv2.id not in conv_ids

    def test_get_with_counts_pagination(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that get_with_counts supports pagination."""
        conv_repo = ConversationRepository(db_session)

        # Create 10 conversations
        for i in range(10):
            conv_repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC) - timedelta(minutes=i),
            )

        # Get first page
        page1 = conv_repo.get_with_counts(limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = conv_repo.get_with_counts(limit=5, offset=5)
        assert len(page2) == 5

        # Should be different conversations
        ids1 = {r[0].id for r in page1}
        ids2 = {r[0].id for r in page2}
        assert len(ids1 & ids2) == 0

    def test_get_with_counts_ordering(
        self,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test get_with_counts ordering by different columns."""
        conv_repo = ConversationRepository(db_session)

        # Create conversations at different times
        now = datetime.now(UTC)
        for i in range(3):
            conv_repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=now - timedelta(minutes=i),
            )

        # Order by start_time desc (default)
        results_desc = conv_repo.get_with_counts(
            order_by="start_time", order_dir="desc"
        )
        times_desc = [r[0].start_time for r in results_desc]

        # Should be in descending order (newest first)
        assert times_desc == sorted(times_desc, reverse=True)

        # Order by start_time asc
        results_asc = conv_repo.get_with_counts(order_by="start_time", order_dir="asc")
        times_asc = [r[0].start_time for r in results_asc]

        # Should be in ascending order (oldest first)
        assert times_asc == sorted(times_asc)


class TestEpochRepository:
    """Tests for EpochRepository."""

    def test_create_epoch(self, db_session: Session, sample_conversation: Conversation):
        """Test creating an epoch via repository."""
        repo = EpochRepository(db_session)
        epoch = repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=0,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(minutes=10),
            intent="feature_add",
            outcome="success",
            sentiment="positive",
            sentiment_score=0.8,
        )

        assert epoch.id is not None
        assert epoch.conversation_id == sample_conversation.id
        assert epoch.sequence == 0
        assert epoch.intent == "feature_add"
        assert epoch.duration_seconds == 600  # 10 minutes

    def test_get_by_conversation(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test getting epochs by conversation."""
        repo = EpochRepository(db_session)

        # Create multiple epochs
        for i in range(3):
            repo.create_epoch(
                conversation_id=sample_conversation.id,
                sequence=i,
                start_time=datetime.now(UTC) + timedelta(minutes=i),
            )

        epochs = repo.get_by_conversation(sample_conversation.id)
        assert len(epochs) >= 3

    def test_get_by_sequence(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test getting epoch by sequence number."""
        repo = EpochRepository(db_session)

        # Create epochs with different sequences
        repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=0,
            start_time=datetime.now(UTC),
        )
        epoch2 = repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=1,
            start_time=datetime.now(UTC),
        )

        # Get specific sequence
        found = repo.get_by_sequence(sample_conversation.id, 1)
        assert found is not None
        assert found.id == epoch2.id

    def test_get_next_sequence(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test getting next sequence number."""
        repo = EpochRepository(db_session)

        # First epoch should be sequence 0
        next_seq = repo.get_next_sequence(sample_conversation.id)
        assert next_seq == 0

        # Create an epoch
        repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=next_seq,
            start_time=datetime.now(UTC),
        )

        # Next should be 1
        next_seq = repo.get_next_sequence(sample_conversation.id)
        assert next_seq == 1

    def test_create_epoch_calculates_duration(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test that duration is auto-calculated."""
        repo = EpochRepository(db_session)

        start = datetime.now(UTC)
        end = start + timedelta(minutes=5, seconds=30)

        epoch = repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=0,
            start_time=start,
            end_time=end,
        )

        assert epoch.duration_seconds == 330  # 5.5 minutes = 330 seconds

    def test_get_by_conversation_ordering(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test that epochs are ordered by sequence."""
        repo = EpochRepository(db_session)

        # Create epochs in reverse order
        for i in [2, 0, 1]:
            repo.create_epoch(
                conversation_id=sample_conversation.id,
                sequence=i,
                start_time=datetime.now(UTC),
            )

        epochs = repo.get_by_conversation(sample_conversation.id)

        # Should be ordered by sequence ascending
        sequences = [e.sequence for e in epochs]
        assert sequences == sorted(sequences)

    def test_create_epoch_with_tags(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test creating epoch with tagging data."""
        repo = EpochRepository(db_session)

        epoch = repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=0,
            start_time=datetime.now(UTC),
            intent="bug_fix",
            outcome="partial",
            sentiment="neutral",
            sentiment_score=0.0,
        )

        assert epoch.intent == "bug_fix"
        assert epoch.outcome == "partial"
        assert epoch.sentiment == "neutral"
        assert epoch.sentiment_score == 0.0

    def test_epoch_cascade_delete(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test that epochs are deleted when conversation is deleted."""
        repo = EpochRepository(db_session)
        conv_repo = ConversationRepository(db_session)

        # Create an epoch
        epoch = repo.create_epoch(
            conversation_id=sample_conversation.id,
            sequence=0,
            start_time=datetime.now(UTC),
        )
        epoch_id = epoch.id

        # Delete conversation
        conv_repo.delete(sample_conversation.id)
        db_session.flush()

        # Epoch should be gone
        deleted_epoch = repo.get(epoch_id)
        assert deleted_epoch is None


class TestMessageRepository:
    """Tests for MessageRepository."""

    def test_create_message(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test creating a message via repository."""
        repo = MessageRepository(db_session)
        message = repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="user",
            content="Test message",
            timestamp=datetime.now(UTC),
            sequence=0,
        )

        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Test message"

    def test_get_by_conversation(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test getting messages by conversation."""
        repo = MessageRepository(db_session)

        # Create multiple messages
        for i in range(3):
            repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        messages = repo.get_by_conversation(sample_conversation.id)
        assert len(messages) >= 3

    def test_get_by_epoch(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test getting messages by epoch."""
        repo = MessageRepository(db_session)

        # Create messages
        for i in range(2):
            repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        messages = repo.get_by_epoch(sample_epoch.id)
        assert len(messages) >= 2

    def test_get_by_role(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test filtering messages by role."""
        repo = MessageRepository(db_session)

        # Create messages with different roles
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="user",
            content="User message 1",
            timestamp=datetime.now(UTC),
            sequence=0,
        )
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Assistant message",
            timestamp=datetime.now(UTC),
            sequence=1,
        )
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="user",
            content="User message 2",
            timestamp=datetime.now(UTC),
            sequence=2,
        )

        user_messages = repo.get_by_role(sample_conversation.id, "user")
        assert len(user_messages) >= 2
        assert all(m.role == "user" for m in user_messages)

    def test_bulk_create(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test bulk creating messages."""
        repo = MessageRepository(db_session)

        messages_data = [
            {
                "epoch_id": sample_epoch.id,
                "conversation_id": sample_conversation.id,
                "role": "user",
                "content": f"Bulk message {i}",
                "timestamp": datetime.now(UTC),
                "sequence": i,
            }
            for i in range(5)
        ]

        created = repo.bulk_create(messages_data)
        assert len(created) == 5

        # Verify they're in the database
        all_messages = repo.get_by_conversation(sample_conversation.id)
        assert len(all_messages) >= 5

    def test_message_with_tool_calls(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test storing messages with tool calls."""
        repo = MessageRepository(db_session)

        tool_calls = [
            {
                "tool_name": "Read",
                "parameters": {"file_path": "test.py"},
                "result": "file contents",
                "success": True,
            }
        ]

        message = repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Reading file",
            timestamp=datetime.now(UTC),
            sequence=0,
            tool_calls=tool_calls,
        )

        assert len(message.tool_calls) == 1
        assert message.tool_calls[0]["tool_name"] == "Read"

    def test_message_with_code_changes(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test storing messages with code changes."""
        repo = MessageRepository(db_session)

        code_changes = [
            {
                "file_path": "test.py",
                "change_type": "edit",
                "old_content": "old",
                "new_content": "new",
                "lines_added": 1,
                "lines_deleted": 1,
            }
        ]

        message = repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Editing file",
            timestamp=datetime.now(UTC),
            sequence=0,
            code_changes=code_changes,
        )

        assert len(message.code_changes) == 1
        assert message.code_changes[0]["file_path"] == "test.py"

    def test_message_ordering(
        self,
        db_session: Session,
        sample_epoch: Epoch,
        sample_conversation: Conversation,
    ):
        """Test that messages are ordered by sequence."""
        repo = MessageRepository(db_session)

        # Create messages in reverse order
        for i in [2, 0, 1]:
            repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        messages = repo.get_by_epoch(sample_epoch.id)

        # Should be ordered by sequence ascending
        sequences = [m.sequence for m in messages]
        assert sequences == sorted(sequences)


class TestRawLogRepository:
    """Tests for RawLogRepository."""

    def test_create_from_content(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test creating raw log from content string."""
        repo = RawLogRepository(db_session)

        raw_log = repo.create_from_content(
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="jsonl",
            raw_content='{"test": "content"}',
            file_path="/path/to/log.jsonl",
        )

        assert raw_log.id is not None
        assert raw_log.raw_content == '{"test": "content"}'
        assert raw_log.file_path == "/path/to/log.jsonl"

    def test_create_from_file(
        self, db_session: Session, sample_conversation: Conversation, tmp_path
    ):
        """Test creating raw log from actual file."""
        repo = RawLogRepository(db_session)

        # Create a temporary file
        log_file = tmp_path / "test.jsonl"
        log_file.write_text('{"session": "test"}')

        raw_log = repo.create_from_file(
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="jsonl",
            file_path=log_file,
        )

        assert raw_log.id is not None
        assert '{"session": "test"}' in raw_log.raw_content
        assert str(log_file) in raw_log.file_path

    def test_get_by_conversation(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test getting raw logs by conversation."""
        repo = RawLogRepository(db_session)

        # Create multiple raw logs
        for i in range(2):
            repo.create_from_content(
                conversation_id=sample_conversation.id,
                agent_type="claude-code",
                log_format="jsonl",
                raw_content=f'{{"log": {i}}}',
            )

        raw_logs = repo.get_by_conversation(sample_conversation.id)
        assert len(raw_logs) >= 2

    def test_get_by_agent_type(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test filtering raw logs by agent type."""
        repo = RawLogRepository(db_session)

        # Create raw logs with different agent types
        repo.create_from_content(
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="jsonl",
            raw_content='{"type": "claude"}',
        )
        repo.create_from_content(
            conversation_id=sample_conversation.id,
            agent_type="copilot",
            log_format="json",
            raw_content='{"type": "copilot"}',
        )

        claude_logs = repo.get_by_agent_type("claude-code")
        assert len(claude_logs) >= 1
        assert all(log.agent_type == "claude-code" for log in claude_logs)

    def test_raw_log_stores_full_content(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test that raw log preserves full content."""
        repo = RawLogRepository(db_session)

        long_content = '{"data": "' + ("x" * 10000) + '"}'

        raw_log = repo.create_from_content(
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="jsonl",
            raw_content=long_content,
        )

        assert len(raw_log.raw_content) == len(long_content)
        assert raw_log.raw_content == long_content

    def test_raw_log_cascade_delete(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test that raw logs are deleted when conversation is deleted."""
        repo = RawLogRepository(db_session)
        conv_repo = ConversationRepository(db_session)

        # Create a raw log
        raw_log = repo.create_from_content(
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="jsonl",
            raw_content='{"test": "data"}',
        )
        raw_log_id = raw_log.id

        # Delete conversation
        conv_repo.delete(sample_conversation.id)
        db_session.flush()

        # Raw log should be gone
        deleted_log = repo.get(raw_log_id)
        assert deleted_log is None
