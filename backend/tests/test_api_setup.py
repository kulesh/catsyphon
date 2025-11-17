"""
Tests for setup/onboarding API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from catsyphon.api.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestSetupStatus:
    """Tests for GET /setup/status endpoint."""

    def test_needs_onboarding_when_no_workspace(self, client: TestClient, db_session):
        """Test that needs_onboarding is true when no workspace exists."""
        response = client.get("/setup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_onboarding"] is True
        assert data["workspace_count"] == 0
        assert data["organization_count"] == 0

    def test_onboarding_complete_when_workspace_exists(
        self, client: TestClient, sample_workspace
    ):
        """Test that needs_onboarding is false when workspace exists."""
        response = client.get("/setup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["needs_onboarding"] is False
        assert data["workspace_count"] == 1
        assert data["organization_count"] == 1


class TestOrganizationEndpoints:
    """Tests for organization CRUD endpoints."""

    def test_create_organization_success(self, client: TestClient, db_session):
        """Test creating an organization with auto-generated slug."""
        response = client.post(
            "/setup/organizations",
            json={
                "name": "ACME Corporation",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "ACME Corporation"
        assert data["slug"] == "acme-corporation"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_organization_with_custom_slug(self, client: TestClient, db_session):
        """Test creating an organization with custom slug."""
        response = client.post(
            "/setup/organizations",
            json={"name": "Test Company", "slug": "custom-slug"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Company"
        assert data["slug"] == "custom-slug"

    def test_create_organization_duplicate_slug(self, client: TestClient, db_session):
        """Test that creating org with duplicate slug fails."""
        # Create first organization
        client.post(
            "/setup/organizations",
            json={"name": "First Company", "slug": "my-company"},
        )

        # Try to create second with same slug
        response = client.post(
            "/setup/organizations",
            json={"name": "Second Company", "slug": "my-company"},
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_organization_invalid_slug(self, client: TestClient, db_session):
        """Test that invalid slug pattern is rejected."""
        response = client.post(
            "/setup/organizations",
            json={"name": "Test", "slug": "Invalid Slug!"},
        )

        assert response.status_code == 422  # Validation error

    def test_list_organizations_empty(self, client: TestClient, db_session):
        """Test listing organizations when none exist."""
        response = client.get("/setup/organizations")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_organizations(self, client: TestClient, sample_organization):
        """Test listing organizations."""
        response = client.get("/setup/organizations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_organization.name
        assert data[0]["slug"] == sample_organization.slug

    def test_get_organization_by_id(self, client: TestClient, sample_organization):
        """Test getting a single organization by ID."""
        response = client.get(f"/setup/organizations/{sample_organization.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_organization.name
        assert data["id"] == str(sample_organization.id)

    def test_get_organization_not_found(self, client: TestClient, db_session):
        """Test getting non-existent organization returns 404."""
        from uuid import uuid4

        response = client.get(f"/setup/organizations/{uuid4()}")

        assert response.status_code == 404


class TestWorkspaceEndpoints:
    """Tests for workspace CRUD endpoints."""

    def test_create_workspace_success(self, client: TestClient, sample_organization):
        """Test creating a workspace with auto-generated slug."""
        response = client.post(
            "/setup/workspaces",
            json={
                "organization_id": str(sample_organization.id),
                "name": "Engineering Team",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Engineering Team"
        assert data["slug"] == "engineering-team"
        assert data["organization_id"] == str(sample_organization.id)
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_workspace_with_custom_slug(
        self, client: TestClient, sample_organization
    ):
        """Test creating a workspace with custom slug."""
        response = client.post(
            "/setup/workspaces",
            json={
                "organization_id": str(sample_organization.id),
                "name": "Test Workspace",
                "slug": "custom-ws",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Workspace"
        assert data["slug"] == "custom-ws"

    def test_create_workspace_duplicate_slug(
        self, client: TestClient, sample_organization
    ):
        """Test that creating workspace with duplicate slug fails."""
        # Create first workspace
        client.post(
            "/setup/workspaces",
            json={
                "organization_id": str(sample_organization.id),
                "name": "First WS",
                "slug": "my-workspace",
            },
        )

        # Try to create second with same slug
        response = client.post(
            "/setup/workspaces",
            json={
                "organization_id": str(sample_organization.id),
                "name": "Second WS",
                "slug": "my-workspace",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_workspace_invalid_org(self, client: TestClient, db_session):
        """Test that creating workspace with non-existent org fails."""
        from uuid import uuid4

        response = client.post(
            "/setup/workspaces",
            json={
                "organization_id": str(uuid4()),
                "name": "Test Workspace",
            },
        )

        assert response.status_code == 404
        assert "Organization" in response.json()["detail"]

    def test_list_workspaces_empty(self, client: TestClient, db_session):
        """Test listing workspaces when none exist."""
        response = client.get("/setup/workspaces")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_workspaces(self, client: TestClient, sample_workspace):
        """Test listing workspaces."""
        response = client.get("/setup/workspaces")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_workspace.name

    def test_list_workspaces_by_organization(
        self, client: TestClient, sample_workspace
    ):
        """Test filtering workspaces by organization."""
        response = client.get(
            f"/setup/workspaces?organization_id={sample_workspace.organization_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_workspace.name

    def test_get_workspace_by_id(self, client: TestClient, sample_workspace):
        """Test getting a single workspace by ID."""
        response = client.get(f"/setup/workspaces/{sample_workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_workspace.name
        assert data["id"] == str(sample_workspace.id)

    def test_get_workspace_not_found(self, client: TestClient, db_session):
        """Test getting non-existent workspace returns 404."""
        from uuid import uuid4

        response = client.get(f"/setup/workspaces/{uuid4()}")

        assert response.status_code == 404


class TestSlugGeneration:
    """Tests for slug auto-generation logic."""

    def test_slug_generation_basic(self, client: TestClient, db_session):
        """Test basic slug generation from name."""
        response = client.post(
            "/setup/organizations",
            json={"name": "Test Company"},
        )

        assert response.status_code == 201
        assert response.json()["slug"] == "test-company"

    def test_slug_generation_special_characters(self, client: TestClient, db_session):
        """Test slug generation removes special characters."""
        response = client.post(
            "/setup/organizations",
            json={"name": "ACME Corp!!! (2024)"},
        )

        assert response.status_code == 201
        assert response.json()["slug"] == "acme-corp-2024"

    def test_slug_generation_multiple_spaces(self, client: TestClient, db_session):
        """Test slug generation collapses multiple spaces."""
        response = client.post(
            "/setup/organizations",
            json={"name": "My    Company   Name"},
        )

        assert response.status_code == 201
        assert response.json()["slug"] == "my-company-name"

    def test_slug_generation_unicode(self, client: TestClient, db_session):
        """Test slug generation handles unicode characters."""
        response = client.post(
            "/setup/organizations",
            json={"name": "Café Société"},
        )

        assert response.status_code == 201
        # Should remove unicode, keep only alphanumeric
        assert response.json()["slug"] in ["caf-socit", "cafe-societe"]
