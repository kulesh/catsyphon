"""
HTTP Collector Client for CatSyphon.

This module provides a client for pushing events to CatSyphon via the
Collector Events API. Used by the watcher when --use-api is enabled.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx

from catsyphon.config import settings
from catsyphon.models.parsed import ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """
    Recursively serialize an object for JSON transmission.

    Handles datetime objects and nested structures (dicts, lists).
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, UUID):
        return str(obj)
    else:
        return obj


@dataclass
class CollectorConfig:
    """
    Configuration for the collector client.

    Defaults are loaded from settings (environment variables):
    - batch_size: CATSYPHON_COLLECTOR_BATCH_SIZE (default: 20)
    - max_retries: CATSYPHON_COLLECTOR_MAX_RETRIES (default: 3)
    - timeout: CATSYPHON_COLLECTOR_HTTP_TIMEOUT (default: 30)
    """

    server_url: str
    api_key: str
    collector_id: str
    batch_size: int | None = None
    max_retries: int | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        """Apply settings defaults for None values."""
        if self.batch_size is None:
            self.batch_size = settings.collector_batch_size
        if self.max_retries is None:
            self.max_retries = settings.collector_max_retries
        if self.timeout is None:
            self.timeout = float(settings.collector_http_timeout)


@dataclass
class EventBatch:
    """A batch of events to send."""

    session_id: str
    events: list[dict[str, Any]] = field(default_factory=list)


def _compute_event_hash(event_type: str, emitted_at: datetime, data: dict) -> str:
    """
    Compute a content-based hash for event deduplication.

    Args:
        event_type: Type of event (message, tool_call, etc.)
        emitted_at: When the event was emitted
        data: Event data payload

    Returns:
        32-character hex digest for deduplication
    """
    content = json.dumps(data, sort_keys=True, default=str)
    hash_input = f"{event_type}:{emitted_at.isoformat()}:{content}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


