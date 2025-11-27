"""
Project analytics API routes.

Endpoints for project-level statistics, sessions, and file aggregations.
"""

from collections import defaultdict
from dataclasses import asdict
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    ProjectFileAggregation,
    ProjectAnalytics,
    ProjectSession,
    ProjectStats,
    SentimentTimelinePoint,
    SentimentByAgent,
    PairingEffectivenessPair,
    RoleDynamicsSummary,
    HandoffStats,
    ImpactMetrics,
    InfluenceFlow,
    ErrorBucket,
    ThinkingTimeStats,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    ProjectRepository,
    WorkspaceRepository,
)
from catsyphon.analytics.thinking_time import (
    aggregate_thinking_time,
    pair_user_assistant,
)
from catsyphon.analytics.cache import PROJECT_ANALYTICS_CACHE
_THINKING_TIME_MAX_LATENCY_SECONDS = 2 * 60 * 60  # 2 hours
from catsyphon.models.db import (
    Conversation,
    Developer,
    FileTouched,
    Message,
    Epoch,
    IngestionJob,
)

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


def _classify_role_dynamics(
    assistant_ratio: float, assistant_tool_calls: int, user_tool_calls: int
) -> str:
    if assistant_ratio >= 0.6 or assistant_tool_calls > user_tool_calls:
        return "agent_led"
    if assistant_ratio <= 0.4:
        return "dev_led"
    return "co_pilot"


def _categorize_error(msg: Optional[str]) -> str:
    if not msg:
        return "other"
    lower = msg.lower()
    if "duplicate" in lower:
        return "duplicate"
    if "auth" in lower or "unauthorized" in lower or "forbidden" in lower:
        return "auth"
    if "timeout" in lower or "connection" in lower:
        return "network"
    if "parse" in lower or "json" in lower:
        return "parse_error"
    if "tool" in lower or "ingestion" in lower:
        return "tool_fail"
    return "other"


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


