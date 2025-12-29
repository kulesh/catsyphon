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
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    CollectorEventsRequest,
    CollectorEventsResponse,
    CollectorRegisterRequest,
    CollectorRegisterResponse,
    CollectorSequenceGapError,
    CollectorSessionCompleteRequest,
    CollectorSessionCompleteResponse,
    CollectorSessionStatusResponse,
)
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    CollectorRepository,
    CollectorSessionRepository,
    ConversationRepository,
    WorkspaceRepository,
)
from catsyphon.models.db import CollectorConfig, IngestionJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collectors", tags=["collectors"])

# Lazy-initialized tagging pipeline (only created when needed)
_tagging_pipeline = None


def _get_tagging_pipeline():
    """Get or create the tagging pipeline (lazy initialization).

    Returns:
        TaggingPipeline instance, or None if tagging is not configured.
    """
    global _tagging_pipeline
    if _tagging_pipeline is None and settings.openai_api_key:
        from pathlib import Path

        from catsyphon.tagging import TaggingPipeline

        # Convert cache_dir to Path if it's a string
        cache_dir = None
        if settings.tagging_cache_dir:
            cache_dir = Path(settings.tagging_cache_dir)

        _tagging_pipeline = TaggingPipeline(
            openai_api_key=settings.openai_api_key,
            openai_model="gpt-4o-mini",
            cache_dir=cache_dir,
            cache_ttl_days=settings.tagging_cache_ttl_days,
            enable_cache=settings.tagging_enable_cache,
        )
        logger.info("TaggingPipeline initialized for collector events")
    return _tagging_pipeline


