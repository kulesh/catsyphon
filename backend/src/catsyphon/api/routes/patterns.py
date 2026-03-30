"""Workflow pattern library routes."""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    WorkflowPatternExample,
    WorkflowPatternItem,
    WorkflowPatternResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.models.db import Conversation, ConversationInsights

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/workflow", response_model=WorkflowPatternResponse)
def get_workflow_patterns(
    auth: AuthContext = Depends(get_auth_context),
    start_date: Optional[datetime] = Query(
        default=None, description="Filter by conversation start date"
    ),
    end_date: Optional[datetime] = Query(
        default=None, description="Filter by conversation end date"
    ),
    session: Session = Depends(get_db),
) -> WorkflowPatternResponse:
    stmt = (
        select(ConversationInsights, Conversation)
        .join(Conversation, Conversation.id == ConversationInsights.conversation_id)
        .where(Conversation.workspace_id == auth.workspace_id)
    )

    if start_date:
        stmt = stmt.where(Conversation.start_time >= start_date)
    if end_date:
        stmt = stmt.where(Conversation.start_time <= end_date)

    results = session.execute(stmt).all()

    aggregates: dict[str, dict] = {}
    for insights, conversation in results:
        patterns = insights.workflow_patterns or []
        for pattern in patterns:
            entry = aggregates.setdefault(
                pattern,
                {
                    "count": 0,
                    "success": 0,
                    "examples": [],
                },
            )
            entry["count"] += 1
            if conversation.success is True:
                entry["success"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append(
                    WorkflowPatternExample(
                        conversation_id=conversation.id,
                        summary=insights.summary,
                        outcome=(
                            conversation.tags.get("outcome")
                            if conversation.tags
                            else None
                        ),
                    )
                )

    items: list[WorkflowPatternItem] = []
    for pattern, data in sorted(
        aggregates.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        success_rate = (
            round(data["success"] / data["count"], 2) if data["count"] else None
        )
        items.append(
            WorkflowPatternItem(
                pattern=pattern,
                count=data["count"],
                success_rate=success_rate,
                examples=data["examples"],
            )
        )

    return WorkflowPatternResponse(items=items)


@router.get("/agents")
def get_agent_patterns(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Agent delegation pattern analysis from metadata + conversation outcomes."""
    from collections import Counter
    from catsyphon.models.db import ArtifactSnapshot, Conversation

    workspace_id = auth.workspace_id

    # Get all agent_metadata snapshots
    agent_snaps = (
        session.query(ArtifactSnapshot)
        .filter(
            ArtifactSnapshot.workspace_id == workspace_id,
            ArtifactSnapshot.source_type == "agent_metadata",
            ArtifactSnapshot.scan_status == "ok",
        )
        .all()
    )

    # Group by agentType
    type_counts = Counter()
    descriptions = Counter()
    for snap in agent_snaps:
        agent_type = snap.body.get("agentType", "unknown")
        type_counts[agent_type] += 1
        desc = snap.body.get("description", "")
        if desc:
            descriptions[desc] += 1

    # Get conversation-level agent outcomes
    agent_convs = (
        session.query(
            Conversation.conversation_type,
            Conversation.agent_metadata,
            Conversation.success,
            Conversation.parent_conversation_id,
        )
        .filter(
            Conversation.workspace_id == workspace_id,
            Conversation.conversation_type == "agent",
        )
        .all()
    )

    # Track success rates per type from conversation tags/metadata
    type_success: dict[str, dict] = {}
    max_depth = 0

    for conv_type, agent_meta, success, parent_id in agent_convs:
        # Try to get agent type from metadata
        a_type = (agent_meta or {}).get("agent_type", "unknown")
        if a_type not in type_success:
            type_success[a_type] = {"total": 0, "success": 0}
        type_success[a_type]["total"] += 1
        if success is True:
            type_success[a_type]["success"] += 1

    # Compute delegation depth (count children per main conversation)
    depth_counts = Counter()
    parent_ids = {parent_id for _, _, _, parent_id in agent_convs if parent_id}
    for pid in parent_ids:
        child_count = sum(1 for _, _, _, p in agent_convs if p == pid)
        depth_counts[child_count] += 1
        max_depth = max(max_depth, child_count)

    # Build agent_types result from both metadata snapshots and conversation data
    all_types = set(type_counts.keys()) | set(type_success.keys())
    agent_types = []
    for t in sorted(all_types):
        snap_count = type_counts.get(t, 0)
        conv_data = type_success.get(t, {"total": 0, "success": 0})
        total = conv_data["total"]
        success_count = conv_data["success"]
        rate = round(success_count / total * 100, 1) if total > 0 else None
        agent_types.append({
            "type": t,
            "metadata_count": snap_count,
            "conversation_count": total,
            "success_rate": rate,
        })

    # Sort by conversation_count descending
    agent_types.sort(key=lambda x: x["conversation_count"], reverse=True)

    common_descs = [
        {"description": desc, "count": count}
        for desc, count in descriptions.most_common(15)
    ]

    return {
        "agent_types": agent_types,
        "max_delegation_depth": max_depth,
        "total_agent_conversations": len(agent_convs),
        "total_metadata_files": len(agent_snaps),
        "common_descriptions": common_descs,
    }
