"""
Ingestion pipeline for transforming parsed conversations into database records.

This module handles the complete transformation of ParsedConversation objects
from parsers into database models, including conversations, epochs, messages,
files touched, and raw logs.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    EpochRepository,
    IngestionJobRepository,
    MessageRepository,
    ProjectRepository,
    RawLogRepository,
    WorkspaceRepository,
)
from catsyphon.exceptions import DuplicateFileError
from catsyphon.models.db import Conversation, Epoch, FileTouched, Message, RawLog
from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.incremental import IncrementalParseResult
from catsyphon.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


def _extract_username_from_path(path: Optional[str]) -> Optional[str]:
    """
    Extract username from a file path.

    Attempts to extract the username from common path patterns like:
    - /Users/username/... (macOS)
    - /home/username/... (Linux)
    - C:\\Users\\username\\... (Windows)

    Args:
        path: File system path (e.g., working_directory)

    Returns:
        Extracted username or None if not found

    Examples:
        >>> _extract_username_from_path("/Users/kulesh/dev/project")
        'kulesh'
        >>> _extract_username_from_path("/home/sarah/code")
        'sarah'
        >>> _extract_username_from_path("C:\\Users\\john\\projects")
        'john'
        >>> _extract_username_from_path(None)
        None
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


def _outcome_to_success(outcome: Optional[str]) -> Optional[bool]:
    """
    Convert outcome tag value to success boolean.

    Args:
        outcome: Outcome tag value (success, failed, partial, unknown, abandoned)

    Returns:
        True for success, False for failed/partial, None for unknown/abandoned/None

    Examples:
        >>> _outcome_to_success("success")
        True
        >>> _outcome_to_success("failed")
        False
        >>> _outcome_to_success("partial")
        False
        >>> _outcome_to_success("unknown")
        None
        >>> _outcome_to_success(None)
        None
    """
    if not outcome:
        return None

    if outcome == "success":
        return True
    elif outcome in ("failed", "partial"):
        return False
    else:  # unknown, abandoned, or other
        return None


def _get_or_create_default_workspace(session: Session) -> UUID:
    """
    Get or create a default workspace for ingestion.

    This is a temporary helper until proper multi-workspace support is implemented.
    Creates a default workspace named "Default" if none exists.

    Args:
        session: Database session

    Returns:
        UUID of the default workspace
    """
    workspace_repo = WorkspaceRepository(session)

    # Try to get the first workspace
    workspaces = workspace_repo.get_all(limit=1)
    if workspaces:
        return workspaces[0].id

    # No workspaces exist - create a default one
    # First, we need an organization
    from catsyphon.db.repositories import OrganizationRepository

    org_repo = OrganizationRepository(session)
    orgs = org_repo.get_all(limit=1)

    if orgs:
        org_id = orgs[0].id
    else:
        # Create default organization
        default_org = org_repo.create(
            name="Default Organization", slug="default-organization"
        )
        session.flush()  # Get the ID
        org_id = default_org.id

    # Create default workspace
    default_workspace = workspace_repo.create(
        organization_id=org_id,
        name="Default Workspace",
        slug="default-workspace",
    )
    session.flush()  # Get the ID

    logger.info(f"Created default workspace: {default_workspace.id}")
    return default_workspace.id


