"""
Tests for database repositories.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    ProjectRepository,
)
from catsyphon.models.db import Conversation, Developer, Project


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
