"""
Statistics API routes.

Endpoints for querying analytics and statistics about conversations.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

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
from catsyphon.models.db import ArtifactSnapshot, Conversation, Message

logger = logging.getLogger(__name__)

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


# ── Cost Analytics ──────────────────────────────────────────────────


def _period_to_days(period: str) -> int:
    return {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)


@router.get("/costs")
async def get_workspace_costs(
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Workspace-level cost summary from token analytics + message data."""
    from catsyphon.llm.pricing import estimate_cost_from_model

    workspace_id = auth.workspace_id
    days = _period_to_days(period)

    # Source 1: Artifact snapshot for pre-aggregated totals
    snapshot = (
        session.query(ArtifactSnapshot)
        .filter(
            ArtifactSnapshot.workspace_id == workspace_id,
            ArtifactSnapshot.source_type == "token_analytics",
            ArtifactSnapshot.scan_status == "ok",
        )
        .first()
    )

    cost_by_model: dict[str, float] = {}
    daily_costs: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0
    total_cache_read = 0

    if snapshot and snapshot.body:
        body = snapshot.body
        # Aggregate from dailyModelTokens within period
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        for day_entry in body.get("dailyModelTokens", []):
            date_str = day_entry.get("date", "")
            if date_str < cutoff_date:
                continue
            day_cost = 0.0
            for model, tokens in day_entry.get("tokensByModel", {}).items():
                inp = tokens.get("inputTokens", 0)
                out = tokens.get("outputTokens", 0)
                cache = tokens.get("cacheReadInputTokens", 0)
                total_input += inp
                total_output += out
                total_cache_read += cache
                cost = estimate_cost_from_model(model, inp, out)
                if cost is not None:
                    cost_by_model[model] = cost_by_model.get(model, 0.0) + cost
                    day_cost += cost
            daily_costs.append({"date": date_str, "cost": round(day_cost, 4)})

    total_cost = round(sum(cost_by_model.values()), 4)
    cost_by_model = {k: round(v, 4) for k, v in sorted(cost_by_model.items(), key=lambda x: -x[1])}
    top_model = next(iter(cost_by_model), None)
    total_tokens = total_input + total_output
    cache_ratio = round(total_cache_read / total_input, 4) if total_input > 0 else 0.0

    # Trend: compare first half vs second half of period
    trend_pct = None
    if len(daily_costs) >= 4:
        mid = len(daily_costs) // 2
        first_half = sum(d["cost"] for d in daily_costs[:mid])
        second_half = sum(d["cost"] for d in daily_costs[mid:])
        if first_half > 0:
            trend_pct = round((second_half - first_half) / first_half * 100, 1)

    return {
        "total_cost_usd": total_cost,
        "cost_by_model": cost_by_model,
        "daily_costs": daily_costs,
        "cache_ratio": cache_ratio,
        "top_model": top_model,
        "trend_pct": trend_pct,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "period": period,
    }


# ── Activity Timeline ───────────────────────────────────────────────


@router.get("/timeline")
async def get_activity_timeline(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Cross-project activity timeline from global history + heatmap data."""
    workspace_id = auth.workspace_id
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    # Get global_history artifact snapshots
    history_snapshots = (
        session.query(ArtifactSnapshot)
        .filter(
            ArtifactSnapshot.workspace_id == workspace_id,
            ArtifactSnapshot.source_type == "global_history",
            ArtifactSnapshot.scan_status == "ok",
        )
        .all()
    )

    # Merge entries from all history snapshots
    raw_entries: list[dict[str, Any]] = []
    for snap in history_snapshots:
        source_label = "codex" if "codex" in snap.source_path else "claude"
        for entry in snap.body.get("latest_entries", []):
            ts = entry.get("timestamp", 0)
            if ts >= cutoff_ms:
                raw_entries.append({**entry, "_source": source_label})

    # Sort by timestamp descending, limit
    raw_entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    raw_entries = raw_entries[:limit]

    # Link sessionIds to conversations
    session_ids = {e.get("sessionId") for e in raw_entries if e.get("sessionId")}
    conv_map: dict[str, dict] = {}
    if session_ids:
        convs = (
            session.query(Conversation.collector_session_id, Conversation.id, Conversation.conversation_type)
            .filter(
                Conversation.workspace_id == workspace_id,
                Conversation.collector_session_id.in_(session_ids),
            )
            .all()
        )
        for csid, cid, ctype in convs:
            conv_map[csid] = {"id": str(cid), "type": ctype}

    entries = []
    prev_project = None
    for entry in raw_entries:
        project = entry.get("project")
        sid = entry.get("sessionId")
        linked = conv_map.get(sid, {})
        is_switch = prev_project is not None and project != prev_project
        entries.append({
            "display": entry.get("display", ""),
            "timestamp": entry.get("timestamp"),
            "project": project,
            "session_id": sid,
            "conversation_id": linked.get("id"),
            "conversation_type": linked.get("type"),
            "source": entry.get("_source"),
            "project_switch": is_switch,
        })
        prev_project = project

    # Heatmap from token_analytics hourCounts
    heatmap: list[dict[str, int]] = []
    token_snap = (
        session.query(ArtifactSnapshot)
        .filter(
            ArtifactSnapshot.workspace_id == workspace_id,
            ArtifactSnapshot.source_type == "token_analytics",
            ArtifactSnapshot.scan_status == "ok",
        )
        .first()
    )
    if token_snap and token_snap.body:
        hour_counts = token_snap.body.get("hourCounts", {})
        for hour_str, count in hour_counts.items():
            try:
                heatmap.append({"hour": int(hour_str), "count": count})
            except (ValueError, TypeError):
                pass

    return {
        "entries": entries,
        "heatmap": heatmap,
        "total_entries": len(entries),
        "period_days": days,
    }
