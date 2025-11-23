"""
Tests for Project API routes.

Tests the /projects endpoints including list, stats, sessions, and file aggregations.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, MessageRepository
from catsyphon.models.db import (
    Conversation,
    Developer,
    Epoch,
    FileTouched,
    Project,
)


def create_file_touched(
    db_session: Session,
    conversation: Conversation,
    file_path: str,
    lines_added: int = 0,
    lines_deleted: int = 0,
    timestamp: datetime | None = None,
) -> FileTouched:
    """Helper to create a FileTouched object with all required fields."""
    if timestamp is None:
        timestamp = datetime.now(UTC)

    # Create epoch for the file
    epoch = Epoch(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        sequence=0,
        start_time=timestamp,
    )
    db_session.add(epoch)
    db_session.commit()

    # Create file
    file = FileTouched(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        epoch_id=epoch.id,
        file_path=file_path,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        timestamp=timestamp,
    )
    db_session.add(file)
    db_session.commit()

    return file


class TestListProjects:
    """Tests for GET /projects endpoint."""

    def test_list_projects_empty(self, api_client: TestClient, db_session: Session):
        """Test listing projects when database is empty."""
        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        assert data == []

    def test_list_projects_basic(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test listing projects returns basic project data with session counts."""
        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 1

        # Check structure of first project
        proj = data[0]
        assert "id" in proj
        assert "name" in proj
        assert "directory_path" in proj
        assert "session_count" in proj
        assert "last_session_at" in proj
        assert "created_at" in proj
        assert "updated_at" in proj

    def test_list_projects_includes_session_counts(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that project list includes accurate session counts."""
        conv_repo = ConversationRepository(db_session)

        # Create 3 conversations for the project
        for i in range(3):
            conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC) - timedelta(minutes=i),
            )

        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        # Find our sample project
        proj = next(p for p in data if p["id"] == str(sample_project.id))

        # Should have session_count = 3
        assert proj["session_count"] == 3
        assert proj["last_session_at"] is not None

    def test_list_projects_multiple_projects(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_developer: Developer,
    ):
        """Test listing multiple projects with different session counts."""
        # Create multiple projects
        project1 = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Project 1",
            directory_path="/path/to/project1",
        )
        project2 = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Project 2",
            directory_path="/path/to/project2",
        )
        db_session.add_all([project1, project2])
        db_session.commit()

        conv_repo = ConversationRepository(db_session)

        # Project 1: 2 conversations
        for _ in range(2):
            conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=project1.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC),
            )

        # Project 2: 1 conversation
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=project2.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        proj1 = next(p for p in data if p["id"] == str(project1.id))
        proj2 = next(p for p in data if p["id"] == str(project2.id))

        assert proj1["session_count"] == 2
        assert proj2["session_count"] == 1


class TestGetProjectStats:
    """Tests for GET /projects/{id}/stats endpoint."""

    def test_get_project_stats_not_found(
        self, api_client: TestClient, db_session: Session
    ):
        """Test getting stats for non-existent project returns 404."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/projects/{fake_id}/stats")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_project_stats_empty_project(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test getting stats for project with no conversations."""
        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == str(sample_project.id)
        assert data["session_count"] == 0
        assert data["total_messages"] == 0
        assert data["total_files_changed"] == 0
        assert data["success_rate"] is None
        assert data["avg_session_duration_seconds"] is None
        assert data["first_session_at"] is None
        assert data["last_session_at"] is None

    def test_get_project_stats_basic_metrics(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test project stats includes basic metrics."""
        conv_repo = ConversationRepository(db_session)

        # Create 3 conversations
        now = datetime.now(UTC)
        conversations = []
        for i in range(3):
            conv = conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=now - timedelta(hours=i * 2),
                end_time=now - timedelta(hours=i * 2 - 1),  # 1 hour duration
                success=True if i < 2 else False,
            )
            conversations.append(conv)

        # Add messages to first conversation
        epoch = Epoch(
            id=uuid.uuid4(),
            conversation_id=conversations[0].id,
            sequence=0,
            start_time=now,
        )
        db_session.add(epoch)
        db_session.commit()

        msg_repo = MessageRepository(db_session)
        for j in range(5):
            msg_repo.create_message(
                epoch_id=epoch.id,
                conversation_id=conversations[0].id,
                role="user" if j % 2 == 0 else "assistant",
                content=f"Message {j}",
                timestamp=now,
                sequence=j,
            )

        # Add files to conversations
        for conv in conversations[:2]:
            create_file_touched(
                db_session,
                conv,
                f"/path/to/file_{conv.id}.py",
                lines_added=10,
                lines_deleted=5,
                timestamp=now,
            )

        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["session_count"] == 3
        assert data["total_messages"] == 5
        assert data["total_files_changed"] == 2
        assert data["success_rate"] == pytest.approx(
            0.6667, rel=0.01
        )  # 2/3 success (as fraction)
        assert data["avg_session_duration_seconds"] == pytest.approx(
            3600.0, rel=0.1
        )  # 1 hour
        assert data["first_session_at"] is not None
        assert data["last_session_at"] is not None

    def test_get_project_stats_with_tags(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test project stats aggregates tags correctly."""
        conv_repo = ConversationRepository(db_session)

        # Create conversations with tags
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            tags={
                "features": ["authentication", "api"],
                "problems": ["slow queries"],
                "tools_used": ["Read", "Edit"],
            },
        )

        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            tags={
                "features": ["authentication", "ui"],
                "problems": ["slow queries", "memory leak"],
                "tools_used": ["Read", "Write"],
            },
        )

        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        # Check top features (authentication appears twice)
        assert "authentication" in data["top_features"]
        assert "api" in data["top_features"]
        assert "ui" in data["top_features"]

        # Check top problems (slow queries appears twice)
        assert "slow queries" in data["top_problems"]
        assert "memory leak" in data["top_problems"]

        # Check tool usage
        assert data["tool_usage"]["Read"] == 2
        assert data["tool_usage"]["Edit"] == 1
        assert data["tool_usage"]["Write"] == 1

    def test_get_project_stats_developer_participation(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test project stats includes developer participation."""
        # Create another developer
        other_dev = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="other_dev",
            email="other@example.com",
        )
        db_session.add(other_dev)
        db_session.commit()

        conv_repo = ConversationRepository(db_session)

        # Create conversations for both developers
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=other_dev.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["developer_count"] == 2
        assert sample_developer.username in data["developers"]
        assert other_dev.username in data["developers"]

    def test_get_project_stats_response_structure(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test project stats response has correct structure."""
        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "project_id",
            "session_count",
            "total_messages",
            "total_files_changed",
            "success_rate",
            "avg_session_duration_seconds",
            "first_session_at",
            "last_session_at",
            "top_features",
            "top_problems",
            "tool_usage",
            "developer_count",
            "developers",
            "sentiment_timeline",  # New in Epic 7
        ]

        for field in required_fields:
            assert field in data

    # ===== Epic 7: Date Range Filtering Tests =====

    def test_get_project_stats_date_range_7d(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test stats filtered to last 7 days."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversation from 5 days ago (should be included)
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now - timedelta(days=5),
        )

        # Create conversation from 10 days ago (should be excluded)
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now - timedelta(days=10),
        )

        response = api_client.get(f"/projects/{sample_project.id}/stats?date_range=7d")

        assert response.status_code == 200
        data = response.json()

        # Should only count the recent conversation
        assert data["session_count"] == 1

    def test_get_project_stats_date_range_30d(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test stats filtered to last 30 days."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations at different times
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now - timedelta(days=20),
        )

        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now - timedelta(days=40),
        )

        response = api_client.get(f"/projects/{sample_project.id}/stats?date_range=30d")

        assert response.status_code == 200
        data = response.json()

        # Should only count conversation within 30 days
        assert data["session_count"] == 1

    def test_get_project_stats_date_range_all(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test stats with no date filtering (all time)."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations at various times
        for days_ago in [5, 50, 200]:
            conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=now - timedelta(days=days_ago),
            )

        response = api_client.get(f"/projects/{sample_project.id}/stats?date_range=all")

        assert response.status_code == 200
        data = response.json()

        # Should count all conversations
        assert data["session_count"] == 3

    # ===== Epic 7: Sentiment Timeline Tests =====

    def test_get_project_stats_sentiment_timeline_structure(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test sentiment_timeline has correct structure."""
        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert "sentiment_timeline" in data
        assert isinstance(data["sentiment_timeline"], list)

    def test_get_project_stats_sentiment_timeline_empty(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test sentiment_timeline is empty for project with no sessions."""
        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["sentiment_timeline"] == []

    def test_get_project_stats_sentiment_timeline_with_data(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test sentiment_timeline aggregates sentiment scores by date."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversation with epoch that has sentiment
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now - timedelta(days=2),
        )

        # Create epochs with sentiment scores
        epoch1 = Epoch(
            id=uuid.uuid4(),
            conversation_id=conv1.id,
            sequence=0,
            start_time=now - timedelta(days=2),
            sentiment_score=0.8,
        )
        db_session.add(epoch1)

        epoch2 = Epoch(
            id=uuid.uuid4(),
            conversation_id=conv1.id,
            sequence=1,
            start_time=now - timedelta(days=2),
            sentiment_score=0.6,
        )
        db_session.add(epoch2)
        db_session.commit()

        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        assert len(data["sentiment_timeline"]) > 0

        # Check structure of timeline points
        point = data["sentiment_timeline"][0]
        assert "date" in point
        assert "avg_sentiment" in point
        assert "session_count" in point

        # Should average the two sentiment scores
        assert point["avg_sentiment"] == pytest.approx(0.7, rel=0.01)
        assert point["session_count"] == 1

    def test_get_project_stats_sentiment_timeline_multiple_days(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test sentiment_timeline aggregates across multiple days."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations on different days
        for days_ago in [1, 2, 3]:
            conv = conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=now - timedelta(days=days_ago),
            )

            epoch = Epoch(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                sequence=0,
                start_time=now - timedelta(days=days_ago),
                sentiment_score=0.5 + (days_ago * 0.1),  # Different sentiments
            )
            db_session.add(epoch)

        db_session.commit()

        response = api_client.get(f"/projects/{sample_project.id}/stats")

        assert response.status_code == 200
        data = response.json()

        # Should have 3 separate date points
        assert len(data["sentiment_timeline"]) == 3

        # Timeline should be sorted by date
        dates = [point["date"] for point in data["sentiment_timeline"]]
        assert dates == sorted(dates)


class TestListProjectSessions:
    """Tests for GET /projects/{id}/sessions endpoint."""

    def test_list_project_sessions_not_found(
        self, api_client: TestClient, db_session: Session
    ):
        """Test listing sessions for non-existent project returns 404."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/projects/{fake_id}/sessions")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_project_sessions_empty(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test listing sessions for project with no conversations."""
        response = api_client.get(f"/projects/{sample_project.id}/sessions")

        assert response.status_code == 200
        data = response.json()

        assert data == []

    def test_list_project_sessions_basic(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test listing sessions returns correct data."""
        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        conv = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
            end_time=now + timedelta(hours=1),
            status="completed",
            success=True,
            message_count=10,
            files_count=3,
        )

        response = api_client.get(f"/projects/{sample_project.id}/sessions")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        session = data[0]

        assert session["id"] == str(conv.id)
        assert session["agent_type"] == "claude-code"
        assert session["status"] == "completed"
        assert session["success"] is True
        assert session["message_count"] == 10
        assert session["files_count"] == 3
        assert session["developer"] == sample_developer.username
        assert session["duration_seconds"] == 3600

    def test_list_project_sessions_pagination(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test session list pagination."""
        conv_repo = ConversationRepository(db_session)

        # Create 25 conversations
        for i in range(25):
            conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC) - timedelta(minutes=i),
            )

        # Get first page (default page_size=20)
        response1 = api_client.get(
            f"/projects/{sample_project.id}/sessions?page=1&page_size=10"
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1) == 10

        # Get second page
        response2 = api_client.get(
            f"/projects/{sample_project.id}/sessions?page=2&page_size=10"
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) == 10

        # Pages should have different sessions
        ids1 = {s["id"] for s in data1}
        ids2 = {s["id"] for s in data2}
        assert len(ids1 & ids2) == 0

    def test_list_project_sessions_sorted_by_start_time(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test sessions are sorted by start_time descending (newest first)."""
        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        times = []
        for i in [2, 0, 1]:  # Create out of order
            start_time = now - timedelta(hours=i)
            times.append(start_time)
            conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=start_time,
            )

        response = api_client.get(f"/projects/{sample_project.id}/sessions")

        assert response.status_code == 200
        data = response.json()

        # Should be sorted newest first
        start_times = [s["start_time"] for s in data]
        assert start_times == sorted(start_times, reverse=True)

    def test_list_project_sessions_only_for_project(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that only sessions for specified project are returned."""
        # Create another project
        other_project = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Other Project",
            directory_path="/other/path",
        )
        db_session.add(other_project)
        db_session.commit()

        conv_repo = ConversationRepository(db_session)

        # Create conversation for sample_project
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        # Create conversation for other_project
        conv2 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=other_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        response = api_client.get(f"/projects/{sample_project.id}/sessions")

        assert response.status_code == 200
        data = response.json()

        session_ids = [s["id"] for s in data]
        assert str(conv1.id) in session_ids
        assert str(conv2.id) not in session_ids

    # ===== Epic 7: Session Filtering Tests =====

    def test_list_project_sessions_filter_by_developer(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering sessions by developer."""
        # Create another developer
        other_dev = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="other_dev",
            email="other@example.com",
        )
        db_session.add(other_dev)
        db_session.commit()

        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations for both developers
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
        )

        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=other_dev.id,
            agent_type="claude-code",
            start_time=now,
        )

        # Filter by sample_developer
        response = api_client.get(
            f"/projects/{sample_project.id}/sessions?developer={sample_developer.username}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return conv1
        assert len(data) == 1
        assert data[0]["id"] == str(conv1.id)
        assert data[0]["developer"] == sample_developer.username

    def test_list_project_sessions_filter_by_outcome(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering sessions by outcome (success)."""
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversations with different outcomes
        conv_success = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
            success=True,
        )

        conv_failed = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
            success=False,
        )

        # Filter by success
        response = api_client.get(
            f"/projects/{sample_project.id}/sessions?outcome=success"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return successful conversation
        assert len(data) == 1
        assert data[0]["id"] == str(conv_success.id)
        assert data[0]["success"] is True

        # Filter by failed
        response = api_client.get(
            f"/projects/{sample_project.id}/sessions?outcome=failed"
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["id"] == str(conv_failed.id)
        assert data[0]["success"] is False

    def test_list_project_sessions_filter_combined(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test combining multiple filters."""
        # Create another developer
        other_dev = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="other_dev",
            email="other@example.com",
        )
        db_session.add(other_dev)
        db_session.commit()

        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create various conversations
        # Match: sample_developer + success
        match = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
            success=True,
        )

        # No match: other_dev + success
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=other_dev.id,
            agent_type="claude-code",
            start_time=now,
            success=True,
        )

        # No match: sample_developer + failed
        conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
            success=False,
        )

        # Filter by both developer and outcome
        response = api_client.get(
            f"/projects/{sample_project.id}/sessions?developer={sample_developer.username}&outcome=success"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return the matching conversation
        assert len(data) == 1
        assert data[0]["id"] == str(match.id)


class TestGetProjectFiles:
    """Tests for GET /projects/{id}/files endpoint."""

    def test_get_project_files_not_found(
        self, api_client: TestClient, db_session: Session
    ):
        """Test getting files for non-existent project returns 404."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/projects/{fake_id}/files")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_project_files_empty(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test getting files for project with no files touched."""
        response = api_client.get(f"/projects/{sample_project.id}/files")

        assert response.status_code == 200
        data = response.json()

        assert data == []

    def test_get_project_files_basic(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test getting project files returns aggregated data."""
        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        conv = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
        )

        # Add files
        create_file_touched(
            db_session,
            conv,
            "/path/to/file1.py",
            lines_added=100,
            lines_deleted=20,
            timestamp=now,
        )
        create_file_touched(
            db_session,
            conv,
            "/path/to/file2.py",
            lines_added=50,
            lines_deleted=10,
            timestamp=now,
        )

        response = api_client.get(f"/projects/{sample_project.id}/files")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2

        # Check structure
        file = data[0]
        assert "file_path" in file
        assert "modification_count" in file
        assert "total_lines_added" in file
        assert "total_lines_deleted" in file
        assert "last_modified_at" in file
        assert "session_ids" in file

    def test_get_project_files_aggregation(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test file aggregation across multiple sessions."""
        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)

        # Create 2 conversations
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
        )

        conv2 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now + timedelta(hours=1),
        )

        # Same file modified in both conversations
        create_file_touched(
            db_session,
            conv1,
            "/path/to/common.py",
            lines_added=50,
            lines_deleted=10,
            timestamp=now,
        )
        create_file_touched(
            db_session,
            conv2,
            "/path/to/common.py",
            lines_added=30,
            lines_deleted=5,
            timestamp=now + timedelta(hours=1),
        )

        response = api_client.get(f"/projects/{sample_project.id}/files")

        assert response.status_code == 200
        data = response.json()

        # Should have 1 file with aggregated data
        assert len(data) == 1
        file = data[0]

        assert file["file_path"] == "/path/to/common.py"
        assert file["modification_count"] == 2
        assert file["total_lines_added"] == 80  # 50 + 30
        assert file["total_lines_deleted"] == 15  # 10 + 5
        assert len(file["session_ids"]) == 2
        assert str(conv1.id) in file["session_ids"]
        assert str(conv2.id) in file["session_ids"]

    def test_get_project_files_sorted_by_modification_count(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test files are sorted by modification count descending."""
        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)

        # Create 3 conversations
        convs = []
        for i in range(3):
            conv = conv_repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=now + timedelta(hours=i),
            )
            convs.append(conv)

        # file1: modified in all 3 conversations
        # file2: modified in 2 conversations
        # file3: modified in 1 conversation

        for conv in convs:
            create_file_touched(
                db_session,
                conv,
                "/path/to/file1.py",
                lines_added=10,
                lines_deleted=5,
                timestamp=now,
            )

        for conv in convs[:2]:
            create_file_touched(
                db_session,
                conv,
                "/path/to/file2.py",
                lines_added=10,
                lines_deleted=5,
                timestamp=now,
            )

        create_file_touched(
            db_session,
            convs[0],
            "/path/to/file3.py",
            lines_added=10,
            lines_deleted=5,
            timestamp=now,
        )

        response = api_client.get(f"/projects/{sample_project.id}/files")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 3

        # Should be sorted by modification_count descending
        assert data[0]["file_path"] == "/path/to/file1.py"
        assert data[0]["modification_count"] == 3
        assert data[1]["file_path"] == "/path/to/file2.py"
        assert data[1]["modification_count"] == 2
        assert data[2]["file_path"] == "/path/to/file3.py"
        assert data[2]["modification_count"] == 1

    def test_get_project_files_only_for_project(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test that only files from specified project are returned."""
        # Create another project
        other_project = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Other Project",
            directory_path="/other/path",
        )
        db_session.add(other_project)
        db_session.commit()

        conv_repo = ConversationRepository(db_session)

        now = datetime.now(UTC)

        # Create conversations for both projects
        conv1 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
        )

        conv2 = conv_repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=other_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=now,
        )

        # Add files to both
        create_file_touched(
            db_session,
            conv1,
            "/path/to/project1_file.py",
            lines_added=10,
            lines_deleted=5,
            timestamp=now,
        )
        create_file_touched(
            db_session,
            conv2,
            "/path/to/project2_file.py",
            lines_added=10,
            lines_deleted=5,
            timestamp=now,
        )

        response = api_client.get(f"/projects/{sample_project.id}/files")

        assert response.status_code == 200
        data = response.json()

        file_paths = [f["file_path"] for f in data]
        assert "/path/to/project1_file.py" in file_paths
        assert "/path/to/project2_file.py" not in file_paths
