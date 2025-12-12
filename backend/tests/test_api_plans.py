"""Tests for Plan API endpoints."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from catsyphon.models.db import (
    Conversation,
    Epoch,
    Message,
    Project,
    Workspace,
)


@pytest.fixture
def conversation_with_plans(
    db_session: Session,
    sample_workspace: Workspace,
) -> Conversation:
    """Create a conversation with plan data in extra_data."""
    # Create a project first
    project = Project(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        name="Test Project",
        directory_path="/Users/test/project",
    )
    db_session.add(project)
    db_session.commit()

    # Create conversation with plan data
    conversation = Conversation(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        project_id=project.id,
        agent_type="claude-code",
        agent_version="2.0.28",
        start_time=datetime.now(UTC),
        status="completed",
        success=True,
        extra_data={
            "session_id": "test-session-001",
            "plans": [
                {
                    "plan_file_path": "/Users/test/.claude/plans/test-plan.md",
                    "initial_content": "# Initial Plan\n\n1. Step one",
                    "final_content": "# Final Plan\n\n1. Step one\n2. Step two",
                    "status": "approved",
                    "iteration_count": 2,
                    "operations": [
                        {
                            "operation_type": "create",
                            "file_path": "/Users/test/.claude/plans/test-plan.md",
                            "content": "# Initial Plan\n\n1. Step one",
                            "timestamp": "2025-01-15T10:00:00.000Z",
                            "message_index": 1,
                        },
                        {
                            "operation_type": "edit",
                            "file_path": "/Users/test/.claude/plans/test-plan.md",
                            "old_content": "1. Step one",
                            "new_content": "1. Step one\n2. Step two",
                            "timestamp": "2025-01-15T10:01:00.000Z",
                            "message_index": 3,
                        },
                    ],
                    "entry_message_index": 0,
                    "exit_message_index": 4,
                    "related_agent_session_ids": [],
                }
            ],
        },
    )
    db_session.add(conversation)

    # Add an epoch
    epoch = Epoch(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        sequence=1,
        start_time=datetime.now(UTC),
    )
    db_session.add(epoch)

    # Add a message
    message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        epoch_id=epoch.id,
        role="user",
        content="Test message",
        timestamp=datetime.now(UTC),
        sequence=1,
    )
    db_session.add(message)

    db_session.commit()
    db_session.refresh(conversation)
    return conversation


@pytest.fixture
def conversation_without_plans(
    db_session: Session,
    sample_workspace: Workspace,
) -> Conversation:
    """Create a conversation without plan data."""
    conversation = Conversation(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        agent_type="claude-code",
        agent_version="2.0.28",
        start_time=datetime.now(UTC),
        status="completed",
        success=True,
        extra_data={
            "session_id": "test-session-002",
        },
    )
    db_session.add(conversation)

    # Add an epoch
    epoch = Epoch(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        sequence=1,
        start_time=datetime.now(UTC),
    )
    db_session.add(epoch)

    db_session.commit()
    db_session.refresh(conversation)
    return conversation


class TestListPlans:
    """Tests for GET /plans endpoint."""

    def test_list_plans_empty(self, api_client, sample_workspace):
        """Test listing plans when no conversations have plans."""
        response = api_client.get("/plans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1

    def test_list_plans_with_data(self, api_client, conversation_with_plans):
        """Test listing plans when conversations have plans."""
        response = api_client.get("/plans")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

        plan = data["items"][0]
        assert plan["plan_file_path"] == "/Users/test/.claude/plans/test-plan.md"
        assert plan["status"] == "approved"
        assert plan["iteration_count"] == 2
        assert plan["conversation_id"] == str(conversation_with_plans.id)

    def test_list_plans_filter_by_status(
        self, api_client, conversation_with_plans, conversation_without_plans
    ):
        """Test filtering plans by status."""
        # Filter for approved plans
        response = api_client.get("/plans?status=approved")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Filter for active plans (should find none)
        response = api_client.get("/plans?status=active")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_plans_pagination(self, api_client, conversation_with_plans):
        """Test pagination parameters."""
        response = api_client.get("/plans?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestGetPlanDetail:
    """Tests for GET /plans/detail/{conversation_id}/{plan_index} endpoint."""

    def test_get_plan_detail(self, api_client, conversation_with_plans):
        """Test getting detailed plan information."""
        conv_id = conversation_with_plans.id
        response = api_client.get(f"/plans/detail/{conv_id}/0")
        assert response.status_code == 200

        data = response.json()
        assert data["plan_file_path"] == "/Users/test/.claude/plans/test-plan.md"
        assert data["initial_content"] == "# Initial Plan\n\n1. Step one"
        assert data["final_content"] == "# Final Plan\n\n1. Step one\n2. Step two"
        assert data["status"] == "approved"
        assert data["iteration_count"] == 2
        assert len(data["operations"]) == 2
        assert data["entry_message_index"] == 0
        assert data["exit_message_index"] == 4
        assert data["conversation_id"] == str(conv_id)

    def test_get_plan_detail_not_found_conversation(self, api_client, sample_workspace):
        """Test getting plan from non-existent conversation."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/plans/detail/{fake_id}/0")
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    def test_get_plan_detail_invalid_index(self, api_client, conversation_with_plans):
        """Test getting plan with invalid index."""
        conv_id = conversation_with_plans.id
        response = api_client.get(f"/plans/detail/{conv_id}/99")
        assert response.status_code == 404
        assert "Plan index" in response.json()["detail"]

    def test_get_plan_detail_no_plans(self, api_client, conversation_without_plans):
        """Test getting plan from conversation without plans."""
        conv_id = conversation_without_plans.id
        response = api_client.get(f"/plans/detail/{conv_id}/0")
        assert response.status_code == 404


class TestGetPlansForConversation:
    """Tests for GET /plans/conversation/{conversation_id} endpoint."""

    def test_get_plans_for_conversation(self, api_client, conversation_with_plans):
        """Test getting all plans for a specific conversation."""
        conv_id = conversation_with_plans.id
        response = api_client.get(f"/plans/conversation/{conv_id}")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["plan_file_path"] == "/Users/test/.claude/plans/test-plan.md"

    def test_get_plans_for_conversation_empty(
        self, api_client, conversation_without_plans
    ):
        """Test getting plans for conversation without plans."""
        conv_id = conversation_without_plans.id
        response = api_client.get(f"/plans/conversation/{conv_id}")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_plans_for_conversation_not_found(self, api_client, sample_workspace):
        """Test getting plans for non-existent conversation."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/plans/conversation/{fake_id}")
        assert response.status_code == 404


class TestConversationDetailWithPlans:
    """Tests for plan data in conversation detail endpoint."""

    def test_conversation_detail_includes_plans(
        self, api_client, conversation_with_plans
    ):
        """Test that GET /conversations/{id} includes plan data."""
        conv_id = conversation_with_plans.id
        response = api_client.get(f"/conversations/{conv_id}")
        assert response.status_code == 200

        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) == 1

        plan = data["plans"][0]
        assert plan["plan_file_path"] == "/Users/test/.claude/plans/test-plan.md"
        assert plan["status"] == "approved"

    def test_conversation_detail_no_plans(self, api_client, conversation_without_plans):
        """Test that conversation without plans has empty plans array."""
        conv_id = conversation_without_plans.id
        response = api_client.get(f"/conversations/{conv_id}")
        assert response.status_code == 200

        data = response.json()
        assert "plans" in data
        assert data["plans"] == []