class CollectorClient:
    """
    HTTP client for the CatSyphon Collector Events API.

    Converts parsed conversations to events and sends them to the server.
    Handles batching and retries. Uses content-based hashing for deduplication.
    """

    def __init__(self, config: CollectorConfig):
        self.config = config
        self._client = httpx.Client(
            base_url=config.server_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "X-Collector-ID": config.collector_id,
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "CollectorClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def ingest_conversation(
        self,
        parsed: ParsedConversation,
        session_id: str,
        agent_type: str = "claude-code",
        agent_version: str = "unknown",
        working_directory: Optional[str] = None,
        git_branch: Optional[str] = None,
        parent_session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Ingest a parsed conversation via the Collector Events API.

        Args:
            parsed: Parsed conversation from a log file
            session_id: Unique session identifier
            agent_type: Type of AI agent (e.g., 'claude-code')
            agent_version: Version of the agent
            working_directory: Working directory for the session
            git_branch: Git branch name
            parent_session_id: Parent session ID for sub-agent conversations

        Returns:
            Response dict with conversation_id and ingestion stats
        """
        events: list[dict[str, Any]] = []

        # Use parsed values with fallbacks
        resolved_working_directory = working_directory or parsed.working_directory
        resolved_git_branch = git_branch or parsed.git_branch
        resolved_parent_session_id = parent_session_id or parsed.parent_session_id

        # Session start event - include parent_session_id for hierarchy
        # Also include metadata for semantic parity with direct ingestion
        session_start_data: dict[str, Any] = {
            "agent_type": agent_type or parsed.agent_type,
            "agent_version": agent_version or parsed.agent_version or "unknown",
            "working_directory": resolved_working_directory,
            "git_branch": resolved_git_branch,
        }
        # Only include parent_session_id if set (for hierarchy tracking)
        if resolved_parent_session_id:
            session_start_data["parent_session_id"] = resolved_parent_session_id

        # Add metadata for semantic parity with direct ingestion
        # Use _serialize_for_json to handle datetime objects in nested structures
        if parsed.slug:
            session_start_data["slug"] = parsed.slug
        if parsed.summaries:
            session_start_data["summaries"] = _serialize_for_json(parsed.summaries)
        if parsed.compaction_events:
            session_start_data["compaction_events"] = _serialize_for_json(
                parsed.compaction_events
            )
        # Spread any additional metadata from the parser
        if parsed.metadata:
            for key, value in parsed.metadata.items():
                if key not in session_start_data:
                    session_start_data[key] = _serialize_for_json(value)

        events.append(
            self._create_event(
                event_type="session_start",
                emitted_at=parsed.start_time or datetime.now(timezone.utc),
                data=session_start_data,
            )
        )

        # Convert messages to events (including tool_call events)
        for msg in parsed.messages:
            events.extend(self._message_to_events(msg))

        # Session end event (if we have an end time)
        # Include plans and files_touched for semantic parity with direct ingestion
        if parsed.end_time:
            session_end_data: dict[str, Any] = {
                "outcome": "unknown",
                "total_messages": len(parsed.messages),
            }
            # Add plans for semantic parity (finalized at session end)
            if parsed.plans:
                session_end_data["plans"] = [plan.to_dict() for plan in parsed.plans]
            # Add files_touched for semantic parity
            if parsed.files_touched:
                session_end_data["files_touched"] = parsed.files_touched

            events.append(
                self._create_event(
                    event_type="session_end",
                    emitted_at=parsed.end_time,
                    data=session_end_data,
                )
            )

        # Send events in batches
        result = self._send_events(session_id, events)

        # Complete the session (event count is a hint, not authoritative)
        self._complete_session(
            session_id,
            event_count=len(events),
            outcome="success",
        )

        return result

    def _create_event(
        self,
        event_type: str,
        emitted_at: datetime,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an event with proper structure and content-based hash."""
        observed_at = datetime.now(timezone.utc)
        resolved_emitted_at = emitted_at or observed_at

        return {
            "type": event_type,
            "emitted_at": resolved_emitted_at.isoformat(),
            "observed_at": observed_at.isoformat(),
            "event_hash": _compute_event_hash(event_type, resolved_emitted_at, data),
            "data": data,
        }

    def _message_to_events(self, msg: ParsedMessage) -> list[dict[str, Any]]:
        """
        Convert a ParsedMessage to collector events.

        Returns a list because a single message may contain multiple tool calls,
        each of which becomes a separate tool_call event.
        """
        events: list[dict[str, Any]] = []

        # Map role to author_role
        role_mapping = {
            "user": "human",
            "human": "human",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
        }
        author_role = msg.author_role or role_mapping.get(msg.role, "assistant")

        # Use emitted_at if available, fall back to timestamp
        event_time = msg.emitted_at or msg.timestamp or datetime.now(timezone.utc)

        # Map to message_type - use parsed value if available
        message_type = msg.message_type
        if not message_type:
            if msg.role in ("user", "human"):
                message_type = "prompt"
            elif msg.role == "tool":
                message_type = "tool_result"
            else:
                message_type = "response"

        # Create tool_call events for each tool call in the message
        if msg.tool_calls:
            for idx, tool_call in enumerate(msg.tool_calls):
                tool_event_time = tool_call.timestamp or event_time
                # Generate unique tool_use_id from timestamp and index
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

                # If tool has a result, also create a tool_result event
                if tool_call.result is not None:
                    # Ensure result is a string (it may be a list of content blocks)
                    result_value = tool_call.result
                    if not isinstance(result_value, str):
                        result_value = json.dumps(result_value)
                    events.append(
                        self._create_event(
                            event_type="tool_result",
                            emitted_at=tool_event_time,
                            data={
                                "tool_use_id": tool_use_id,  # Match the tool_call above
                                "success": tool_call.success,
                                "result": result_value,
                            },
                        )
                    )

        # Create the main message event
        data: dict[str, Any] = {
            "author_role": author_role,
            "message_type": message_type,
            "content": msg.content or "",
        }

        # Add optional fields
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

    def _send_events(
        self,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send events in batches with retry logic."""
        total_accepted = 0
        conversation_id = None
        batch_size = self.config.batch_size

        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]
            result = self._send_batch_with_retry(session_id, batch)
            total_accepted += result.get("accepted", 0)
            if result.get("conversation_id"):
                conversation_id = result["conversation_id"]

        return {
            "accepted": total_accepted,
            "conversation_id": conversation_id,
            "total_events": len(events),
        }

    def _send_batch_with_retry(
        self,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send a batch with exponential backoff retry.

        Uses content-based deduplication on the server side.
        Retries only on network errors and 5xx server errors.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries):
            try:
                response = self._client.post(
                    "/collectors/events",
                    json={
                        "session_id": session_id,
                        "events": events,
                    },
                )

                if response.status_code == 202:
                    return response.json()

                if response.status_code >= 500:
                    # Server error - retry with backoff
                    wait_time = 2**attempt
                    logger.warning(
                        f"Server error {response.status_code}, retrying in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue

                # Client error (4xx) - don't retry, fail immediately
                response.raise_for_status()

            except httpx.RequestError as e:
                last_error = e
                wait_time = 2**attempt
                logger.warning(f"Network error: {e}, retrying in {wait_time}s")
                time.sleep(wait_time)

        raise RuntimeError(
            f"Failed to send events after {self.config.max_retries} retries: {last_error}"
        )

    def _get_session_status(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session status for resumption."""
        try:
            response = self._client.get(f"/collectors/sessions/{session_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError:
            return None

    def ensure_session_started(
        self,
        *,
        session_id: str,
        agent_type: str,
        agent_version: Optional[str] = None,
        working_directory: Optional[str] = None,
        git_branch: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        emitted_at: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Ensure a session exists on the server by sending a session_start event.

        Returns True if a session_start was sent, False if the session already exists.
        """
        status = self._get_session_status(session_id)
        if status:
            return False

        session_start_data: dict[str, Any] = {
            "agent_type": agent_type or "unknown",
            "agent_version": agent_version or "unknown",
            "working_directory": working_directory,
            "git_branch": git_branch,
        }
        if parent_session_id:
            session_start_data["parent_session_id"] = parent_session_id

        if metadata:
            for key, value in metadata.items():
                if key not in session_start_data:
                    session_start_data[key] = _serialize_for_json(value)

        event_time = emitted_at or datetime.now(timezone.utc)
        event = self._create_event(
            event_type="session_start",
            emitted_at=event_time,
            data=session_start_data,
        )
        self._send_events(session_id, [event])
        return True

    def _complete_session(
        self,
        session_id: str,
        event_count: int = 0,
        outcome: str = "success",
        summary: Optional[str] = None,
    ) -> dict[str, Any]:
        """Mark a session as completed."""
        try:
            response = self._client.post(
                f"/collectors/sessions/{session_id}/complete",
                json={
                    "event_count": event_count,
                    "outcome": outcome,
                    "summary": summary,
                },
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to complete session: {response.status_code}")
            return {}
        except httpx.RequestError as e:
            logger.warning(f"Failed to complete session: {e}")
            return {}

    def ingest_incremental_messages(
        self,
        messages: list[ParsedMessage],
        session_id: str,
    ) -> dict[str, Any]:
        """
        Ingest only new messages for an existing session (incremental update).

        Unlike ingest_conversation, this method:
        - Does NOT send session_start event (session already exists)
        - Does NOT send session_end event (session may still be active)
        - Only sends message and tool_call events for new messages

        Args:
            messages: List of new ParsedMessage objects to ingest
            session_id: Existing session identifier

        Returns:
            Response dict with conversation_id and ingestion stats
        """
        if not messages:
            return {"accepted": 0, "conversation_id": None, "total_events": 0}

        events: list[dict[str, Any]] = []

        # Convert only new messages to events
        for msg in messages:
            events.extend(self._message_to_events(msg))

        if not events:
            return {"accepted": 0, "conversation_id": None, "total_events": 0}

        # Send events in batches (no session completion for incremental)
        result = self._send_events(session_id, events)

        logger.debug(
            f"Incremental ingest: {len(messages)} messages → {result.get('accepted', 0)} events"
        )

        return result


def compute_ingestion_fingerprint(
    messages: list[Any],
    include_content: bool = True,
) -> str:
    """
    Compute a deterministic fingerprint for ingested messages.

    Used for reconciliation between direct and API-based ingestion.

    Args:
        messages: List of message objects (ParsedMessage or Message ORM)
        include_content: Whether to include message content in hash

    Returns:
        SHA-256 hex digest of the canonical representation
    """
    hasher = hashlib.sha256()

    # Sort by sequence/index for deterministic ordering
    sorted_msgs = sorted(
        messages,
        key=lambda m: getattr(m, "sequence", 0) or getattr(m, "message_index", 0) or 0,
    )

    for msg in sorted_msgs:
        # Extract fields that should match between methods
        role = getattr(msg, "role", "") or ""
        content = getattr(msg, "content", "") or "" if include_content else ""
        timestamp = getattr(msg, "timestamp", None) or getattr(msg, "emitted_at", None)
        ts_str = timestamp.isoformat() if timestamp else ""

        # Hash each message's canonical representation
        canonical = f"{role}|{ts_str}|{len(content)}|{content[:100]}"
        hasher.update(canonical.encode("utf-8"))

    return hasher.hexdigest()


def register_collector(
    server_url: str,
    workspace_id: str,
    collector_type: str = "watcher",
    collector_version: str = "1.0.0",
    hostname: Optional[str] = None,
) -> dict[str, Any]:
    """
    Register a new collector with the CatSyphon server.

    Args:
        server_url: Base URL of the CatSyphon server
        workspace_id: UUID of the workspace to register with
        collector_type: Type of collector (e.g., 'watcher', 'aiobscura')
        collector_version: Version string
        hostname: Hostname of this machine

    Returns:
        Dict with collector_id, api_key, api_key_prefix
    """
    import socket

    if hostname is None:
        hostname = socket.gethostname()

    with httpx.Client(base_url=server_url, timeout=30.0) as client:
        response = client.post(
            "/collectors",
            json={
                "collector_type": collector_type,
                "collector_version": collector_version,
                "hostname": hostname,
                "workspace_id": workspace_id,
            },
        )
        response.raise_for_status()
        return response.json()
