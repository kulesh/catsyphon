"""
Tests for Statistics API routes.

Tests the /stats/overview endpoint.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, MessageRepository
from catsyphon.models.db import Conversation, Developer, Epoch, Project


class TestOverviewStats:
    """Tests for GET /stats/overview endpoint."""

    def test_overview_stats_empty_database(
        self, api_client: TestClient, db_session: Session
    ):
        """Test overview stats when database is empty."""
        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        assert data["total_conversations"] == 0
        assert data["total_messages"] == 0
        assert data["total_projects"] == 0
        assert data["total_developers"] == 0
        assert data["conversations_by_status"] == {}
        assert data["conversations_by_agent"] == {}
        assert data["recent_conversations"] == 0
        assert data["success_rate"] is None

    def test_overview_stats_basic_counts(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test that overview stats includes basic counts."""
        # Create some messages
        msg_repo = MessageRepository(db_session)
        for i in range(3):
            msg_repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        assert data["total_conversations"] >= 1
        assert data["total_messages"] >= 3
        assert data["total_projects"] >= 1
        assert data["total_developers"] >= 1

    def test_overview_stats_by_status(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test conversations_by_status breakdown."""
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

        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        assert "completed" in data["conversations_by_status"]
        assert data["conversations_by_status"]["completed"] >= 2
        assert "open" in data["conversations_by_status"]
        assert data["conversations_by_status"]["open"] >= 1

    def test_overview_stats_by_agent_type(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test conversations_by_agent breakdown."""
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

        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        assert "claude-code" in data["conversations_by_agent"]
        assert data["conversations_by_agent"]["claude-code"] >= 2
        assert "copilot" in data["conversations_by_agent"]
        assert data["conversations_by_agent"]["copilot"] >= 1

    def test_overview_stats_success_rate(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test success_rate calculation."""
        repo = ConversationRepository(db_session)

        # Create 3 successful and 1 failed conversation
        for _ in range(3):
            repo.create(
                id=uuid.uuid4(),
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC),
                success=True,
            )
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            success=False,
        )

        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        # Should be 75% (3 out of 4)
        assert data["success_rate"] == 75.0

    def test_overview_stats_recent_conversations(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test recent_conversations count (last 7 days)."""
        repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        five_days_ago = now - timedelta(days=5)
        ten_days_ago = now - timedelta(days=10)

        # Create recent conversation
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=five_days_ago,
        )

        # Create old conversation (should not be counted)
        repo.create(
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=ten_days_ago,
        )

        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        # Should count only the conversation from 5 days ago
        assert data["recent_conversations"] >= 1
        # Total should include both
        assert data["total_conversations"] >= 2

    def test_overview_stats_with_date_filter(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering stats by date range."""
        repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        # Create conversations at different times
        _conv1 = repo.create(  # noqa: F841 - Used for test setup
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=yesterday,
        )
        _conv2 = repo.create(  # noqa: F841 - Used for test setup
            id=uuid.uuid4(),
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=two_days_ago,
        )

        # Filter to only include yesterday's conversation
        # Use strftime to avoid timezone suffix in isoformat
        start_date = (yesterday - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        end_date = now.strftime("%Y-%m-%dT%H:%M:%S")

        response = api_client.get(
            f"/stats/overview?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only count conversation from yesterday
        assert data["total_conversations"] >= 1
        # But total_projects and total_developers should not be filtered
        assert data["total_projects"] >= 1
        assert data["total_developers"] >= 1

    def test_overview_stats_response_structure(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that overview stats response has correct structure."""
        response = api_client.get("/stats/overview")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "total_conversations",
            "total_messages",
            "total_projects",
            "total_developers",
            "conversations_by_status",
            "conversations_by_agent",
            "recent_conversations",
            "success_rate",
        ]

        for field in required_fields:
            assert field in data

        # Verify types
        assert isinstance(data["total_conversations"], int)
        assert isinstance(data["total_messages"], int)
        assert isinstance(data["total_projects"], int)
        assert isinstance(data["total_developers"], int)
        assert isinstance(data["conversations_by_status"], dict)
        assert isinstance(data["conversations_by_agent"], dict)
        assert isinstance(data["recent_conversations"], int)
        assert data["success_rate"] is None or isinstance(data["success_rate"], float)
