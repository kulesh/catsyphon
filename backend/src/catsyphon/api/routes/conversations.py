"""
Conversation API routes.

Endpoints for querying and retrieving conversation data.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    ConversationDetail,
    ConversationListItem,
    ConversationListResponse,
    MessageResponse,
    PlanOperationResponse,
    PlanResponse,
    RawLogInfo,
)
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    MessageRepository,
)
from catsyphon.models.db import Conversation
from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.tagging.pipeline import TaggingPipeline

router = APIRouter()


def _get_plan_count(conv: Conversation) -> int:
    """Get the number of plans from conversation's extra_data."""
    if not conv.extra_data:
        return 0
    plans = conv.extra_data.get("plans", [])
    return len(plans) if isinstance(plans, list) else 0


def _conversation_to_list_item(
    conv: Conversation,
    message_count: Optional[int] = None,
    epoch_count: Optional[int] = None,
    files_count: Optional[int] = None,
    children_count: Optional[int] = None,
    depth_level: Optional[int] = None,
) -> ConversationListItem:
    """
    Convert Conversation model to ConversationListItem schema.

    Args:
        conv: Conversation model instance
        message_count: Pre-computed message count (from SQL aggregation)
        epoch_count: Pre-computed epoch count (from SQL aggregation)
        files_count: Pre-computed files count (from SQL aggregation)
        children_count: Pre-computed children count (from SQL aggregation)
        depth_level: Hierarchy depth (0 for parent, 1 for child)

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

    # Children count (Phase 2: Epic 7u2)
    if children_count is not None:
        item.children_count = children_count
    else:
        item.children_count = (
            len(conv.children) if hasattr(conv, "children") and conv.children else 0
        )

    # Depth level for hierarchical display
    if depth_level is not None:
        item.depth_level = depth_level

    # Plan count from extra_data
    item.plan_count = _get_plan_count(conv)

    # Extract additional fields from extra_data
    if conv.extra_data:
        item.slug = conv.extra_data.get("slug")
        item.git_branch = conv.extra_data.get("git_branch")

    return item


def _message_to_response(message) -> MessageResponse:
    """Convert Message model to MessageResponse with extra_data fields extracted."""
    # Handle None values that would fail Pydantic validation
    # Database may have NULL for these JSONB columns
    response = MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content or "",
        thinking_content=message.thinking_content,
        timestamp=message.timestamp,
        sequence=message.sequence,
        tool_calls=message.tool_calls or [],
        tool_results=message.tool_results or [],
        code_changes=message.code_changes or [],
        entities=message.entities or {},
        extra_data=message.extra_data or {},
    )

    # Extract additional fields from extra_data
    if message.extra_data:
        response.model = message.extra_data.get("model")
        response.token_usage = message.extra_data.get("token_usage")
        response.stop_reason = message.extra_data.get("stop_reason")

    return response


def _extract_plans_from_extra_data(extra_data: dict | None) -> list[PlanResponse]:
    """Extract plan data from conversation's extra_data and convert to response schema."""
    if not extra_data:
        return []

    plans_data = extra_data.get("plans", [])
    plans = []

    for plan_data in plans_data:
        operations = [
            PlanOperationResponse(
                operation_type=op.get("operation_type", ""),
                file_path=op.get("file_path", ""),
                content=op.get("content"),
                old_content=op.get("old_content"),
                new_content=op.get("new_content"),
                timestamp=(
                    datetime.fromisoformat(op["timestamp"])
                    if op.get("timestamp")
                    else None
                ),
                message_index=op.get("message_index", 0),
            )
            for op in plan_data.get("operations", [])
        ]

        plans.append(
            PlanResponse(
                plan_file_path=plan_data.get("plan_file_path", ""),
                initial_content=plan_data.get("initial_content"),
                final_content=plan_data.get("final_content"),
                status=plan_data.get("status", "active"),
                iteration_count=plan_data.get("iteration_count", 1),
                operations=operations,
                entry_message_index=plan_data.get("entry_message_index"),
                exit_message_index=plan_data.get("exit_message_index"),
                related_agent_session_ids=plan_data.get(
                    "related_agent_session_ids", []
                ),
            )
        )

    return plans


