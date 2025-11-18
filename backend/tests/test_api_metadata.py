"""
Tests for Metadata API routes.

Tests the /projects and /developers endpoints.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories import DeveloperRepository, ProjectRepository
from catsyphon.models.db import Developer, Project


class TestListProjects:
    """Tests for GET /projects endpoint."""

    def test_list_projects_empty(self, api_client: TestClient, db_session: Session):
        """Test listing projects when database is empty."""
        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_projects_returns_all(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_project: Project,
    ):
        """Test listing projects returns all projects."""
        repo = ProjectRepository(db_session)

        # Create additional projects
        repo.create(
            id=uuid.uuid4(), workspace_id=sample_workspace.id, name="Project Alpha", directory_path="/path/to/alpha"
        )
        repo.create(
            id=uuid.uuid4(), workspace_id=sample_workspace.id, name="Project Beta", directory_path="/path/to/beta"
        )

        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 3
        project_names = {p["name"] for p in data}
        assert "Test Project" in project_names
        assert "Project Alpha" in project_names
        assert "Project Beta" in project_names

    def test_list_projects_response_structure(
        self, api_client: TestClient, db_session: Session, sample_project: Project
    ):
        """Test that project response has correct structure."""
        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 1
        project = data[0]

        assert "id" in project
        assert "name" in project
        assert "description" in project
        assert "created_at" in project

    def test_list_projects_includes_all_fields(
        self, api_client: TestClient, db_session: Session, sample_workspace
    ):
        """Test that all project fields are included in response."""
        repo = ProjectRepository(db_session)
        proj = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            name="Test Project",
            directory_path="/test/path",
            description="Test Description",
        )

        response = api_client.get("/projects")

        assert response.status_code == 200
        data = response.json()

        project = next(p for p in data if p["id"] == str(proj.id))
        assert project["name"] == "Test Project"
        assert project["description"] == "Test Description"


class TestListDevelopers:
    """Tests for GET /developers endpoint."""

    def test_list_developers_empty(self, api_client: TestClient, db_session: Session):
        """Test listing developers when database is empty."""
        response = api_client.get("/developers")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_developers_returns_all(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_workspace,
        sample_developer: Developer,
    ):
        """Test listing developers returns all developers."""
        repo = DeveloperRepository(db_session)

        # Create additional developers
        repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="alice",
            email="alice@example.com",
        )
        repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="bob",
            email="bob@example.com",
        )

        response = api_client.get("/developers")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 3
        usernames = {d["username"] for d in data}
        assert "test_developer" in usernames
        assert "alice" in usernames
        assert "bob" in usernames

    def test_list_developers_response_structure(
        self, api_client: TestClient, db_session: Session, sample_developer: Developer
    ):
        """Test that developer response has correct structure."""
        response = api_client.get("/developers")

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 1
        developer = data[0]

        assert "id" in developer
        assert "username" in developer
        assert "email" in developer
        assert "created_at" in developer

    def test_list_developers_includes_all_fields(
        self, api_client: TestClient, db_session: Session, sample_workspace
    ):
        """Test that all developer fields are included in response."""
        repo = DeveloperRepository(db_session)
        dev = repo.create(
            id=uuid.uuid4(),
            workspace_id=sample_workspace.id,
            username="john_doe",
            email="john@example.com",
        )

        response = api_client.get("/developers")

        assert response.status_code == 200
        data = response.json()

        developer = next(d for d in data if d["id"] == str(dev.id))
        assert developer["username"] == "john_doe"
        assert developer["email"] == "john@example.com"
