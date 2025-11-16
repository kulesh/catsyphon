"""
Watch configuration repository.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import WatchConfiguration


class WatchConfigurationRepository(BaseRepository[WatchConfiguration]):
    """Repository for WatchConfiguration model."""

    def __init__(self, session: Session):
        super().__init__(WatchConfiguration, session)

    def get_by_directory(
        self, directory: str, workspace_id: uuid.UUID
    ) -> Optional[WatchConfiguration]:
        """
        Get watch configuration by directory path within a workspace.

        Args:
            directory: Directory path
            workspace_id: Workspace UUID

        Returns:
            WatchConfiguration instance or None
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(
                WatchConfiguration.directory == directory,
                WatchConfiguration.workspace_id == workspace_id,
            )
            .first()
        )

    def get_all_active(self, workspace_id: uuid.UUID) -> List[WatchConfiguration]:
        """
        Get all active watch configurations for a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            List of active watch configurations
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(
                WatchConfiguration.is_active == True,  # noqa: E712
                WatchConfiguration.workspace_id == workspace_id,
            )
            .all()
        )

    def get_all_inactive(self, workspace_id: uuid.UUID) -> List[WatchConfiguration]:
        """
        Get all inactive watch configurations for a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            List of inactive watch configurations
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(
                WatchConfiguration.is_active == False,  # noqa: E712
                WatchConfiguration.workspace_id == workspace_id,
            )
            .all()
        )

    def activate(self, id: uuid.UUID) -> Optional[WatchConfiguration]:
        """
        Activate a watch configuration.

        Args:
            id: Configuration UUID

        Returns:
            Updated configuration or None
        """
        from datetime import datetime

        return self.update(id, is_active=True, last_started_at=datetime.utcnow())

    def deactivate(self, id: uuid.UUID) -> Optional[WatchConfiguration]:
        """
        Deactivate a watch configuration.

        Args:
            id: Configuration UUID

        Returns:
            Updated configuration or None
        """
        from datetime import datetime

        return self.update(id, is_active=False, last_stopped_at=datetime.utcnow())

    def update_stats(
        self, id: uuid.UUID, stats: dict[str, int]
    ) -> Optional[WatchConfiguration]:
        """
        Update statistics for a watch configuration.

        Args:
            id: Configuration UUID
            stats: Statistics dictionary (from WatcherStats)

        Returns:
            Updated configuration or None
        """
        return self.update(id, stats=stats)

    def get_by_project(
        self, project_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> List[WatchConfiguration]:
        """
        Get watch configurations for a specific project within a workspace.

        Args:
            project_id: Project UUID
            workspace_id: Workspace UUID

        Returns:
            List of watch configurations
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(
                WatchConfiguration.project_id == project_id,
                WatchConfiguration.workspace_id == workspace_id,
            )
            .all()
        )

    def get_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[WatchConfiguration]:
        """
        Get all watch configurations for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of watch configurations
        """
        query = (
            self.session.query(WatchConfiguration)
            .filter(WatchConfiguration.workspace_id == workspace_id)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count watch configurations in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of watch configurations
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(WatchConfiguration.workspace_id == workspace_id)
            .count()
        )
