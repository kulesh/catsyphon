"""
Collector configuration repository.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import CollectorConfig


class CollectorRepository(BaseRepository[CollectorConfig]):
    """Repository for CollectorConfig model."""

    def __init__(self, session: Session):
        super().__init__(CollectorConfig, session)

    def get_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[CollectorConfig]:
        """
        Get all collectors for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of collector configs
        """
        query = (
            self.session.query(CollectorConfig)
            .filter(CollectorConfig.workspace_id == workspace_id)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_active_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[CollectorConfig]:
        """
        Get active collectors for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of active collector configs
        """
        query = (
            self.session.query(CollectorConfig)
            .filter(
                CollectorConfig.workspace_id == workspace_id,
                CollectorConfig.is_active == True,
            )
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_api_key_prefix(self, api_key_prefix: str) -> Optional[CollectorConfig]:
        """
        Get collector by API key prefix.

        Used during authentication to find collector for key validation.

        Args:
            api_key_prefix: API key prefix (e.g., "cs_abc123")

        Returns:
            CollectorConfig or None
        """
        return (
            self.session.query(CollectorConfig)
            .filter(
                CollectorConfig.api_key_prefix == api_key_prefix,
                CollectorConfig.is_active == True,
            )
            .first()
        )

    def get_by_name(
        self, name: str, workspace_id: uuid.UUID
    ) -> Optional[CollectorConfig]:
        """
        Get collector by name within a workspace.

        Args:
            name: Collector name
            workspace_id: Workspace UUID

        Returns:
            CollectorConfig or None
        """
        return (
            self.session.query(CollectorConfig)
            .filter(
                CollectorConfig.name == name,
                CollectorConfig.workspace_id == workspace_id,
            )
            .first()
        )

    def update_heartbeat(
        self, id: uuid.UUID, heartbeat_time: Optional[datetime] = None
    ) -> Optional[CollectorConfig]:
        """
        Update collector's last heartbeat timestamp.

        Args:
            id: Collector UUID
            heartbeat_time: Heartbeat timestamp (defaults to now)

        Returns:
            Updated CollectorConfig or None
        """
        if heartbeat_time is None:
            heartbeat_time = datetime.utcnow()
        return self.update(id, last_heartbeat=heartbeat_time)

    def increment_uploads(
        self, id: uuid.UUID, conversation_count: int = 1
    ) -> Optional[CollectorConfig]:
        """
        Increment collector's upload statistics.

        Args:
            id: Collector UUID
            conversation_count: Number of conversations uploaded

        Returns:
            Updated CollectorConfig or None
        """
        collector = self.get(id)
        if collector:
            return self.update(
                id,
                total_uploads=collector.total_uploads + 1,
                total_conversations=collector.total_conversations + conversation_count,
                last_upload_at=datetime.utcnow(),
            )
        return None

    def get_stale_collectors(
        self, stale_threshold_minutes: int = 5
    ) -> List[CollectorConfig]:
        """
        Get collectors with stale heartbeats.

        Args:
            stale_threshold_minutes: Minutes since last heartbeat to consider stale

        Returns:
            List of stale collectors
        """
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(minutes=stale_threshold_minutes)
        return (
            self.session.query(CollectorConfig)
            .filter(
                CollectorConfig.is_active == True,
                CollectorConfig.last_heartbeat < threshold,
            )
            .all()
        )

    def deactivate(self, id: uuid.UUID) -> Optional[CollectorConfig]:
        """
        Deactivate a collector (soft delete).

        Args:
            id: Collector UUID

        Returns:
            Updated collector or None
        """
        return self.update(id, is_active=False)

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count collectors in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of collectors
        """
        return (
            self.session.query(CollectorConfig)
            .filter(CollectorConfig.workspace_id == workspace_id)
            .count()
        )

    def count_active_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count active collectors in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of active collectors
        """
        return (
            self.session.query(CollectorConfig)
            .filter(
                CollectorConfig.workspace_id == workspace_id,
                CollectorConfig.is_active == True,
            )
            .count()
        )

    def search_by_name(
        self, name_pattern: str, workspace_id: Optional[uuid.UUID] = None
    ) -> List[CollectorConfig]:
        """
        Search collectors by name pattern.

        Args:
            name_pattern: SQL LIKE pattern (e.g., "%search%")
            workspace_id: Optional workspace UUID to scope search

        Returns:
            List of matching collectors
        """
        query = self.session.query(CollectorConfig).filter(
            CollectorConfig.name.ilike(name_pattern)
        )
        if workspace_id:
            query = query.filter(CollectorConfig.workspace_id == workspace_id)
        return query.all()