def ingest_conversation(
    session: Session,
    parsed: ParsedConversation,
    project_name: Optional[str] = None,
    developer_username: Optional[str] = None,
    file_path: Optional[Path] = None,
    tags: Optional[dict[str, Any]] = None,
    skip_duplicates: bool = True,
    update_mode: str = "skip",
    source_type: str = "cli",
    source_config_id: Optional[UUID] = None,
    created_by: Optional[str] = None,
) -> Conversation:
    """
    Ingest a parsed conversation into the database.

    Args:
        session: Database session
        parsed: Parsed conversation from parser
        project_name: Project name for grouping (optional)
        developer_username: Developer username (optional)
        file_path: Path to original log file (optional)
        tags: Pre-computed tags from tagging engine (optional)
        skip_duplicates: If True, skip files already processed
            (default: True)
        update_mode: How to handle existing conversations by session_id:
            - "skip": Return existing without changes (default)
            - "replace": Delete children and recreate with new data (full reparse)
            - "append": Reserved for future incremental updates
        source_type: Source of ingestion ('cli', 'upload', 'watch')
        source_config_id: UUID of watch configuration if source_type='watch'
        created_by: Username who triggered the ingestion (for 'upload')

    Returns:
        Created or updated Conversation instance with all relationships loaded

    Raises:
        DuplicateFileError: If file is a duplicate and skip_duplicates=False
        Exception: If database operation fails (transaction will be rolled back)

    Example:
        from catsyphon.parsers import get_default_registry
        from catsyphon.db.connection import get_db

        # Parse conversation
        registry = get_default_registry()
        parsed = registry.parse(Path("conversation.jsonl"))

        # Ingest into database
        with get_db() as session:
            conversation = ingest_conversation(
                session,
                parsed,
                project_name="my-project",
                developer_username="john",
                file_path=Path("conversation.jsonl"),
            )
            session.commit()
    """
    logger.info(f"Starting ingestion: {len(parsed.messages)} messages")

    # Get or create default workspace
    workspace_id = _get_or_create_default_workspace(session)
    logger.debug(f"Using workspace: {workspace_id}")

    # Initialize timing for ingestion job tracking
    start_time = datetime.utcnow()
    start_ms = time.time() * 1000  # Convert to milliseconds

    # Initialize ingestion job repository
    ingestion_repo = IngestionJobRepository(session)

    # Create initial ingestion job record
    ingestion_job = ingestion_repo.create(
        source_type=source_type,
        source_config_id=source_config_id,
        file_path=str(file_path) if file_path else None,
        status="processing",
        started_at=start_time,
        created_by=created_by,
        incremental=False,  # Will update if incremental path taken
        messages_added=0,
    )
    session.flush()  # Get job ID
    logger.debug(f"Created ingestion job: {ingestion_job.id}")

    # Check for duplicate files before processing
    if file_path:
        raw_log_repo = RawLogRepository(session)
        file_hash = calculate_file_hash(file_path)

        if raw_log_repo.exists_by_file_hash(file_hash):
            if skip_duplicates:
                logger.info(
                    f"Skipping duplicate file: {file_path} (hash: {file_hash[:8]}...)"
                )
                # Get existing conversation for this file
                existing_raw_log = raw_log_repo.get_by_file_hash(file_hash)
                if existing_raw_log:
                    # Update ingestion job as duplicate
                    elapsed_ms = int((time.time() * 1000) - start_ms)
                    ingestion_job.status = "duplicate"
                    ingestion_job.raw_log_id = existing_raw_log.id
                    ingestion_job.conversation_id = existing_raw_log.conversation_id
                    ingestion_job.processing_time_ms = elapsed_ms
                    ingestion_job.completed_at = datetime.utcnow()
                    session.flush()
                    logger.debug(
                        f"Updated ingestion job to duplicate: {ingestion_job.id}"
                    )

                    session.refresh(existing_raw_log.conversation)
                    return existing_raw_log.conversation
            else:
                # Update ingestion job as failed
                elapsed_ms = int((time.time() * 1000) - start_ms)
                ingestion_job.status = "failed"
                ingestion_job.error_message = (
                    f"Duplicate file (hash: {file_hash[:8]}...)"
                )
                ingestion_job.processing_time_ms = elapsed_ms
                ingestion_job.completed_at = datetime.utcnow()
                session.flush()
                raise DuplicateFileError(file_hash, str(file_path))

    # Initialize repositories
    conversation_repo = ConversationRepository(session)

    # Track whether this is an update or new conversation
    is_update = False
    conversation = None

    # Check for existing conversation by session_id AND conversation_type (if provided)
    # CRITICAL: Agent conversations share the parent's session_id, so we need to check
    # BOTH session_id and conversation_type to avoid false duplicates
    if parsed.session_id:
        existing_conversation = conversation_repo.get_by_session_id(
            parsed.session_id, workspace_id
        )

        # Filter to only matching conversation_type (allow main and agent to coexist)
        # NOTE: Normalize to uppercase for comparison (db has uppercase, parser has lowercase)
        if (
            existing_conversation
            and existing_conversation.conversation_type.upper()
            != parsed.conversation_type.upper()
        ):
            logger.info(
                f"Found conversation with same session_id but different type: "
                f"existing={existing_conversation.conversation_type}, new={parsed.conversation_type}. "
                f"Treating as separate conversations."
            )
            existing_conversation = None  # Treat as new conversation

        if existing_conversation:
            # Check if this is the SAME file being re-processed
            if file_path and existing_conversation.raw_logs:
                existing_file_paths = {
                    Path(rl.file_path)
                    for rl in existing_conversation.raw_logs
                    if rl.file_path is not None
                }
                is_same_file = file_path in existing_file_paths
            else:
                is_same_file = False

            if update_mode == "skip":
                logger.info(
                    f"Skipping existing conversation: session_id={parsed.session_id}, "
                    f"conversation_id={existing_conversation.id}"
                )
                # Update ingestion job as skipped
                elapsed_ms = int((time.time() * 1000) - start_ms)
                ingestion_job.status = "skipped"
                ingestion_job.conversation_id = existing_conversation.id
                ingestion_job.processing_time_ms = elapsed_ms
                ingestion_job.completed_at = datetime.utcnow()
                session.flush()
                logger.debug(f"Updated ingestion job to skipped: {ingestion_job.id}")

                session.refresh(existing_conversation)
                return existing_conversation

            elif update_mode == "replace":
                logger.info(
                    f"Replacing existing conversation: session_id={parsed.session_id}, "
                    f"conversation_id={existing_conversation.id}"
                )
                # Delete children (CASCADE will handle epochs, messages, files_touched)
                # and raw_logs if they exist

                # Delete children explicitly to ensure CASCADE works
                # NOTE: We do NOT delete RawLog - it will be updated in place
                # to avoid FK constraint violations
                session.query(Message).filter(
                    Message.conversation_id == existing_conversation.id
                ).delete()
                session.query(Epoch).filter(
                    Epoch.conversation_id == existing_conversation.id
                ).delete()
                session.query(FileTouched).filter(
                    FileTouched.conversation_id == existing_conversation.id
                ).delete()

                session.flush()

                # Update conversation fields with new data
                existing_conversation.project_id = None  # Will be set below
                existing_conversation.developer_id = None  # Will be set below
                existing_conversation.agent_type = parsed.agent_type
                existing_conversation.agent_version = parsed.agent_version
                existing_conversation.start_time = parsed.start_time
                existing_conversation.end_time = parsed.end_time
                existing_conversation.status = (
                    "completed" if parsed.end_time else "open"
                )
                existing_conversation.iteration_count = 1
                existing_conversation.tags = tags or {}
                existing_conversation.extra_data = {
                    "session_id": parsed.session_id,
                    "git_branch": parsed.git_branch,
                    "working_directory": parsed.working_directory,
                    **parsed.metadata,
                }

                # Use existing conversation for the rest of the ingestion
                conversation = existing_conversation
                logger.debug(f"Updated conversation: {conversation.id}")

                # Continue with ingestion flow but skip conversation creation
                # Jump to project/developer handling
                is_update = True

            elif update_mode == "append":
                # Incremental update: append only NEW messages (Phase 2)
                logger.info(
                    f"Appending to existing conversation: "
                    f"session_id={parsed.session_id}, "
                    f"conversation_id={existing_conversation.id}"
                )

                # Get existing raw_log for state tracking (if file_path provided)
                if not file_path:
                    raise ValueError(
                        "append mode requires file_path to track incremental state"
                    )

                # Get raw_log by file path
                existing_raw_log = raw_log_repo.get_by_file_path(str(file_path))
                if not existing_raw_log:
                    logger.warning(
                        f"No existing raw_log found for {file_path}, "
                        "falling back to full ingest"
                    )
                    # Fall through to regular ingestion (will create raw_log)
                    is_update = False
                else:
                    # Perform incremental append
                    updated_conversation = _append_messages_incremental(
                        session=session,
                        existing_conversation=existing_conversation,
                        existing_raw_log=existing_raw_log,
                        parsed=parsed,
                        tags=tags,
                    )

                    # Update ingestion job as successful incremental
                    elapsed_ms = int((time.time() * 1000) - start_ms)
                    messages_added = (
                        len(parsed.messages) - existing_conversation.message_count
                    )
                    ingestion_job.status = "success"
                    ingestion_job.conversation_id = updated_conversation.id
                    ingestion_job.raw_log_id = existing_raw_log.id
                    ingestion_job.processing_time_ms = elapsed_ms
                    ingestion_job.messages_added = messages_added
                    ingestion_job.incremental = True  # Incremental append
                    ingestion_job.completed_at = datetime.utcnow()
                    session.flush()
                    logger.debug(
                        f"Updated ingestion job to success (incremental): "
                        f"{ingestion_job.id}, messages_added={messages_added}, "
                        f"processing_time={elapsed_ms}ms"
                    )

                    return updated_conversation

    # Initialize remaining repositories
    project_repo = ProjectRepository(session)
    developer_repo = DeveloperRepository(session)
    conversation_repo = ConversationRepository(session)
    epoch_repo = EpochRepository(session)
    message_repo = MessageRepository(session)
    raw_log_repo = RawLogRepository(session)

    # Step 1: Get or create Project
    # Auto-detect from working_directory or use manual project_name
    project_id = None
    if project_name:
        # Manual override: use project_name as display name
        # If working_directory is available, use it as directory_path
        if parsed.working_directory:
            project = project_repo.get_or_create_by_directory(
                directory_path=parsed.working_directory,
                workspace_id=workspace_id,
                name=project_name,  # Override auto-generated name
            )
        else:
            # Fallback to old behavior if no working_directory
            project = project_repo.get_or_create_by_name(project_name, workspace_id)
        project_id = project.id
        logger.debug(f"Project: {project.name} ({project.id})")
    elif parsed.working_directory:
        # Auto-detect project from working_directory
        project = project_repo.get_or_create_by_directory(
            directory_path=parsed.working_directory, workspace_id=workspace_id
        )
        project_id = project.id
        logger.debug(
            f"Auto-detected project: {project.name} from {parsed.working_directory}"
        )
    else:
        logger.warning(
            "No project association: working_directory not found and --project not provided"
        )

    # Step 2: Get or create Developer
    developer_id = None
    # Auto-extract username from working_directory if not explicitly provided
    effective_username = developer_username or _extract_username_from_path(
        parsed.working_directory
    )
    if effective_username:
        developer = developer_repo.get_or_create_by_username(
            effective_username, workspace_id
        )
        developer_id = developer.id
        source = "explicit" if developer_username else "auto-extracted from path"
        logger.debug(f"Developer: {developer.username} ({developer.id}) [{source}]")

    # Step 3: Hierarchical conversation linking (Phase 2: Epic 7u2)
    # If this is an agent/subagent conversation, find the parent conversation
    parent_conversation_id = None
    # NOTE: Parser returns lowercase "agent" but database stores uppercase "AGENT"
    # (due to migration using enum key names instead of values)
    if parsed.conversation_type.lower() == "agent" and parsed.parent_session_id:
        # Look up parent - it should be the MAIN conversation with this session_id
        parent_conversation = conversation_repo.get_by_session_id(
            parsed.parent_session_id, workspace_id
        )
        # Only link if we found a MAIN conversation (avoid self-reference with agents)
        # Database has uppercase values, so compare with uppercase
        if parent_conversation and parent_conversation.conversation_type.upper() == "MAIN":
            parent_conversation_id = parent_conversation.id
            logger.info(
                f"Linking agent conversation (session_id={parsed.session_id}) "
                f"to parent (session_id={parsed.parent_session_id}, id={parent_conversation_id})"
            )
        else:
            logger.warning(
                f"Parent MAIN conversation not found for agent (parent_session_id={parsed.parent_session_id}). "
                f"Agent conversation will be created without parent link."
            )

    # Step 4: Create or Update Conversation
    # Convert outcome tag to success boolean
    success_value = None
    if tags and "outcome" in tags:
        success_value = _outcome_to_success(tags["outcome"])

    if not is_update:
        # Create new conversation
        conversation = conversation_repo.create(
            workspace_id=workspace_id,
            project_id=project_id,
            developer_id=developer_id,
            parent_conversation_id=parent_conversation_id,
            conversation_type=parsed.conversation_type,
            agent_type=parsed.agent_type,
            agent_version=parsed.agent_version,
            start_time=parsed.start_time,
            end_time=parsed.end_time,
            status="completed" if parsed.end_time else "open",
            success=success_value,
            iteration_count=1,  # TODO: Detect iterations from parsed data
            tags=tags or {},
            context_semantics=parsed.context_semantics,
            agent_metadata=parsed.agent_metadata,
            extra_data={
                "session_id": parsed.session_id,
                "git_branch": parsed.git_branch,
                "working_directory": parsed.working_directory,
                **parsed.metadata,
            },
        )
        logger.info(f"Created conversation: {conversation.id} (success={success_value})")
    else:
        # Update existing conversation with project/developer/hierarchy associations
        assert conversation is not None, "conversation must be set in replace mode"
        conversation.project_id = project_id
        conversation.developer_id = developer_id
        conversation.parent_conversation_id = parent_conversation_id
        conversation.conversation_type = parsed.conversation_type
        conversation.context_semantics = parsed.context_semantics
        conversation.agent_metadata = parsed.agent_metadata
        conversation.success = success_value  # Update success from tags
        logger.info(f"Updated conversation associations: {conversation.id} (success={success_value})")

    # Step 4: Create Epoch (one epoch per conversation for now)
    # TODO: Implement multi-epoch detection based on conversation restarts
    epoch = epoch_repo.create_epoch(
        conversation_id=conversation.id,
        sequence=0,
        start_time=parsed.start_time,
        end_time=parsed.end_time,
        # Tags can provide intent/outcome/sentiment if available
        intent=tags.get("intent") if tags else None,
        outcome=tags.get("outcome") if tags else None,
        sentiment=tags.get("sentiment") if tags else None,
        sentiment_score=tags.get("sentiment_score") if tags else None,
    )
    logger.debug(f"Created epoch: {epoch.id}")

    # Step 5: Create Messages (bulk insert for efficiency)
    message_data = []
    for idx, msg in enumerate(parsed.messages):
        # Serialize tool calls and code changes to JSON
        tool_calls_json = [
            {
                "tool_name": tc.tool_name,
                "parameters": tc.parameters,
                "result": tc.result,
                "success": tc.success,
                "timestamp": tc.timestamp.isoformat() if tc.timestamp else None,
            }
            for tc in msg.tool_calls
        ]

        code_changes_json = [
            {
                "file_path": cc.file_path,
                "change_type": cc.change_type,
                "old_content": cc.old_content,
                "new_content": cc.new_content,
                "lines_added": cc.lines_added,
                "lines_deleted": cc.lines_deleted,
            }
            for cc in msg.code_changes
        ]

        # Add model and token_usage to extra_data
        extra_data: dict[str, Any] = {}
        if msg.model:
            extra_data["model"] = msg.model
        if msg.token_usage:
            extra_data["token_usage"] = msg.token_usage

        message_data.append(
            {
                "epoch_id": epoch.id,
                "conversation_id": conversation.id,
                "role": msg.role,
                "content": msg.content,
                "thinking_content": msg.thinking_content,
                "timestamp": msg.timestamp,
                "sequence": idx,
                "tool_calls": tool_calls_json,
                "code_changes": code_changes_json,
                "entities": msg.entities,
                "extra_data": extra_data,
            }
        )

    # Bulk create messages
    messages = message_repo.bulk_create(message_data)
    logger.info(f"Created {len(messages)} messages")

    # Step 6: Create FileTouched records
    if parsed.files_touched:
        for file_path_str in parsed.files_touched:
            file_touched = FileTouched(
                conversation_id=conversation.id,
                epoch_id=epoch.id,
                file_path=file_path_str,
                change_type="read",  # Default to 'read', could be enhanced
                timestamp=parsed.start_time,
            )
            session.add(file_touched)
        logger.debug(f"Created {len(parsed.files_touched)} file touched records")

    # Step 7: Create FileTouched records from code changes
    for code_change in parsed.code_changes:
        file_touched = FileTouched(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            file_path=code_change.file_path,
            change_type=code_change.change_type,
            lines_added=code_change.lines_added,
            lines_deleted=code_change.lines_deleted,
            timestamp=parsed.start_time,  # Use conversation start time
        )
        session.add(file_touched)
    if parsed.code_changes:
        logger.debug(f"Created {len(parsed.code_changes)} code change file records")

    # Step 8: Store or update raw log (if file path provided)
    raw_log = None
    if file_path:
        # Check if raw_log already exists for this conversation
        # (happens when update_mode="replace" and we're doing a full reparse)
        existing_raw_logs = raw_log_repo.get_by_conversation(conversation.id)

        if existing_raw_logs:
            # Update existing raw_log instead of creating new one
            # This avoids FK constraint violations
            raw_log = raw_log_repo.update_from_file(
                raw_log=existing_raw_logs[0],
                file_path=file_path,
            )
            logger.debug(f"Updated existing raw log: {raw_log.id} (file_path updated to {file_path.name})")
        else:
            # Create new raw_log
            raw_log = raw_log_repo.create_from_file(
                conversation_id=conversation.id,
                agent_type=parsed.agent_type,
                log_format="jsonl",  # Assume JSONL for now
                file_path=file_path,
            )
            logger.debug(f"Stored raw log: {raw_log.id}")

    # Step 9: Update denormalized counts for performance
    total_files = len(parsed.files_touched) + len(parsed.code_changes)
    conversation.message_count = len(messages)
    conversation.epoch_count = 1  # Currently 1 epoch per conversation
    conversation.files_count = total_files
    logger.debug(
        f"Updated counts: messages={conversation.message_count}, "
        f"epochs={conversation.epoch_count}, files={conversation.files_count}"
    )

    # Flush to ensure all IDs are generated and counts are saved
    session.flush()

    # Refresh conversation to load relationships
    session.refresh(conversation)

    # Update ingestion job as successful
    elapsed_ms = int((time.time() * 1000) - start_ms)
    ingestion_job.status = "success"
    ingestion_job.conversation_id = conversation.id
    ingestion_job.raw_log_id = raw_log.id if raw_log else None
    ingestion_job.processing_time_ms = elapsed_ms
    ingestion_job.messages_added = len(messages)
    ingestion_job.incremental = False  # Full parse (not incremental)
    ingestion_job.completed_at = datetime.utcnow()
    session.flush()
    logger.debug(
        f"Updated ingestion job to success: {ingestion_job.id}, "
        f"processing_time={elapsed_ms}ms"
    )

    total_files = len(parsed.files_touched) + len(parsed.code_changes)
    logger.info(
        f"Ingestion complete: conversation={conversation.id}, "
        f"messages={len(messages)}, files={total_files}"
    )

    return conversation


