"""
Ingestion pipeline for transforming parsed conversations into database records.

This module handles the complete transformation of ParsedConversation objects
from parsers into database models, including conversations, epochs, messages,
files touched, and raw logs.
"""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    EpochRepository,
    MessageRepository,
    ProjectRepository,
    RawLogRepository,
)
from catsyphon.exceptions import DuplicateFileError
from catsyphon.models.db import Conversation, FileTouched
from catsyphon.models.parsed import ParsedConversation
from catsyphon.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


def ingest_conversation(
    session: Session,
    parsed: ParsedConversation,
    project_name: Optional[str] = None,
    developer_username: Optional[str] = None,
    file_path: Optional[Path] = None,
    tags: Optional[dict] = None,
    skip_duplicates: bool = True,
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
        skip_duplicates: If True, skip files that have already been processed (default: True)

    Returns:
        Created Conversation instance with all relationships loaded

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
                    session.refresh(existing_raw_log.conversation)
                    return existing_raw_log.conversation
            else:
                raise DuplicateFileError(file_hash, str(file_path))

    # Initialize repositories
    project_repo = ProjectRepository(session)
    developer_repo = DeveloperRepository(session)
    conversation_repo = ConversationRepository(session)
    epoch_repo = EpochRepository(session)
    message_repo = MessageRepository(session)
    raw_log_repo = RawLogRepository(session)

    # Step 1: Get or create Project
    project_id = None
    if project_name:
        project = project_repo.get_or_create_by_name(project_name)
        project_id = project.id
        logger.debug(f"Project: {project.name} ({project.id})")

    # Step 2: Get or create Developer
    developer_id = None
    if developer_username:
        developer = developer_repo.get_or_create_by_username(developer_username)
        developer_id = developer.id
        logger.debug(f"Developer: {developer.username} ({developer.id})")

    # Step 3: Create Conversation
    conversation = conversation_repo.create(
        project_id=project_id,
        developer_id=developer_id,
        agent_type=parsed.agent_type,
        agent_version=parsed.agent_version,
        start_time=parsed.start_time,
        end_time=parsed.end_time,
        status="completed" if parsed.end_time else "open",
        iteration_count=1,  # TODO: Detect iterations from parsed data
        tags=tags or {},
        extra_data={
            "session_id": parsed.session_id,
            "git_branch": parsed.git_branch,
            "working_directory": parsed.working_directory,
            **parsed.metadata,
        },
    )
    logger.info(f"Created conversation: {conversation.id}")

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
        extra_data = {}
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

    # Step 8: Store raw log (if file path provided)
    if file_path:
        raw_log = raw_log_repo.create_from_file(
            conversation_id=conversation.id,
            agent_type=parsed.agent_type,
            log_format="jsonl",  # Assume JSONL for now
            file_path=file_path,
        )
        logger.debug(f"Stored raw log: {raw_log.id}")

    # Flush to ensure all IDs are generated
    session.flush()

    # Refresh conversation to load relationships
    session.refresh(conversation)

    total_files = len(parsed.files_touched) + len(parsed.code_changes)
    logger.info(
        f"Ingestion complete: conversation={conversation.id}, "
        f"messages={len(messages)}, files={total_files}"
    )

    return conversation
