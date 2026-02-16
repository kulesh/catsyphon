"""
Unified ingestion service for CatSyphon.

This service handles all ingestion paths:
- CLI ingestion (direct call)
- Upload API (direct call)
- Collector Events API (via process_events)
- Watch daemon (via HTTP to Collector Events API)

All paths ultimately use the same event processing logic for semantic consistency.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from catsyphon.config import settings
from catsyphon.db.repositories.collector_session import CollectorSessionRepository
from catsyphon.db.repositories.raw_log import RawLogRepository
from catsyphon.models.db import IngestionJob
from catsyphon.parsers.registry import ParserRegistry

if TYPE_CHECKING:
    from catsyphon.models.parsed import ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _is_deadlock_error(exc: BaseException) -> bool:
    """Check whether a database error is a deadlock or serialization failure."""
    if not isinstance(exc, DBAPIError):
        return False
    orig = exc.orig
    pgcode = getattr(orig, "pgcode", None)
    if pgcode in {"40P01", "40001"}:  # deadlock detected / serialization failure
        return True
    return orig.__class__.__name__ in {"DeadlockDetected", "SerializationFailure"}


def _compute_event_hash(
    event_type: str, emitted_at: datetime, data: dict[str, Any]
) -> str:
    """
    Compute a content-based hash for event deduplication.

    Same algorithm as collector_client.py for consistency.
    """
    content = json.dumps(data, sort_keys=True, default=str)
    hash_input = f"{event_type}:{emitted_at.isoformat()}:{content}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def _serialize_for_json(obj: Any) -> Any:
    """Recursively serialize objects for JSON, handling datetime."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    return obj


def _apply_session_start_metadata(
    conversation: Conversation, data: dict[str, Any]
) -> bool:
    """Update conversation metadata from a session_start event."""
    changed = False
    agent_type = data.get("agent_type")
    if agent_type and conversation.agent_type == "unknown":
        conversation.agent_type = agent_type
        changed = True

    agent_version = data.get("agent_version")
    if agent_version and (conversation.agent_version in (None, "unknown")):
        conversation.agent_version = agent_version
        changed = True

    if conversation.extra_data is None:
        conversation.extra_data = {}

    for key in ("working_directory", "git_branch", "parent_session_id", "slug"):
        if key in data and data[key] is not None:
            if key not in conversation.extra_data:
                conversation.extra_data[key] = data[key]
                changed = True

    return changed


@dataclass
class IngestionOutcome:
    """Result of an ingestion operation."""

    status: str  # success, duplicate, skipped, error
    conversation_id: Optional[UUID] = None
    messages_added: int = 0
    events_accepted: int = 0
    events_deduplicated: int = 0
    processing_time_ms: int = 0
    error_message: Optional[str] = None
    last_sequence: int = 0  # Last event sequence in conversation
    warnings: list[str] | None = None  # Processing warnings

    @property
    def success(self) -> bool:
        return self.status in ("success", "duplicate")


@dataclass
class CollectorEvent:
    """Internal event representation for processing."""

    type: str
    emitted_at: datetime
    observed_at: datetime
    event_hash: str
    data: dict[str, Any]