def _append_messages_incremental(
    session: Session,
    existing_conversation: Conversation,
    existing_raw_log: RawLog,
    parsed: ParsedConversation,
    tags: Optional[dict[str, Any]] = None,
) -> Conversation:
    """
    Append only NEW messages to existing conversation (incremental update).

    This function is called during append mode to incrementally update
    a conversation with new messages, avoiding full reparse.

    Args:
        session: Database session
        existing_conversation: Existing conversation to update
        existing_raw_log: Existing raw_log with state tracking
        parsed: Parsed conversation with ALL messages (existing + new)
        tags: Optional tags for epoch metadata

    Returns:
        Updated conversation instance

    Note:
        The 'parsed' object contains ALL messages, but we only create
        database records for messages beyond the existing count.
    """
    logger.info(
        f"Incremental append: conversation={existing_conversation.id}, "
        f"existing_messages={existing_conversation.message_count}"
    )

    # Get existing message count to determine sequence offset
    existing_message_count = existing_conversation.message_count
    existing_epoch_count = existing_conversation.epoch_count

    # Filter to only NEW messages (beyond existing count)
    new_messages = parsed.messages[existing_message_count:]

    if not new_messages:
        logger.info("No new messages to append, conversation already up-to-date")
        session.refresh(existing_conversation)
        return existing_conversation

    logger.info(f"Appending {len(new_messages)} new messages")

    # Get existing epoch (or create if none exists)
    epoch_repo = EpochRepository(session)
    message_repo = MessageRepository(session)

    if existing_epoch_count > 0:
        # Get the most recent epoch
        existing_epochs = (
            session.query(Epoch)
            .filter(Epoch.conversation_id == existing_conversation.id)
            .order_by(Epoch.sequence.desc())
            .all()
        )
        if existing_epochs:
            epoch = existing_epochs[0]
            # Update epoch end time
            if parsed.end_time:
                epoch.end_time = parsed.end_time
        else:
            # No epochs found, create one
            epoch = epoch_repo.create_epoch(
                conversation_id=existing_conversation.id,
                sequence=0,
                start_time=parsed.start_time,
                end_time=parsed.end_time,
                intent=tags.get("intent") if tags else None,
                outcome=tags.get("outcome") if tags else None,
                sentiment=tags.get("sentiment") if tags else None,
                sentiment_score=tags.get("sentiment_score") if tags else None,
            )
    else:
        # Create first epoch
        epoch = epoch_repo.create_epoch(
            conversation_id=existing_conversation.id,
            sequence=0,
            start_time=parsed.start_time,
            end_time=parsed.end_time,
            intent=tags.get("intent") if tags else None,
            outcome=tags.get("outcome") if tags else None,
            sentiment=tags.get("sentiment") if tags else None,
            sentiment_score=tags.get("sentiment_score") if tags else None,
        )

    # Create Message records for NEW messages only
    message_data = []
    for idx, msg in enumerate(new_messages):
        # Calculate global sequence (existing + new index)
        sequence = existing_message_count + idx

        # Serialize tool calls and code changes to JSON
        tool_calls_json = [
            {
                "tool_name": tc.tool_name,
                "parameters": tc.parameters,
                "result": tc.result,
                "success": tc.success,
                "timestamp": tc.timestamp.isoformat() if tc.timestamp else None,
            }
            for tc in msg.tool_calls
        ]

        code_changes_json = [
            {
                "file_path": cc.file_path,
                "change_type": cc.change_type,
                "old_content": cc.old_content,
                "new_content": cc.new_content,
                "lines_added": cc.lines_added,
                "lines_deleted": cc.lines_deleted,
            }
            for cc in msg.code_changes
        ]

        # Add model and token_usage to extra_data
        extra_data: dict[str, Any] = {}
        if msg.model:
            extra_data["model"] = msg.model
        if msg.token_usage:
            extra_data["token_usage"] = msg.token_usage

        message_data.append(
            {
                "epoch_id": epoch.id,
                "conversation_id": existing_conversation.id,
                "role": msg.role,
                "content": msg.content,
                "thinking_content": msg.thinking_content,
                "timestamp": msg.timestamp,
                "sequence": sequence,
                "tool_calls": tool_calls_json,
                "code_changes": code_changes_json,
                "entities": msg.entities,
                "extra_data": extra_data,
            }
        )

    # Bulk create new messages
    new_message_records = message_repo.bulk_create(message_data)
    logger.info(f"Created {len(new_message_records)} new message records")

    # Create FileTouched records from new code changes
    new_code_changes = []
    for msg in new_messages:
        new_code_changes.extend(msg.code_changes)

    for code_change in new_code_changes:
        file_touched = FileTouched(
            conversation_id=existing_conversation.id,
            epoch_id=epoch.id,
            file_path=code_change.file_path,
            change_type=code_change.change_type,
            lines_added=code_change.lines_added,
            lines_deleted=code_change.lines_deleted,
            timestamp=parsed.end_time or parsed.start_time,
        )
        session.add(file_touched)

    if new_code_changes:
        logger.debug(f"Created {len(new_code_changes)} new file touched records")

    # Update conversation metadata
    if parsed.end_time:
        existing_conversation.end_time = parsed.end_time
        existing_conversation.status = "completed"

    # Increment denormalized counts
    existing_conversation.message_count += len(new_messages)
    existing_conversation.files_count += len(new_code_changes)
    # epoch_count stays the same (still 1 epoch per conversation)

    logger.debug(
        f"Updated counts: messages={existing_conversation.message_count}, "
        f"files={existing_conversation.files_count}"
    )

    # Update raw_log state tracking
    # Note: This assumes parsed contains the incremental state info
    # In practice, the caller should provide IncrementalParseResult
    # For now, we'll update file_size_bytes based on current file
    raw_log_repo = RawLogRepository(session)
    if existing_raw_log.file_path:
        file_path = Path(existing_raw_log.file_path)
        if file_path.exists():
            from catsyphon.parsers.incremental import calculate_partial_hash

            file_size = file_path.stat().st_size
            partial_hash = calculate_partial_hash(file_path, file_size)

            # Get last message timestamp
            last_message_timestamp = None
            if new_messages:
                last_message_timestamp = new_messages[-1].timestamp

            # Update raw_log state
            raw_log_repo.update_state(
                raw_log=existing_raw_log,
                last_processed_offset=file_size,
                last_processed_line=existing_conversation.message_count,
                file_size_bytes=file_size,
                partial_hash=partial_hash,
                last_message_timestamp=last_message_timestamp,
            )
            logger.debug("Updated raw_log incremental state")

    # Flush and refresh
    session.flush()
    session.refresh(existing_conversation)

    logger.info(
        f"Incremental append complete: conversation={existing_conversation.id}, "
        f"added {len(new_messages)} messages, "
        f"total={existing_conversation.message_count}"
    )

    return existing_conversation


