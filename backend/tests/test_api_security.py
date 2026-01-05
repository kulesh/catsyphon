"""
Security tests for multi-tenancy workspace isolation.

These tests verify that all endpoints properly require the X-Workspace-Id header
and that workspace isolation is enforced.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from catsyphon.api.app import app


@pytest.fixture
def client():
    """Create a test client without database overrides."""
    return TestClient(app)


class TestWorkspaceHeaderRequired:
    """Tests that endpoints require X-Workspace-Id header."""

    def test_projects_requires_workspace_header(self, client: TestClient):
        """GET /projects should require X-Workspace-Id header."""
        response = client.get("/projects")
        # Should return 401 or 400 when header is missing
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_developers_requires_workspace_header(self, client: TestClient):
        """GET /developers should require X-Workspace-Id header."""
        response = client.get("/developers")
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_watch_configs_requires_workspace_header(self, client: TestClient):
        """GET /watch/configs should require X-Workspace-Id header."""
        response = client.get("/watch/configs")
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_watch_status_requires_workspace_header(self, client: TestClient):
        """GET /watch/status should require X-Workspace-Id header."""
        response = client.get("/watch/status")
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_stats_overview_requires_workspace_header(self, client: TestClient):
        """GET /stats/overview should require X-Workspace-Id header."""
        response = client.get("/stats/overview")
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_plans_list_requires_workspace_header(self, client: TestClient):
        """GET /plans should require X-Workspace-Id header."""
        response = client.get("/plans")
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"

    def test_upload_requires_workspace_header(self, client: TestClient):
        """POST /upload should require X-Workspace-Id header."""
        # Create a minimal file for upload
        files = {"files": ("test.jsonl", b"{}", "application/octet-stream")}
        response = client.post("/upload/", files=files)
        assert response.status_code in (
            400,
            401,
            422,
        ), f"Expected 400/401/422, got {response.status_code}: {response.text}"


class TestInvalidWorkspaceHeader:
    """Tests that endpoints reject invalid workspace UUIDs."""

    def test_invalid_uuid_format_rejected(self, client: TestClient):
        """Invalid UUID format should be rejected."""
        response = client.get("/projects", headers={"X-Workspace-Id": "not-a-uuid"})
        assert response.status_code in (
            400,
            422,
        ), f"Expected 400/422, got {response.status_code}: {response.text}"

    def test_nonexistent_workspace_rejected(self, client: TestClient):
        """Non-existent workspace UUID should return 401."""
        fake_uuid = str(uuid.uuid4())
        response = client.get("/projects", headers={"X-Workspace-Id": fake_uuid})
        # Should return 401 (unauthorized) for non-existent workspace
        assert response.status_code in (
            401,
            404,
        ), f"Expected 401/404, got {response.status_code}: {response.text}"


class TestWorkspaceIsolation:
    """Tests that resources are properly isolated by workspace."""

    @pytest.fixture
    def workspace_a(self, db_session):
        """Create test workspace A."""
        from catsyphon.db.repositories import (
            OrganizationRepository,
            WorkspaceRepository,
        )

        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        org = org_repo.get_or_create_by_slug(slug="test-org", name="Test Org")
        workspace = ws_repo.create(
            name="Workspace A",
            slug="workspace-a",
            organization_id=org.id,
        )
        db_session.commit()
        return workspace

    @pytest.fixture
    def workspace_b(self, db_session):
        """Create test workspace B."""
        from catsyphon.db.repositories import (
            OrganizationRepository,
            WorkspaceRepository,
        )

        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        org = org_repo.get_or_create_by_slug(slug="test-org", name="Test Org")
        workspace = ws_repo.create(
            name="Workspace B",
            slug="workspace-b",
            organization_id=org.id,
        )
        db_session.commit()
        return workspace

    @pytest.fixture
    def project_in_workspace_a(self, db_session, workspace_a):
        """Create a project in workspace A."""
        from catsyphon.db.repositories import ProjectRepository

        repo = ProjectRepository(db_session)
        project = repo.create(
            workspace_id=workspace_a.id,
            name="Project in A",
            directory_path="/path/to/a",
        )
        db_session.commit()
        return project

    def test_project_visible_in_own_workspace(
        self, api_client, workspace_a, project_in_workspace_a
    ):
        """Project should be visible when querying with correct workspace."""
        response = api_client.get(
            "/projects", headers={"X-Workspace-Id": str(workspace_a.id)}
        )
        assert response.status_code == 200
        projects = response.json()
        assert any(p["id"] == str(project_in_workspace_a.id) for p in projects)

    def test_project_not_visible_in_other_workspace(
        self, api_client, workspace_b, project_in_workspace_a
    ):
        """Project should NOT be visible when querying with different workspace."""
        response = api_client.get(
            "/projects", headers={"X-Workspace-Id": str(workspace_b.id)}
        )
        assert response.status_code == 200
        projects = response.json()
        # Project from workspace A should not appear in workspace B results
        assert not any(p["id"] == str(project_in_workspace_a.id) for p in projects)
