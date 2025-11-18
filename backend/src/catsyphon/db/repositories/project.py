"""
Project repository.
"""

import uuid
from pathlib import Path
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

        Note: This method is deprecated in favor of get_or_create_by_directory.
        For backward compatibility, if directory_path is not provided,
        it uses the name as a fallback directory_path.

        Args:
            name: Project name
            workspace_id: Workspace UUID
            **kwargs: Additional project fields (e.g., description, directory_path)

        Returns:
            Project instance
        """
        project = self.get_by_name(name, workspace_id)
        if not project:
            # Use name as fallback directory_path if not provided
            if "directory_path" not in kwargs:
                kwargs["directory_path"] = name
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

    def get_by_directory(
        self, directory_path: str, workspace_id: uuid.UUID
    ) -> Optional[Project]:
        """
        Get project by directory path within a workspace.

        Args:
            directory_path: Full directory path (e.g., "/Users/kulesh/dev/catsyphon")
            workspace_id: Workspace UUID

        Returns:
            Project instance or None
        """
        return (
            self.session.query(Project)
            .filter(
                Project.directory_path == directory_path,
                Project.workspace_id == workspace_id,
            )
            .first()
        )

    def get_or_create_by_directory(
        self, directory_path: str, workspace_id: uuid.UUID, name: Optional[str] = None
    ) -> Project:
        """
        Get existing project or create new one by directory path.

        Args:
            directory_path: Full directory path
            workspace_id: Workspace UUID
            name: Optional custom name (defaults to auto-generated)

        Returns:
            Project instance
        """
        project = self.get_by_directory(directory_path, workspace_id)
        if project:
            return project

        # Generate name if not provided
        if name is None:
            name = self._generate_project_name(directory_path)

        return self.create(
            workspace_id=workspace_id, name=name, directory_path=directory_path
        )

    def _generate_project_name(self, directory_path: str) -> str:
        """
        Generate a human-readable project name from directory path.

        Uses the directory basename if meaningful, otherwise generates
        a name with short UUID suffix for uniqueness.

        Args:
            directory_path: Full directory path

        Returns:
            Generated project name
        """
        basename = Path(directory_path).name

        # If basename is meaningful (not empty, not '.', not '/'), use it
        if basename and basename not in {".", "/", ".."}:
            return basename

        # Otherwise use short UUID suffix
        short_uuid = str(uuid.uuid4())[:6]
        return f"Project {short_uuid}"
