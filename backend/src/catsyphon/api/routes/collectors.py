"""
Collector Events API routes.

Implements the collector events protocol for aiobscura and watcher integration:
- POST /collectors - Register new collector
- POST /collectors/events - Submit event batch
- GET /collectors/sessions/{session_id} - Get session status
- POST /collectors/sessions/{session_id}/complete - Complete session
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    CollectorEvent as PydanticCollectorEvent,
    CollectorEventsRequest,
    CollectorEventsResponse,
    CollectorRegisterRequest,
    CollectorRegisterResponse,
    CollectorSessionCompleteRequest,
    CollectorSessionCompleteResponse,
    CollectorSessionStatusResponse,
)
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    CollectorRepository,
    CollectorSessionRepository,
    WorkspaceRepository,
)
from catsyphon.models.db import CollectorConfig
from catsyphon.services.ingestion_service import (
    CollectorEvent as InternalCollectorEvent,
    IngestionService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collectors", tags=["collectors"])


def _convert_pydantic_event(event: PydanticCollectorEvent) -> InternalCollectorEvent:
    """Convert Pydantic CollectorEvent to internal CollectorEvent."""
    # Compute hash if not provided
    event_hash = event.event_hash
    if not event_hash:
        import json

        data_dict = event.data.model_dump(exclude_none=True)
        content = json.dumps(data_dict, sort_keys=True, default=str)
        hash_input = f"{event.type}:{event.emitted_at.isoformat()}:{content}"
        event_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    return InternalCollectorEvent(
        type=event.type,
        emitted_at=event.emitted_at,
        observed_at=event.observed_at,
        event_hash=event_hash,
        data=event.data.model_dump(exclude_none=True),
    )


def _queue_tagging(conversation_id: uuid.UUID, db: Session) -> None:
    """Queue a conversation for async tagging.

    Adds the conversation to the tagging job queue. The actual tagging
    is performed by the background TaggingWorker, preventing connection
    pool exhaustion during high-throughput ingestion.

    Args:
        conversation_id: UUID of the conversation to tag
        db: Database session for queue operations
    """
    if not settings.openai_api_key:
        return  # Tagging not configured

    from catsyphon.tagging import TaggingJobQueue

    try:
        queue = TaggingJobQueue(db)
        job_id = queue.enqueue(conversation_id)
        logger.debug(f"Queued tagging job {job_id} for conversation {conversation_id}")
    except Exception as e:
        # Don't fail ingestion if queueing fails
        logger.warning(f"Failed to queue tagging for {conversation_id}: {e}")


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, prefix, sha256_hash)
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"cs_live_{random_part}"
    prefix = f"cs_live_{random_part[:4]}"
    # Hash the key for storage using SHA-256
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    computed_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return hmac.compare_digest(computed_hash, stored_hash)


def get_collector_from_auth(
    authorization: Annotated[str, Header()],
    x_collector_id: Annotated[str, Header()],
    db: Session = Depends(get_db),
) -> CollectorConfig:
    """
    Authenticate collector from headers.

    Args:
        authorization: Bearer token header
        x_collector_id: Collector ID header
        db: Database session

    Returns:
        Authenticated CollectorConfig

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    api_key = authorization[7:]  # Remove "Bearer " prefix

    try:
        collector_id = uuid.UUID(x_collector_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid collector ID format",
        )

    collector_repo = CollectorRepository(db)
    collector = collector_repo.get(collector_id)

    if not collector:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Collector not found",
        )

    if not collector.api_key_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Collector has no API key configured",
        )

    if not verify_api_key(api_key, collector.api_key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not collector.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Collector is disabled",
        )

    return collector


@router.post(
    "",
    response_model=CollectorRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new collector",
)
def register_collector(
    request: CollectorRegisterRequest,
    db: Session = Depends(get_db),
) -> CollectorRegisterResponse:
    """
    Register a new collector instance and obtain API credentials.

    The returned API key is only shown once - store it securely.
    """
    # Verify workspace exists
    workspace_repo = WorkspaceRepository(db)
    workspace = workspace_repo.get(request.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace {request.workspace_id} not found",
        )

    # Generate API key
    api_key, api_key_prefix, api_key_hash = generate_api_key()

    # Create collector config
    collector_repo = CollectorRepository(db)
    collector = collector_repo.create(
        name=f"{request.collector_type}@{request.hostname}",
        collector_type=request.collector_type,
        workspace_id=request.workspace_id,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key_prefix,
        is_active=True,
        extra_data={
            "collector_version": request.collector_version,
            "hostname": request.hostname,
            **(request.metadata or {}),
        },
    )

    db.commit()

    return CollectorRegisterResponse(
        collector_id=collector.id,
        api_key=api_key,
        api_key_prefix=api_key_prefix,
        created_at=collector.created_at,
    )