@router.get("/{project_id}/analytics", response_model=ProjectAnalytics)
async def get_project_analytics(
    project_id: UUID,
    session: Session = Depends(get_db),
    date_range: Optional[str] = Query(
        None, description="Date range filter: 7d, 30d, 90d, or all (default: all)"
    ),
) -> ProjectAnalytics:
    """
    Advanced analytics for a project focused on pairing effectiveness and handoffs.
    """
    from datetime import datetime, timedelta
    import statistics

    # Cache lookup
    cached = PROJECT_ANALYTICS_CACHE.get(project_id, date_range)
    if cached:
        return cached

    project_repo = ProjectRepository(session)
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Calculate date cutoff
    cutoff_date = None
    if date_range:
        now = datetime.now()
        if date_range == "7d":
            cutoff_date = now - timedelta(days=7)
        elif date_range == "30d":
            cutoff_date = now - timedelta(days=30)
        elif date_range == "90d":
            cutoff_date = now - timedelta(days=90)

    conv_query = session.query(Conversation).filter(Conversation.project_id == project_id)
    if cutoff_date:
        conv_query = conv_query.filter(Conversation.start_time >= cutoff_date)
    conversations = conv_query.all()

    if not conversations:
        return ProjectAnalytics(project_id=project_id, date_range=date_range)

    conv_ids = [c.id for c in conversations]

    # Developers lookup
    dev_ids = {c.developer_id for c in conversations if c.developer_id}
    dev_map = {
        d.id: d.username
        for d in session.query(Developer).filter(Developer.id.in_(dev_ids)).all()
    } if dev_ids else {}

    # Messages and files
    messages = session.query(Message).filter(Message.conversation_id.in_(conv_ids)).all()
    msgs_by_conv: dict[UUID, list[Message]] = {}
    for m in messages:
        msgs_by_conv.setdefault(m.conversation_id, []).append(m)

    files = session.query(FileTouched).filter(FileTouched.conversation_id.in_(conv_ids)).all()
    files_by_conv: dict[UUID, list[FileTouched]] = {}
    for f in files:
        files_by_conv.setdefault(f.conversation_id, []).append(f)

    # Pairing effectiveness aggregation
    pair_buckets: dict[tuple[Optional[UUID], str], dict[str, Any]] = {}
    role_counts = {"agent_led": 0, "dev_led": 0, "co_pilot": 0}
    handoff_latencies: list[float] = []
    handoff_successes = 0
    handoff_clarifications: list[int] = []
    impact_lines_total = 0
    impact_sessions = 0
    first_change_latencies: list[float] = []
    all_thinking_pairs = []

    conversation_lookup = {c.id: c for c in conversations}

    for conv in conversations:
        key = (conv.developer_id, conv.agent_type)
        bucket = pair_buckets.setdefault(
            key,
            {
                "sessions": 0,
                "successes": 0,
                "lines": 0,
                "duration_hours": 0.0,
                "first_change_minutes_total": 0.0,
                "first_change_count": 0,
            },
        )
        bucket["sessions"] += 1
        if conv.success is True:
            bucket["successes"] += 1

        # Duration
        duration_hours = 0.0
        if conv.start_time and conv.end_time:
            duration_hours = max(
                (conv.end_time - conv.start_time).total_seconds() / 3600.0, 0.0001
            )
            bucket["duration_hours"] += duration_hours

        # Lines and first-change latency
        conv_files = files_by_conv.get(conv.id, [])
        lines_changed = sum((f.lines_added or 0) + (f.lines_deleted or 0) for f in conv_files)
        impact_lines_total += lines_changed
        if lines_changed > 0:
            impact_sessions += 1
        bucket["lines"] += lines_changed

        if conv_files:
            first_change_ts = min(f.timestamp for f in conv_files if f.timestamp)
            if first_change_ts and conv.start_time:
                latency_minutes = max(
                    (first_change_ts - conv.start_time).total_seconds() / 60.0, 0.0
                )
                bucket["first_change_minutes_total"] += latency_minutes
                bucket["first_change_count"] += 1
                first_change_latencies.append(latency_minutes)

        # Role dynamics
        conv_msgs = msgs_by_conv.get(conv.id, [])
        assistant_msgs = sum(1 for m in conv_msgs if m.role == "assistant")
        user_msgs = sum(1 for m in conv_msgs if m.role == "user")
        total_msgs = assistant_msgs + user_msgs
        assistant_tool_calls = sum(1 for m in conv_msgs if m.role == "assistant" and m.tool_calls)
        user_tool_calls = sum(1 for m in conv_msgs if m.role == "user" and m.tool_calls)
        assistant_ratio = assistant_msgs / total_msgs if total_msgs else 0.5
        role = _classify_role_dynamics(assistant_ratio, assistant_tool_calls, user_tool_calls)
        role_counts[role] += 1

        # Thinking-time pairs
        all_thinking_pairs.extend(pair_user_assistant(conv_msgs))

        # Handoff stats
        if conv.parent_conversation_id:
            parent = conversation_lookup.get(conv.parent_conversation_id)
            if parent and parent.start_time and conv.start_time:
                delta_minutes = max(
                    (conv.start_time - parent.start_time).total_seconds() / 60.0, 0.0
                )
                handoff_latencies.append(delta_minutes)
                if conv.success is True:
                    handoff_successes += 1
                # Clarifications: user messages in parent between parent start and agent start
                parent_msgs = msgs_by_conv.get(parent.id, [])
                clarifications = sum(
                    1
                    for m in parent_msgs
                    if m.role == "user"
                    and m.timestamp >= parent.start_time
                    and m.timestamp <= conv.start_time
                )
                handoff_clarifications.append(clarifications)

    # Influence flows (file introduction -> later adopter)
    influence_counts: dict[tuple[str, str], int] = {}
    first_touch: dict[str, tuple[str, datetime]] = {}
    for f in sorted(files, key=lambda x: x.timestamp):
        # Identify actor string
        conv = conversation_lookup.get(f.conversation_id)
        actor = "unknown"
        if conv:
            dev_name = dev_map.get(conv.developer_id) if conv.developer_id else None
            actor = dev_name or conv.agent_type or "unknown"

        existing = first_touch.get(f.file_path)
        if existing:
            introducer, _ = existing
            if introducer != actor:
                influence_counts[(introducer, actor)] = influence_counts.get(
                    (introducer, actor), 0
                ) + 1
        else:
            first_touch[f.file_path] = (actor, f.timestamp)

    influence_flows = [
        InfluenceFlow(source=src, target=dst, count=count)
        for (src, dst), count in sorted(
            influence_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:10]
    ]

    # Error heatmap from ingestion jobs
    error_counts: dict[tuple[str, str], int] = {}
    ingestion_jobs = (
        session.query(IngestionJob)
        .filter(IngestionJob.conversation_id.in_(conv_ids))
        .filter(IngestionJob.status == "failed")
        .all()
    )
    for job in ingestion_jobs:
        conv = conversation_lookup.get(job.conversation_id)
        agent_type = conv.agent_type if conv else "unknown"
        category = _categorize_error(job.error_message)
        error_counts[(agent_type, category)] = error_counts.get(
            (agent_type, category), 0
        ) + 1

    error_heatmap = [
        ErrorBucket(agent_type=a, category=c, count=count)
        for (a, c), count in sorted(
            error_counts.items(), key=lambda kv: kv[1], reverse=True
        )
    ]

    # Build pairing pairs
    pairs: list[PairingEffectivenessPair] = []
    for (dev_id, agent_type), data in pair_buckets.items():
        sessions = data["sessions"]
        success_rate = data["successes"] / sessions if sessions else None
        lines_per_hour = (
            data["lines"] / data["duration_hours"] if data["duration_hours"] > 0 else None
        )
        avg_first_change = (
            data["first_change_minutes_total"] / data["first_change_count"]
            if data["first_change_count"] > 0
            else None
        )
        throughput_component = min(lines_per_hour / 200.0, 1.0) if lines_per_hour else 0.0
        latency_component = (
            max(0.0, 1 - (avg_first_change / 60.0)) if avg_first_change is not None else 0.5
        )
        score = (success_rate or 0.5) * 0.6 + throughput_component * 0.3 + latency_component * 0.1

        pairs.append(
            PairingEffectivenessPair(
                developer=dev_map.get(dev_id),
                agent_type=agent_type,
                score=round(score, 3),
                success_rate=success_rate,
                lines_per_hour=lines_per_hour,
                first_change_minutes=avg_first_change,
                sessions=sessions,
            )
        )

    pairing_top = sorted(pairs, key=lambda p: p.score, reverse=True)[:5]
    pairing_bottom = sorted(pairs, key=lambda p: p.score)[:5]

    # Handoff stats aggregate
    handoff_count = len(handoff_latencies)
    handoff_avg = sum(handoff_latencies) / handoff_count if handoff_count else None
    handoff_success_rate = (
        handoff_successes / handoff_count if handoff_count else None
    )
    clarifications_avg = (
        sum(handoff_clarifications) / len(handoff_clarifications)
        if handoff_clarifications
        else None
    )

    # Impact metrics
    impact_avg_lines = (
        impact_lines_total / impact_sessions if impact_sessions > 0 else None
    )
    median_first_change = (
        statistics.median(first_change_latencies) if first_change_latencies else None
    )

    # Sentiment by agent
    sentiment_rollup: dict[str, list[float]] = {}
    for conv in conversations:
        sentiment = conv.tags.get("sentiment_score") if isinstance(conv.tags, dict) else None
        if sentiment is None:
            # Fallback: map sentiment label to score
            label = conv.tags.get("sentiment") if isinstance(conv.tags, dict) else None
            if label == "positive":
                sentiment = 0.6
            elif label == "negative":
                sentiment = -0.6
            elif label == "neutral":
                sentiment = 0.0
        if sentiment is not None:
            sentiment_rollup.setdefault(conv.agent_type, []).append(float(sentiment))

    sentiment_by_agent = [
        SentimentByAgent(
            agent_type=agent,
            avg_sentiment=sum(scores) / len(scores) if scores else None,
            sessions=len(scores),
        )
        for agent, scores in sentiment_rollup.items()
    ]

    result = ProjectAnalytics(
        project_id=project_id,
        date_range=date_range,
        pairing_top=pairing_top,
        pairing_bottom=pairing_bottom,
        role_dynamics=RoleDynamicsSummary(**role_counts),
        handoffs=HandoffStats(
            handoff_count=handoff_count,
            avg_response_minutes=handoff_avg,
            success_rate=handoff_success_rate,
            clarifications_avg=clarifications_avg,
        ),
        impact=ImpactMetrics(
            avg_lines_per_hour=impact_avg_lines,
            median_first_change_minutes=median_first_change,
            total_lines_changed=impact_lines_total,
            sessions_measured=impact_sessions,
        ),
        sentiment_by_agent=sentiment_by_agent,
        influence_flows=influence_flows,
        error_heatmap=error_heatmap,
        thinking_time=ThinkingTimeStats(
            **asdict(
                aggregate_thinking_time(
                    all_thinking_pairs,
                    max_latency_seconds=_THINKING_TIME_MAX_LATENCY_SECONDS,
                )
            )
        ),
    )

    # Cache set
    PROJECT_ANALYTICS_CACHE.set(project_id, date_range, result)
    return result


