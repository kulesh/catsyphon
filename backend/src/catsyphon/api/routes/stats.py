"""
Statistics API routes.

Endpoints for querying analytics and statistics about conversations.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.api.schemas import OverviewStats
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    ProjectRepository,
    WorkspaceRepository,
)
from catsyphon.models.db import Conversation, Message

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


@router.get("/overview", response_model=OverviewStats)
async def get_overview_stats(
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    session: Session = Depends(get_db),
) -> OverviewStats:
    """
    Get overview statistics.

    Returns high-level metrics about conversations, messages, projects, and developers.
    Optionally filtered by date range.
    """
    conv_repo = ConversationRepository(session)
    proj_repo = ProjectRepository(session)
    dev_repo = DeveloperRepository(session)
    workspace_id = _get_default_workspace_id(session)

    # If no workspace, return empty stats
    if workspace_id is None:
        return OverviewStats(
            total_conversations=0,
            total_messages=0,
            total_projects=0,
            total_developers=0,
            conversations_by_status={},
            conversations_by_agent={},
            recent_conversations=0,
            success_rate=None,
        )

    # Build date filter
    date_filter = {"workspace_id": workspace_id}
    if start_date:
        date_filter["start_date"] = start_date
    if end_date:
        date_filter["end_date"] = end_date

    # Total conversations (with optional date filter)
    total_conversations = conv_repo.count_by_filters(**date_filter)

    # Total messages (requires custom query if date filtered)
    if start_date or end_date:
        # Count messages in conversations within date range
        query = session.query(func.count(Message.id)).join(Conversation).filter(
            Conversation.workspace_id == workspace_id
        )
        if start_date:
            query = query.filter(Conversation.start_time >= start_date)
        if end_date:
            query = query.filter(Conversation.start_time <= end_date)
        total_messages = query.scalar() or 0
    else:
        # Count all messages in workspace
        total_messages = (
            session.query(func.count(Message.id))
            .join(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .scalar()
            or 0
        )

    # Total projects and developers in workspace
    total_projects = proj_repo.count_by_workspace(workspace_id)
    total_developers = dev_repo.count_by_workspace(workspace_id)

    # Conversations by status (workspace scoped)
    conversations_by_status = {}
    status_counts = (
        session.query(Conversation.status, func.count(Conversation.id))
        .filter(Conversation.workspace_id == workspace_id)
        .group_by(Conversation.status)
        .all()
    )
    for status, count in status_counts:
        conversations_by_status[status or "unknown"] = count

    # Conversations by agent type (workspace scoped)
    conversations_by_agent = {}
    agent_counts = (
        session.query(Conversation.agent_type, func.count(Conversation.id))
        .filter(Conversation.workspace_id == workspace_id)
        .group_by(Conversation.agent_type)
        .all()
    )
    for agent_type, count in agent_counts:
        conversations_by_agent[agent_type] = count

    # Recent conversations (last 7 days, workspace scoped)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_conversations = conv_repo.count_by_filters(
        workspace_id=workspace_id, start_date=seven_days_ago
    )

    # Success rate (workspace scoped)
    total_with_success = (
        session.query(func.count(Conversation.id))
        .filter(Conversation.workspace_id == workspace_id)
        .filter(Conversation.success.isnot(None))
        .scalar()
        or 0
    )
    if total_with_success > 0:
        successful = (
            session.query(func.count(Conversation.id))
            .filter(Conversation.workspace_id == workspace_id)
            .filter(Conversation.success == True)  # noqa: E712
            .scalar()
            or 0
        )
        success_rate = (successful / total_with_success) * 100
    else:
        success_rate = None

    return OverviewStats(
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_projects=total_projects,
        total_developers=total_developers,
        conversations_by_status=conversations_by_status,
        conversations_by_agent=conversations_by_agent,
        recent_conversations=recent_conversations,
        success_rate=success_rate,
    )
