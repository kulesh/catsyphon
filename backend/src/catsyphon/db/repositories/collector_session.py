"""
Collector session repository.

Handles collector events protocol operations:
- Session creation/lookup by collector_session_id
- Sequence tracking for resumption
- Event deduplication

Semantic Parity Notes:
This repository mirrors the behavior of the direct file ingestion pipeline
(pipeline/ingestion.py) to ensure conversations ingested via the Collector
Events API have the same fields populated as those ingested from log files.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import (
    AuthorRole,
    Conversation,
    ConversationType,
    Developer,
    Epoch,
    FileTouched,
    Message,
    MessageType,
    Project,
)

logger = logging.getLogger(__name__)


def _extract_username_from_path(path: Optional[str]) -> Optional[str]:
    """
    Extract username from a file path.

    Mirrors pipeline/ingestion.py:_extract_username_from_path for semantic parity.

    Attempts to extract the username from common path patterns like:
    - /Users/username/... (macOS)
    - /home/username/... (Linux)
    - C:\\Users\\username\\... (Windows)

    Args:
        path: File system path (e.g., working_directory)

    Returns:
        Extracted username or None if not found
    """
    if not path:
        return None

    # Normalize path separators
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")

    # Check for /Users/username (macOS)
    if len(parts) > 2 and parts[1].lower() == "users":
        return parts[2]

    # Check for /home/username (Linux)
    if len(parts) > 2 and parts[1].lower() == "home":
        return parts[2]

    # Check for C:/Users/username (Windows, already normalized)
    if len(parts) > 2 and parts[-3].lower() == "users":
        return parts[-2]

    return None


class CollectorSessionRepository(BaseRepository[Conversation]):
    """Repository for collector session operations."""

    def __init__(self, session: Session):
        super().__init__(Conversation, session)

    def get_by_collector_session_id(
        self, collector_session_id: str
    ) -> Optional[Conversation]:
        """
        Get conversation by collector session ID.

        Args:
            collector_session_id: Original session_id from collector

        Returns:
            Conversation if found, None otherwise
        """
        return (
            self.session.query(Conversation)
            .filter(Conversation.collector_session_id == collector_session_id)
            .first()
        )

    def _get_or_create_project(
        self, workspace_id: uuid.UUID, working_directory: Optional[str]
    ) -> Optional[Project]:
        """
        Get or create a project based on working directory.

        Args:
            workspace_id: Workspace UUID
            working_directory: Working directory path

        Returns:
            Project if working_directory provided, None otherwise
        """
        if not working_directory:
            return None

        # Derive project name from working directory
        path = Path(working_directory)
        project_name = path.name or working_directory

        # Look for existing project by directory_path
        project = (
            self.session.query(Project)
            .filter(
                Project.workspace_id == workspace_id,
                Project.directory_path == working_directory,
            )
            .first()
        )

        if not project:
            # Create new project
            project = Project(
                workspace_id=workspace_id,
                name=project_name,
                directory_path=working_directory,
            )
            self.session.add(project)
            self.session.flush()

        return project

    def _get_or_create_developer(
        self, workspace_id: uuid.UUID, working_directory: Optional[str]
    ) -> Optional[Developer]:
        """
        Get or create a developer based on username extracted from working directory.

        Mirrors pipeline/ingestion.py:_resolve_project_and_developer for semantic parity.

        Args:
            workspace_id: Workspace UUID
            working_directory: Working directory path to extract username from

        Returns:
            Developer if username can be extracted, None otherwise
        """
        username = _extract_username_from_path(working_directory)
        if not username:
            return None

        # Look for existing developer
        developer = (
            self.session.query(Developer)
            .filter(
                Developer.workspace_id == workspace_id,
                Developer.username == username,
            )
            .first()
        )

        if not developer:
            # Create new developer
            developer = Developer(
                workspace_id=workspace_id,
                username=username,
            )
            self.session.add(developer)
            self.session.flush()
            logger.debug(f"Created developer: {username} ({developer.id})")

        return developer

    def get_or_create_session(
        self,
        collector_session_id: str,
        workspace_id: uuid.UUID,
        collector_id: uuid.UUID,
        agent_type: str = "unknown",
        agent_version: Optional[str] = None,
        working_directory: Optional[str] = None,
        git_branch: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        context_semantics: Optional[dict] = None,
        first_event_timestamp: Optional[datetime] = None,
        agent_metadata: Optional[dict] = None,
        # New fields for semantic parity with direct ingestion
        slug: Optional[str] = None,
        summaries: Optional[list[dict]] = None,
        compaction_events: Optional[list[dict]] = None,
        session_metadata: Optional[dict] = None,
    ) -> tuple[Conversation, bool]:
        """
        Get existing session or create new one.

        Mirrors pipeline/ingestion.py:ingest_conversation for semantic parity.

        Args:
            collector_session_id: Original session_id from collector
            workspace_id: Workspace UUID
            collector_id: Collector config UUID
            agent_type: Type of agent (e.g., 'claude-code')
            agent_version: Agent version string
            working_directory: Working directory path
            git_branch: Git branch name
            parent_session_id: Parent session ID for sub-agents
            context_semantics: Context sharing settings
            first_event_timestamp: Timestamp of first event (for accurate start_time)
            agent_metadata: Additional agent metadata (for agent conversations)
            slug: Human-readable session name (semantic parity)
            summaries: Session checkpoint summaries (semantic parity)
            compaction_events: Context compaction events (semantic parity)
            session_metadata: Additional metadata fields to spread into extra_data

        Returns:
            Tuple of (conversation, created) where created is True if new
        """
        existing = self.get_by_collector_session_id(collector_session_id)
        if existing:
            return existing, False

        # Look up parent conversation if parent_session_id provided
        parent_conversation_id = None
        parent_conversation = None
        if parent_session_id:
            parent_conversation = self.get_by_collector_session_id(parent_session_id)
            if parent_conversation:
                parent_conversation_id = parent_conversation.id

        # Determine conversation_type based on parent (mirrors ingestion.py logic)
        # If has parent_session_id, this is an agent/sub-agent conversation
        conversation_type = ConversationType.AGENT if parent_session_id else ConversationType.MAIN

        # Get or create project from working directory
        project = self._get_or_create_project(workspace_id, working_directory)

        # Get or create developer from working directory (semantic parity)
        developer = self._get_or_create_developer(workspace_id, working_directory)

        # Inherit project/developer from parent if not resolved locally (semantic parity)
        project_id = project.id if project else None
        developer_id = developer.id if developer else None

        if parent_conversation:
            if project_id is None and parent_conversation.project_id:
                project_id = parent_conversation.project_id
                logger.debug(f"Inherited project_id={project_id} from parent conversation")
            if developer_id is None and parent_conversation.developer_id:
                developer_id = parent_conversation.developer_id
                logger.debug(f"Inherited developer_id={developer_id} from parent conversation")

        # Use first event timestamp for start_time if provided, else now
        now = datetime.now(timezone.utc)
        start_time = first_event_timestamp or now

        # Build extra_data (mirrors _build_extra_data in ingestion.py)
        extra_data: dict[str, Any] = {
            "session_id": collector_session_id,
            "working_directory": working_directory,
            "git_branch": git_branch,
            "parent_session_id": parent_session_id,  # Store for deferred linking
        }
        # Add metadata for semantic parity with direct ingestion
        if slug:
            extra_data["slug"] = slug
        if summaries:
            extra_data["summaries"] = summaries
        if compaction_events:
            extra_data["compaction_events"] = compaction_events
        # Spread any additional metadata from the collector
        if session_metadata:
            for key, value in session_metadata.items():
                if key not in extra_data:
                    extra_data[key] = value

        # Build agent_metadata if this is an agent conversation
        resolved_agent_metadata: dict[str, Any] = agent_metadata or {}
        if parent_session_id:
            resolved_agent_metadata["parent_session_id"] = parent_session_id

        # Create new conversation (mirrors conversation_repo.create in ingestion.py)
        conversation = Conversation(
            workspace_id=workspace_id,
            collector_id=collector_id,
            collector_session_id=collector_session_id,
            project_id=project_id,
            developer_id=developer_id,  # NEW: semantic parity
            conversation_type=conversation_type,  # NEW: semantic parity
            agent_type=agent_type,
            agent_version=agent_version,
            start_time=start_time,
            status="active",
            iteration_count=1,  # NEW: semantic parity (matches ingestion.py)
            last_event_sequence=0,
            server_received_at=now,
            parent_conversation_id=parent_conversation_id,
            context_semantics=context_semantics or {},
            agent_metadata=resolved_agent_metadata,  # Never None - always a dict
            extra_data=extra_data,
        )
        self.session.add(conversation)
        self.session.flush()

        # Create default epoch for the conversation
        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=1,
            start_time=start_time,
            extra_data={"source": "collector"},
        )
        self.session.add(epoch)
        self.session.flush()

        return conversation, True

    def update_sequence(
        self,
        conversation: Conversation,
        last_sequence: int,
        event_count_delta: int = 0,
    ) -> None:
        """
        Update the last received sequence number.

        Args:
            conversation: Conversation to update
            last_sequence: New last sequence number
            event_count_delta: Number of events to add to message_count
        """
        conversation.last_event_sequence = last_sequence
        conversation.server_received_at = datetime.now(timezone.utc)
        if event_count_delta > 0:
            conversation.message_count += event_count_delta
        self.session.flush()

    def check_sequence_gap(
        self, conversation: Conversation, first_sequence: int
    ) -> Optional[tuple[int, int]]:
        """
        Check if there's a sequence gap.

        Args:
            conversation: Conversation to check
            first_sequence: First sequence number in incoming batch

        Returns:
            None if no gap, otherwise (last_received, expected) tuple
        """
        expected = conversation.last_event_sequence + 1
        if first_sequence > expected:
            return (conversation.last_event_sequence, expected)
        return None

    def filter_duplicate_sequences(
        self, conversation: Conversation, events: list[dict]
    ) -> list[dict]:
        """
        Filter out events with sequences already received.

        Args:
            conversation: Conversation to check against
            events: List of event dicts with 'sequence' key

        Returns:
            List of events with sequences > last_event_sequence
        """
        last_seq = conversation.last_event_sequence
        return [e for e in events if e.get("sequence", 0) > last_seq]

    def complete_session(
        self,
        conversation: Conversation,
        final_sequence: int,
        outcome: str,
        summary: Optional[str] = None,
        event_timestamp: Optional[datetime] = None,
        # New fields for semantic parity with direct ingestion
        plans: Optional[list[dict]] = None,
        files_touched: Optional[list[str]] = None,
    ) -> None:
        """
        Mark a session as completed.

        Args:
            conversation: Conversation to complete
            final_sequence: Expected final sequence number
            outcome: Session outcome (success, partial, failed, abandoned)
            summary: Optional session summary
            event_timestamp: Timestamp of the session_end event (for accurate end_time)
            plans: Plan data from session (semantic parity)
            files_touched: All files touched during session (semantic parity)
        """
        conversation.status = "completed"
        # Use event timestamp if provided, else now
        end_time = event_timestamp or datetime.now(timezone.utc)
        conversation.end_time = end_time
        conversation.last_event_sequence = max(
            conversation.last_event_sequence, final_sequence
        )

        # Map outcome to success boolean
        if outcome == "success":
            conversation.success = True
        elif outcome in ("failed", "abandoned"):
            conversation.success = False
        # partial and other outcomes leave success as None

        # Store summary and plans in extra_data if provided
        if summary or plans:
            extra = dict(conversation.extra_data or {})
            if summary:
                extra["summary"] = summary
            if plans:
                extra["plans"] = plans
            conversation.extra_data = extra

        # Create FileTouched records for files not already tracked
        if files_touched:
            self._add_batch_files_touched(conversation, files_touched, end_time)

        self.session.flush()

    def update_last_activity(
        self,
        conversation: Conversation,
        event_timestamp: datetime,
    ) -> None:
        """
        Update the conversation's last activity timestamp.

        Called after processing events to keep end_time current.

        Args:
            conversation: Conversation to update
            event_timestamp: Timestamp of the latest event
        """
        # Update end_time to latest event if newer
        if conversation.end_time is None or event_timestamp > conversation.end_time:
            conversation.end_time = event_timestamp
        self.session.flush()

    def link_orphaned_collectors(self, workspace_id: uuid.UUID) -> int:
        """
        Link orphaned collector sessions to their parents.

        Finds sessions that have parent_session_id in extra_data but no
        parent_conversation_id set (parent wasn't created yet when child was).

        Also updates conversation_type and inherits project/developer from parent
        for full semantic parity with direct ingestion.

        Args:
            workspace_id: Workspace to process

        Returns:
            Number of sessions linked
        """
        linked_count = 0

        # Find sessions without parent_conversation_id that have extra_data
        # We check parent_session_id in Python to be DB-agnostic (SQLite vs PostgreSQL)
        orphans = (
            self.session.query(Conversation)
            .filter(
                Conversation.workspace_id == workspace_id,
                Conversation.parent_conversation_id.is_(None),
                Conversation.extra_data.isnot(None),
            )
            .all()
        )

        for orphan in orphans:
            if not orphan.extra_data:
                continue
            parent_session_id = orphan.extra_data.get("parent_session_id")
            if not parent_session_id:
                continue

            # Look up parent
            parent = self.get_by_collector_session_id(parent_session_id)
            if parent:
                orphan.parent_conversation_id = parent.id

                # Update conversation_type to AGENT since it has a parent (semantic parity)
                if orphan.conversation_type != ConversationType.AGENT:
                    orphan.conversation_type = ConversationType.AGENT
                    logger.debug(f"Updated conversation_type to AGENT for {orphan.id}")

                # Inherit project and developer from parent if not set (semantic parity)
                if orphan.project_id is None and parent.project_id:
                    orphan.project_id = parent.project_id
                    logger.debug(f"Inherited project_id from parent for {orphan.id}")
                if orphan.developer_id is None and parent.developer_id:
                    orphan.developer_id = parent.developer_id
                    logger.debug(f"Inherited developer_id from parent for {orphan.id}")

                linked_count += 1

        if linked_count > 0:
            self.session.flush()

        return linked_count

    def _get_default_epoch(self, conversation: Conversation) -> Epoch:
        """Get or create the default epoch for a conversation."""
        epoch = (
            self.session.query(Epoch)
            .filter(Epoch.conversation_id == conversation.id)
            .order_by(Epoch.sequence.desc())
            .first()
        )
        if not epoch:
            # Create one if missing (shouldn't happen normally)
            epoch = Epoch(
                conversation_id=conversation.id,
                sequence=1,
                start_time=datetime.now(timezone.utc),
                extra_data={"source": "collector"},
            )
            self.session.add(epoch)
            self.session.flush()
        return epoch

    def add_message(
        self,
        conversation: Conversation,
        sequence: int,
        event_type: str,
        emitted_at: datetime,
        observed_at: datetime,
        data: dict,
    ) -> Message:
        """
        Add a message from a collector event.

        Mirrors pipeline/ingestion.py message creation for semantic parity.

        Args:
            conversation: Parent conversation
            sequence: Event sequence number
            event_type: Event type (message, tool_call, tool_result, etc.)
            emitted_at: When event was produced at source
            observed_at: When collector observed the event
            data: Event data payload

        Returns:
            Created Message instance
        """
        epoch = self._get_default_epoch(conversation)

        # Map event types to message roles
        role = self._derive_role(event_type, data)
        content = self._derive_content(event_type, data)

        # Map author_role string to enum
        author_role_str = data.get("author_role", "assistant")
        author_role = AuthorRole(author_role_str) if author_role_str else AuthorRole.ASSISTANT

        # Map message_type string to enum
        message_type_str = data.get("message_type") or event_type
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            message_type = MessageType.RESPONSE

        # Build tool_calls JSONB for tool_call events (semantic parity)
        # Mirrors the tool_calls_json structure in ingestion.py
        tool_calls: Optional[list[dict[str, Any]]] = None
        if event_type == "tool_call":
            tool_calls = [
                {
                    "tool_name": data.get("tool_name", "unknown"),
                    "tool_use_id": data.get("tool_use_id"),
                    "parameters": data.get("parameters", {}),
                    "result": None,  # Will be updated when tool_result arrives
                    "success": None,
                    "timestamp": emitted_at.isoformat(),
                }
            ]

        # Build extra_data for model and token_usage (semantic parity)
        # Mirrors the extra_data structure in ingestion.py
        extra_data: dict[str, Any] = {}
        if data.get("model"):
            extra_data["model"] = data["model"]
        if data.get("token_usage"):
            extra_data["token_usage"] = data["token_usage"]
        if data.get("stop_reason"):
            extra_data["stop_reason"] = data["stop_reason"]
        if data.get("thinking_metadata"):
            extra_data["thinking_metadata"] = data["thinking_metadata"]

        message = Message(
            epoch_id=epoch.id,
            conversation_id=conversation.id,
            sequence=sequence,
            role=role,
            content=content,
            timestamp=emitted_at,
            emitted_at=emitted_at,
            observed_at=observed_at,
            author_role=author_role,
            message_type=message_type,
            thinking_content=data.get("thinking_content"),
            tool_calls=tool_calls,  # NEW: semantic parity
            extra_data=extra_data if extra_data else None,  # NEW: semantic parity
            raw_data=data,  # Store full event data for reference
        )
        self.session.add(message)
        return message

    def add_file_touched(
        self,
        conversation: Conversation,
        file_path: str,
        change_type: str,
        timestamp: datetime,
        lines_added: int = 0,
        lines_deleted: int = 0,
    ) -> FileTouched:
        """
        Record a file that was touched during the conversation.

        Mirrors pipeline/ingestion.py FileTouched creation for semantic parity.

        Args:
            conversation: Parent conversation
            file_path: Path to the file
            change_type: Type of change (read, write, create, delete)
            timestamp: When the file was touched
            lines_added: Number of lines added
            lines_deleted: Number of lines deleted

        Returns:
            Created FileTouched instance
        """
        epoch = self._get_default_epoch(conversation)

        file_touched = FileTouched(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            file_path=file_path,
            change_type=change_type,
            timestamp=timestamp,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )
        self.session.add(file_touched)

        # Update denormalized count (semantic parity)
        conversation.files_count = (conversation.files_count or 0) + 1

        return file_touched

    def _add_batch_files_touched(
        self,
        conversation: Conversation,
        file_paths: list[str],
        timestamp: datetime,
    ) -> int:
        """
        Add batch of file touched records, deduplicating against existing records.

        Used by complete_session to add files from the parsed.files_touched list
        that weren't already tracked via tool_call events.

        Args:
            conversation: Parent conversation
            file_paths: List of file paths to add
            timestamp: When the files were touched

        Returns:
            Number of new files added
        """
        epoch = self._get_default_epoch(conversation)

        # Get existing file paths to avoid duplicates
        existing_paths = {
            ft.file_path
            for ft in self.session.query(FileTouched)
            .filter(FileTouched.conversation_id == conversation.id)
            .all()
        }

        added_count = 0
        for file_path in file_paths:
            if file_path not in existing_paths:
                file_touched = FileTouched(
                    conversation_id=conversation.id,
                    epoch_id=epoch.id,
                    file_path=file_path,
                    change_type="read",  # Default to 'read' for global list
                    timestamp=timestamp,
                )
                self.session.add(file_touched)
                added_count += 1

        # Update denormalized count
        if added_count > 0:
            conversation.files_count = (conversation.files_count or 0) + added_count

        return added_count

    def _derive_role(self, event_type: str, data: dict) -> str:
        """Derive message role from event type and data."""
        author_role = data.get("author_role", "")

        if author_role == "human":
            return "user"
        elif author_role in ("assistant", "agent"):
            return "assistant"
        elif author_role in ("tool", "system"):
            return "system"
        elif event_type in ("tool_call", "tool_result"):
            return "system"
        elif event_type == "thinking":
            return "assistant"
        else:
            return "user"

    def _derive_content(self, event_type: str, data: dict) -> str:
        """Derive message content from event type and data."""
        if event_type == "message":
            return data.get("content", "")
        elif event_type == "tool_call":
            tool_name = data.get("tool_name", "unknown")
            params = data.get("parameters", {})
            return f"[Tool Call: {tool_name}] {params}"
        elif event_type == "tool_result":
            result = data.get("result", "")
            error = data.get("error_message", "")
            if error:
                return f"[Tool Error] {error}"
            return f"[Tool Result] {result[:500]}" if len(result) > 500 else f"[Tool Result] {result}"
        elif event_type == "thinking":
            return data.get("content", "")
        elif event_type == "error":
            return f"[Error: {data.get('error_type', 'unknown')}] {data.get('message', '')}"
        elif event_type in ("session_start", "session_end", "metadata"):
            return f"[{event_type}] {data}"
        else:
            return str(data)
