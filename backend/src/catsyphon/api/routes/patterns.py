"""Workflow pattern library routes."""

from datetime import datetime
from typing import Optional

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