def _conversation_to_detail(conv: Conversation) -> ConversationDetail:
    """Convert Conversation model to ConversationDetail schema."""
    # Convert to list item first
    base = _conversation_to_list_item(conv)

    # Hierarchical relationships (Phase 2: Epic 7u2)
    children = []
    if hasattr(conv, "children") and conv.children:
        children = [_conversation_to_list_item(child) for child in conv.children]

    parent = None
    if hasattr(conv, "parent_conversation") and conv.parent_conversation:
        parent = _conversation_to_list_item(conv.parent_conversation)

    # Extract plan data from extra_data
    plans = _extract_plans_from_extra_data(conv.extra_data)

    # Extract summaries and compaction_events from extra_data
    summaries = []
    compaction_events = []
    if conv.extra_data:
        summaries = conv.extra_data.get("summaries", [])
        compaction_events = conv.extra_data.get("compaction_events", [])

    # Calculate total tokens from messages
    total_tokens = 0
    messages_response = []
    for m in conv.messages or []:
        msg_response = _message_to_response(m)
        messages_response.append(msg_response)
        if msg_response.token_usage:
            total_tokens += msg_response.token_usage.get("input_tokens", 0)
            total_tokens += msg_response.token_usage.get("output_tokens", 0)

    # Add related data
    detail = ConversationDetail(
        **base.model_dump(),
        messages=messages_response,
        epochs=conv.epochs or [],
        files_touched=conv.files_touched or [],
        raw_logs=[
            RawLogInfo(
                id=rl.id,
                file_path=rl.file_path,
                file_hash=rl.file_hash,
                created_at=rl.created_at,
            )
            for rl in (conv.raw_logs or [])
        ],
        children=children,
        parent=parent,
        plans=plans,
        summaries=summaries,
        compaction_events=compaction_events,
    )

    # Set total_tokens if we calculated any
    if total_tokens > 0:
        detail.total_tokens = total_tokens

    return detail


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
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ConversationListResponse:
    """
    List conversations with optional filters.

    Returns paginated list of conversations with basic metadata.
    For full conversation details including messages, use GET /conversations/{id}.
    """
    # Parse date filters first (for validation)
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
    workspace_id = auth.workspace_id

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

    # Get conversations WITH counts in hierarchical order (parents followed by children)
    results = repo.get_with_counts_hierarchical(
        workspace_id=workspace_id,
        **filters,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # Convert to response schema using pre-computed counts
    # Note: last_activity is returned but not used in this endpoint
    items = [
        _conversation_to_list_item(
            conv,
            message_count=msg_count,
            epoch_count=epoch_count,
            files_count=files_count,
            children_count=child_count,
            depth_level=depth,
        )
        for conv, msg_count, epoch_count, files_count, child_count, depth, _last_activity in results
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
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ConversationDetail:
    """
    Get detailed conversation by ID.

    Returns full conversation with all messages, epochs, files touched, and tags.
    """
    repo = ConversationRepository(session)

    # Get conversation with all relations loaded (workspace-filtered)
    conversation = repo.get_with_relations(conversation_id, auth.workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return _conversation_to_detail(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Maximum messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[MessageResponse]:
    """
    Get messages for a specific conversation.

    Supports pagination for large conversations.
    Messages are returned in chronological order.
    """
    # Verify conversation exists and belongs to workspace
    conv_repo = ConversationRepository(session)
    conversation = conv_repo.get_by_id_workspace(conversation_id, auth.workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    msg_repo = MessageRepository(session)
    messages = msg_repo.get_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )

    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/{conversation_id}/tag", response_model=ConversationDetail)
async def tag_conversation(
    conversation_id: UUID,
    force: bool = Query(
        False, description="Force retagging even if tags already exist"
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ConversationDetail:
    """
    Tag or retag a conversation using AI analysis.

    This endpoint runs the tagging pipeline (rule-based + LLM) on a conversation
    and updates its tags. By default, it only tags conversations that haven't been
    tagged yet. Use force=true to retag existing conversations.

    **Minimum Requirements:**
    - Conversation must have at least 2 messages (1 user + 1 assistant)

    **Tagging Fields:**
    - intent: What the user was trying to accomplish
    - outcome: Result of the conversation
    - sentiment: Overall emotional tone
    - sentiment_score: Numeric sentiment (-1.0 to 1.0)
    - features: List of features discussed
    - problems: List of problems encountered
    - has_errors: Whether errors were detected
    - tools_used: List of tools invoked

    Returns the updated conversation with tags.
    """
    # Get conversation with relations (workspace-filtered)
    conv_repo = ConversationRepository(session)
    conversation = conv_repo.get_with_relations(conversation_id, auth.workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if already tagged (unless force=true)
    if not force and conversation.tags:
        raise HTTPException(
            status_code=400,
            detail="Conversation already tagged. Use force=true to retag.",
        )

    # Validate minimum message count
    min_messages = 2
    if conversation.message_count < min_messages:
        raise HTTPException(
            status_code=400,
            detail=f"Conversation too short to tag. Minimum {min_messages} messages required (found {conversation.message_count}).",
        )

    # Convert database conversation to ParsedConversation for tagging pipeline
    parsed_messages = [
        ParsedMessage(
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
            thinking_content=msg.thinking_content,
        )
        for msg in conversation.messages
    ]

    parsed = ParsedConversation(
        agent_type=conversation.agent_type,
        agent_version=conversation.agent_version,
        start_time=conversation.start_time,
        end_time=conversation.end_time,
        messages=parsed_messages,
        session_id=conversation.extra_data.get("session_id"),
        git_branch=conversation.extra_data.get("git_branch"),
        working_directory=conversation.extra_data.get("working_directory"),
        metadata=conversation.extra_data,
    )

    # Run tagging pipeline
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Tagging service unavailable. OpenAI API key not configured.",
        )

    pipeline = TaggingPipeline(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        cache_dir=Path(settings.tagging_cache_dir),
        cache_ttl_days=settings.tagging_cache_ttl_days,
        enable_cache=settings.tagging_enable_cache
        and not force,  # Disable cache when forcing
    )

    try:
        tags, llm_metrics = pipeline.tag_conversation(parsed)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Tagging failed: {str(e)}",
        )

    # Update conversation with tags
    conversation.tags = tags
    session.commit()
    session.refresh(conversation)

    return _conversation_to_detail(conversation)
