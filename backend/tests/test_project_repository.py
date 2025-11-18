"""
Tests for ProjectRepository.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from catsyphon.db.repositories.project import ProjectRepository
from catsyphon.models.db import Project, Workspace


def test_generate_project_name_from_meaningful_basename(db_session: Session):
    """Test name generation from meaningful directory basename."""
    repo = ProjectRepository(db_session)

    # Test standard project path
    name = repo._generate_project_name("/Users/kulesh/dev/catsyphon")
    assert name == "catsyphon"

    # Test another path
    name = repo._generate_project_name("/home/user/projects/my-awesome-app")
    assert name == "my-awesome-app"


def test_generate_project_name_from_root_directory(db_session: Session):
    """Test name generation when basename is not meaningful."""
    repo = ProjectRepository(db_session)

    # Test root directory
    name = repo._generate_project_name("/")
    assert name.startswith("Project ")
    assert len(name) == 14  # "Project " + 6-char UUID

    # Test current directory
    name = repo._generate_project_name(".")
    assert name.startswith("Project ")

    # Test parent directory
    name = repo._generate_project_name("..")
    assert name.startswith("Project ")


def test_get_by_directory(db_session: Session, sample_workspace: Workspace):
    """Test getting project by directory path."""
    repo = ProjectRepository(db_session)

    # Create a project
    project = repo.create(
        workspace_id=sample_workspace.id,
        name="Test Project",
        directory_path="/Users/test/project",
    )

    # Get by directory
    found = repo.get_by_directory("/Users/test/project", sample_workspace.id)
    assert found is not None
    assert found.id == project.id
    assert found.directory_path == "/Users/test/project"

    # Non-existent directory
    not_found = repo.get_by_directory("/Users/test/other", sample_workspace.id)
    assert not_found is None


def test_get_or_create_by_directory_creates_new(
    db_session: Session, sample_workspace: Workspace
):
    """Test that get_or_create_by_directory creates new project."""
    repo = ProjectRepository(db_session)

    project = repo.get_or_create_by_directory(
        directory_path="/Users/test/newproject", workspace_id=sample_workspace.id
    )

    assert project is not None
    assert project.directory_path == "/Users/test/newproject"
    assert project.name == "newproject"  # Auto-generated from basename
    assert project.workspace_id == sample_workspace.id


def test_get_or_create_by_directory_returns_existing(
    db_session: Session, sample_workspace: Workspace
):
    """Test that get_or_create_by_directory returns existing project."""
    repo = ProjectRepository(db_session)

    # Create first
    project1 = repo.get_or_create_by_directory(
        directory_path="/Users/test/existing", workspace_id=sample_workspace.id
    )

    # Get same project
    project2 = repo.get_or_create_by_directory(
        directory_path="/Users/test/existing", workspace_id=sample_workspace.id
    )

    assert project1.id == project2.id
    assert project1.name == project2.name


def test_get_or_create_by_directory_with_custom_name(
    db_session: Session, sample_workspace: Workspace
):
    """Test creating project with custom name override."""
    repo = ProjectRepository(db_session)

    project = repo.get_or_create_by_directory(
        directory_path="/Users/test/myapp",
        workspace_id=sample_workspace.id,
        name="My Awesome App",
    )

    assert project.directory_path == "/Users/test/myapp"
    assert project.name == "My Awesome App"  # Custom name, not "myapp"


def test_get_or_create_by_directory_workspace_isolation(
    db_session: Session, sample_workspace: Workspace
):
    """Test that projects are isolated by workspace."""
    repo = ProjectRepository(db_session)

    workspace1_id = sample_workspace.id
    workspace2_id = uuid.uuid4()

    # Create project in workspace 1
    project1 = repo.get_or_create_by_directory(
        directory_path="/Users/test/shared", workspace_id=workspace1_id
    )

    # Create project with same directory in workspace 2
    project2 = repo.get_or_create_by_directory(
        directory_path="/Users/test/shared", workspace_id=workspace2_id
    )

    # Should be different projects
    assert project1.id != project2.id
    assert project1.workspace_id == workspace1_id
    assert project2.workspace_id == workspace2_id
    assert project1.directory_path == project2.directory_path


def test_unique_constraint_on_workspace_directory(
    db_session: Session, sample_workspace: Workspace
):
    """Test that unique constraint prevents duplicate directory paths in same workspace."""
    repo = ProjectRepository(db_session)

    # Create first project
    repo.create(
        workspace_id=sample_workspace.id,
        name="Project 1",
        directory_path="/Users/test/dup",
    )

    # Try to create duplicate
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        repo.create(
            workspace_id=sample_workspace.id,
            name="Project 2",
            directory_path="/Users/test/dup",  # Same directory
        )
        db_session.commit()