def _tag_conversation_async(conversation_id: uuid.UUID, workspace_id: uuid.UUID, db: Session):
    """Tag a conversation after session completion.

    This runs synchronously but is designed to not block the response.
    Failures are logged but do not fail the request.

    Args:
        conversation_id: UUID of the conversation to tag
        workspace_id: UUID of the workspace
        db: Database session
    """
    pipeline = _get_tagging_pipeline()
    if not pipeline:
        return

    try:
        conv_repo = ConversationRepository(db)
        conversation = conv_repo.get_with_relations(conversation_id, workspace_id)

        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found for tagging")
            return

        # Run tagging pipeline
        tags, metrics = pipeline.tag_from_canonical(
            conversation=conversation,
            session=db,
            children=[],  # Agent children already have session_end processed separately
        )

        # Update conversation with tags
        conversation.tags = tags
        db.commit()

        logger.info(
            f"Tagged conversation {conversation_id}: "
            f"intent={tags.get('intent')}, outcome={tags.get('outcome')}, "
            f"tokens={metrics.get('llm_total_tokens', 0)}"
        )

    except Exception as e:
        logger.warning(f"Tagging failed for conversation {conversation_id}: {e}")
        # Don't fail the request - tagging is optional
        db.rollback()


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
    responses={
        409: {"model": CollectorSequenceGapError, "description": "Sequence gap detected"},
    },
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

    Events are deduplicated by (session_id, sequence).
    Sequence gaps result in 409 Conflict - call GET /collectors/sessions/{id}
    to get the last received sequence and resend from there.
    """
    start_time = time.time()
    start_datetime = datetime.now(timezone.utc)

    collector = get_collector_from_auth(authorization, x_collector_id, db)

    session_repo = CollectorSessionRepository(db)
    # Note: We create IngestionJob directly rather than using repository
    # to avoid extra queries when we just need to insert

    # Create ingestion job for tracking
    ingestion_job = IngestionJob(
        source_type="collector",
        collector_id=collector.id,
        status="processing",
        started_at=start_datetime,
        messages_added=0,
        metrics={},
    )
    db.add(ingestion_job)
    db.flush()

    try:
        # Sort events by sequence
        sorted_events = sorted(request.events, key=lambda e: e.sequence)

        # Get or create session
        first_event = sorted_events[0]
        session_data = first_event.data

        # Extract known fields and additional metadata for semantic parity
        # session_data.model_dump() gives us all fields including extra ones
        session_data_dict = session_data.model_dump(exclude_none=True)
        known_fields = {
            "agent_type",
            "agent_version",
            "working_directory",
            "git_branch",
            "parent_session_id",
            "context_semantics",
            "slug",
            "summaries",
            "compaction_events",
        }
        session_metadata = {
            k: v for k, v in session_data_dict.items() if k not in known_fields
        }

        conversation, created = session_repo.get_or_create_session(
            collector_session_id=request.session_id,
            workspace_id=collector.workspace_id,
            collector_id=collector.id,
            agent_type=session_data.agent_type or "unknown",
            agent_version=session_data.agent_version,
            working_directory=session_data.working_directory,
            git_branch=session_data.git_branch,
            parent_session_id=session_data.parent_session_id,
            context_semantics=session_data.context_semantics,
            first_event_timestamp=first_event.emitted_at,  # Use event timestamp
            # New fields for semantic parity
            slug=session_data.slug,
            summaries=session_data.summaries,
            compaction_events=session_data.compaction_events,
            session_metadata=session_metadata if session_metadata else None,
        )

        # Update ingestion job with conversation
        ingestion_job.conversation_id = conversation.id

        # Check for sequence gap (only for existing sessions)
        if not created:
            gap = session_repo.check_sequence_gap(conversation, first_event.sequence)
            if gap:
                last_received, expected = gap
                # Mark job as failed due to sequence gap
                ingestion_job.status = "failed"
                ingestion_job.error_message = f"Sequence gap: expected {expected}, got {first_event.sequence}"
                ingestion_job.processing_time_ms = int((time.time() - start_time) * 1000)
                ingestion_job.completed_at = datetime.now(timezone.utc)
                db.commit()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=CollectorSequenceGapError(
                        message=f"Expected sequence {expected}, got {first_event.sequence}",
                        last_received_sequence=last_received,
                        expected_sequence=expected,
                    ).model_dump(),
                )

        # Filter duplicates
        events_dict = [
            {"sequence": e.sequence, "event": e} for e in sorted_events
        ]
        new_events = session_repo.filter_duplicate_sequences(conversation, events_dict)

        # Track message-like events added
        messages_added = 0
        files_touched = 0
        session_completed = False  # Track if session_end was processed

        # Tools that modify files (for FileTouched tracking)
        # Maps tool_name -> change_type for semantic parity with direct ingestion
        FILE_MODIFYING_TOOLS = {
            "Edit": "write",
            "Write": "write",
            "NotebookEdit": "write",
            "MultiEdit": "write",
        }
        FILE_READING_TOOLS = {"Read", "Glob", "Grep"}

        # Process new events
        warnings = []
        for event_item in new_events:
            event = event_item["event"]

            # Skip session_start for existing sessions
            if event.type == "session_start" and not created:
                continue

            # Add message for message-like events
            if event.type in ("message", "tool_call", "tool_result", "thinking", "error"):
                session_repo.add_message(
                    conversation=conversation,
                    sequence=event.sequence,
                    event_type=event.type,
                    emitted_at=event.emitted_at,
                    observed_at=event.observed_at,
                    data=event.data.model_dump(exclude_none=True),
                )
                messages_added += 1

                # Track file touches from tool_call events (semantic parity)
                # Mirrors FileTouched creation in pipeline/ingestion.py
                if event.type == "tool_call" and event.data.tool_name:
                    tool_name = event.data.tool_name
                    params = event.data.parameters or {}

                    # Extract file_path from tool parameters
                    file_path = params.get("file_path") or params.get("path")
                    if file_path:
                        if tool_name in FILE_MODIFYING_TOOLS:
                            change_type = FILE_MODIFYING_TOOLS[tool_name]
                            session_repo.add_file_touched(
                                conversation=conversation,
                                file_path=file_path,
                                change_type=change_type,
                                timestamp=event.emitted_at,
                            )
                            files_touched += 1
                        elif tool_name in FILE_READING_TOOLS:
                            session_repo.add_file_touched(
                                conversation=conversation,
                                file_path=file_path,
                                change_type="read",
                                timestamp=event.emitted_at,
                            )
                            files_touched += 1

            # Handle session_end - include plans and files for semantic parity
            if event.type == "session_end":
                session_repo.complete_session(
                    conversation=conversation,
                    final_sequence=event.sequence,
                    outcome=event.data.outcome or "unknown",
                    summary=event.data.summary,
                    event_timestamp=event.emitted_at,  # Use event timestamp
                    # New fields for semantic parity
                    plans=event.data.plans,
                    files_touched=event.data.files_touched,
                )
                session_completed = True

        # Update sequence tracking and last activity timestamp
        if new_events:
            last_seq = max(e["sequence"] for e in new_events)
            session_repo.update_sequence(
                conversation=conversation,
                last_sequence=last_seq,
                event_count_delta=len(new_events),
            )
            # Update end_time to latest event's timestamp (for "last activity")
            last_event = max(new_events, key=lambda e: e["event"].emitted_at)
            session_repo.update_last_activity(
                conversation=conversation,
                event_timestamp=last_event["event"].emitted_at,
            )

        # Try to link any orphaned collector sessions (deferred parent linking)
        linked = session_repo.link_orphaned_collectors(collector.workspace_id)
        if linked > 0:
            logger.info(f"Linked {linked} orphaned collector sessions to parents")

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update ingestion job as successful
        ingestion_job.status = "success"
        ingestion_job.messages_added = messages_added
        ingestion_job.processing_time_ms = processing_time_ms
        ingestion_job.completed_at = datetime.now(timezone.utc)
        ingestion_job.metrics = {
            "events_received": len(sorted_events),
            "events_accepted": len(new_events),
            "events_deduplicated": len(sorted_events) - len(new_events),
            "files_touched": files_touched,
            "session_created": created,
            "total_ms": processing_time_ms,
        }

        db.commit()

        # Run tagging pipeline after session completion (non-blocking)
        # This provides semantic parity with CLI/Watch/Upload ingestion paths
        if session_completed and settings.openai_api_key:
            _tag_conversation_async(conversation.id, collector.workspace_id, db)

        logger.debug(
            f"Collector ingestion completed: job={ingestion_job.id}, "
            f"conversation={conversation.id}, messages={messages_added}, "
            f"time={processing_time_ms}ms"
        )

        return CollectorEventsResponse(
            accepted=len(new_events),
            last_sequence=conversation.last_event_sequence,
            conversation_id=conversation.id,
            warnings=warnings,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (already handled above)
        raise
    except Exception as e:
        # Mark job as failed
        processing_time_ms = int((time.time() - start_time) * 1000)
        ingestion_job.status = "failed"
        ingestion_job.error_message = f"{type(e).__name__}: {str(e)}"
        ingestion_job.processing_time_ms = processing_time_ms
        ingestion_job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.error(f"Collector ingestion failed: {e}", exc_info=True)
        raise


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

    # Complete the session
    session_repo.complete_session(
        conversation=conversation,
        final_sequence=request.final_sequence,
        outcome=request.outcome,
        summary=request.summary,
    )

    db.commit()

    # Run tagging pipeline after session completion (non-blocking)
    if settings.openai_api_key:
        _tag_conversation_async(conversation.id, collector.workspace_id, db)

    return CollectorSessionCompleteResponse(
        session_id=session_id,
        conversation_id=conversation.id,
        status="completed",
        total_events=conversation.message_count,
    )