def ingest_messages_incremental(
    session: Session,
    incremental_result: IncrementalParseResult,
    conversation_id: str,
    raw_log_id: str,
    tags: Optional[dict[str, Any]] = None,
    source_type: str = "watch",
    source_config_id: Optional[UUID] = None,
    created_by: Optional[str] = None,
) -> Conversation:
    """
    Ingest only NEW messages from incremental parsing (Phase 2).

    This is the main entry point for incremental updates, called by
    the watch daemon when it detects an append operation.

    Args:
        session: Database session
        incremental_result: Result from ClaudeCodeParser.parse_incremental()
        conversation_id: UUID of existing conversation
        raw_log_id: UUID of existing raw_log
        tags: Optional tags for new messages
        source_type: Source of ingestion ('cli', 'upload', 'watch')
        source_config_id: UUID of watch configuration if source_type='watch'
        created_by: Username who triggered the ingestion

    Returns:
        Updated conversation instance

    Example:
        from catsyphon.parsers.claude_code import ClaudeCodeParser
        from catsyphon.db.connection import get_db

        parser = ClaudeCodeParser()
        result = parser.parse_incremental(file_path, last_offset, last_line)

        with get_db() as session:
            conversation = ingest_messages_incremental(
                session,
                result,
                conversation_id,
                raw_log_id,
            )
            session.commit()
    """
    import uuid

    logger.info(
        f"Incremental ingest: conversation={conversation_id}, "
        f"new_messages={len(incremental_result.new_messages)}"
    )

    # Initialize timing for ingestion job tracking
    start_time = datetime.utcnow()
    start_ms = time.time() * 1000  # Convert to milliseconds

    # Initialize ingestion job repository
    ingestion_repo = IngestionJobRepository(session)

    # Create initial ingestion job record
    ingestion_job = ingestion_repo.create(
        source_type=source_type,
        source_config_id=source_config_id,
        file_path=None,  # Not provided in incremental mode
        status="processing",
        started_at=start_time,
        created_by=created_by,
        incremental=True,
        messages_added=0,
    )
    session.flush()  # Get job ID
    logger.debug(f"Created ingestion job (incremental): {ingestion_job.id}")

    # Get existing conversation and raw_log
    conversation_repo = ConversationRepository(session)
    raw_log_repo = RawLogRepository(session)

    conversation = conversation_repo.get(uuid.UUID(conversation_id))
    if not conversation:
        raise ValueError(f"Conversation not found: {conversation_id}")

    raw_log = raw_log_repo.get(uuid.UUID(raw_log_id))
    if not raw_log:
        raise ValueError(f"Raw log not found: {raw_log_id}")

    # Get existing epoch (assume 1 epoch per conversation for now)
    epoch_repo = EpochRepository(session)
    message_repo = MessageRepository(session)

    epochs = (
        session.query(Epoch)
        .filter(Epoch.conversation_id == conversation.id)
        .order_by(Epoch.sequence.desc())
        .all()
    )

    if epochs:
        epoch = epochs[0]
    else:
        # Create epoch if none exists
        epoch = epoch_repo.create_epoch(
            conversation_id=conversation.id,
            sequence=0,
            start_time=conversation.start_time,
            end_time=conversation.end_time,
        )

    # Get current message count for sequencing
    existing_message_count = conversation.message_count

    # Create Message records for NEW messages only
    message_data = []
    for idx, msg in enumerate(incremental_result.new_messages):
        sequence = existing_message_count + idx

        # Serialize tool calls and code changes
        tool_calls_json = [
            {
                "tool_name": tc.tool_name,
                "parameters": tc.parameters,
                "result": tc.result,
                "success": tc.success,
                "timestamp": tc.timestamp.isoformat() if tc.timestamp else None,
            }
            for tc in msg.tool_calls
        ]

        code_changes_json = [
            {
                "file_path": cc.file_path,
                "change_type": cc.change_type,
                "old_content": cc.old_content,
                "new_content": cc.new_content,
                "lines_added": cc.lines_added,
                "lines_deleted": cc.lines_deleted,
            }
            for cc in msg.code_changes
        ]

        extra_data: dict[str, Any] = {}
        if msg.model:
            extra_data["model"] = msg.model
        if msg.token_usage:
            extra_data["token_usage"] = msg.token_usage

        message_data.append(
            {
                "epoch_id": epoch.id,
                "conversation_id": conversation.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "sequence": sequence,
                "tool_calls": tool_calls_json,
                "code_changes": code_changes_json,
                "entities": msg.entities,
                "extra_data": extra_data,
            }
        )

    # Bulk create messages
    new_messages = message_repo.bulk_create(message_data)
    logger.info(f"Created {len(new_messages)} new message records")

    # Create FileTouched records
    new_code_changes = []
    for msg in incremental_result.new_messages:
        new_code_changes.extend(msg.code_changes)

    for code_change in new_code_changes:
        file_touched = FileTouched(
            conversation_id=conversation.id,
            epoch_id=epoch.id,
            file_path=code_change.file_path,
            change_type=code_change.change_type,
            lines_added=code_change.lines_added,
            lines_deleted=code_change.lines_deleted,
            timestamp=incremental_result.last_message_timestamp
            or conversation.end_time,
        )
        session.add(file_touched)

    # Update conversation counts
    conversation.message_count += len(incremental_result.new_messages)
    conversation.files_count += len(new_code_changes)

    # Update epoch end time if available
    if incremental_result.last_message_timestamp:
        epoch.end_time = incremental_result.last_message_timestamp
        conversation.end_time = incremental_result.last_message_timestamp

    # Update raw_log state
    raw_log_repo.update_state(
        raw_log=raw_log,
        last_processed_offset=incremental_result.last_processed_offset,
        last_processed_line=incremental_result.last_processed_line,
        file_size_bytes=incremental_result.file_size_bytes,
        partial_hash=incremental_result.partial_hash,
        last_message_timestamp=incremental_result.last_message_timestamp,
    )

    logger.debug(
        f"Updated raw_log state: offset={incremental_result.last_processed_offset}, "
        f"line={incremental_result.last_processed_line}"
    )

    # Flush and refresh
    session.flush()
    session.refresh(conversation)

    # Update ingestion job as successful
    elapsed_ms = int((time.time() * 1000) - start_ms)
    ingestion_job.status = "success"
    ingestion_job.conversation_id = conversation.id
    ingestion_job.raw_log_id = uuid.UUID(raw_log_id)
    ingestion_job.processing_time_ms = elapsed_ms
    ingestion_job.messages_added = len(incremental_result.new_messages)
    ingestion_job.completed_at = datetime.utcnow()
    session.flush()
    logger.debug(
        f"Updated ingestion job to success: {ingestion_job.id}, "
        f"messages_added={len(incremental_result.new_messages)}, "
        f"processing_time={elapsed_ms}ms"
    )

    logger.info(
        f"Incremental ingest complete: conversation={conversation.id}, "
        f"added={len(new_messages)}, total={conversation.message_count}"
    )

    return conversation


