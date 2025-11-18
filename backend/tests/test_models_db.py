"""
Tests for SQLAlchemy database models.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from catsyphon.models.db import (
    Conversation,
    ConversationTag,
    Developer,
    Epoch,
    FileTouched,
    Message,
    Project,
    RawLog,
)


class TestModelRepr:
    """Tests for model __repr__ methods."""

    def test_project_repr(self, sample_project: Project):
        """Test Project __repr__ method."""
        repr_str = repr(sample_project)
        assert "Project" in repr_str
        assert sample_project.name in repr_str

    def test_developer_repr(self, sample_developer: Developer):
        """Test Developer __repr__ method."""
        repr_str = repr(sample_developer)
        assert "Developer" in repr_str
        assert sample_developer.username in repr_str

    def test_conversation_repr(self, sample_conversation: Conversation):
        """Test Conversation __repr__ method."""
        repr_str = repr(sample_conversation)
        assert "Conversation" in repr_str
        assert str(sample_conversation.id) in repr_str

    def test_epoch_repr(self, sample_epoch: Epoch):
        """Test Epoch __repr__ method."""
        repr_str = repr(sample_epoch)
        assert "Epoch" in repr_str
        assert str(sample_epoch.id) in repr_str

    def test_message_repr(self, sample_message: Message):
        """Test Message __repr__ method."""
        repr_str = repr(sample_message)
        assert "Message" in repr_str
        assert str(sample_message.id) in repr_str

    def test_file_touched_repr(self, sample_file_touched: FileTouched):
        """Test FileTouched __repr__ method."""
        repr_str = repr(sample_file_touched)
        assert "FileTouched" in repr_str
        assert str(sample_file_touched.id) in repr_str

    def test_conversation_tag_repr(self, sample_conversation_tag: ConversationTag):
        """Test ConversationTag __repr__ method."""
        repr_str = repr(sample_conversation_tag)
        assert "ConversationTag" in repr_str
        assert str(sample_conversation_tag.id) in repr_str

    def test_raw_log_repr(self, sample_raw_log: RawLog):
        """Test RawLog __repr__ method."""
        repr_str = repr(sample_raw_log)
        assert "RawLog" in repr_str
        assert str(sample_raw_log.id) in repr_str


class TestProject:
    """Tests for Project model."""

    def test_create_project(self, db_session: Session, sample_workspace):
        """Test creating a project."""
        project = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="My Project",
            description="Test project description",
            directory_path="/tmp/my-project",
        )
        db_session.add(project)
        db_session.commit()

        assert project.id is not None
        assert project.workspace_id == sample_workspace.id
        assert project.name == "My Project"
        assert project.description == "Test project description"
        assert project.created_at is not None
        assert project.updated_at is not None

    def test_project_repr(self, sample_project: Project):
        """Test project string representation."""
        repr_str = repr(sample_project)
        assert "Project" in repr_str
        assert str(sample_project.id) in repr_str
        assert "Test Project" in repr_str

    def test_project_conversations_relationship(
        self,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test project-conversations relationship."""
        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        db_session.add(conversation)
        db_session.commit()

        db_session.refresh(sample_project)
        assert len(sample_project.conversations) == 1
        assert sample_project.conversations[0].id == conversation.id


class TestDeveloper:
    """Tests for Developer model."""

    def test_create_developer(self, db_session: Session, sample_workspace):
        """Test creating a developer."""
        developer = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="john_doe",
            email="john@example.com",
            extra_data={"role": "engineer", "team": "backend"},
        )
        db_session.add(developer)
        db_session.commit()

        assert developer.id is not None
        assert developer.workspace_id == sample_workspace.id
        assert developer.username == "john_doe"
        assert developer.email == "john@example.com"
        assert developer.extra_data["role"] == "engineer"
        assert developer.created_at is not None

    def test_developer_without_email(self, db_session: Session, sample_workspace):
        """Test creating a developer without email."""
        developer = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="jane_doe",
        )
        db_session.add(developer)
        db_session.commit()

        assert developer.email is None
        assert developer.extra_data == {}

    def test_developer_repr(self, sample_developer: Developer):
        """Test developer string representation."""
        repr_str = repr(sample_developer)
        assert "Developer" in repr_str
        assert "test_developer" in repr_str