@router.get("/{project_id}/insights")
async def get_project_insights(
    project_id: UUID,
    date_range: str = Query(
        "30d",
        description="Date range: '7d', '30d', '90d', or 'all'",
        pattern="^(7d|30d|90d|all)$",
    ),
    include_summary: bool = Query(
        True,
        description="Include LLM-generated narrative summary (adds ~1-2s latency)",
    ),
    force_regenerate: bool = Query(
        False,
        description="Force regeneration of all insights (ignores cache)",
    ),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get comprehensive insights for a project.

    This endpoint aggregates conversation-level insights across a project to provide:
    - **Pattern Aggregation**: Top workflow patterns, learning opportunities, anti-patterns
    - **Temporal Trends**: Weekly collaboration quality, agent effectiveness, scope clarity
    - **LLM Summary**: Narrative overview of the project's AI collaboration health

    **Performance Notes:**
    - Uses cached conversation insights when available (instant)
    - On-demand generation for conversations without cached insights (~2-5s per conversation)
    - LLM summary adds ~1-2s latency (disable with include_summary=false)
    - First-time generation may take 1-2 minutes for projects with many conversations

    **Cache Metadata:**
    The response includes freshness indicators:
    - insights_cached: Number of insights from cache
    - insights_generated: Number of insights generated in this request
    - insights_failed: Number of conversations that failed to generate
    - oldest_insight_at: Timestamp of oldest cached insight
    - latest_conversation_at: Timestamp of most recent conversation

    Args:
        project_id: UUID of the project
        date_range: Time filter for conversations ('7d', '30d', '90d', 'all')
        include_summary: Whether to generate LLM narrative summary
        force_regenerate: Force regeneration of all insights (clears cache first)
        session: Database session

    Returns:
        ProjectInsightsResponse with patterns, trends, averages, and optional summary

    Raises:
        HTTPException 404: Project not found
        HTTPException 500: Insights generation failed
    """
    from catsyphon.config import settings
    from catsyphon.db.repositories import ProjectRepository
    from catsyphon.insights import ProjectInsightsGenerator

    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project {project_id} not found"
        )

    # Get project
    project_repo = ProjectRepository(session)
    project = project_repo.get(project_id)

    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project {project_id} not found"
        )

    # Generate insights
    if not settings.openai_api_key and include_summary:
        # Fall back to no summary if no API key
        include_summary = False

    generator = ProjectInsightsGenerator(
        api_key=settings.openai_api_key or "",
        model="gpt-4o-mini",
        max_tokens=500,
    )

    insights = generator.generate(
        project_id=project_id,
        project_name=project.name,
        session=session,
        date_range=date_range,
        include_summary=include_summary,
        workspace_id=workspace_id,
        force_regenerate=force_regenerate,
    )

    return insights


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
    session: Session = Depends(get_db),
) -> list[ProjectSession]:
    """
    List all sessions (conversations) for a project with hierarchical ordering.

    Returns paginated list of conversations in hierarchical order (parents followed by children)
    with lightweight metadata.

    Filters:
    - developer: Filter by developer username
    - outcome: Filter by success/failed status
    - date_from/date_to: Filter by date range
    """
    from datetime import datetime

    project_repo = ProjectRepository(session)

    # Verify project exists
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get workspace ID
    workspace_id = _get_default_workspace_id(session)
    if workspace_id is None:
        return []

    # Build filters
    filters = {"project_id": project_id}

    # Developer filter (need to get developer_id from username)
    if developer:
        dev_query = session.query(Developer.id).filter(Developer.username == developer).first()
        if dev_query:
            filters["developer_id"] = dev_query[0]

    # Outcome filter
    if outcome:
        if outcome == "success":
            filters["success"] = True
        elif outcome == "failed":
            filters["success"] = False

    # Date filters
    if date_from:
        try:
            filters["start_date"] = datetime.fromisoformat(date_from)
        except ValueError:
            pass

    if date_to:
        try:
            filters["end_date"] = datetime.fromisoformat(date_to)
        except ValueError:
            pass

    # Use hierarchical query
    repo = ConversationRepository(session)
    results = repo.get_with_counts_hierarchical(
        workspace_id=workspace_id,
        **filters,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # Build response
    sessions = []
    for conv, msg_count, epoch_count, files_count, child_count, depth in results:
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
                message_count=msg_count,
                files_count=files_count,
                developer=conv.developer.username if conv.developer else None,
                agent_type=conv.agent_type,
                children_count=child_count,
                depth_level=depth,
                parent_conversation_id=conv.parent_conversation_id,
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
