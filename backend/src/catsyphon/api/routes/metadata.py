"""
Metadata API routes.

Endpoints for querying projects, developers, and other metadata.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    DeveloperResponse,
    ProjectListItem,
    RecentSession,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    DeveloperRepository,
    ProjectRepository,
)
from catsyphon.models.db import Conversation

router = APIRouter()

# Maximum recent sessions to include per project card
_RECENT_SESSIONS_LIMIT = 3


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[ProjectListItem]:
    """
    List all projects with session counts, sorted by most recently active.

    Each project includes up to 3 recent parent sessions with intent/outcome/feature
    extracted from AI-generated tags.

    Requires X-Workspace-Id header.
    """
    repo = ProjectRepository(session)
    workspace_id = auth.workspace_id

    projects = repo.get_by_workspace(workspace_id)
    project_ids = [p.id for p in projects]

    if not project_ids:
        return []

    # --- Aggregate stats (session_count, last_session_at) ---
    # Use updated_at for recency: incremental parsing bumps it on every
    # new message, so it reflects the latest activity — not just session start.
    project_stats = (
        session.query(
            Conversation.project_id,
            func.count(Conversation.id).label("session_count"),
            func.max(Conversation.updated_at).label("last_session_at"),
        )
        .filter(Conversation.project_id.in_(project_ids))
        .group_by(Conversation.project_id)
        .all()
    )
    stats_map = {
        row.project_id: (row.session_count, row.last_session_at)
        for row in project_stats
    }

    # --- Recent sessions via window function ---
    # Ordered by updated_at DESC so currently-active sessions surface first.
    # Includes both parent and agent sessions — modern coding agents
    # delegate most real work (features, fixes, refactors) to subagents.
    row_num = (
        func.row_number()
        .over(
            partition_by=Conversation.project_id,
            order_by=Conversation.updated_at.desc(),
        )
        .label("rn")
    )

    ranked = (
        session.query(
            Conversation.project_id,
            Conversation.id,
            Conversation.start_time,
            Conversation.updated_at,
            Conversation.agent_type,
            Conversation.tags,
        )
        .filter(Conversation.project_id.in_(project_ids))
        .add_columns(row_num)
        .subquery()
    )

    recent_rows = (
        session.query(
            ranked.c.project_id,
            ranked.c.id,
            ranked.c.start_time,
            ranked.c.updated_at,
            ranked.c.agent_type,
            ranked.c.tags,
        )
        .filter(ranked.c.rn <= _RECENT_SESSIONS_LIMIT)
        .order_by(ranked.c.project_id, ranked.c.updated_at.desc())
        .all()
    )

    # Build lookup: project_id -> list[RecentSession]
    recent_map: dict[str, list[RecentSession]] = {}
    for row in recent_rows:
        tags = row.tags or {}
        features = tags.get("features") or []
        rs = RecentSession(
            id=row.id,
            start_time=row.start_time,
            last_active=row.updated_at,
            agent_type=row.agent_type,
            intent=tags.get("intent"),
            outcome=tags.get("outcome"),
            feature=features[0] if features else None,
        )
        recent_map.setdefault(str(row.project_id), []).append(rs)

    # --- Assemble response, sorted by last_session_at DESC ---
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
                recent_sessions=recent_map.get(str(project.id), []),
            )
        )

    # Sort by most recently active first; projects with no sessions go last
    result.sort(
        key=lambda p: p.last_session_at or p.created_at,
        reverse=True,
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
