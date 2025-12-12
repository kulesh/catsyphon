"""
Plan API routes.

Endpoints for querying and retrieving plan data extracted from conversations.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    PlanDetailResponse,
    PlanListItem,
    PlanListResponse,
    PlanOperationResponse,
    PlanResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository, WorkspaceRepository

router = APIRouter()


def _get_default_workspace_id(session: Session) -> Optional[UUID]:
    """
    Get default workspace ID for API operations.

    This is a temporary helper until proper authentication is implemented.
    Returns the first workspace in the database, or None if no workspaces exist.
    """
    workspace_repo = WorkspaceRepository(session)
    workspaces = workspace_repo.get_all(limit=1)

    if not workspaces:
        return None

    return workspaces[0].id


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
    """
    workspace_id = _get_default_workspace_id(session)
    if workspace_id is None:
        return PlanListResponse(
            items=[], total=0, page=page, page_size=page_size, pages=0
        )

    conv_repo = ConversationRepository(session)

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

    # Query conversations - we need to filter for those with plans
    # For now, fetch all matching conversations and filter client-side
    # Future optimization: Add JSONB index on extra_data->'plans'
    conversations = conv_repo.get_by_filters(
        workspace_id=workspace_id,
        load_relations=True,
        **filters,
    )

    # Extract plans from conversations
    items: list[PlanListItem] = []
    for conv in conversations:
        plans = _extract_plans_from_conversation(conv)
        for plan_data in plans:
            # Apply status filter
            if status and plan_data.get("status") != status:
                continue

            items.append(
                PlanListItem(
                    plan_file_path=plan_data.get("plan_file_path", ""),
                    status=plan_data.get("status", "active"),
                    iteration_count=plan_data.get("iteration_count", 1),
                    conversation_id=conv.id,
                    conversation_start_time=conv.start_time,
                    project_id=conv.project_id,
                    project_name=conv.project.name if conv.project else None,
                )
            )

    # Sort by conversation start time descending (newest first)
    items.sort(key=lambda x: x.conversation_start_time, reverse=True)

    # Paginate
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
    session: Session = Depends(get_db),
) -> list[PlanResponse]:
    """
    Get all plans for a specific conversation.

    This is a convenience endpoint for fetching all plans from a single conversation.
    """
    workspace_id = _get_default_workspace_id(session)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

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
    session: Session = Depends(get_db),
) -> PlanDetailResponse:
    """
    Get detailed plan information including content and execution tracking.

    Args:
        conversation_id: UUID of the conversation containing the plan
        plan_index: Index of the plan in the conversation's plan list (0-based)
    """
    workspace_id = _get_default_workspace_id(session)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

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
