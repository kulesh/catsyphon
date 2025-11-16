"""
Tests for Conversation API routes.

Tests the /conversations endpoints including list, detail, and messages.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, MessageRepository
from catsyphon.models.db import Conversation, Developer, Epoch, Message, Project


class TestListConversations:
    """Tests for GET /conversations endpoint."""

    def test_list_conversations_empty(
        self, api_client: TestClient, db_session: Session
    ):
        """Test listing conversations when database is empty."""
        response = api_client.get("/conversations")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["pages"] == 0

    def test_list_conversations_basic(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
    ):
        """Test listing conversations returns basic conversation data."""
        response = api_client.get("/conversations")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 1
        assert len(data["items"]) >= 1

        # Check structure of first conversation
        conv = data["items"][0]
        assert "id" in conv
        assert "agent_type" in conv
        assert "start_time" in conv
        assert "message_count" in conv
        assert "epoch_count" in conv
        assert "files_count" in conv

    def test_list_conversations_includes_counts(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        sample_message: Message,
    ):
        """Test that conversation list includes accurate counts."""
        response = api_client.get("/conversations")

        assert response.status_code == 200
        data = response.json()

        # Find our sample conversation
        conv = next(c for c in data["items"] if c["id"] == str(sample_conversation.id))

        # Should have counts from SQL aggregation
        assert conv["message_count"] >= 1
        assert conv["epoch_count"] >= 1
        assert isinstance(conv["files_count"], int)

    def test_filter_by_project(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by project_id."""
        repo = ConversationRepository(db_session)

        # Create conversations for different projects
        other_project = Project(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Other Project",
        )
        db_session.add(other_project)
        db_session.commit()

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=other_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        response = api_client.get(f"/conversations?project_id={sample_project.id}")

        assert response.status_code == 200
        data = response.json()

        # Should only include conversations from sample_project
        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        assert str(conv2.id) not in conv_ids

    def test_filter_by_developer(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by developer_id."""
        repo = ConversationRepository(db_session)

        # Create another developer
        other_dev = Developer(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="other_dev",
            email="other@example.com",
        )
        db_session.add(other_dev)
        db_session.commit()

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=other_dev.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )

        response = api_client.get(f"/conversations?developer_id={sample_developer.id}")

        assert response.status_code == 200
        data = response.json()

        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        assert str(conv2.id) not in conv_ids

    def test_filter_by_agent_type(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by agent_type."""
        repo = ConversationRepository(db_session)

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="copilot",
            start_time=datetime.now(UTC),
        )

        response = api_client.get("/conversations?agent_type=claude")

        assert response.status_code == 200
        data = response.json()

        # Should match partial agent_type (ilike)
        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        # copilot should not match "claude"
        assert str(conv2.id) not in conv_ids

    def test_filter_by_status(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by status."""
        repo = ConversationRepository(db_session)

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            status="completed",
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            status="open",
        )

        response = api_client.get("/conversations?status=completed")

        assert response.status_code == 200
        data = response.json()

        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        assert str(conv2.id) not in conv_ids

    def test_filter_by_success(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by success status."""
        repo = ConversationRepository(db_session)

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            success=True,
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=datetime.now(UTC),
            success=False,
        )

        response = api_client.get("/conversations?success=true")

        assert response.status_code == 200
        data = response.json()

        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        assert str(conv2.id) not in conv_ids

    def test_filter_by_date_range(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test filtering conversations by date range."""
        repo = ConversationRepository(db_session)

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        conv1 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=yesterday,
        )
        conv2 = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            project_id=sample_project.id,
            developer_id=sample_developer.id,
            agent_type="claude-code",
            start_time=two_days_ago,
        )

        # Use URL-encoded ISO format without timezone suffix
        start_date = (yesterday - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        end_date = now.strftime("%Y-%m-%dT%H:%M:%S")

        response = api_client.get(
            f"/conversations?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()

        conv_ids = [c["id"] for c in data["items"]]
        assert str(conv1.id) in conv_ids
        assert str(conv2.id) not in conv_ids

    def test_pagination(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test pagination parameters."""
        repo = ConversationRepository(db_session)

        # Create 10 conversations
        for i in range(10):
            repo.create(
                id=uuid.uuid4(),
                workspace_id=sample_workspace.id,
                project_id=sample_project.id,
                developer_id=sample_developer.id,
                agent_type="claude-code",
                start_time=datetime.now(UTC) - timedelta(minutes=i),
            )

            # Get first page
            response1 = api_client.get("/conversations?page=1&page_size=5")
            data1 = response1.json()

            # Get second page
            response2 = api_client.get("/conversations?page=2&page_size=5")
            data2 = response2.json()

        assert data1["page"] == 1
        assert data1["page_size"] == 5
        assert len(data1["items"]) == 5

        assert data2["page"] == 2
        assert len(data2["items"]) == 5

        # Pages should have different conversations
        ids1 = {c["id"] for c in data1["items"]}
        ids2 = {c["id"] for c in data2["items"]}
        assert len(ids1 & ids2) == 0

    def test_invalid_date_format_returns_400(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that invalid date format returns 400 error."""
        response = api_client.get("/conversations?start_date=invalid-date")

        assert response.status_code == 400
        assert "Invalid start_date format" in response.json()["detail"]


class TestGetConversation:
    """Tests for GET /conversations/{id} endpoint."""

    def test_get_conversation_success(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
    ):
        """Test getting a conversation by ID."""
        response = api_client.get(f"/conversations/{sample_conversation.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(sample_conversation.id)
        assert data["agent_type"] == sample_conversation.agent_type

        # Should include relations
        assert "project" in data
        assert "developer" in data
        assert "messages" in data
        assert "epochs" in data
        assert "files_touched" in data
        assert "conversation_tags" in data

    def test_get_conversation_includes_messages(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        sample_message: Message,
    ):
        """Test that conversation detail includes messages."""
        response = api_client.get(f"/conversations/{sample_conversation.id}")

        assert response.status_code == 200
        data = response.json()

        assert len(data["messages"]) >= 1
        msg = data["messages"][0]
        assert "role" in msg
        assert "content" in msg
        assert "timestamp" in msg

    def test_get_nonexistent_conversation_returns_404(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that getting non-existent conversation returns 404."""
        fake_id = uuid.uuid4()

        response = api_client.get(f"/conversations/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_conversation_invalid_uuid_returns_422(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that invalid UUID format returns 422."""
        response = api_client.get("/conversations/not-a-uuid")

        assert response.status_code == 422


class TestGetConversationMessages:
    """Tests for GET /conversations/{id}/messages endpoint."""

    def test_get_messages_success(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test getting messages for a conversation."""
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

        response = api_client.get(f"/conversations/{sample_conversation.id}/messages")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 3
        assert all("role" in msg for msg in data)
        assert all("content" in msg for msg in data)

    def test_get_messages_pagination(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test message pagination."""
        repo = MessageRepository(db_session)

        # Create 10 messages
        for i in range(10):
            repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime.now(UTC),
                sequence=i,
            )

        response = api_client.get(
            f"/conversations/{sample_conversation.id}/messages?limit=5&offset=0"
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 5

    def test_get_messages_for_nonexistent_conversation_returns_404(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that getting messages for non-existent conversation returns 404."""
        fake_id = uuid.uuid4()

        response = api_client.get(f"/conversations/{fake_id}/messages")

        assert response.status_code == 404

    def test_get_messages_chronological_order(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test that messages are returned in chronological order."""
        repo = MessageRepository(db_session)

        # Create messages in reverse order
        timestamps = []
        for i in [2, 0, 1]:
            ts = datetime.now(UTC) + timedelta(seconds=i)
            timestamps.append(ts)
            repo.create_message(
                epoch_id=sample_epoch.id,
                conversation_id=sample_conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=ts,
                sequence=i,
            )

        response = api_client.get(f"/conversations/{sample_conversation.id}/messages")

        assert response.status_code == 200
        data = response.json()

        # Should be ordered by sequence (which corresponds to chronological order)
        sequences = [msg["sequence"] for msg in data]
        assert sequences == sorted(sequences)