@router.post(
    "/events",
    response_model=CollectorEventsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit event batch",
)
def submit_events(
    request: CollectorEventsRequest,
    authorization: Annotated[str, Header()],
    x_collector_id: Annotated[str, Header()],
    db: Session = Depends(get_db),
) -> CollectorEventsResponse:
    """
    Submit a batch of events from an active session.

    Events are deduplicated by content hash (event_hash field).
    Duplicate events are silently ignored, making re-ingestion idempotent.
    """
    # Authenticate collector
    collector = get_collector_from_auth(authorization, x_collector_id, db)

    # Convert Pydantic events to internal events
    internal_events = [_convert_pydantic_event(e) for e in request.events]

    # Process events using unified service
    service = IngestionService(db)
    outcome = service.process_events(
        events=internal_events,
        session_id=request.session_id,
        workspace_id=collector.workspace_id,
        collector_id=collector.id,
        source_type="collector",
        enable_tagging=True,  # Always enable tagging for collector API
    )

    # Handle errors
    if outcome.status == "error":
        logger.error(f"Collector ingestion failed: {outcome.error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=outcome.error_message or "Ingestion failed",
        )

    # Commit the transaction
    db.commit()

    logger.debug(
        f"Collector ingestion completed: conversation={outcome.conversation_id}, "
        f"messages={outcome.messages_added}, time={outcome.processing_time_ms}ms"
    )

    return CollectorEventsResponse(
        accepted=outcome.events_accepted,
        last_sequence=outcome.last_sequence,
        conversation_id=outcome.conversation_id,
        warnings=outcome.warnings or [],
    )


@router.get(
    "/sessions/{session_id}",
    response_model=CollectorSessionStatusResponse,
    summary="Get session status",
)
def get_session_status(
    session_id: str,
    authorization: Annotated[str, Header()],
    x_collector_id: Annotated[str, Header()],
    db: Session = Depends(get_db),
) -> CollectorSessionStatusResponse:
    """
    Check the last received sequence for a session (for resumption).

    Use this after a 409 Conflict to determine where to resume sending events.
    """
    collector = get_collector_from_auth(authorization, x_collector_id, db)

    session_repo = CollectorSessionRepository(db)
    conversation = session_repo.get_by_collector_session_id(session_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events received for session {session_id}",
        )

    # Verify this session belongs to the authenticated collector
    if conversation.collector_id != collector.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session belongs to a different collector",
        )

    return CollectorSessionStatusResponse(
        session_id=session_id,
        conversation_id=conversation.id,
        last_sequence=conversation.last_event_sequence,
        event_count=conversation.message_count,
        first_event_at=conversation.start_time,
        last_event_at=conversation.server_received_at or conversation.start_time,
        status="completed" if conversation.status == "completed" else "active",
    )


@router.get(
    "/builtin/credentials",
    response_model=CollectorRegisterResponse,
    summary="Get built-in collector credentials (internal use)",
)
def get_builtin_credentials(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CollectorRegisterResponse:
    """
    Get credentials for the built-in watcher collector.

    This is used internally by watch daemons when API mode is enabled.
    The built-in collector is automatically created if it doesn't exist.
    """
    # Verify workspace exists
    workspace_repo = WorkspaceRepository(db)
    workspace = workspace_repo.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace {workspace_id} not found",
        )

    collector_repo = CollectorRepository(db)
    collector, created = collector_repo.get_or_create_builtin(
        workspace_id=workspace_id,
        api_key_generator=generate_api_key,
    )

    if created:
        db.commit()

    # Get the plaintext API key from extra_data
    api_key = collector.extra_data.get("_api_key_plaintext", "")
    if not api_key:
        # Collector exists but lost its key - regenerate
        api_key, api_key_prefix, api_key_hash = generate_api_key()
        collector.api_key_hash = api_key_hash
        collector.api_key_prefix = api_key_prefix
        collector.extra_data = {**collector.extra_data, "_api_key_plaintext": api_key}
        db.commit()

    return CollectorRegisterResponse(
        collector_id=collector.id,
        api_key=api_key,
        api_key_prefix=collector.api_key_prefix,
        created_at=collector.created_at,
    )


@router.post(
    "/sessions/{session_id}/complete",
    response_model=CollectorSessionCompleteResponse,
    summary="Complete a session",
)
def complete_session(
    session_id: str,
    request: CollectorSessionCompleteRequest,
    authorization: Annotated[str, Header()],
    x_collector_id: Annotated[str, Header()],
    db: Session = Depends(get_db),
) -> CollectorSessionCompleteResponse:
    """
    Mark a session as completed (no more events expected).

    This should be called when the agent session ends to finalize the conversation.
    """
    collector = get_collector_from_auth(authorization, x_collector_id, db)

    session_repo = CollectorSessionRepository(db)
    conversation = session_repo.get_by_collector_session_id(session_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events received for session {session_id}",
        )

    # Verify this session belongs to the authenticated collector
    if conversation.collector_id != collector.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session belongs to a different collector",
        )

    # Complete the session (final_sequence no longer used, kept for API compatibility)
    session_repo.complete_session(
        conversation=conversation,
        final_sequence=0,  # Deprecated, not used
        outcome=request.outcome,
        summary=request.summary,
    )

    # Extract values BEFORE commit to avoid lazy load after session expires
    conversation_id = conversation.id
    message_count = conversation.message_count

    # Queue tagging job BEFORE commit so it's part of the same transaction
    if settings.openai_api_key:
        _queue_tagging(conversation_id, db)

    db.commit()

    return CollectorSessionCompleteResponse(
        session_id=session_id,
        conversation_id=conversation_id,
        status="completed",
        total_events=message_count,
    )
