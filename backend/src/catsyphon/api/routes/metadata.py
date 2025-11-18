"""
Metadata API routes.

Endpoints for querying projects, developers, and other metadata.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from catsyphon.api.schemas import DeveloperResponse, ProjectListItem
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import DeveloperRepository, ProjectRepository, WorkspaceRepository
from catsyphon.models.db import Conversation
from sqlalchemy import func

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


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(
    session: Session = Depends(get_db),
) -> list[ProjectListItem]:
    """
    List all projects with session counts.

    Returns all projects in the system with metadata about session counts
    and last activity timestamp.
    """
    repo = ProjectRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        return []

    projects = repo.get_by_workspace(workspace_id)

    # Enrich with session counts
    result = []
    for project in projects:
        # Count sessions for this project
        session_count = (
            session.query(func.count(Conversation.id))
            .filter(Conversation.project_id == project.id)
            .scalar()
            or 0
        )

        # Get last session timestamp
        last_session_at = (
            session.query(func.max(Conversation.start_time))
            .filter(Conversation.project_id == project.id)
            .scalar()
        )

        result.append(
            ProjectListItem(
                id=project.id,
                name=project.name,
                directory_path=project.directory_path,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
                session_count=session_count,
                last_session_at=last_session_at,
            )
        )

    return result


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
