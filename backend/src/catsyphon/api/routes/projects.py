"""
Project analytics API routes.

Endpoints for project-level statistics, sessions, and file aggregations.
"""

from collections import defaultdict
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    ProjectFileAggregation,
    ProjectSession,
    ProjectStats,
    SentimentTimelinePoint,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ProjectRepository
from catsyphon.models.db import Conversation, Developer, Epoch, FileTouched, Message

router = APIRouter()


@router.get("/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(
    project_id: UUID,
    session: Session = Depends(get_db),
    date_range: Optional[str] = Query(
        None, description="Date range filter: 7d, 30d, 90d, or all (default: all)"
    ),
) -> ProjectStats:
    """
    Get aggregated statistics for a project.

    Computes metrics across all conversations/sessions belonging to this project:
    - Session count, success rate, average duration
    - Total messages and files changed
    - Top features and problems (from AI tags)
    - Tool usage distribution
    - Developer participation
    - Sentiment timeline

    Args:
        project_id: UUID of the project
        date_range: Optional date range filter (7d, 30d, 90d, all). Defaults to 'all'.
                    Filters conversations by start_time >= cutoff date.
    """
    from datetime import datetime, timedelta

    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Calculate date cutoff based on date_range
    cutoff_date = None
    if date_range:
        now = datetime.now()
        if date_range == "7d":
            cutoff_date = now - timedelta(days=7)
        elif date_range == "30d":
            cutoff_date = now - timedelta(days=30)
        elif date_range == "90d":
            cutoff_date = now - timedelta(days=90)
        # "all" or invalid values default to no cutoff (None)

    # Get conversations for this project, optionally filtered by date
    query = session.query(Conversation).filter(Conversation.project_id == project_id)
    if cutoff_date:
        query = query.filter(Conversation.start_time >= cutoff_date)
    conversations = query.all()

    if not conversations:
        # Return empty stats
        return ProjectStats(
            project_id=project_id,
            session_count=0,
            total_messages=0,
            total_files_changed=0,
            success_rate=None,
            avg_session_duration_seconds=None,
            first_session_at=None,
            last_session_at=None,
        )

    # Basic counts
    session_count = len(conversations)

    # Message count aggregation
    total_messages = (
        session.query(func.count(Message.id))
        .join(Conversation)
        .filter(Conversation.project_id == project_id)
        .scalar()
        or 0
    )

    # Files changed aggregation (use subquery for SQLite compatibility)

    total_files = (
        session.query(FileTouched.file_path)
        .join(Conversation)
        .filter(Conversation.project_id == project_id)
        .distinct()
        .count()
    )

    # Success rate calculation
    success_conversations = [c for c in conversations if c.success is True]
    failed_conversations = [c for c in conversations if c.success is False]
    total_with_outcome = len(success_conversations) + len(failed_conversations)

    success_rate = (
        len(success_conversations) / total_with_outcome
        if total_with_outcome > 0
        else None
    )

    # Average duration
    durations = []
    for conv in conversations:
        if conv.end_time and conv.start_time:
            duration = (conv.end_time - conv.start_time).total_seconds()
            durations.append(duration)

    avg_duration = sum(durations) / len(durations) if durations else None

    # Temporal bounds
    start_times = [c.start_time for c in conversations if c.start_time]
    end_times = [c.end_time for c in conversations if c.end_time]

    first_session_at = min(start_times) if start_times else None
    last_session_at = max(end_times) if end_times else None

    # Aggregate features and problems from tags
    all_features: dict[str, int] = {}
    all_problems: dict[str, int] = {}
    tool_usage: dict[str, int] = {}

    for conv in conversations:
        # Extract features
        if "features" in conv.tags and isinstance(conv.tags["features"], list):
            for feature in conv.tags["features"]:
                all_features[feature] = all_features.get(feature, 0) + 1

        # Extract problems
        if "problems" in conv.tags and isinstance(conv.tags["problems"], list):
            for problem in conv.tags["problems"]:
                all_problems[problem] = all_problems.get(problem, 0) + 1

        # Extract tool usage
        if "tools_used" in conv.tags and isinstance(conv.tags["tools_used"], list):
            for tool in conv.tags["tools_used"]:
                tool_usage[tool] = tool_usage.get(tool, 0) + 1

    # Get top 10 features and problems
    top_features = sorted(all_features.items(), key=lambda x: x[1], reverse=True)[:10]
    top_problems = sorted(all_problems.items(), key=lambda x: x[1], reverse=True)[:10]

    # Developer participation
    developer_ids = {c.developer_id for c in conversations if c.developer_id}
    developers = (
        session.query(Developer.username).filter(Developer.id.in_(developer_ids)).all()
        if developer_ids
        else []
    )
    developer_names = [d.username for d in developers]

    # Sentiment timeline (group epochs by date)
    sentiment_timeline: list[SentimentTimelinePoint] = []
    if conversations:
        conversation_ids = [c.id for c in conversations]
        epochs = (
            session.query(Epoch)
            .filter(Epoch.conversation_id.in_(conversation_ids))
            .filter(Epoch.sentiment_score.isnot(None))
            .all()
        )

        # Group by date
        date_sentiments: dict[str, list[float]] = defaultdict(list)
        date_conversations: dict[str, set[UUID]] = defaultdict(set)

        for epoch in epochs:
            if epoch.start_time and epoch.sentiment_score is not None:
                date_str = epoch.start_time.date().isoformat()
                date_sentiments[date_str].append(epoch.sentiment_score)
                date_conversations[date_str].add(epoch.conversation_id)

        # Calculate averages and create timeline points
        for date_str in sorted(date_sentiments.keys()):
            sentiments = date_sentiments[date_str]
            avg_sentiment = sum(sentiments) / len(sentiments)
            session_count_for_date = len(date_conversations[date_str])

            sentiment_timeline.append(
                SentimentTimelinePoint(
                    date=date_str,
                    avg_sentiment=avg_sentiment,
                    session_count=session_count_for_date,
                )
            )

    return ProjectStats(
        project_id=project_id,
        session_count=session_count,
        total_messages=total_messages,
        total_files_changed=total_files,
        success_rate=success_rate,
        avg_session_duration_seconds=avg_duration,
        first_session_at=first_session_at,
        last_session_at=last_session_at,
        top_features=[f[0] for f in top_features],
        top_problems=[p[0] for p in top_problems],
        tool_usage=tool_usage,
        developer_count=len(developer_ids),
        developers=developer_names,
        sentiment_timeline=sentiment_timeline,
    )


