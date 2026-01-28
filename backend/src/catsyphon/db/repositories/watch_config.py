"""
Watch configuration repository.
"""

import uuid
from datetime import datetime, timezone
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

        return self.update(id, is_active=True, last_started_at=datetime.now(timezone.utc))

    def deactivate(self, id: uuid.UUID) -> Optional[WatchConfiguration]:
        """
        Deactivate a watch configuration.

        Args:
            id: Configuration UUID

        Returns:
            Updated configuration or None
        """
        from datetime import datetime

        return self.update(id, is_active=False, last_stopped_at=datetime.now(timezone.utc))

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

    def set_daemon_pid(self, id: uuid.UUID, pid: int) -> Optional[WatchConfiguration]:
        """
        Set the daemon PID for a watch configuration.

        Args:
            id: Configuration UUID
            pid: Process ID of the running daemon

        Returns:
            Updated configuration or None
        """
        return self.update(id, daemon_pid=pid)

    def clear_daemon_pid(self, id: uuid.UUID) -> Optional[WatchConfiguration]:
        """
        Clear the daemon PID for a watch configuration.

        Args:
            id: Configuration UUID

        Returns:
            Updated configuration or None
        """
        return self.update(id, daemon_pid=None)

    def get_configs_with_pids(
        self, workspace_id: uuid.UUID
    ) -> List[WatchConfiguration]:
        """
        Get all watch configurations with active PIDs in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            List of configurations with non-null daemon_pid
        """
        return (
            self.session.query(WatchConfiguration)
            .filter(
                WatchConfiguration.workspace_id == workspace_id,
                WatchConfiguration.daemon_pid.isnot(None),
            )
            .all()
        )
