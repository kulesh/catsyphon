"""REST endpoints for supplemental artifact data sources."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.db.connection import get_db
from catsyphon.scanner.repository import ArtifactRepository

logger = logging.getLogger(__name__)

router = APIRouter()

SOURCE_DESCRIPTIONS = {
    "token_analytics": "Claude Code token usage and cost analytics",
    "project_memory": "Claude Code per-project AI memory files",
    "global_history": "Cross-project prompt history timeline",
    "codex_sqlite": "Codex CLI structured metadata (threads, tools, jobs)",
    "standalone_plans": "Claude Code standalone plan files",
    "settings_config": "Tool configuration (settings.json, config.toml)",
    "file_history": "Per-session file modification history",
    "agent_metadata": "Sub-agent delegation metadata",
    "shell_snapshots": "Shell environment snapshots",
    "plugin_inventory": "Installed plugins and skills",
}


@router.get("/sources")
def list_sources(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all artifact source types with current scan status."""
    repo = ArtifactRepository(session)
    stats = {s["source_type"]: s for s in repo.get_all_source_stats(auth.workspace_id)}

    result = []
    for source_type, description in SOURCE_DESCRIPTIONS.items():
        s = stats.get(source_type, {})
        result.append({
            "source_type": source_type,
            "description": description,
            "snapshot_count": s.get("snapshot_count", 0),
            "last_scanned_at": s.get("last_scanned_at"),
        })
    return result


@router.get("/settings_config/impact")
def get_settings_impact(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Correlate settings changes with conversation outcome metrics."""
    from catsyphon.models.db import ArtifactHistory, Conversation

    workspace_id = auth.workspace_id

    # Get config change history
    changes = (
        session.query(ArtifactHistory)
        .filter(
            ArtifactHistory.workspace_id == workspace_id,
            ArtifactHistory.source_type == "settings_config",
        )
        .order_by(ArtifactHistory.detected_at.desc())
        .limit(20)
        .all()
    )

    if not changes:
        return {"changes": []}

    result = []
    for change in changes:
        detected_at = change.detected_at
        if not detected_at:
            continue

        # 7-day windows before and after
        before_start = detected_at - timedelta(days=7)
        after_end = detected_at + timedelta(days=7)

        def _window_metrics(start, end):
            from sqlalchemy import func as sqla_func
            q = session.query(
                sqla_func.count(Conversation.id).label("session_count"),
                sqla_func.avg(Conversation.message_count).label("avg_messages"),
            ).filter(
                Conversation.workspace_id == workspace_id,
                Conversation.start_time >= start,
                Conversation.start_time < end,
            )
            row = q.first()
            count = row.session_count if row else 0
            avg_msg = round(float(row.avg_messages or 0), 1) if row and row.avg_messages else 0

            # Success rate
            success_q = session.query(sqla_func.count(Conversation.id)).filter(
                Conversation.workspace_id == workspace_id,
                Conversation.start_time >= start,
                Conversation.start_time < end,
                Conversation.success == True,
            ).scalar() or 0
            rate = round(success_q / count * 100, 1) if count > 0 else None

            return {"session_count": count, "avg_messages": avg_msg, "success_rate": rate}

        before_metrics = _window_metrics(before_start, detected_at)
        after_metrics = _window_metrics(detected_at, after_end)

        result.append({
            "detected_at": detected_at.isoformat() if detected_at else None,
            "change_type": change.change_type,
            "diff_summary": change.diff_summary,
            "before": before_metrics,
            "after": after_metrics,
        })

    return {"changes": result}


@router.get("/{source_type}")
def get_source_snapshots(
    source_type: str,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current snapshot(s) for a data source."""
    if source_type not in SOURCE_DESCRIPTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown source type: {source_type}")

    repo = ArtifactRepository(session)
    snapshots = repo.get_snapshots_by_source(auth.workspace_id, source_type)

    return {
        "source_type": source_type,
        "description": SOURCE_DESCRIPTIONS[source_type],
        "snapshots": [
            {
                "id": str(s.id),
                "source_path": s.source_path,
                "body": s.body,
                "content_hash": s.content_hash,
                "file_size_bytes": s.file_size_bytes,
                "scan_status": s.scan_status,
                "scanned_at": s.scanned_at.isoformat() if s.scanned_at else None,
            }
            for s in snapshots
        ],
    }


@router.get("/{source_type}/history")
def get_source_history(
    source_type: str,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Get change history for a data source (paginated)."""
    if source_type not in SOURCE_DESCRIPTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown source type: {source_type}")

    repo = ArtifactRepository(session)
    items, total = repo.get_history(auth.workspace_id, source_type, limit=limit, offset=offset)

    return {
        "source_type": source_type,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(h.id),
                "change_type": h.change_type,
                "diff_summary": h.diff_summary,
                "prev_content_hash": h.prev_content_hash,
                "new_content_hash": h.new_content_hash,
                "detected_at": h.detected_at.isoformat() if h.detected_at else None,
            }
            for h in items
        ],
    }


@router.get("/stats")
def get_scanner_health() -> dict[str, Any]:
    """Scanner health and statistics."""
    from catsyphon.scanner import get_scanner_stats

    return get_scanner_stats()


@router.post("/scan")
def trigger_scan() -> dict[str, bool]:
    """Trigger an immediate scan cycle."""
    from catsyphon.scanner.worker import get_scanner

    scanner = get_scanner()
    if scanner is None:
        raise HTTPException(status_code=503, detail="Scanner not running")
    scanner.trigger_scan()
    return {"triggered": True}