class TestConversation:
    """Tests for Conversation model."""

    def test_create_conversation(
        self,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test creating a conversation."""
        start_time = datetime.now(UTC)
        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=start_time,
            status="open",
            iteration_count=1,
        )
        db_session.add(conversation)
        db_session.commit()

        assert conversation.id is not None
        assert conversation.project_id == sample_project.id
        assert conversation.developer_id == sample_developer.id
        assert conversation.agent_type == "claude-code"
        assert conversation.status == "open"
        assert conversation.iteration_count == 1

    def test_conversation_default_values(
        self, db_session: Session, sample_workspace, sample_project: Project
    ):
        """Test conversation default values."""
        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        db_session.add(conversation)
        db_session.commit()

        # Status defaults to 'open'
        # iteration_count defaults to 1
        assert conversation.tags == {}
        assert conversation.extra_data == {}

    def test_conversation_relationships(self, sample_conversation: Conversation):
        """Test conversation relationships."""
        assert sample_conversation.project is not None
        assert sample_conversation.developer is not None
        assert isinstance(sample_conversation.epochs, list)
        assert isinstance(sample_conversation.messages, list)


class TestEpoch:
    """Tests for Epoch model."""

    def test_create_epoch(self, db_session: Session, sample_conversation: Conversation):
        """Test creating an epoch."""
        start_time = datetime.now(UTC)
        epoch = Epoch(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            sequence=1,
            intent="bug_fix",
            outcome="success",
            sentiment="positive",
            sentiment_score=0.7,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=5),
            duration_seconds=300,
        )
        db_session.add(epoch)
        db_session.commit()

        assert epoch.id is not None
        assert epoch.conversation_id == sample_conversation.id
        assert epoch.sequence == 1
        assert epoch.intent == "bug_fix"
        assert epoch.outcome == "success"
        assert epoch.sentiment_score == 0.7

    @pytest.mark.skip(reason="Unique constraints behave differently in SQLite")
    def test_epoch_unique_constraint(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test epoch unique constraint on (conversation_id, sequence)."""
        epoch1 = Epoch(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            sequence=1,
            start_time=datetime.now(UTC),
        )
        db_session.add(epoch1)
        db_session.commit()

        # Try to add another epoch with same conversation_id and sequence
        epoch2 = Epoch(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            sequence=1,  # Same sequence!
            start_time=datetime.now(UTC),
        )
        db_session.add(epoch2)

        # SQLite and PostgreSQL handle this differently
        # In PostgreSQL it raises IntegrityError immediately
        # In SQLite it may raise on commit or flush
        try:
            db_session.commit()
            # If we got here, the constraint didn't work
            pytest.fail("Expected unique constraint violation")
        except Exception:
            # Expected - constraint violation
            db_session.rollback()
            assert True


class TestMessage:
    """Tests for Message model."""

    def test_create_message(
        self,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test creating a message."""
        timestamp = datetime.now(UTC)
        message = Message(
            id=uuid.uuid4(),
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="I'll help you implement that feature.",
            timestamp=timestamp,
            sequence=1,
            tool_calls=[{"tool": "Read", "file": "main.py"}],
            entities={"files": ["main.py"]},
        )
        db_session.add(message)
        db_session.commit()

        assert message.id is not None
        assert message.role == "assistant"
        assert "feature" in message.content
        assert len(message.tool_calls) == 1

    def test_message_jsonb_fields(self, sample_message: Message):
        """Test JSONB field access."""
        assert isinstance(sample_message.tool_calls, list)
        assert isinstance(sample_message.entities, dict)
        assert "files" in sample_message.entities


class TestFileTouched:
    """Tests for FileTouched model."""

    def test_create_file_touched(
        self,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test creating a file touched record."""
        timestamp = datetime.now(UTC)
        file_touched = FileTouched(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            epoch_id=sample_epoch.id,
            file_path="src/models.py",
            change_type="modified",
            lines_added=15,
            lines_deleted=3,
            timestamp=timestamp,
        )
        db_session.add(file_touched)
        db_session.commit()

        assert file_touched.file_path == "src/models.py"
        assert file_touched.change_type == "modified"
        assert file_touched.lines_added == 15
        assert file_touched.lines_deleted == 3


class TestConversationTag:
    """Tests for ConversationTag model."""

    def test_create_tag(self, db_session: Session, sample_conversation: Conversation):
        """Test creating a conversation tag."""
        tag = ConversationTag(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            tag_type="feature",
            tag_value="authentication",
            confidence=0.92,
        )
        db_session.add(tag)
        db_session.commit()

        assert tag.tag_type == "feature"
        assert tag.tag_value == "authentication"
        assert tag.confidence == 0.92

    @pytest.mark.skip(reason="Unique constraints behave differently in SQLite")
    def test_tag_unique_constraint(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test tag unique constraint on (conversation_id, tag_type, tag_value)."""
        tag1 = ConversationTag(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            tag_type="technology",
            tag_value="Python",
        )
        db_session.add(tag1)
        db_session.commit()

        # Try to add duplicate tag
        tag2 = ConversationTag(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            tag_type="technology",
            tag_value="Python",
        )
        db_session.add(tag2)

        # SQLite and PostgreSQL handle this differently
        try:
            db_session.commit()
            # If we got here, the constraint didn't work
            pytest.fail("Expected unique constraint violation")
        except Exception:
            # Expected - constraint violation
            db_session.rollback()
            assert True


class TestRawLog:
    """Tests for RawLog model."""

    def test_create_raw_log(
        self, db_session: Session, sample_conversation: Conversation
    ):
        """Test creating a raw log."""
        from catsyphon.utils.hashing import calculate_content_hash

        raw_content = '{"test": "data"}'
        raw_log = RawLog(
            id=uuid.uuid4(),
            conversation_id=sample_conversation.id,
            agent_type="claude-code",
            log_format="json",
            raw_content=raw_content,
            file_path="/logs/conversation.json",
            file_hash=calculate_content_hash(raw_content),
        )
        db_session.add(raw_log)
        db_session.commit()

        assert raw_log.agent_type == "claude-code"
        assert raw_log.log_format == "json"
        assert '"test"' in raw_log.raw_content
        assert raw_log.file_hash is not None
        assert len(raw_log.file_hash) == 64


class TestCascadeDeletes:
    """Tests for cascade delete behavior."""

    def test_delete_conversation_cascades(
        self,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        sample_message: Message,
    ):
        """Test that deleting a conversation cascades to related records."""
        conversation_id = sample_conversation.id
        epoch_id = sample_epoch.id
        message_id = sample_message.id

        # Delete conversation
        db_session.delete(sample_conversation)
        db_session.commit()

        # Verify cascading deletes
        assert (
            db_session.query(Conversation).filter_by(id=conversation_id).first() is None
        )
        assert db_session.query(Epoch).filter_by(id=epoch_id).first() is None
        assert db_session.query(Message).filter_by(id=message_id).first() is None

    def test_delete_project_with_conversations(
        self,
        db_session: Session,
        sample_project: Project,
        sample_conversation: Conversation,
    ):
        """Test that deleting a project cascades to conversations."""
        project_id = sample_project.id
        conversation_id = sample_conversation.id

        db_session.delete(sample_project)
        db_session.commit()

        assert db_session.query(Project).filter_by(id=project_id).first() is None
        assert (
            db_session.query(Conversation).filter_by(id=conversation_id).first() is None
        )
