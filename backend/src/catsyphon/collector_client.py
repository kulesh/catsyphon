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

from catsyphon.models.parsed import ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    """Configuration for the collector client."""

    server_url: str
    api_key: str
    collector_id: str
    batch_size: int = 20
    max_retries: int = 3
    timeout: float = 30.0


@dataclass
class EventBatch:
    """A batch of events to send."""

    session_id: str
    events: list[dict[str, Any]] = field(default_factory=list)


class CollectorClient:
    """
    HTTP client for the CatSyphon Collector Events API.

    Converts parsed conversations to events and sends them to the server.
    Handles batching, retries, and sequence tracking.
    """

    def __init__(self, config: CollectorConfig):
        self.config = config
        self.sequence = 0
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
        self.sequence = 0
        events: list[dict[str, Any]] = []

        # Use parsed values with fallbacks
        resolved_working_directory = working_directory or parsed.working_directory
        resolved_git_branch = git_branch or parsed.git_branch
        resolved_parent_session_id = parent_session_id or parsed.parent_session_id

        # Session start event - include parent_session_id for hierarchy
        session_start_data: dict[str, Any] = {
            "agent_type": agent_type or parsed.agent_type,
            "agent_version": agent_version or parsed.agent_version or "unknown",
            "working_directory": resolved_working_directory,
            "git_branch": resolved_git_branch,
        }
        # Only include parent_session_id if set (for hierarchy tracking)
        if resolved_parent_session_id:
            session_start_data["parent_session_id"] = resolved_parent_session_id

        events.append(self._create_event(
            event_type="session_start",
            emitted_at=parsed.start_time or datetime.now(timezone.utc),
            data=session_start_data,
        ))

        # Convert messages to events (including tool_call events)
        for msg in parsed.messages:
            events.extend(self._message_to_events(msg))

        # Session end event (if we have an end time)
        if parsed.end_time:
            events.append(self._create_event(
                event_type="session_end",
                emitted_at=parsed.end_time,
                data={
                    "outcome": "unknown",
                    "total_messages": len(parsed.messages),
                },
            ))

        # Send events in batches
        result = self._send_events(session_id, events)

        # Complete the session
        self._complete_session(
            session_id,
            final_sequence=self.sequence,
            outcome="success",
        )

        return result

    def _create_event(
        self,
        event_type: str,
        emitted_at: datetime,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an event with proper structure."""
        self.sequence += 1
        observed_at = datetime.now(timezone.utc)

        return {
            "sequence": self.sequence,
            "type": event_type,
            "emitted_at": emitted_at.isoformat() if emitted_at else observed_at.isoformat(),
            "observed_at": observed_at.isoformat(),
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
            for tool_call in msg.tool_calls:
                tool_event_time = tool_call.timestamp or event_time
                events.append(self._create_event(
                    event_type="tool_call",
                    emitted_at=tool_event_time,
                    data={
                        "tool_name": tool_call.tool_name,
                        "tool_use_id": f"tool_{self.sequence}",  # Generate ID if not available
                        "parameters": tool_call.parameters or {},
                    },
                ))

                # If tool has a result, also create a tool_result event
                if tool_call.result is not None:
                    events.append(self._create_event(
                        event_type="tool_result",
                        emitted_at=tool_event_time,
                        data={
                            "tool_use_id": f"tool_{self.sequence - 1}",  # Match previous tool_call
                            "success": tool_call.success,
                            "result": tool_call.result,
                        },
                    ))

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

        events.append(self._create_event(
            event_type="message",
            emitted_at=event_time,
            data=data,
        ))

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
            batch = events[i:i + batch_size]
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
        """Send a batch with exponential backoff retry."""
        last_error = None

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

                if response.status_code == 409:
                    # Sequence gap - check session status and resend
                    logger.warning(f"Sequence gap detected: {response.json()}")
                    status = self._get_session_status(session_id)
                    if status:
                        # Filter out already-received events
                        last_seq = status.get("last_sequence", 0)
                        events = [e for e in events if e["sequence"] > last_seq]
                        if not events:
                            return {"accepted": 0, "conversation_id": status.get("conversation_id")}
                        continue

                if response.status_code >= 500:
                    # Server error - retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue

                # Client error - don't retry
                response.raise_for_status()

            except httpx.RequestError as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(f"Network error: {e}, retrying in {wait_time}s")
                time.sleep(wait_time)

        raise RuntimeError(f"Failed to send events after {self.config.max_retries} retries: {last_error}")

    def _get_session_status(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session status for resumption."""
        try:
            response = self._client.get(f"/collectors/sessions/{session_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError:
            return None

    def _complete_session(
        self,
        session_id: str,
        final_sequence: int,
        outcome: str = "success",
        summary: Optional[str] = None,
    ) -> dict[str, Any]:
        """Mark a session as completed."""
        try:
            response = self._client.post(
                f"/collectors/sessions/{session_id}/complete",
                json={
                    "final_sequence": final_sequence,
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
    sorted_msgs = sorted(messages, key=lambda m: getattr(m, 'sequence', 0) or getattr(m, 'message_index', 0) or 0)

    for msg in sorted_msgs:
        # Extract fields that should match between methods
        role = getattr(msg, 'role', '') or ''
        content = getattr(msg, 'content', '') or '' if include_content else ''
        timestamp = getattr(msg, 'timestamp', None) or getattr(msg, 'emitted_at', None)
        ts_str = timestamp.isoformat() if timestamp else ''

        # Hash each message's canonical representation
        canonical = f"{role}|{ts_str}|{len(content)}|{content[:100]}"
        hasher.update(canonical.encode('utf-8'))

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
