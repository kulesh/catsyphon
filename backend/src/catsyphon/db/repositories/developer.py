"""
Developer repository.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Developer


class DeveloperRepository(BaseRepository[Developer]):
    """Repository for Developer model."""

    def __init__(self, session: Session):
        super().__init__(Developer, session)

    def get_by_username(
        self, username: str, workspace_id: uuid.UUID
    ) -> Optional[Developer]:
        """
        Get developer by username within a workspace.

        Args:
            username: Developer username
            workspace_id: Workspace UUID

        Returns:
            Developer instance or None
        """
        return (
            self.session.query(Developer)
            .filter(
                Developer.username == username, Developer.workspace_id == workspace_id
            )
            .first()
        )

    def get_by_email(self, email: str, workspace_id: uuid.UUID) -> Optional[Developer]:
        """
        Get developer by email within a workspace.

        Args:
            email: Developer email
            workspace_id: Workspace UUID

        Returns:
            Developer instance or None
        """
        return (
            self.session.query(Developer)
            .filter(Developer.email == email, Developer.workspace_id == workspace_id)
            .first()
        )

    def get_or_create(
        self, username: str, workspace_id: uuid.UUID, **kwargs
    ) -> Developer:
        """
        Get existing developer or create new one within a workspace.

        NOTE: This method has a race condition similar to the one fixed in
        ProjectRepository.get_or_create_by_directory(). However, the Developer
        model currently lacks a unique constraint on (workspace_id, username),
        so we cannot use the same ON CONFLICT approach without first adding
        the constraint via migration.

        TODO: Add unique constraint to developers table:
            UniqueConstraint('workspace_id', 'username', name='uq_workspace_developer')
        Then update this method to use ON CONFLICT DO NOTHING.

        Race condition behavior WITHOUT unique constraint:
        - Multiple concurrent calls can create duplicate developers
        - No IntegrityError raised (constraint doesn't exist)
        - Duplicates may exist silently in the database

        Args:
            username: Developer username
            workspace_id: Workspace UUID
            **kwargs: Additional developer fields

        Returns:
            Developer instance
        """
        developer = self.get_by_username(username, workspace_id)
        if not developer:
            developer = self.create(
                username=username, workspace_id=workspace_id, **kwargs
            )
        return developer

    def get_or_create_by_username(
        self, username: str, workspace_id: uuid.UUID, **kwargs
    ) -> Developer:
        """
        Get existing developer or create new one (alias for get_or_create).

        Args:
            username: Developer username
            workspace_id: Workspace UUID
            **kwargs: Additional developer fields

        Returns:
            Developer instance
        """
        return self.get_or_create(username, workspace_id, **kwargs)

    def get_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Developer]:
        """
        Get all developers for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of developers
        """
        query = (
            self.session.query(Developer)
            .filter(Developer.workspace_id == workspace_id)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count developers in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of developers
        """
        return (
            self.session.query(Developer)
            .filter(Developer.workspace_id == workspace_id)
            .count()
        )