@router.get("/{project_id}/sessions", response_model=list[ProjectSession])
async def list_project_sessions(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    developer: Optional[str] = Query(None, description="Filter by developer username"),
    outcome: Optional[str] = Query(
        None, description="Filter by outcome: success, failed, all (default: all)"
    ),
    date_from: Optional[str] = Query(
        None, description="Filter sessions from this date (ISO format: YYYY-MM-DD)"
    ),
    date_to: Optional[str] = Query(
        None, description="Filter sessions to this date (ISO format: YYYY-MM-DD)"
    ),
    sort_by: Optional[str] = Query(
        "start_time", description="Sort by: start_time, duration, status, developer"
    ),
    order: str = Query("desc", description="Sort order: asc or desc"),
    session: Session = Depends(get_db),
) -> list[ProjectSession]:
    """
    List all sessions (conversations) for a project with filtering and sorting.

    Returns paginated list of conversations with lightweight metadata.

    Filters:
    - developer: Filter by developer username
    - outcome: Filter by success/failed status
    - date_from/date_to: Filter by date range

    Sorting:
    - sort_by: Column to sort by (start_time, duration, status, developer)
    - order: asc or desc
    """
    from datetime import datetime

    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build base query
    query = (
        session.query(Conversation, Developer.username)
        .outerjoin(Developer, Conversation.developer_id == Developer.id)
        .filter(Conversation.project_id == project_id)
    )

    # Apply filters
    if developer:
        query = query.filter(Developer.username == developer)

    if outcome:
        if outcome == "success":
            query = query.filter(Conversation.success.is_(True))
        elif outcome == "failed":
            query = query.filter(Conversation.success.is_(False))
        # "all" or invalid values: no filter

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.filter(Conversation.start_time >= from_date)
        except ValueError:
            pass  # Invalid date format, skip filter

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            query = query.filter(Conversation.start_time <= to_date)
        except ValueError:
            pass  # Invalid date format, skip filter

    # Apply sorting
    if sort_by == "duration":
        # Sort by calculated duration (end_time - start_time)
        # Use database-agnostic approach with epoch timestamps
        from sqlalchemy import Integer, cast, func

        # Calculate duration as difference between Unix timestamps (in seconds)
        # This works with both PostgreSQL and SQLite
        end_epoch = func.extract("epoch", Conversation.end_time)
        start_epoch = func.extract("epoch", Conversation.start_time)
        duration_seconds = cast(end_epoch - start_epoch, Integer)

        if order == "desc":
            query = query.order_by(duration_seconds.desc().nulls_last())
        else:
            query = query.order_by(duration_seconds.asc().nulls_last())
    elif sort_by == "status":
        query = query.order_by(
            Conversation.status.desc() if order == "desc" else Conversation.status.asc()
        )
    elif sort_by == "developer":
        query = query.order_by(
            Developer.username.desc() if order == "desc" else Developer.username.asc()
        )
    else:  # default: start_time
        query = query.order_by(
            Conversation.start_time.desc()
            if order == "desc"
            else Conversation.start_time.asc()
        )

    # Apply pagination
    offset = (page - 1) * page_size
    results = query.offset(offset).limit(page_size).all()

    # Build response
    sessions = []
    for conv, developer_username in results:
        duration_seconds = None
        if conv.end_time and conv.start_time:
            duration_seconds = int((conv.end_time - conv.start_time).total_seconds())

        sessions.append(
            ProjectSession(
                id=conv.id,
                start_time=conv.start_time,
                end_time=conv.end_time,
                duration_seconds=duration_seconds,
                status=conv.status,
                success=conv.success,
                message_count=conv.message_count or 0,
                files_count=conv.files_count or 0,
                developer=developer_username,
                agent_type=conv.agent_type,
            )
        )

    return sessions