def link_orphaned_agents(session: Session, workspace_id: UUID) -> int:
    """
    Link orphaned agent conversations to their parent conversations.

    This function is called after batch ingestion to handle cases where agents
    were ingested before their parent conversations. It finds all agent
    conversations without parent links and attempts to link them using the
    parent_session_id from agent_metadata.

    Args:
        session: Database session
        workspace_id: Workspace UUID to scope the linking

    Returns:
        Number of agents successfully linked

    Note:
        This is necessary because ingestion order is not guaranteed - agents
        may be processed before their parent main conversations exist in the
        database. By running this after all files are ingested, we can link
        agents that couldn't be linked during initial ingestion.
    """
    logger.info(f"Starting post-ingestion agent linking for workspace {workspace_id}")

    conversation_repo = ConversationRepository(session)

    # Find all orphaned agent conversations in this workspace
    orphaned_agents = (
        session.query(Conversation)
        .filter(
            Conversation.workspace_id == workspace_id,
            Conversation.conversation_type == "agent",
            Conversation.parent_conversation_id.is_(None),
        )
        .all()
    )

    if not orphaned_agents:
        logger.info("No orphaned agents found")
        return 0

    logger.info(f"Found {len(orphaned_agents)} orphaned agent conversations to link")

    linked_count = 0

    for agent in orphaned_agents:
        # Get parent_session_id from agent_metadata
        parent_session_id = agent.agent_metadata.get("parent_session_id")

        if not parent_session_id:
            logger.warning(
                f"Agent conversation {agent.id} has no parent_session_id in agent_metadata"
            )
            continue

        # Look up parent conversation by session_id
        parent_conversation = conversation_repo.get_by_session_id(
            parent_session_id, workspace_id
        )

        if not parent_conversation:
            logger.warning(
                f"Parent MAIN conversation not found for agent {agent.id} "
                f"(parent_session_id={parent_session_id})"
            )
            continue

        # Verify parent is a MAIN conversation (avoid linking agents to other agents)
        if parent_conversation.conversation_type.upper() != "MAIN":
            logger.warning(
                f"Parent conversation {parent_conversation.id} is not MAIN type "
                f"(type={parent_conversation.conversation_type}), skipping agent {agent.id}"
            )
            continue

        # Link agent to parent
        agent.parent_conversation_id = parent_conversation.id
        linked_count += 1

        logger.info(
            f"Linked agent conversation {agent.id} (session_id={agent.extra_data.get('session_id')}) "
            f"to parent {parent_conversation.id} (session_id={parent_session_id})"
        )

    session.flush()

    logger.info(f"Post-ingestion linking complete: linked {linked_count}/{len(orphaned_agents)} agents")

    return linked_count
