"""
RawLog repository.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import RawLog
from catsyphon.parsers.incremental import calculate_partial_hash
from catsyphon.utils.hashing import calculate_content_hash, calculate_file_hash


class RawLogRepository(BaseRepository[RawLog]):
    """Repository for RawLog model."""

    def __init__(self, session: Session):
        super().__init__(RawLog, session)

    def get_by_conversation(self, conversation_id: uuid.UUID) -> List[RawLog]:
        """
        Get raw logs for a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of raw log instances
        """
        return (
            self.session.query(RawLog)
            .filter(RawLog.conversation_id == conversation_id)
            .order_by(RawLog.imported_at.desc())
            .all()
        )

    def get_by_agent_type(
        self,
        agent_type: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[RawLog]:
        """
        Get raw logs by agent type.

        Args:
            agent_type: Agent type (e.g., 'claude-code')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of raw log instances
        """
        query = (
            self.session.query(RawLog)
            .filter(RawLog.agent_type == agent_type)
            .order_by(RawLog.imported_at.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_file_hash(self, file_hash: str) -> Optional[RawLog]:
        """
        Get raw log by file hash.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            Raw log instance if found, None otherwise
        """
        return self.session.query(RawLog).filter(RawLog.file_hash == file_hash).first()

    def get_by_file_path(self, file_path: str) -> Optional[RawLog]:
        """
        Get raw log by file path (for incremental parsing).

        Args:
            file_path: Path to the log file

        Returns:
            Raw log instance if found, None otherwise
        """
        return self.session.query(RawLog).filter(RawLog.file_path == file_path).first()

    def get_files_in_directory(self, directory: str) -> List[RawLog]:
        """
        Get all raw logs with file_path under the given directory.

        Used by watch daemon startup scan to detect files that changed
        during downtime.

        Args:
            directory: Directory path (will match any file_path starting with this)

        Returns:
            List of RawLog instances in the directory
        """
        # Ensure directory path ends with separator for proper matching
        search_pattern = directory.rstrip("/") + "/%"
        return (
            self.session.query(RawLog)
            .filter(RawLog.file_path.like(search_pattern))
            .order_by(RawLog.imported_at.desc())
            .all()
        )

    def exists_by_file_hash(self, file_hash: str) -> bool:
        """
        Check if a raw log with the given file hash exists.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            True if exists, False otherwise
        """
        return (
            self.session.query(RawLog.id).filter(RawLog.file_hash == file_hash).first()
            is not None
        )

    def create_from_file(
        self,
        conversation_id: uuid.UUID,
        agent_type: str,
        log_format: str,
        file_path: Path,
        **kwargs,
    ) -> RawLog:
        """
        Create raw log entry from file.

        Args:
            conversation_id: Conversation UUID
            agent_type: Agent type (e.g., 'claude-code')
            log_format: Log format (e.g., 'jsonl')
            file_path: Path to original log file
            **kwargs: Additional fields (e.g., extra_data)

        Returns:
            Created raw log instance
        """
        # Calculate file hash for deduplication
        file_hash = calculate_file_hash(file_path)

        # Read file content
        raw_content = file_path.read_text(encoding="utf-8")

        # Get file size
        file_size = file_path.stat().st_size

        # Calculate partial hash for the entire file (since we processed all of it)
        partial_hash = calculate_partial_hash(file_path, file_size)

        return self.create(
            conversation_id=conversation_id,
            agent_type=agent_type,
            log_format=log_format,
            raw_content=raw_content,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size_bytes=file_size,
            last_processed_offset=file_size,
            partial_hash=partial_hash,
            **kwargs,
        )

    def update_from_file(
        self,
        raw_log: RawLog,
        file_path: Path,
    ) -> RawLog:
        """
        Update existing raw log from file (for full reparse scenarios).

        This is used when a conversation needs to be re-ingested but we want
        to preserve the existing raw_log record to avoid foreign key constraint
        violations.

        Args:
            raw_log: Existing raw log instance to update
            file_path: Path to original log file

        Returns:
            Updated raw log instance
        """
        # Calculate new file hash
        file_hash = calculate_file_hash(file_path)

        # Read new file content
        raw_content = file_path.read_text(encoding="utf-8")

        # Get file size
        file_size = file_path.stat().st_size

        # Calculate partial hash for the entire file (since we processed all of it)
        partial_hash = calculate_partial_hash(file_path, file_size)

        # Update raw log fields
        raw_log.raw_content = raw_content
        raw_log.file_path = str(file_path)  # Update file path (handles file renames)
        raw_log.file_hash = file_hash
        raw_log.file_size_bytes = file_size
        raw_log.last_processed_offset = file_size  # Processed entire file
        raw_log.partial_hash = partial_hash
        raw_log.imported_at = datetime.utcnow()

        # Note: Caller is responsible for flushing to ensure proper
        # transaction ordering (messages must be persisted before RawLog state)
        return raw_log

    def create_from_content(
        self,
        conversation_id: uuid.UUID,
        agent_type: str,
        log_format: str,
        raw_content: str,
        file_path: Optional[str] = None,
        **kwargs,
    ) -> RawLog:
        """
        Create raw log entry from content string.

        Args:
            conversation_id: Conversation UUID
            agent_type: Agent type (e.g., 'claude-code')
            log_format: Log format (e.g., 'jsonl')
            raw_content: Raw log content
            file_path: Optional file path
            **kwargs: Additional fields (e.g., extra_data)

        Returns:
            Created raw log instance
        """
        # Calculate content hash for deduplication
        file_hash = calculate_content_hash(raw_content)

        # Calculate content size in bytes
        content_size = len(raw_content.encode('utf-8'))

        return self.create(
            conversation_id=conversation_id,
            agent_type=agent_type,
            log_format=log_format,
            raw_content=raw_content,
            file_path=file_path,
            file_hash=file_hash,
            file_size_bytes=content_size,
            last_processed_offset=content_size,
            **kwargs,
        )

    def update_state(
        self,
        raw_log: RawLog,
        last_processed_offset: int,
        last_processed_line: int,
        file_size_bytes: int,
        partial_hash: str,
        last_message_timestamp: Optional[object] = None,
    ) -> RawLog:
        """
        Update incremental parsing state for a raw log.

        Args:
            raw_log: Raw log instance to update
            last_processed_offset: New byte offset where parsing stopped
            last_processed_line: New line number where parsing stopped
            file_size_bytes: Current file size in bytes
            partial_hash: SHA-256 hash of content up to last_processed_offset
            last_message_timestamp: Timestamp of last processed message

        Returns:
            Updated raw log instance
        """
        raw_log.last_processed_offset = last_processed_offset
        raw_log.last_processed_line = last_processed_line
        raw_log.file_size_bytes = file_size_bytes
        raw_log.partial_hash = partial_hash
        raw_log.last_message_timestamp = last_message_timestamp
        # Note: Caller is responsible for flushing to ensure proper
        # transaction ordering (messages must be persisted before RawLog state)
        return raw_log
