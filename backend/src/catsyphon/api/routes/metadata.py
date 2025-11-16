"""
Metadata API routes.

Endpoints for querying projects, developers, and other metadata.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from catsyphon.api.schemas import DeveloperResponse, ProjectResponse
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import DeveloperRepository, ProjectRepository, WorkspaceRepository

router = APIRouter()


def _get_default_workspace_id(session: Session) -> Optional[UUID]:
    """
    Get default workspace ID for API operations.

    This is a temporary helper until proper authentication is implemented.
    Returns the first workspace in the database, or None if no workspaces exist.

    Returns:
        UUID of the first workspace, or None if no workspaces exist
    """
    workspace_repo = WorkspaceRepository(session)
    workspaces = workspace_repo.get_all(limit=1)

    if not workspaces:
        return None

    return workspaces[0].id


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    session: Session = Depends(get_db),
) -> list[ProjectResponse]:
    """
    List all projects.

    Returns all projects in the system, useful for filter dropdowns.
    """
    repo = ProjectRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        return []

    projects = repo.get_by_workspace(workspace_id)

    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/developers", response_model=list[DeveloperResponse])
async def list_developers(
    session: Session = Depends(get_db),
) -> list[DeveloperResponse]:
    """
    List all developers.

    Returns all developers in the system, useful for filter dropdowns.
    """
    repo = DeveloperRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        return []

    developers = repo.get_by_workspace(workspace_id)

    return [DeveloperResponse.model_validate(d) for d in developers]
