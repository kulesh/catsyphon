"""
Developer repository.
"""

import uuid
from typing import List, Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

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
        Get existing developer or create new one within a workspace (race-safe).

        This method uses PostgreSQL's ON CONFLICT DO NOTHING to prevent race conditions
        when multiple threads/processes attempt to create the same developer simultaneously.

        Args:
            username: Developer username
            workspace_id: Workspace UUID
            **kwargs: Additional developer fields (e.g., email)

        Returns:
            Developer instance

        Raises:
            RuntimeError: If developer creation/fetch fails unexpectedly
        """
        # Fast path: try to get existing first
        developer = self.get_by_username(username, workspace_id)
        if developer:
            return developer

        # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING for atomic upsert
        # This prevents IntegrityError when multiple threads race to create same developer
        stmt = (
            pg_insert(Developer)
            .values(
                id=uuid.uuid4(), workspace_id=workspace_id, username=username, **kwargs
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "workspace_id",
                    "username",
                ]  # uq_workspace_developer constraint
            )
        )

        self.session.execute(stmt)
        self.session.flush()

        # Fetch the developer (either newly created or existing from conflict)
        developer = self.get_by_username(username, workspace_id)
        if not developer:
            # Extremely rare: another transaction created and deleted it between insert and fetch
            raise RuntimeError(
                f"Developer creation/fetch failed for workspace_id={workspace_id}, "
                f"username={username}"
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

    def get_by_id_workspace(
        self, id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[Developer]:
        """
        Get a single developer by ID with workspace validation.

        This is the secure method for fetching a developer by ID,
        ensuring the developer belongs to the specified workspace.
        Use this instead of the base `get()` method for multi-tenant security.

        Args:
            id: Developer UUID
            workspace_id: Workspace UUID for validation

        Returns:
            Developer instance if found and belongs to workspace, None otherwise
        """
        return (
            self.session.query(Developer)
            .filter(
                Developer.id == id,
                Developer.workspace_id == workspace_id,
            )
            .first()
        )

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
