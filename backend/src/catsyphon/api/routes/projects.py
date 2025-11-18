"""
Project analytics API routes.

Endpoints for project-level statistics, sessions, and file aggregations.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from catsyphon.api.schemas import ProjectStats, ProjectSession, ProjectFileAggregation
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ProjectRepository, ConversationRepository
from catsyphon.models.db import Conversation, Developer, FileTouched, Message

router = APIRouter()


@router.get("/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(
    project_id: UUID,
    session: Session = Depends(get_db),
) -> ProjectStats:
    """
    Get aggregated statistics for a project.

    Computes metrics across all conversations/sessions belonging to this project:
    - Session count, success rate, average duration
    - Total messages and files changed
    - Top features and problems (from AI tags)
    - Tool usage distribution
    - Developer participation
    """
    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all conversations for this project
    conversations = (
        session.query(Conversation).filter(Conversation.project_id == project_id).all()
    )

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
    from sqlalchemy import distinct

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
        len(success_conversations) / total_with_outcome if total_with_outcome > 0 else None
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
        session.query(Developer.username)
        .filter(Developer.id.in_(developer_ids))
        .all()
        if developer_ids
        else []
    )
    developer_names = [d.username for d in developers]

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
    )


@router.get("/{project_id}/sessions", response_model=list[ProjectSession])
async def list_project_sessions(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: Session = Depends(get_db),
) -> list[ProjectSession]:
    """
    List all sessions (conversations) for a project.

    Returns paginated list of conversations with lightweight metadata,
    sorted by start_time descending (newest first).
    """
    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Query conversations with pagination
    query = (
        session.query(Conversation, Developer.username)
        .outerjoin(Developer, Conversation.developer_id == Developer.id)
        .filter(Conversation.project_id == project_id)
        .order_by(Conversation.start_time.desc())
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
