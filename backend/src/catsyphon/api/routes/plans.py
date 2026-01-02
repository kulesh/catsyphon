"""
Plan API routes.

Endpoints for querying and retrieving plan data extracted from conversations.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    PlanDetailResponse,
    PlanListItem,
    PlanListResponse,
    PlanOperationResponse,
    PlanResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository

router = APIRouter()


def _extract_plans_from_conversation(conv: Any) -> list[dict[str, Any]]:
    """Extract plan data from conversation's extra_data."""
    if conv.extra_data is None:
        return []
    return conv.extra_data.get("plans", [])


def _plan_dict_to_response(plan_data: dict[str, Any]) -> PlanResponse:
    """Convert plan dictionary from JSONB to PlanResponse schema."""
    operations = [
        PlanOperationResponse(
            operation_type=op.get("operation_type", ""),
            file_path=op.get("file_path", ""),
            content=op.get("content"),
            old_content=op.get("old_content"),
            new_content=op.get("new_content"),
            timestamp=(
                datetime.fromisoformat(op["timestamp"]) if op.get("timestamp") else None
            ),
            message_index=op.get("message_index", 0),
        )
        for op in plan_data.get("operations", [])
    ]

    return PlanResponse(
        plan_file_path=plan_data.get("plan_file_path", ""),
        initial_content=plan_data.get("initial_content"),
        final_content=plan_data.get("final_content"),
        status=plan_data.get("status", "active"),
        iteration_count=plan_data.get("iteration_count", 1),
        operations=operations,
        entry_message_index=plan_data.get("entry_message_index"),
        exit_message_index=plan_data.get("exit_message_index"),
        related_agent_session_ids=plan_data.get("related_agent_session_ids", []),
    )