@router.get("/{project_id}/files", response_model=list[ProjectFileAggregation])
async def get_project_files(
    project_id: UUID,
    session: Session = Depends(get_db),
) -> list[ProjectFileAggregation]:
    """
    Get aggregated file modifications across all project sessions.

    Returns list of files touched in this project with:
    - Total modification count
    - Lines added/deleted
    - Last modification timestamp
    - Session IDs that touched the file
    """
    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Aggregate files_touched across all conversations
    # Note: Avoid array_agg for SQLite compatibility
    results = (
        session.query(
            FileTouched.file_path,
            func.count(FileTouched.id).label("modification_count"),
            func.sum(FileTouched.lines_added).label("total_lines_added"),
            func.sum(FileTouched.lines_deleted).label("total_lines_deleted"),
            func.max(FileTouched.timestamp).label("last_modified_at"),
        )
        .join(Conversation, FileTouched.conversation_id == Conversation.id)
        .filter(Conversation.project_id == project_id)
        .group_by(FileTouched.file_path)
        .order_by(func.count(FileTouched.id).desc())
        .all()
    )

    files = []
    for row in results:
        # Get all conversation_ids for this file (SQLite-compatible approach)
        session_ids = (
            session.query(FileTouched.conversation_id)
            .join(Conversation)
            .filter(
                Conversation.project_id == project_id,
                FileTouched.file_path == row.file_path,
            )
            .distinct()
            .all()
        )
        session_id_list = [str(sid[0]) for sid in session_ids]

        files.append(
            ProjectFileAggregation(
                file_path=row.file_path,
                modification_count=row.modification_count,
                total_lines_added=row.total_lines_added or 0,
                total_lines_deleted=row.total_lines_deleted or 0,
                last_modified_at=row.last_modified_at,
                session_ids=session_id_list,
            )
        )

    return files
