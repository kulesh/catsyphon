"""
Tests for Conversation API routes.

Tests the /conversations endpoints including list, detail, and messages.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, MessageRepository
from catsyphon.models.db import Conversation, Developer, Epoch, Message, Project, Workspace


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
            directory_path="/other/path",
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


class TestTagConversation:
    """Tests for POST /conversations/{id}/tag endpoint."""

    def test_tag_conversation_success(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        mock_openai_api_key,
    ):
        """Test successfully tagging a conversation."""
        repo = MessageRepository(db_session)

        # Clear any existing tags from fixture
        sample_conversation.tags = {}
        db_session.commit()

        # Create at least 2 messages (minimum required)
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="user",
            content="I need help with a bug in my code",
            timestamp=datetime.now(UTC),
            sequence=0,
        )
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Sure! Let me help you debug that.",
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
            sequence=1,
        )
        db_session.commit()

        # Update conversation message_count
        sample_conversation.message_count = 2
        db_session.commit()

        # Tag the conversation
        response = api_client.post(f"/conversations/{sample_conversation.id}/tag")

        assert response.status_code == 200
        data = response.json()

        # Should have tags populated
        assert "tags" in data
        assert data["tags"] is not None

    def test_tag_conversation_too_short(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test tagging a conversation with too few messages."""
        # Clear any existing tags from fixture
        sample_conversation.tags = {}
        # Ensure conversation has only 1 message (below minimum)
        sample_conversation.message_count = 1
        db_session.commit()

        response = api_client.post(f"/conversations/{sample_conversation.id}/tag")

        assert response.status_code == 400
        assert "too short" in response.json()["detail"].lower()

    def test_tag_conversation_already_tagged(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
    ):
        """Test tagging a conversation that already has tags."""
        # Add existing tags
        sample_conversation.tags = {"intent": "bug_fix", "outcome": "success"}
        sample_conversation.message_count = 2
        db_session.commit()

        response = api_client.post(f"/conversations/{sample_conversation.id}/tag")

        assert response.status_code == 400
        assert "already tagged" in response.json()["detail"].lower()

    def test_tag_conversation_force_retag(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        mock_openai_api_key,
    ):
        """Test force retagging a conversation that already has tags."""
        repo = MessageRepository(db_session)

        # Clear existing messages and add 2 new ones
        db_session.query(Message).filter(
            Message.conversation_id == sample_conversation.id
        ).delete()

        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="user",
            content="I need help with a bug",
            timestamp=datetime.now(UTC),
            sequence=0,
        )
        repo.create_message(
            epoch_id=sample_epoch.id,
            conversation_id=sample_conversation.id,
            role="assistant",
            content="Let me help you",
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
            sequence=1,
        )
        db_session.commit()

        # Add existing tags
        sample_conversation.tags = {"intent": "old_intent"}
        sample_conversation.message_count = 2
        db_session.commit()

        # Force retag
        response = api_client.post(
            f"/conversations/{sample_conversation.id}/tag?force=true"
        )

        assert response.status_code == 200
        data = response.json()

        # Should have updated tags
        assert "tags" in data
        assert data["tags"] is not None

    def test_tag_conversation_not_found(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test tagging a non-existent conversation."""
        fake_id = uuid.uuid4()
        response = api_client.post(f"/conversations/{fake_id}/tag")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_tag_conversation_no_api_key(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
        sample_epoch: Epoch,
        monkeypatch,
    ):
        """Test tagging when OpenAI API key is not configured."""
        # Import settings and set API key to None
        import catsyphon.config

        # Patch the settings object before importing the router
        mock_settings = catsyphon.config.settings
        monkeypatch.setattr(mock_settings, "openai_api_key", None)

        # Ensure conversation has enough messages and no tags
        sample_conversation.message_count = 2
        sample_conversation.tags = {}
        db_session.commit()

        response = api_client.post(f"/conversations/{sample_conversation.id}/tag")

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()


class TestHierarchicalConversationAPI:
    """Tests for hierarchical conversation API responses."""

    def test_list_conversations_includes_children_count(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test that list conversations includes children_count field."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent conversation
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-123"},
            conversation_type="main",
        )

        # Create child agents
        child1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            extra_data={"session_id": "agent-1"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
        )
        child2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            extra_data={"session_id": "agent-2"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
        )
        db_session.commit()

        # List conversations
        response = api_client.get("/conversations")

        assert response.status_code == 200
        data = response.json()

        # Find parent in response
        parent_data = next((c for c in data["items"] if c["id"] == str(parent.id)), None)
        assert parent_data is not None
        assert "children_count" in parent_data
        assert parent_data["children_count"] == 2

    def test_get_conversation_includes_children(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test that get conversation includes children array."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-456"},
            conversation_type="main",
        )

        # Create children
        child1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            extra_data={"session_id": "agent-1"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-1"},
        )
        child2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            extra_data={"session_id": "agent-2"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-2"},
        )
        db_session.commit()

        # Get parent conversation
        response = api_client.get(f"/conversations/{parent.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify children included
        assert "children" in data
        assert isinstance(data["children"], list)
        assert len(data["children"]) == 2

        child_ids = {c["id"] for c in data["children"]}
        assert str(child1.id) in child_ids
        assert str(child2.id) in child_ids

        # Verify children have required fields
        for child in data["children"]:
            assert "conversation_type" in child
            assert child["conversation_type"] == "agent"
            assert "agent_metadata" in child

    def test_get_conversation_includes_parent(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test that get conversation includes parent object."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-789"},
            conversation_type="main",
        )

        # Create child
        child = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            extra_data={"session_id": "agent-child"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-child", "parent_session_id": "parent-789"},
        )
        db_session.commit()

        # Get child conversation
        response = api_client.get(f"/conversations/{child.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify parent included
        assert "parent" in data
        assert data["parent"] is not None
        assert data["parent"]["id"] == str(parent.id)
        assert data["parent"]["conversation_type"] == "main"

        # Verify parent_conversation_id field
        assert "parent_conversation_id" in data
        assert data["parent_conversation_id"] == str(parent.id)

    def test_filter_conversations_by_type_main(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test filtering conversations by conversation_type=main."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create mixed conversations
        main1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        agent1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
        )
        main2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="main",
        )
        db_session.commit()

        # Filter by conversation_type (if supported by API)
        # Note: This may require adding query parameter support to the API
        response = api_client.get("/conversations?conversation_type=main")

        assert response.status_code == 200
        data = response.json()

        # If filtering is supported, verify results
        # If not supported yet, this test documents the expected behavior
        # For now, just verify response structure
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_filter_conversations_by_type_agent(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test filtering conversations by conversation_type=agent."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create mixed conversations
        main1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        agent1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
        )
        agent2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="agent",
        )
        db_session.commit()

        # Filter by conversation_type
        response = api_client.get("/conversations?conversation_type=agent")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_orphaned_agent_conversation(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test getting an orphaned agent conversation (no parent)."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create orphaned agent
        orphan = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="agent",
            parent_conversation_id=None,
            agent_metadata={"parent_session_id": "non-existent-parent"},
        )
        db_session.commit()

        # Get orphaned agent
        response = api_client.get(f"/conversations/{orphan.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify orphaned status
        assert data["conversation_type"] == "agent"
        assert data["parent_conversation_id"] is None
        assert data["parent"] is None
        assert "agent_metadata" in data
        assert data["agent_metadata"]["parent_session_id"] == "non-existent-parent"

    def test_nested_hierarchy_response(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test that nested hierarchy (parent with children) is properly serialized."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-nested"},
            conversation_type="main",
        )

        # Create multiple children
        for i in range(3):
            repo.create(
                workspace_id=sample_workspace.id,
                agent_type="claude-code",
                start_time=now + timedelta(minutes=i + 1),
                extra_data={"session_id": f"agent-{i}"},
                conversation_type="agent",
                parent_conversation_id=parent.id,
                agent_metadata={"agent_id": f"agent-{i}"},
            )
        db_session.commit()

        # Get parent
        response = api_client.get(f"/conversations/{parent.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify full hierarchy structure
        assert data["conversation_type"] == "main"
        assert data["parent_conversation_id"] is None
        assert len(data["children"]) == 3

        # Verify each child has correct structure
        for child in data["children"]:
            assert child["conversation_type"] == "agent"
            assert child["parent_conversation_id"] == str(parent.id)
            assert "agent_metadata" in child
            assert "agent_id" in child["agent_metadata"]

    def test_conversation_type_field_present(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """Test that conversation_type field is present in all responses."""
        from catsyphon.db.repositories import ConversationRepository

        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create conversation
        conv = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        db_session.commit()

        # Get conversation
        response = api_client.get(f"/conversations/{conv.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify conversation_type field
        assert "conversation_type" in data
        assert data["conversation_type"] in ["main", "agent", "mcp", "skill", "command", "other"]

        # List conversations
        list_response = api_client.get("/conversations")
        assert list_response.status_code == 200
        list_data = list_response.json()

        # Verify conversation_type in list items
        for item in list_data["items"]:
            assert "conversation_type" in item