@router.get("", response_model=PlanListResponse)
async def list_plans(
    auth: AuthContext = Depends(get_auth_context),
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    status: Optional[str] = Query(
        None, description="Filter by status (active/approved/abandoned)"
    ),
    start_date: Optional[str] = Query(
        None, description="Filter by conversation start date (ISO format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter by conversation end date (ISO format)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_db),
) -> PlanListResponse:
    """
    List all plans extracted from conversations.

    Plans are stored in conversation extra_data and indexed by this endpoint.
    Filters apply to the parent conversation's metadata.

    Requires X-Workspace-Id header.
    """
    workspace_id = auth.workspace_id

    # Build filters for conversation query
    filters: dict[str, Any] = {}
    if start_date:
        try:
            filters["start_date"] = datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            filters["end_date"] = datetime.fromisoformat(
                end_date.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    if project_id:
        filters["project_id"] = project_id

    # ===== OPTIMIZED: Use database-level filtering and pagination =====
    # Query only conversations with plans (JSONB filter) and load minimal data
    from sqlalchemy import func

    from catsyphon.models.db import Conversation, Project

    # Detect database dialect for JSONB/JSON function selection
    bind = session.bind
    if bind is None:
        raise RuntimeError("Session has no bind")
    dialect_name = bind.dialect.name

    # Build base query with only needed columns (not full ORM objects with relations)
    query = (
        session.query(
            Conversation.id,
            Conversation.start_time,
            Conversation.project_id,
            Conversation.extra_data,
            Project.name.label("project_name"),
        )
        .outerjoin(Project, Conversation.project_id == Project.id)
        .filter(Conversation.workspace_id == workspace_id)
        .filter(Conversation.extra_data.isnot(None))
    )

    # Apply JSONB/JSON filter based on database dialect
    if dialect_name == "postgresql":
        # PostgreSQL: Use JSONB operators
        query = query.filter(
            func.jsonb_array_length(
                func.coalesce(Conversation.extra_data["plans"], "[]")
            )
            > 0
        )
    else:
        # SQLite: Use json_array_length with JSON path extraction
        query = query.filter(
            func.json_array_length(
                func.coalesce(
                    func.json_extract(Conversation.extra_data, "$.plans"), "[]"
                )
            )
            > 0
        )

    # Apply date filters
    if filters.get("start_date"):
        query = query.filter(Conversation.start_time >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(Conversation.start_time <= filters["end_date"])
    if filters.get("project_id"):
        query = query.filter(Conversation.project_id == filters["project_id"])

    # Order by start time descending (newest first)
    query = query.order_by(Conversation.start_time.desc())

    # Execute query and extract plans
    conversations_data = query.all()

    # Extract plans from lightweight conversation data
    items: list[PlanListItem] = []
    for conv_id, start_time, proj_id, extra_data, proj_name in conversations_data:
        plans = extra_data.get("plans", []) if extra_data else []
        for plan_data in plans:
            # Apply status filter
            if status and plan_data.get("status") != status:
                continue

            items.append(
                PlanListItem(
                    plan_file_path=plan_data.get("plan_file_path", ""),
                    status=plan_data.get("status", "active"),
                    iteration_count=plan_data.get("iteration_count", 1),
                    conversation_id=conv_id,
                    conversation_start_time=start_time,
                    project_id=proj_id,
                    project_name=proj_name,
                )
            )

    # Paginate (items already sorted by conversation start_time from query)
    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = items[start_idx:end_idx]
    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PlanListResponse(
        items=paginated_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/conversation/{conversation_id}", response_model=list[PlanResponse])
async def get_plans_for_conversation(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[PlanResponse]:
    """
    Get all plans for a specific conversation.

    This is a convenience endpoint for fetching all plans from a single conversation.

    Requires X-Workspace-Id header.
    """
    workspace_id = auth.workspace_id

    conv_repo = ConversationRepository(session)
    conversation = conv_repo.get_with_relations(conversation_id, workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    plans = _extract_plans_from_conversation(conversation)
    return [_plan_dict_to_response(plan_data) for plan_data in plans]


@router.get("/detail/{conversation_id}/{plan_index}", response_model=PlanDetailResponse)
async def get_plan_detail(
    conversation_id: UUID,
    plan_index: int,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> PlanDetailResponse:
    """
    Get detailed plan information including content and execution tracking.

    Args:
        conversation_id: UUID of the conversation containing the plan
        plan_index: Index of the plan in the conversation's plan list (0-based)

    Requires X-Workspace-Id header.
    """
    workspace_id = auth.workspace_id

    conv_repo = ConversationRepository(session)
    conversation = conv_repo.get_with_relations(conversation_id, workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    plans = _extract_plans_from_conversation(conversation)
    if plan_index < 0 or plan_index >= len(plans):
        raise HTTPException(
            status_code=404,
            detail=f"Plan index {plan_index} not found. "
            f"Conversation has {len(plans)} plan(s).",
        )

    plan_data = plans[plan_index]

    # Convert operations
    operations = [
        PlanOperationResponse(
            operation_type=op.get("operation_type", ""),
            file_path=op.get("file_path", ""),
            content=op.get("content"),
            old_content=op.get("old_content"),
            new_content=op.get("new_content"),
            timestamp=(
                datetime.fromisoformat(op["timestamp"]) if op.get("timestamp") else None
            ),
            message_index=op.get("message_index", 0),
        )
        for op in plan_data.get("operations", [])
    ]

    return PlanDetailResponse(
        plan_file_path=plan_data.get("plan_file_path", ""),
        initial_content=plan_data.get("initial_content"),
        final_content=plan_data.get("final_content"),
        status=plan_data.get("status", "active"),
        iteration_count=plan_data.get("iteration_count", 1),
        operations=operations,
        entry_message_index=plan_data.get("entry_message_index"),
        exit_message_index=plan_data.get("exit_message_index"),
        related_agent_session_ids=plan_data.get("related_agent_session_ids", []),
        conversation_id=conversation.id,
        conversation_start_time=conversation.start_time,
        project_id=conversation.project_id,
        project_name=conversation.project.name if conversation.project else None,
        executed_steps=[],  # Future enhancement
        execution_progress=None,
    )