class IngestionService:
    """
    Unified ingestion service for all ingestion paths.

    This service provides:
    - `ingest_from_file()`: Parse a file and ingest via event pipeline
    - `process_events()`: Process events directly (used by HTTP endpoint)

    All methods use the same underlying event processing logic for consistency.
    """

    def __init__(self, session: Session):
        self.session = session
        self.session_repo = CollectorSessionRepository(session)
        self.raw_log_repo = RawLogRepository(session)
        self._parser_registry: Optional[ParserRegistry] = None

    @property
    def parser_registry(self) -> ParserRegistry:
        """Lazy-load parser registry with default parsers."""
        if self._parser_registry is None:
            from catsyphon.parsers import get_default_registry

            self._parser_registry = get_default_registry()
        return self._parser_registry

    def ingest_from_file(
        self,
        file_path: Path,
        workspace_id: UUID,
        project_name: Optional[str] = None,
        developer_username: Optional[str] = None,
        source_type: str = "cli",
        enable_tagging: bool = False,
        collector_id: Optional[UUID] = None,
    ) -> IngestionOutcome:
        """
        Parse a file and ingest via the event pipeline.

        This is the main entry point for CLI and Upload API ingestion.

        Args:
            file_path: Path to the log file to ingest
            workspace_id: Workspace to ingest into
            project_name: Optional project name (auto-detected from working_directory if not provided)
            developer_username: Optional developer username
            source_type: Source identifier (cli, upload, etc.)
            enable_tagging: Whether to queue for LLM tagging after ingestion
            collector_id: Optional collector ID for tracking

        Returns:
            IngestionOutcome with status and details
        """
        start_time = time.time()

        try:
            # ADR-009: Prefer chunked parsing to keep memory bounded
            chunked_parser = self.parser_registry.find_chunked_parser(file_path)
            if chunked_parser:
                return self._ingest_chunked(
                    file_path=file_path,
                    chunked_parser=chunked_parser,
                    workspace_id=workspace_id,
                    collector_id=collector_id,
                    source_type=source_type,
                    enable_tagging=enable_tagging,
                    start_time=start_time,
                )

            # Fallback: full parse for non-chunked parsers
            parsed = self.parser_registry.parse(file_path)
            if not parsed:
                return IngestionOutcome(
                    status="error",
                    error_message=f"Failed to parse file: {file_path}",
                )

            session_id = parsed.session_id or file_path.stem
            events = self._parsed_to_events(parsed)

            if not events:
                return IngestionOutcome(
                    status="skipped",
                    error_message="No events generated from file",
                )

            outcome = self.process_events(
                events=events,
                session_id=session_id,
                workspace_id=workspace_id,
                collector_id=collector_id,
                source_type=source_type,
                enable_tagging=enable_tagging,
            )

            if outcome.success and outcome.conversation_id:
                self._ensure_raw_log(
                    conversation_id=outcome.conversation_id,
                    file_path=file_path,
                    agent_type=parsed.agent_type or "unknown",
                )

            return outcome

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Ingestion failed for {file_path}: {e}", exc_info=True)
            return IngestionOutcome(
                status="error",
                error_message=str(e),
                processing_time_ms=processing_time_ms,
            )

    def _ingest_chunked(
        self,
        file_path: Path,
        chunked_parser: Any,
        workspace_id: UUID,
        collector_id: Optional[UUID],
        source_type: str,
        enable_tagging: bool,
        start_time: float,
    ) -> IngestionOutcome:
        """Ingest a file using chunked parsing (ADR-009).

        Extracts metadata, then iterates parse_messages() in a loop,
        converting each chunk to events and processing them. Peak memory
        is ~3 MB per chunk regardless of file size.
        """
        meta = chunked_parser.parse_metadata(file_path)
        session_id = meta.session_id or file_path.stem

        # Accumulate events across chunks (we still process in one batch
        # per the events API contract, but memory is bounded by chunk size
        # since messages are converted to lightweight event dicts)
        all_events: list[CollectorEvent] = []

        # Session start event
        session_start_data: dict[str, Any] = {
            "agent_type": meta.agent_type or "unknown",
            "agent_version": meta.agent_version or "unknown",
            "working_directory": meta.working_directory,
            "git_branch": meta.git_branch,
        }
        if meta.parent_session_id:
            session_start_data["parent_session_id"] = meta.parent_session_id
        if meta.slug:
            session_start_data["slug"] = meta.slug
        if meta.metadata:
            for key, value in meta.metadata.items():
                if key not in session_start_data:
                    session_start_data[key] = _serialize_for_json(value)

        all_events.append(
            self._create_event(
                event_type="session_start",
                emitted_at=meta.start_time or _utc_now(),
                data=session_start_data,
            )
        )

        # Parse messages in chunks
        offset = 0
        all_summaries: list[dict] = []
        all_compaction: list[dict] = []
        last_message_time = meta.start_time

        while True:
            chunk = chunked_parser.parse_messages(file_path, offset)

            for msg in chunk.messages:
                all_events.extend(self._message_to_events(msg))
                if msg.timestamp:
                    last_message_time = msg.timestamp

            all_summaries.extend(chunk.summaries)
            all_compaction.extend(chunk.compaction_events)
            offset = chunk.next_offset
            if chunk.is_last:
                break

        # Session end event
        if last_message_time:
            session_end_data: dict[str, Any] = {
                "outcome": "unknown",
                "total_messages": sum(1 for e in all_events if e.type == "message"),
            }
            all_events.append(
                self._create_event(
                    event_type="session_end",
                    emitted_at=last_message_time,
                    data=session_end_data,
                )
            )

        if not all_events:
            return IngestionOutcome(
                status="skipped",
                error_message="No events generated from file",
            )

        outcome = self.process_events(
            events=all_events,
            session_id=session_id,
            workspace_id=workspace_id,
            collector_id=collector_id,
            source_type=source_type,
            enable_tagging=enable_tagging,
        )

        if outcome.success and outcome.conversation_id:
            self._ensure_raw_log(
                conversation_id=outcome.conversation_id,
                file_path=file_path,
                agent_type=meta.agent_type or "unknown",
            )

        return outcome

    def process_events(
        self,
        events: list[CollectorEvent],
        session_id: str,
        workspace_id: UUID,
        collector_id: Optional[UUID] = None,
        source_type: str = "service",
        enable_tagging: bool = False,
    ) -> IngestionOutcome:
        """
        Process a list of events.

        This is the core event processing logic, shared between:
        - Internal service calls (CLI, Upload API)
        - HTTP Collector Events API

        Args:
            events: List of events to process
            session_id: Unique session identifier
            workspace_id: Workspace to ingest into
            collector_id: Optional collector ID for tracking
            source_type: Source identifier for ingestion job
            enable_tagging: Whether to queue for LLM tagging

        Returns:
            IngestionOutcome with processing results
        """
        start_time = time.time()
        start_datetime = _utc_now()
        max_attempts = 3

        for attempt in range(max_attempts):
            # Create ingestion job for tracking
            ingestion_job = IngestionJob(
                source_type=source_type,
                collector_id=collector_id,
                status="processing",
                started_at=start_datetime,
                messages_added=0,
                metrics={},
            )
            self.session.add(ingestion_job)
            self.session.flush()

            try:
                # Sort events by timestamp
                sorted_events = sorted(events, key=lambda e: e.emitted_at)

                if not sorted_events:
                    ingestion_job.status = "skipped"
                    ingestion_job.completed_at = _utc_now()
                    return IngestionOutcome(status="skipped")

                session_start_event = next(
                    (event for event in sorted_events if event.type == "session_start"),
                    None,
                )
                earliest_event = sorted_events[0]

                # Extract session metadata from session_start when available
                session_data = (session_start_event or earliest_event).data
                conversation, created = self.session_repo.get_or_create_session(
                    collector_session_id=session_id,
                    workspace_id=workspace_id,
                    collector_id=collector_id,
                    agent_type=session_data.get("agent_type", "unknown"),
                    agent_version=session_data.get("agent_version"),
                    working_directory=session_data.get("working_directory"),
                    git_branch=session_data.get("git_branch"),
                    parent_session_id=session_data.get("parent_session_id"),
                    context_semantics=session_data.get("context_semantics"),
                    first_event_timestamp=earliest_event.emitted_at,
                    slug=session_data.get("slug"),
                    summaries=session_data.get("summaries"),
                    compaction_events=session_data.get("compaction_events"),
                )

                ingestion_job.conversation_id = conversation.id

                # Content-based deduplication: send only candidate hashes
                # to DB instead of loading all existing hashes into Python
                candidate_hashes = {e.event_hash for e in sorted_events}
                existing_hashes = self.session_repo.filter_existing_event_hashes(
                    conversation.id, candidate_hashes
                )
                new_events = [
                    e for e in sorted_events if e.event_hash not in existing_hashes
                ]

                # Process events
                messages_added = 0
                files_touched_count = 0
                session_completed = False

                # Accumulate file touches for batch insert
                pending_file_touches: list[tuple[str, str, datetime]] = []

                # Tools for file tracking
                file_modifying_tools = {
                    "Edit": "write",
                    "Write": "write",
                    "NotebookEdit": "write",
                    "MultiEdit": "write",
                }
                file_reading_tools = {"Read", "Glob", "Grep"}

                for event in new_events:
                    # Skip session_start for existing sessions
                    if event.type == "session_start":
                        if not created:
                            if _apply_session_start_metadata(conversation, event.data):
                                logger.debug(
                                    "Backfilled session metadata for %s",
                                    conversation.id,
                                )
                        continue

                    # Add message for message-like events
                    if event.type in (
                        "message",
                        "tool_call",
                        "tool_result",
                        "thinking",
                        "error",
                    ):
                        self.session_repo.add_message(
                            conversation=conversation,
                            event_type=event.type,
                            emitted_at=event.emitted_at,
                            observed_at=event.observed_at,
                            data=event.data,
                            event_hash=event.event_hash,
                        )
                        messages_added += 1

                        # Accumulate file touches from tool_call events
                        if event.type == "tool_call":
                            tool_name = event.data.get("tool_name")
                            params = event.data.get("parameters", {})
                            file_path = params.get("file_path") or params.get("path")

                            if file_path:
                                if tool_name in file_modifying_tools:
                                    pending_file_touches.append(
                                        (
                                            file_path,
                                            file_modifying_tools[tool_name],
                                            event.emitted_at,
                                        )
                                    )
                                elif tool_name in file_reading_tools:
                                    pending_file_touches.append(
                                        (file_path, "read", event.emitted_at)
                                    )

                    # Handle session_end
                    if event.type == "session_end":
                        self.session_repo.complete_session(
                            conversation=conversation,
                            final_sequence=0,
                            outcome=event.data.get("outcome", "unknown"),
                            summary=event.data.get("summary"),
                            event_timestamp=event.emitted_at,
                            plans=event.data.get("plans"),
                            files_touched=event.data.get("files_touched"),
                        )
                        session_completed = True

                # Batch-insert accumulated file touches
                if pending_file_touches:
                    files_touched_count = self.session_repo.add_file_touches_batch(
                        conversation=conversation,
                        touches=pending_file_touches,
                    )

                # Update counts
                if new_events:
                    last_sequence = (conversation.last_event_sequence or 0) + len(
                        new_events
                    )
                    self.session_repo.update_sequence(
                        conversation=conversation,
                        last_sequence=last_sequence,
                        event_count_delta=messages_added,
                    )
                    last_event = max(new_events, key=lambda e: e.emitted_at)
                    self.session_repo.update_last_activity(
                        conversation=conversation,
                        event_timestamp=last_event.emitted_at,
                    )

                # Link orphaned sessions only when needed:
                # - A new conversation was created (potential parent for existing orphans)
                # - Batch contains a session_start with parent_session_id (potential orphan)
                has_parent_ref = any(
                    e.type == "session_start" and e.data.get("parent_session_id")
                    for e in new_events
                )
                if created or has_parent_ref:
                    linked = self.session_repo.link_orphaned_collectors(workspace_id)
                    if linked > 0:
                        logger.info(f"Linked {linked} orphaned collector sessions")

                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)

                # Update ingestion job
                ingestion_job.status = "success"
                ingestion_job.messages_added = messages_added
                ingestion_job.processing_time_ms = processing_time_ms
                ingestion_job.completed_at = _utc_now()
                ingestion_job.metrics = {
                    "events_received": len(sorted_events),
                    "events_accepted": len(new_events),
                    "events_deduplicated": len(sorted_events) - len(new_events),
                    "files_touched": files_touched_count,
                    "session_created": created,
                    "total_ms": processing_time_ms,
                }

                # Queue tagging if enabled
                if enable_tagging and session_completed and settings.openai_api_key:
                    self._queue_tagging(conversation.id)

                # Extract values before potential session expiry
                conversation_id = conversation.id
                last_sequence = conversation.last_event_sequence

                return IngestionOutcome(
                    status="success",
                    conversation_id=conversation_id,
                    messages_added=messages_added,
                    events_accepted=len(new_events),
                    events_deduplicated=len(sorted_events) - len(new_events),
                    processing_time_ms=processing_time_ms,
                    last_sequence=last_sequence,
                    warnings=[],
                )

            except DBAPIError as e:
                self.session.rollback()
                if _is_deadlock_error(e) and attempt < max_attempts - 1:
                    backoff = 0.05 * (2**attempt)
                    logger.warning(
                        "Deadlock detected during ingestion for session %s "
                        "(attempt %s/%s), retrying in %.2fs",
                        session_id,
                        attempt + 1,
                        max_attempts,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Event processing failed: {e}", exc_info=True)
                return IngestionOutcome(
                    status="error",
                    error_message=str(e),
                    processing_time_ms=processing_time_ms,
                )
            except Exception as e:
                self.session.rollback()
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Event processing failed: {e}", exc_info=True)
                return IngestionOutcome(
                    status="error",
                    error_message=str(e),
                    processing_time_ms=processing_time_ms,
                )

        processing_time_ms = int((time.time() - start_time) * 1000)
        return IngestionOutcome(
            status="error",
            error_message="Event processing failed after retries",
            processing_time_ms=processing_time_ms,
        )

    def _parsed_to_events(self, parsed: "ParsedConversation") -> list[CollectorEvent]:
        """
        Convert a ParsedConversation to a list of events.

        Same logic as CollectorClient._message_to_events() but returns internal
        CollectorEvent objects instead of dicts for HTTP transport.
        """
        events: list[CollectorEvent] = []

        # Session start event
        session_start_data: dict[str, Any] = {
            "agent_type": parsed.agent_type or "unknown",
            "agent_version": parsed.agent_version or "unknown",
            "working_directory": parsed.working_directory,
            "git_branch": parsed.git_branch,
        }
        if parsed.parent_session_id:
            session_start_data["parent_session_id"] = parsed.parent_session_id
        if parsed.slug:
            session_start_data["slug"] = parsed.slug
        if parsed.summaries:
            session_start_data["summaries"] = _serialize_for_json(parsed.summaries)
        if parsed.compaction_events:
            session_start_data["compaction_events"] = _serialize_for_json(
                parsed.compaction_events
            )
        if parsed.metadata:
            for key, value in parsed.metadata.items():
                if key not in session_start_data:
                    session_start_data[key] = _serialize_for_json(value)

        start_time = parsed.start_time or _utc_now()
        events.append(
            self._create_event(
                event_type="session_start",
                emitted_at=start_time,
                data=session_start_data,
            )
        )

        # Message events
        for msg in parsed.messages:
            events.extend(self._message_to_events(msg))

        # Session end event
        if parsed.end_time:
            session_end_data: dict[str, Any] = {
                "outcome": "unknown",
                "total_messages": len(parsed.messages),
            }
            if parsed.plans:
                session_end_data["plans"] = [
                    plan.to_dict() if hasattr(plan, "to_dict") else plan
                    for plan in parsed.plans
                ]
            if parsed.files_touched:
                session_end_data["files_touched"] = parsed.files_touched

            events.append(
                self._create_event(
                    event_type="session_end",
                    emitted_at=parsed.end_time,
                    data=session_end_data,
                )
            )

        return events

    def _message_to_events(self, msg: "ParsedMessage") -> list[CollectorEvent]:
        """Convert a ParsedMessage to events."""
        events: list[CollectorEvent] = []

        # Map role to author_role
        role_mapping = {
            "user": "human",
            "human": "human",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
        }
        author_role = msg.author_role or role_mapping.get(msg.role or "", "assistant")
        event_time = msg.emitted_at or msg.timestamp or _utc_now()

        # Determine message_type
        message_type = msg.message_type
        if not message_type:
            if msg.role in ("user", "human"):
                message_type = "prompt"
            elif msg.role == "tool":
                message_type = "tool_result"
            else:
                message_type = "response"

        # Tool call events
        if msg.tool_calls:
            for idx, tool_call in enumerate(msg.tool_calls):
                tool_event_time = tool_call.timestamp or event_time
                tool_use_id = f"tool_{tool_event_time.isoformat()}_{idx}"

                events.append(
                    self._create_event(
                        event_type="tool_call",
                        emitted_at=tool_event_time,
                        data={
                            "tool_name": tool_call.tool_name,
                            "tool_use_id": tool_use_id,
                            "parameters": tool_call.parameters or {},
                        },
                    )
                )

                if tool_call.result is not None:
                    result_value = tool_call.result
                    if not isinstance(result_value, str):
                        result_value = json.dumps(result_value)
                    events.append(
                        self._create_event(
                            event_type="tool_result",
                            emitted_at=tool_event_time,
                            data={
                                "tool_use_id": tool_use_id,
                                "success": tool_call.success,
                                "result": result_value,
                            },
                        )
                    )

        # Main message event
        data: dict[str, Any] = {
            "author_role": author_role,
            "message_type": message_type,
            "content": msg.content or "",
        }
        if msg.model:
            data["model"] = msg.model
        if msg.token_usage:
            data["token_usage"] = msg.token_usage
        if msg.thinking_content:
            data["thinking_content"] = msg.thinking_content
        if msg.stop_reason:
            data["stop_reason"] = msg.stop_reason
        if msg.thinking_metadata:
            data["thinking_metadata"] = msg.thinking_metadata

        events.append(
            self._create_event(
                event_type="message",
                emitted_at=event_time,
                data=data,
            )
        )

        return events

    def _create_event(
        self,
        event_type: str,
        emitted_at: datetime,
        data: dict[str, Any],
    ) -> CollectorEvent:
        """Create an event with computed hash."""
        observed_at = _utc_now()
        return CollectorEvent(
            type=event_type,
            emitted_at=emitted_at,
            observed_at=observed_at,
            event_hash=_compute_event_hash(event_type, emitted_at, data),
            data=data,
        )

    def _ensure_raw_log(
        self,
        conversation_id: UUID,
        file_path: Path,
        agent_type: str,
    ) -> None:
        """
        Create or update RawLog entry for incremental parsing state.

        This enables future incremental parsing by storing file state.
        Uses a savepoint to isolate failures (e.g., duplicate file_hash) from
        the main transaction.
        """
        from catsyphon.utils.hashing import calculate_partial_hash

        try:
            file_size = file_path.stat().st_size
            partial_hash = calculate_partial_hash(file_path, file_size)

            # Use savepoint to isolate RawLog operations from main transaction
            # This prevents IntegrityError from corrupting the session state
            savepoint = self.session.begin_nested()
            try:
                existing = self.raw_log_repo.get_by_file_path(str(file_path))
                if existing:
                    self.raw_log_repo.update_state(
                        raw_log=existing,
                        last_processed_offset=file_size,
                        last_processed_line=0,  # Not tracked in this mode
                        file_size_bytes=file_size,
                        partial_hash=partial_hash,
                    )
                else:
                    self.raw_log_repo.create_from_file(
                        conversation_id=conversation_id,
                        agent_type=agent_type,
                        log_format="jsonl",
                        file_path=file_path,
                    )
                    # Update with state
                    new_raw_log = self.raw_log_repo.get_by_file_path(str(file_path))
                    if new_raw_log:
                        self.raw_log_repo.update_state(
                            raw_log=new_raw_log,
                            last_processed_offset=file_size,
                            last_processed_line=0,
                            file_size_bytes=file_size,
                            partial_hash=partial_hash,
                        )
                savepoint.commit()
            except Exception:
                # Rollback savepoint on any error (IntegrityError, etc.)
                savepoint.rollback()
                raise
        except Exception as e:
            # Log but don't fail - RawLog is optional for uploaded files
            logger.warning(f"Failed to update raw_log for {file_path}: {e}")

    def _queue_tagging(self, conversation_id: UUID) -> None:
        """Queue a conversation for LLM tagging."""
        from catsyphon.models.db import TaggingJob

        try:
            tagging_job = TaggingJob(
                conversation_id=conversation_id,
                status="pending",
            )
            self.session.add(tagging_job)
            logger.debug(f"Queued tagging job for conversation {conversation_id}")
        except Exception as e:
            logger.warning(f"Failed to queue tagging: {e}")
