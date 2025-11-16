"""
Project repository.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Project


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project model."""

    def __init__(self, session: Session):
        super().__init__(Project, session)

    def get_by_name(self, name: str, workspace_id: uuid.UUID) -> Optional[Project]:
        """
        Get project by name within a workspace.

        Args:
            name: Project name
            workspace_id: Workspace UUID

        Returns:
            Project instance or None
        """
        return (
            self.session.query(Project)
            .filter(Project.name == name, Project.workspace_id == workspace_id)
            .first()
        )

    def search_by_name(
        self, name_pattern: str, workspace_id: uuid.UUID
    ) -> List[Project]:
        """
        Search projects by name pattern within a workspace.

        Args:
            name_pattern: SQL LIKE pattern (e.g., "%search%")
            workspace_id: Workspace UUID

        Returns:
            List of matching projects
        """
        return (
            self.session.query(Project)
            .filter(
                Project.name.ilike(name_pattern), Project.workspace_id == workspace_id
            )
            .all()
        )

    def get_or_create_by_name(
        self, name: str, workspace_id: uuid.UUID, **kwargs
    ) -> Project:
        """
        Get existing project or create new one within a workspace.

        Args:
            name: Project name
            workspace_id: Workspace UUID
            **kwargs: Additional project fields (e.g., description)

        Returns:
            Project instance
        """
        project = self.get_by_name(name, workspace_id)
        if not project:
            project = self.create(name=name, workspace_id=workspace_id, **kwargs)
        return project

    def get_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Project]:
        """
        Get all projects for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of projects
        """
        query = (
            self.session.query(Project)
            .filter(Project.workspace_id == workspace_id)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count projects in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of projects
        """
        return (
            self.session.query(Project)
            .filter(Project.workspace_id == workspace_id)
            .count()
        )
