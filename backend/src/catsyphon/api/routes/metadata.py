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

    # ===== OPTIMIZED: Single GROUP BY query instead of N+1 per-project queries =====
    # Get all project IDs
    project_ids = [p.id for p in projects]

    # Single batch query for all project stats
    if project_ids:
        project_stats = (
            session.query(
                Conversation.project_id,
                func.count(Conversation.id).label("session_count"),
                func.max(Conversation.start_time).label("last_session_at"),
            )
            .filter(Conversation.project_id.in_(project_ids))
            .group_by(Conversation.project_id)
            .all()
        )

        # Build lookup dictionary: project_id -> (count, last_at)
        stats_map = {
            row.project_id: (row.session_count, row.last_session_at)
            for row in project_stats
        }
    else:
        stats_map = {}

    # Enrich with session counts from the batch query
    result = []
    for project in projects:
        count, last_at = stats_map.get(project.id, (0, None))
        result.append(
            ProjectListItem(
                id=project.id,
                name=project.name,
                directory_path=project.directory_path,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
                session_count=count,
                last_session_at=last_at,
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
