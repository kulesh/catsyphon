"""
RawLog repository.
"""

import uuid
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import RawLog
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

        return self.create(
            conversation_id=conversation_id,
            agent_type=agent_type,
            log_format=log_format,
            raw_content=raw_content,
            file_path=str(file_path),
            file_hash=file_hash,
            **kwargs,
        )

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

        return self.create(
            conversation_id=conversation_id,
            agent_type=agent_type,
            log_format=log_format,
            raw_content=raw_content,
            file_path=file_path,
            file_hash=file_hash,
            **kwargs,
        )
