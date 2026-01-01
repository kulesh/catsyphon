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

from catsyphon.analytics.cache import PROJECT_ANALYTICS_CACHE
from catsyphon.analytics.thinking_time import (
    aggregate_thinking_time,
    pair_user_assistant,
)
from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    ErrorBucket,
    HandoffStats,
    ImpactMetrics,
    InfluenceFlow,
    PairingEffectivenessPair,
    ProjectAnalytics,
    ProjectFileAggregation,
    ProjectSession,
    ProjectSessionsResponse,
    ProjectStats,
    RoleDynamicsSummary,
    SentimentByAgent,
    SentimentTimelinePoint,
    ThinkingTimeStats,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    ProjectRepository,
)
from catsyphon.models.db import (
    Conversation,
    Developer,
    Epoch,
    FileTouched,
    IngestionJob,
    Message,
)

_THINKING_TIME_MAX_LATENCY_SECONDS = 2 * 60 * 60  # 2 hours

router = APIRouter()


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
    auth: AuthContext = Depends(get_auth_context),
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

    # Verify project exists and belongs to workspace
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)
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

    # Build base filter for conversations
    conv_filter = Conversation.project_id == project_id
    if cutoff_date:
        conv_filter = conv_filter & (Conversation.start_time >= cutoff_date)

    # ===== DATABASE AGGREGATIONS (avoid loading all conversations) =====

    # Session count using database aggregation
    session_count = (
        session.query(func.count(Conversation.id))
        .filter(conv_filter)
        .scalar()
        or 0
    )

    if session_count == 0:
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

    # Message count aggregation
    total_messages = (
        session.query(func.count(Message.id))
        .join(Conversation)
        .filter(conv_filter)
        .scalar()
        or 0
    )

    # Files changed aggregation
    total_files = (
        session.query(FileTouched.file_path)
        .join(Conversation)
        .filter(conv_filter)
        .distinct()
        .count()
    )

    # Success rate using database aggregation
    success_count = (
        session.query(func.count(Conversation.id))
        .filter(conv_filter)
        .filter(Conversation.success == True)  # noqa: E712
        .scalar()
        or 0
    )
    failed_count = (
        session.query(func.count(Conversation.id))
        .filter(conv_filter)
        .filter(Conversation.success == False)  # noqa: E712
        .scalar()
        or 0
    )
    total_with_outcome = success_count + failed_count
    success_rate = success_count / total_with_outcome if total_with_outcome > 0 else None

    # Average duration using database aggregation
    # Extract seconds from end_time - start_time
    from sqlalchemy import extract

    # Query for average duration where both times exist
    avg_duration_result = (
        session.query(
            func.avg(
                extract("epoch", Conversation.end_time)
                - extract("epoch", Conversation.start_time)
            )
        )
        .filter(conv_filter)
        .filter(Conversation.start_time.isnot(None))
        .filter(Conversation.end_time.isnot(None))
        .scalar()
    )
    avg_duration = float(avg_duration_result) if avg_duration_result else None

    # Temporal bounds using database aggregation
    temporal_bounds = (
        session.query(
            func.min(Conversation.start_time).label("first_session"),
            func.max(Conversation.end_time).label("last_session"),
        )
        .filter(conv_filter)
        .first()
    )
    first_session_at = temporal_bounds.first_session if temporal_bounds else None
    last_session_at = temporal_bounds.last_session if temporal_bounds else None

    # Developer participation using database aggregation
    developer_ids_result = (
        session.query(Conversation.developer_id)
        .filter(conv_filter)
        .filter(Conversation.developer_id.isnot(None))
        .distinct()
        .all()
    )
    developer_ids = {d[0] for d in developer_ids_result}
    developers = (
        session.query(Developer.username).filter(Developer.id.in_(developer_ids)).all()
        if developer_ids
        else []
    )
    developer_names = [d.username for d in developers]

    # ===== TAGS AGGREGATION (limited fetch for top features/problems) =====
    # Fetch only tags column for conversations (much lighter than full objects)
    tags_results = (
        session.query(Conversation.tags)
        .filter(conv_filter)
        .filter(Conversation.tags.isnot(None))
        .all()
    )

    all_features: dict[str, int] = {}
    all_problems: dict[str, int] = {}
    tool_usage: dict[str, int] = {}

    for (tags,) in tags_results:
        if not isinstance(tags, dict):
            continue

        # Extract features
        if "features" in tags and isinstance(tags["features"], list):
            for feature in tags["features"]:
                all_features[feature] = all_features.get(feature, 0) + 1

        # Extract problems
        if "problems" in tags and isinstance(tags["problems"], list):
            for problem in tags["problems"]:
                all_problems[problem] = all_problems.get(problem, 0) + 1

        # Extract tool usage
        if "tools_used" in tags and isinstance(tags["tools_used"], list):
            for tool in tags["tools_used"]:
                tool_usage[tool] = tool_usage.get(tool, 0) + 1

    # Get top 10 features and problems
    top_features = sorted(all_features.items(), key=lambda x: x[1], reverse=True)[:10]
    top_problems = sorted(all_problems.items(), key=lambda x: x[1], reverse=True)[:10]

    # ===== SENTIMENT TIMELINE (using aggregation) =====
    # Get conversation IDs for epoch query
    conversation_ids = (
        session.query(Conversation.id)
        .filter(conv_filter)
        .all()
    )
    conversation_id_list = [c[0] for c in conversation_ids]

    sentiment_timeline: list[SentimentTimelinePoint] = []
    if conversation_id_list:
        # Use database aggregation for sentiment by date
        # Use func.date() for SQLite compatibility (returns string directly)
        date_expr = func.date(Epoch.start_time)

        sentiment_by_date = (
            session.query(
                date_expr.label("date_str"),
                func.avg(Epoch.sentiment_score).label("avg_sentiment"),
                func.count(func.distinct(Epoch.conversation_id)).label("session_count"),
            )
            .filter(Epoch.conversation_id.in_(conversation_id_list))
            .filter(Epoch.sentiment_score.isnot(None))
            .filter(Epoch.start_time.isnot(None))
            .group_by(date_expr)
            .order_by(date_expr)
            .all()
        )

        for row in sentiment_by_date:
            # func.date() returns string in both SQLite and PostgreSQL
            date_str = str(row.date_str) if row.date_str else ""

            sentiment_timeline.append(
                SentimentTimelinePoint(
                    date=date_str,
                    avg_sentiment=float(row.avg_sentiment) if row.avg_sentiment else 0.0,
                    session_count=row.session_count or 0,
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
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
    date_range: Optional[str] = Query(
        None, description="Date range filter: 7d, 30d, 90d, or all (default: all)"
    ),
) -> ProjectAnalytics:
    """
    Advanced analytics for a project focused on pairing effectiveness and handoffs.
    """
    import statistics
    from datetime import datetime, timedelta

    # Cache lookup
    cached = PROJECT_ANALYTICS_CACHE.get(project_id, date_range)
    if cached:
        return cached

    project_repo = ProjectRepository(session)
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)
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

    # Build base filter
    conv_filter = Conversation.project_id == project_id
    if cutoff_date:
        conv_filter = conv_filter & (Conversation.start_time >= cutoff_date)

    # Load only essential conversation columns (not full objects)
    # This significantly reduces memory usage
    from sqlalchemy.orm import load_only

    conv_query = session.query(Conversation).filter(conv_filter).options(
        load_only(
            Conversation.id,
            Conversation.developer_id,
            Conversation.agent_type,
            Conversation.start_time,
            Conversation.end_time,
            Conversation.success,
            Conversation.parent_conversation_id,
            Conversation.tags,
        )
    )
    conversations = conv_query.all()

    if not conversations:
        return ProjectAnalytics(project_id=project_id, date_range=date_range)

    conv_ids = [c.id for c in conversations]

    # Developers lookup
    dev_ids = {c.developer_id for c in conversations if c.developer_id}
    dev_map = (
        {
            d.id: d.username
            for d in session.query(Developer).filter(Developer.id.in_(dev_ids)).all()
        }
        if dev_ids
        else {}
    )

    # ===== DATABASE AGGREGATIONS FOR MESSAGES =====
    # Instead of loading all messages, aggregate counts in database
    from sqlalchemy import case

    msg_agg = (
        session.query(
            Message.conversation_id,
            func.count(case((Message.role == "assistant", 1))).label("assistant_count"),
            func.count(case((Message.role == "user", 1))).label("user_count"),
            func.count(
                case((Message.role == "assistant", Message.tool_calls))
            ).label("assistant_tool_count"),
            func.count(case((Message.role == "user", Message.tool_calls))).label(
                "user_tool_count"
            ),
        )
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .all()
    )
    msg_counts_by_conv: dict[UUID, dict[str, int]] = {
        row.conversation_id: {
            "assistant": row.assistant_count or 0,
            "user": row.user_count or 0,
            "assistant_tool": row.assistant_tool_count or 0,
            "user_tool": row.user_tool_count or 0,
        }
        for row in msg_agg
    }

    # ===== DATABASE AGGREGATIONS FOR FILES =====
    # Aggregate file stats per conversation in database
    file_agg = (
        session.query(
            FileTouched.conversation_id,
            func.sum(FileTouched.lines_added).label("total_added"),
            func.sum(FileTouched.lines_deleted).label("total_deleted"),
            func.min(FileTouched.timestamp).label("first_change"),
        )
        .filter(FileTouched.conversation_id.in_(conv_ids))
        .group_by(FileTouched.conversation_id)
        .all()
    )
    file_stats_by_conv: dict[UUID, dict[str, Any]] = {
        row.conversation_id: {
            "lines_added": row.total_added or 0,
            "lines_deleted": row.total_deleted or 0,
            "first_change": row.first_change,
        }
        for row in file_agg
    }

    # ===== THINKING TIME (load minimal message data, capped for performance) =====
    # Limit to most recent 100 conversations to cap memory usage
    thinking_conv_ids = conv_ids[-100:] if len(conv_ids) > 100 else conv_ids
    thinking_messages = (
        session.query(
            Message.conversation_id,
            Message.role,
            Message.timestamp,
            Message.tool_calls,
        )
        .filter(Message.conversation_id.in_(thinking_conv_ids))
        .filter(Message.role.in_(["user", "assistant"]))
        .order_by(Message.timestamp)
        .all()
    )

    # Group by conversation and compute thinking pairs
    all_thinking_pairs = []
    msgs_for_thinking: dict[UUID, list] = {}
    for row in thinking_messages:
        msgs_for_thinking.setdefault(row.conversation_id, []).append(row)

    # Create lightweight message-like objects for pair_user_assistant
    class LightMessage:
        """Minimal message object for thinking pair calculation."""

        def __init__(
            self, role: str, timestamp: datetime, tool_calls: Optional[Any]
        ) -> None:
            self.role = role
            self.timestamp = timestamp
            self.tool_calls = tool_calls
            self.thinking_content = None

    for conv_id, msg_rows in msgs_for_thinking.items():
        light_msgs = [
            LightMessage(row.role, row.timestamp, row.tool_calls) for row in msg_rows
        ]
        all_thinking_pairs.extend(pair_user_assistant(light_msgs))  # type: ignore

    # Pairing effectiveness aggregation
    pair_buckets: dict[tuple[Optional[UUID], str], dict[str, Any]] = {}
    role_counts = {"agent_led": 0, "dev_led": 0, "co_pilot": 0}
    handoff_latencies: list[float] = []
    handoff_successes = 0
    handoff_clarifications: list[int] = []
    impact_lines_total = 0
    impact_sessions = 0
    first_change_latencies: list[float] = []

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

        # Lines and first-change latency (using pre-aggregated data)
        conv_file_stats = file_stats_by_conv.get(conv.id, {})
        lines_changed = (
            conv_file_stats.get("lines_added", 0)
            + conv_file_stats.get("lines_deleted", 0)
        )
        impact_lines_total += lines_changed
        if lines_changed > 0:
            impact_sessions += 1
        bucket["lines"] += lines_changed

        first_change_ts = conv_file_stats.get("first_change")
        if first_change_ts and conv.start_time:
            latency_minutes = max(
                (first_change_ts - conv.start_time).total_seconds() / 60.0, 0.0
            )
            bucket["first_change_minutes_total"] += latency_minutes
            bucket["first_change_count"] += 1
            first_change_latencies.append(latency_minutes)

        # Role dynamics (using pre-aggregated counts)
        msg_stats = msg_counts_by_conv.get(conv.id, {})
        assistant_msgs = msg_stats.get("assistant", 0)
        user_msgs = msg_stats.get("user", 0)
        total_msgs = assistant_msgs + user_msgs
        assistant_tool_calls = msg_stats.get("assistant_tool", 0)
        user_tool_calls = msg_stats.get("user_tool", 0)
        assistant_ratio = assistant_msgs / total_msgs if total_msgs else 0.5
        role = _classify_role_dynamics(
            assistant_ratio, assistant_tool_calls, user_tool_calls
        )
        role_counts[role] += 1

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
                # Clarifications: count user messages in parent between parent start and agent start
                # Use database count query instead of loading all messages
                clarifications = (
                    session.query(func.count(Message.id))
                    .filter(Message.conversation_id == parent.id)
                    .filter(Message.role == "user")
                    .filter(Message.timestamp >= parent.start_time)
                    .filter(Message.timestamp <= conv.start_time)
                    .scalar()
                    or 0
                )
                handoff_clarifications.append(clarifications)

    # Influence flows (file introduction -> later adopter)
    # Load only needed columns for influence calculation (file_path, conversation_id, timestamp)
    file_touches = (
        session.query(
            FileTouched.file_path,
            FileTouched.conversation_id,
            FileTouched.timestamp,
        )
        .filter(FileTouched.conversation_id.in_(conv_ids))
        .filter(FileTouched.timestamp.isnot(None))
        .order_by(FileTouched.timestamp)
        .all()
    )

    influence_counts: dict[tuple[str, str], int] = {}
    first_touch: dict[str, tuple[str, datetime]] = {}
    for file_path, conv_id, timestamp in file_touches:
        # Identify actor string
        conv = conversation_lookup.get(conv_id)
        actor = "unknown"
        if conv:
            dev_name = dev_map.get(conv.developer_id) if conv.developer_id else None
            actor = dev_name or conv.agent_type or "unknown"

        existing = first_touch.get(file_path)
        if existing:
            introducer, _ = existing
            if introducer != actor:
                influence_counts[(introducer, actor)] = (
                    influence_counts.get((introducer, actor), 0) + 1
                )
        else:
            first_touch[file_path] = (actor, timestamp)

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
        error_counts[(agent_type, category)] = (
            error_counts.get((agent_type, category), 0) + 1
        )

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
            data["lines"] / data["duration_hours"]
            if data["duration_hours"] > 0
            else None
        )
        avg_first_change = (
            data["first_change_minutes_total"] / data["first_change_count"]
            if data["first_change_count"] > 0
            else None
        )
        throughput_component = (
            min(lines_per_hour / 200.0, 1.0) if lines_per_hour else 0.0
        )
        latency_component = (
            max(0.0, 1 - (avg_first_change / 60.0))
            if avg_first_change is not None
            else 0.5
        )
        score = (
            (success_rate or 0.5) * 0.6
            + throughput_component * 0.3
            + latency_component * 0.1
        )

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
    handoff_success_rate = handoff_successes / handoff_count if handoff_count else None
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
        sentiment = (
            conv.tags.get("sentiment_score") if isinstance(conv.tags, dict) else None
        )
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
    auth: AuthContext = Depends(get_auth_context),
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

    # Get project with workspace validation
    project_repo = ProjectRepository(session)
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

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
        workspace_id=auth.workspace_id,
        force_regenerate=force_regenerate,
    )

    return insights


