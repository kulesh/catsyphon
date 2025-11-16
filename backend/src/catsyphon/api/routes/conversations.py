"""
Conversation API routes.

Endpoints for querying and retrieving conversation data.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    ConversationDetail,
    ConversationListItem,
    ConversationListResponse,
    MessageResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository, MessageRepository, WorkspaceRepository
from catsyphon.models.db import Conversation

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


def _conversation_to_list_item(
    conv: Conversation,
    message_count: Optional[int] = None,
    epoch_count: Optional[int] = None,
    files_count: Optional[int] = None,
) -> ConversationListItem:
    """
    Convert Conversation model to ConversationListItem schema.

    Args:
        conv: Conversation model instance
        message_count: Pre-computed message count (from SQL aggregation)
        epoch_count: Pre-computed epoch count (from SQL aggregation)
        files_count: Pre-computed files count (from SQL aggregation)

    Returns:
        ConversationListItem schema

    Note:
        If counts are not provided, they will be computed from loaded relationships.
        For better performance, use SQL aggregation via get_with_counts().
    """
    item = ConversationListItem.model_validate(conv)

    # Use pre-computed counts if provided, otherwise compute from relationships
    if message_count is not None:
        item.message_count = message_count
    else:
        item.message_count = len(conv.messages) if conv.messages else 0

    if epoch_count is not None:
        item.epoch_count = epoch_count
    else:
        item.epoch_count = len(conv.epochs) if conv.epochs else 0

    if files_count is not None:
        item.files_count = files_count
    else:
        item.files_count = len(conv.files_touched) if conv.files_touched else 0

    return item


def _conversation_to_detail(conv: Conversation) -> ConversationDetail:
    """Convert Conversation model to ConversationDetail schema."""
    # Convert to list item first
    base = _conversation_to_list_item(conv)

    # Add related data
    return ConversationDetail(
        **base.model_dump(),
        messages=[MessageResponse.model_validate(m) for m in (conv.messages or [])],
        epochs=conv.epochs or [],
        files_touched=conv.files_touched or [],
        conversation_tags=conv.conversation_tags or [],
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    developer_id: Optional[UUID] = Query(None, description="Filter by developer ID"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(
        None, description="Filter by start date (ISO format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter by end date (ISO format)"
    ),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    session: Session = Depends(get_db),
) -> ConversationListResponse:
    """
    List conversations with optional filters.

    Returns paginated list of conversations with basic metadata.
    For full conversation details including messages, use GET /conversations/{id}.
    """
    # Parse date filters first (for validation before workspace check)
    filters = {}
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

    repo = ConversationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    # If no workspace exists, return empty results
    if workspace_id is None:
        return ConversationListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
        )

    # Build remaining filters
    if project_id:
        filters["project_id"] = project_id
    if developer_id:
        filters["developer_id"] = developer_id
    if agent_type:
        filters["agent_type"] = agent_type
    if status:
        filters["status"] = status
    if success is not None:
        filters["success"] = success

    # Get total count for pagination
    total = repo.count_by_filters(workspace_id=workspace_id, **filters)

    # Get conversations WITH counts (efficient SQL aggregation)
    results = repo.get_with_counts(
        workspace_id=workspace_id,
        **filters,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # Convert to response schema using pre-computed counts
    items = [
        _conversation_to_list_item(
            conv,
            message_count=msg_count,
            epoch_count=epoch_count,
            files_count=files_count,
        )
        for conv, msg_count, epoch_count, files_count in results
    ]

    return ConversationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,  # Ceiling division
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    session: Session = Depends(get_db),
) -> ConversationDetail:
    """
    Get detailed conversation by ID.

    Returns full conversation with all messages, epochs, files touched, and tags.
    """
    repo = ConversationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation with all relations loaded
    conversation = repo.get_with_relations(conversation_id, workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return _conversation_to_detail(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Maximum messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    session: Session = Depends(get_db),
) -> list[MessageResponse]:
    """
    Get messages for a specific conversation.

    Supports pagination for large conversations.
    Messages are returned in chronological order.
    """
    # First verify conversation exists
    conv_repo = ConversationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify conversation exists and belongs to workspace
    conversation = conv_repo.get(conversation_id)
    if not conversation or conversation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    msg_repo = MessageRepository(session)
    messages = msg_repo.get_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )

    return [MessageResponse.model_validate(m) for m in messages]
