"""
Collector session repository.

Handles collector events protocol operations:
- Session creation/lookup by collector_session_id
- Sequence tracking for resumption
- Event deduplication
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import (
    AuthorRole,
    Conversation,
    Developer,
    Epoch,
    Message,
    MessageType,
    Project,
)


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
    ) -> tuple[Conversation, bool]:
        """
        Get existing session or create new one.

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

        Returns:
            Tuple of (conversation, created) where created is True if new
        """
        existing = self.get_by_collector_session_id(collector_session_id)
        if existing:
            return existing, False

        # Look up parent conversation if parent_session_id provided
        parent_conversation_id = None
        if parent_session_id:
            parent = self.get_by_collector_session_id(parent_session_id)
            if parent:
                parent_conversation_id = parent.id

        # Get or create project from working directory
        project = self._get_or_create_project(workspace_id, working_directory)

        # Create new conversation
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            workspace_id=workspace_id,
            collector_id=collector_id,
            collector_session_id=collector_session_id,
            project_id=project.id if project else None,
            agent_type=agent_type,
            agent_version=agent_version,
            start_time=now,
            status="active",
            last_event_sequence=0,
            server_received_at=now,
            parent_conversation_id=parent_conversation_id,
            context_semantics=context_semantics or {},
            extra_data={
                "session_id": collector_session_id,
                "working_directory": working_directory,
                "git_branch": git_branch,
            },
        )
        self.session.add(conversation)
        self.session.flush()

        # Create default epoch for the conversation
        epoch = Epoch(
            conversation_id=conversation.id,
            sequence=1,
            start_time=now,
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
    ) -> None:
        """
        Mark a session as completed.

        Args:
            conversation: Conversation to complete
            final_sequence: Expected final sequence number
            outcome: Session outcome (success, partial, failed, abandoned)
            summary: Optional session summary
        """
        conversation.status = "completed"
        conversation.end_time = datetime.now(timezone.utc)
        conversation.last_event_sequence = max(
            conversation.last_event_sequence, final_sequence
        )

        # Map outcome to success boolean
        if outcome == "success":
            conversation.success = True
        elif outcome in ("failed", "abandoned"):
            conversation.success = False
        # partial and other outcomes leave success as None

        # Store summary in extra_data if provided
        if summary:
            extra = dict(conversation.extra_data or {})
            extra["summary"] = summary
            conversation.extra_data = extra

        self.session.flush()

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
            raw_data=data,  # Store full event data for reference
        )
        self.session.add(message)
        return message

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