@router.get("/{project_id}/health-report")
async def get_project_health_report(
    project_id: UUID,
    date_range: str = Query(
        "30d",
        description="Date range: '7d', '30d', '90d', or 'all'",
        pattern="^(7d|30d|90d|all)$",
    ),
    developer: Optional[str] = Query(
        None,
        description="Filter by developer username",
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get an evidence-based health report for a project's AI collaboration.

    Returns:
    - **Hero**: Overall health score with plain English summary
    - **Diagnosis**: Strengths and gaps based on metrics
    - **Evidence**: Real session examples showing what works and what doesn't
    - **Recommendations**: AI-generated advice backed by data from your sessions

    Args:
        project_id: UUID of the project
        date_range: Time filter for conversations ('7d', '30d', '90d', 'all')
        developer: Optional filter by developer username
        session: Database session

    Returns:
        HealthReportResponse with score, diagnosis, evidence, and recommendations
    """
    from catsyphon.config import settings
    from catsyphon.db.repositories import ProjectRepository
    from catsyphon.insights import HealthReportGenerator

    # Verify project exists and belongs to workspace
    project_repo = ProjectRepository(session)
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)

    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Generate health report
    generator = HealthReportGenerator(
        api_key=settings.openai_api_key or "",
        model="gpt-4o-mini",
        max_tokens=500,
    )

    report = generator.generate(
        project_id=project_id,
        session=session,
        workspace_id=auth.workspace_id,
        date_range=date_range,
        developer_filter=developer,
    )

    return report


@router.get("/{project_id}/sessions", response_model=ProjectSessionsResponse)
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
    sort_by: str = Query(
        "last_activity",
        description="Sort by: last_activity, start_time, message_count",
    ),
    order: str = Query("desc", description="Sort order: asc, desc"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ProjectSessionsResponse:
    """
    List all sessions (conversations) for a project with hierarchical ordering.

    Returns paginated list of conversations in hierarchical order (parents followed by children)
    with lightweight metadata. Default sort is by last_activity (most recent first) with
    secondary sort by message_count (more content first).

    Filters:
    - developer: Filter by developer username
    - outcome: Filter by success/failed status
    - date_from/date_to: Filter by date range
    - sort_by: Column to sort by (last_activity, start_time, message_count)
    - order: Sort direction (asc, desc)
    """
    from datetime import datetime

    project_repo = ProjectRepository(session)

    # Verify project exists and belongs to workspace
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build filters
    filters = {"project_id": project_id}

    # Developer filter (need to get developer_id from username)
    if developer:
        dev_query = (
            session.query(Developer.id).filter(Developer.username == developer).first()
        )
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

    # Get total count for pagination
    total = repo.count_by_filters(workspace_id=auth.workspace_id, **filters)

    results = repo.get_with_counts_hierarchical(
        workspace_id=auth.workspace_id,
        **filters,
        order_by=sort_by,
        order_dir=order,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # Build response
    # Tuple order: (conv, msg_count, epoch_count, files_count, children_count, last_activity, depth)
    sessions = []
    for conv, msg_count, epoch_count, files_count, child_count, last_activity, depth in results:
        duration_seconds = None
        if conv.end_time and conv.start_time:
            duration_seconds = int((conv.end_time - conv.start_time).total_seconds())

        # Get plan count and status from extra_data
        plan_count = 0
        plan_status = None
        if conv.extra_data:
            plans = conv.extra_data.get("plans", [])
            if isinstance(plans, list):
                plan_count = len(plans)
                if plan_count > 0:
                    # Determine status: approved > active > abandoned
                    has_approved = any(p.get("status") == "approved" for p in plans)
                    has_active = any(p.get("status") == "active" for p in plans)
                    plan_status = "approved" if has_approved else "active" if has_active else "abandoned"

        sessions.append(
            ProjectSession(
                id=conv.id,
                start_time=conv.start_time,
                end_time=conv.end_time,
                last_activity=last_activity,
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
                plan_count=plan_count,
                plan_status=plan_status,
            )
        )

    return ProjectSessionsResponse(
        items=sessions,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,  # Ceiling division
    )


@router.get("/{project_id}/files", response_model=list[ProjectFileAggregation])
async def get_project_files(
    project_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
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

    # Verify project exists and belongs to workspace
    project = project_repo.get_by_id_workspace(project_id, auth.workspace_id)
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

    # ===== FIX N+1 QUERY: Batch fetch all file_path -> session_ids mapping =====
    # Single query to get all (file_path, conversation_id) pairs for this project
    all_file_sessions = (
        session.query(FileTouched.file_path, FileTouched.conversation_id)
        .join(Conversation, FileTouched.conversation_id == Conversation.id)
        .filter(Conversation.project_id == project_id)
        .distinct()
        .all()
    )

    # Build mapping from file_path to list of session_ids
    file_to_sessions: dict[str, list[str]] = {}
    for file_path, conv_id in all_file_sessions:
        file_to_sessions.setdefault(file_path, []).append(str(conv_id))

    files = []
    for row in results:
        # Use pre-fetched mapping instead of N+1 queries
        session_id_list = file_to_sessions.get(row.file_path, [])

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
