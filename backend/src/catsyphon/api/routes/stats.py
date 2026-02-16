"""
Statistics API routes.

Endpoints for querying analytics and statistics about conversations.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import OverviewStats
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    ProjectRepository,
)
from catsyphon.models.db import Conversation, Message

router = APIRouter()


@router.get("/overview", response_model=OverviewStats)
async def get_overview_stats(
    auth: AuthContext = Depends(get_auth_context),
    start_date: Optional[datetime] = Query(None, description="Filter start date"),
    end_date: Optional[datetime] = Query(None, description="Filter end date"),
    session: Session = Depends(get_db),
) -> OverviewStats:
    """
    Get overview statistics.

    Returns high-level metrics about conversations, messages, projects, and developers.
    Optionally filtered by date range.

    Requires X-Workspace-Id header.
    """
    conv_repo = ConversationRepository(session)
    proj_repo = ProjectRepository(session)
    dev_repo = DeveloperRepository(session)
    workspace_id = auth.workspace_id

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
        query = (
            session.query(func.count(Message.id))
            .join(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
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

    # Hierarchical conversation stats (Phase 2: Epic 7u2)
    conversations_by_type = {}
    type_counts = (
        session.query(Conversation.conversation_type, func.count(Conversation.id))
        .filter(Conversation.workspace_id == workspace_id)
        .group_by(Conversation.conversation_type)
        .all()
    )
    total_main_conversations = 0
    total_agent_conversations = 0
    for conv_type, count in type_counts:
        conversations_by_type[conv_type] = count
        if conv_type == "main":
            total_main_conversations = count
        elif conv_type == "agent":
            total_agent_conversations = count

    # Recent conversations (last 7 days, workspace scoped)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_conversations = conv_repo.count_by_filters(
        workspace_id=workspace_id, start_date=seven_days_ago
    )

    # Plan statistics (extracted from extra_data JSONB)
    # ===== OPTIMIZED: Use database aggregation instead of loading all into memory =====
    total_plans = 0
    plans_by_status: dict[str, int] = {}
    conversations_with_plans = 0

    # Try PostgreSQL JSONB aggregation first (production), fall back to limited scan
    try:
        # PostgreSQL: Use JSONB operators to count plans at database level
        # Count conversations with plans
        conversations_with_plans = (
            session.query(func.count(Conversation.id))
            .filter(Conversation.workspace_id == workspace_id)
            .filter(Conversation.extra_data.isnot(None))
            .filter(
                func.jsonb_array_length(
                    func.coalesce(Conversation.extra_data["plans"], "[]")
                )
                > 0
            )
            .scalar()
            or 0
        )

        # Count total plans across all conversations
        # Use subquery to sum JSONB array lengths
        total_plans = (
            session.query(
                func.coalesce(
                    func.sum(
                        func.jsonb_array_length(
                            func.coalesce(Conversation.extra_data["plans"], "[]")
                        )
                    ),
                    0,
                )
            )
            .filter(Conversation.workspace_id == workspace_id)
            .filter(Conversation.extra_data.isnot(None))
            .scalar()
            or 0
        )

        # Plan status breakdown using jsonb_array_elements() — fully in SQL
        status_rows = (
            session.execute(
                text(
                    """
                    SELECT
                        COALESCE(plan_elem->>'status', 'active') AS plan_status,
                        COUNT(*) AS cnt
                    FROM conversations,
                         jsonb_array_elements(
                             COALESCE(metadata->'plans', '[]'::jsonb)
                         ) AS plan_elem
                    WHERE workspace_id = :ws
                      AND metadata IS NOT NULL
                      AND jsonb_array_length(COALESCE(metadata->'plans', '[]'::jsonb)) > 0
                    GROUP BY plan_status
                    """
                ),
                {"ws": workspace_id},
            )
            .mappings()
            .all()
        )
        for row in status_rows:
            plans_by_status[row["plan_status"]] = row["cnt"]

    except Exception:
        # SQLite fallback: Use limited scan (less efficient but compatible)
        plans_query = (
            session.query(Conversation.extra_data)
            .filter(Conversation.workspace_id == workspace_id)
            .filter(Conversation.extra_data.isnot(None))
            .limit(5000)  # Cap to prevent OOM
        )

        for (extra_data,) in plans_query.all():
            if not extra_data:
                continue
            plans = extra_data.get("plans", [])
            if plans and isinstance(plans, list) and len(plans) > 0:
                conversations_with_plans += 1
                total_plans += len(plans)
                for plan in plans:
                    status = plan.get("status", "active")
                    plans_by_status[status] = plans_by_status.get(status, 0) + 1

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

    # Message activity over last 60 minutes (1-minute buckets for bar chart)
    message_activity_60m = []
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
        bucket_seconds = 60  # 1 minute

        message_activity_query = (
            session.query(
                func.to_timestamp(
                    func.floor(
                        func.extract("epoch", Message.created_at) / bucket_seconds
                    )
                    * bucket_seconds
                ).label("bucket"),
                func.count(Message.id).label("count"),
            )
            .join(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .filter(Message.created_at >= cutoff)
            .group_by(text("bucket"))
            .order_by(text("bucket"))
            .all()
        )

        message_activity_60m = [
            {"timestamp": row.bucket, "count": row.count}
            for row in message_activity_query
        ]
    except Exception:
        # SQLite doesn't support to_timestamp - skip sparkline data
        pass

    return OverviewStats(
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_projects=total_projects,
        total_developers=total_developers,
        conversations_by_status=conversations_by_status,
        conversations_by_agent=conversations_by_agent,
        recent_conversations=recent_conversations,
        success_rate=success_rate,
        total_main_conversations=total_main_conversations,
        total_agent_conversations=total_agent_conversations,
        conversations_by_type=conversations_by_type,
        total_plans=total_plans,
        plans_by_status=plans_by_status,
        conversations_with_plans=conversations_with_plans,
        message_activity_60m=message_activity_60m,
    )
