"""
Metadata API routes.

Endpoints for querying projects, developers, and other metadata.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import DeveloperResponse, ProjectListItem
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    DeveloperRepository,
    ProjectRepository,
)
from catsyphon.models.db import Conversation

router = APIRouter()


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[ProjectListItem]:
    """
    List all projects with session counts.

    Returns all projects in the workspace with metadata about session counts
    and last activity timestamp.

    Requires X-Workspace-Id header.
    """
    repo = ProjectRepository(session)
    workspace_id = auth.workspace_id

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
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[DeveloperResponse]:
    """
    List all developers.

    Returns all developers in the workspace, useful for filter dropdowns.

    Requires X-Workspace-Id header.
    """
    repo = DeveloperRepository(session)
    workspace_id = auth.workspace_id

    developers = repo.get_by_workspace(workspace_id)

    return [DeveloperResponse.model_validate(d) for d in developers]
