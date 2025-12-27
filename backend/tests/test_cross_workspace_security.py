"""
Cross-workspace security tests for Phase 1 multi-tenancy fixes.

These tests verify that users cannot access resources from other workspaces,
ensuring proper tenant isolation across all API endpoints.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    IngestionJobRepository,
    OrganizationRepository,
    ProjectRepository,
    WorkspaceRepository,
)
from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.models.db import (
    Conversation,
    Developer,
    IngestionJob,
    Organization,
    Project,
    WatchConfiguration,
    Workspace,
)


class TestCrossWorkspaceSecurity:
    """Tests to verify cross-workspace access is properly denied."""

    @pytest.fixture
    def other_workspace(self, db_session: Session) -> tuple[Organization, Workspace]:
        """Create a separate workspace for cross-workspace testing."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(
            name=f"Other Org {unique_id}",
            slug=f"other-org-{unique_id}",
        )
        workspace = ws_repo.create(
            name=f"Other Workspace {unique_id}",
            slug=f"other-workspace-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace

    @pytest.fixture
    def other_project(
        self, db_session: Session, other_workspace: tuple[Organization, Workspace]
    ) -> Project:
        """Create a project in the other workspace."""
        _, workspace = other_workspace
        project_repo = ProjectRepository(db_session)

        project = project_repo.create(
            name="Other Project",
            directory_path="/other/project/path",
            workspace_id=workspace.id,
        )
        db_session.commit()
        return project

    @pytest.fixture
    def other_developer(
        self, db_session: Session, other_workspace: tuple[Organization, Workspace]
    ) -> Developer:
        """Create a developer in the other workspace."""
        _, workspace = other_workspace
        developer = Developer(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            username="other_developer",
            email="other@example.com",
        )
        db_session.add(developer)
        db_session.commit()
        return developer

    @pytest.fixture
    def other_conversation(
        self,
        db_session: Session,
        other_workspace: tuple[Organization, Workspace],
        other_project: Project,
        other_developer: Developer,
    ) -> Conversation:
        """Create a conversation in the other workspace."""
        from datetime import UTC, datetime

        _, workspace = other_workspace
        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=other_project.id,
            developer_id=other_developer.id,
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=datetime.now(UTC),
            status="completed",
            extra_data={"session_id": f"other-session-{uuid.uuid4()}"},
            message_count=0,
            epoch_count=0,
            files_count=0,
        )
        db_session.add(conversation)
        db_session.commit()
        return conversation

    @pytest.fixture
    def other_ingestion_job(
        self,
        db_session: Session,
        other_conversation: Conversation,
    ) -> IngestionJob:
        """Create an ingestion job in the other workspace."""
        from datetime import UTC, datetime

        repo = IngestionJobRepository(db_session)
        job = repo.create(
            source_type="cli",
            conversation_id=other_conversation.id,
            status="success",
            started_at=datetime.now(UTC),
        )
        db_session.commit()
        return job

    # Conversation endpoint tests

    def test_cannot_get_conversation_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that getting a conversation from another workspace returns 404."""
        response = api_client.get(f"/conversations/{other_conversation.id}")

        # Should return 404 to prevent ID enumeration
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cannot_get_conversation_messages_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that getting messages for a conversation from another workspace returns 404."""
        response = api_client.get(f"/conversations/{other_conversation.id}/messages")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_conversations_excludes_other_workspace(
        self,
        api_client: TestClient,
        sample_conversation: Conversation,
        other_conversation: Conversation,
    ):
        """Verify that listing conversations excludes those from other workspaces."""
        response = api_client.get("/conversations")

        assert response.status_code == 200
        data = response.json()

        # Response is paginated with items array
        items = data["items"]
        conversation_ids = [c["id"] for c in items]
        assert str(sample_conversation.id) in conversation_ids
        assert str(other_conversation.id) not in conversation_ids

    # Project endpoint tests

    def test_cannot_get_project_from_other_workspace(
        self,
        api_client: TestClient,
        other_project: Project,
    ):
        """Verify that getting a project from another workspace returns 404."""
        response = api_client.get(f"/projects/{other_project.id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_projects_excludes_other_workspace(
        self,
        api_client: TestClient,
        sample_project: Project,
        other_project: Project,
    ):
        """Verify that listing projects excludes those from other workspaces."""
        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        # Should only include our workspace's project
        project_ids = [p["id"] for p in data]
        assert str(sample_project.id) in project_ids
        assert str(other_project.id) not in project_ids

    # Ingestion job endpoint tests

    def test_cannot_get_ingestion_job_from_other_workspace(
        self,
        api_client: TestClient,
        other_ingestion_job: IngestionJob,
    ):
        """Verify that getting an ingestion job from another workspace returns 404."""
        response = api_client.get(f"/ingestion/jobs/{other_ingestion_job.id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_ingestion_jobs_excludes_other_workspace(
        self,
        api_client: TestClient,
        ingestion_job_success: IngestionJob,  # From our workspace (via conftest)
        other_ingestion_job: IngestionJob,
    ):
        """Verify that listing ingestion jobs excludes those from other workspaces."""
        response = api_client.get("/ingestion/jobs")

        assert response.status_code == 200
        data = response.json()

        # Should only include our workspace's jobs, not other workspace's
        job_ids = [j["id"] for j in data]
        assert str(ingestion_job_success.id) in job_ids
        assert str(other_ingestion_job.id) not in job_ids

    def test_cannot_get_other_workspace_conversation_jobs(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that getting ingestion jobs for another workspace's conversation returns 404."""
        response = api_client.get(
            f"/ingestion/jobs/conversation/{other_conversation.id}"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCanonicalCrossWorkspaceSecurity:
    """Tests for canonical endpoint cross-workspace isolation."""

    @pytest.fixture
    def other_workspace(self, db_session: Session) -> tuple[Organization, Workspace]:
        """Create a separate workspace for cross-workspace testing."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(
            name=f"Canonical Other Org {unique_id}",
            slug=f"canonical-other-org-{unique_id}",
        )
        workspace = ws_repo.create(
            name=f"Canonical Other Workspace {unique_id}",
            slug=f"canonical-other-ws-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace

    @pytest.fixture
    def other_conversation(
        self,
        db_session: Session,
        other_workspace: tuple[Organization, Workspace],
    ) -> Conversation:
        """Create a conversation in the other workspace."""
        _, workspace = other_workspace

        # Create minimal required entities
        project = Project(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name="Canonical Other Project",
            directory_path="/canonical/other/path",
        )
        db_session.add(project)

        developer = Developer(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            username=f"canonical_other_developer_{uuid.uuid4().hex[:8]}",
            email=f"canonical-other-{uuid.uuid4().hex[:8]}@example.com",
        )
        db_session.add(developer)

        from datetime import UTC, datetime

        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=project.id,
            developer_id=developer.id,
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=datetime.now(UTC),
            status="completed",
            extra_data={"session_id": f"canonical-other-session-{uuid.uuid4()}"},
            message_count=0,
            epoch_count=0,
            files_count=0,
        )
        db_session.add(conversation)
        db_session.commit()
        return conversation

    def test_cannot_get_canonical_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that getting canonical for another workspace's conversation returns 404."""
        response = api_client.get(f"/conversations/{other_conversation.id}/canonical")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cannot_get_canonical_narrative_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that getting canonical narrative from another workspace returns 404."""
        response = api_client.get(
            f"/conversations/{other_conversation.id}/canonical/narrative"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cannot_regenerate_canonical_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that regenerating canonical for another workspace returns 404."""
        response = api_client.post(
            f"/conversations/{other_conversation.id}/canonical/regenerate",
            json={"canonical_type": "tagging", "sampling_strategy": "semantic"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cannot_delete_canonical_from_other_workspace(
        self,
        api_client: TestClient,
        other_conversation: Conversation,
    ):
        """Verify that deleting canonical for another workspace returns 404."""
        response = api_client.delete(
            f"/conversations/{other_conversation.id}/canonical"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestWatchConfigCrossWorkspaceSecurity:
    """Tests for watch config endpoint cross-workspace isolation."""

    @pytest.fixture
    def other_workspace(self, db_session: Session) -> tuple[Organization, Workspace]:
        """Create a separate workspace for cross-workspace testing."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(
            name=f"Watch Other Org {unique_id}",
            slug=f"watch-other-org-{unique_id}",
        )
        workspace = ws_repo.create(
            name=f"Watch Other Workspace {unique_id}",
            slug=f"watch-other-ws-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace

    @pytest.fixture
    def other_watch_config(
        self,
        db_session: Session,
        other_workspace: tuple[Organization, Workspace],
    ) -> WatchConfiguration:
        """Create a watch config in the other workspace."""
        _, workspace = other_workspace

        # Create a project for the watch config
        project = Project(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name="Watch Other Project",
            directory_path="/watch/other/path",
        )
        db_session.add(project)

        config_repo = WatchConfigurationRepository(db_session)
        config = config_repo.create(
            workspace_id=workspace.id,
            directory="/other/watch/dir",
            project_id=project.id,
            is_active=False,
        )
        db_session.commit()
        return config

    def test_cannot_get_ingestion_jobs_for_other_workspace_watch_config(
        self,
        api_client: TestClient,
        other_watch_config: WatchConfiguration,
    ):
        """Verify that getting jobs for another workspace's watch config returns 404."""
        response = api_client.get(
            f"/ingestion/jobs/watch-config/{other_watch_config.id}"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
