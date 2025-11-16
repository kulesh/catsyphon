"""
Workspace repository.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Workspace


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository for Workspace model."""

    def __init__(self, session: Session):
        super().__init__(Workspace, session)

    def get_by_slug(self, slug: str) -> Optional[Workspace]:
        """
        Get workspace by slug.

        Args:
            slug: Workspace slug (URL-friendly identifier)

        Returns:
            Workspace instance or None
        """
        return self.session.query(Workspace).filter(Workspace.slug == slug).first()

    def get_by_name(
        self, name: str, organization_id: Optional[uuid.UUID] = None
    ) -> Optional[Workspace]:
        """
        Get workspace by name (optionally scoped to organization).

        Args:
            name: Workspace name
            organization_id: Organization UUID to scope search

        Returns:
            Workspace instance or None
        """
        query = self.session.query(Workspace).filter(Workspace.name == name)
        if organization_id:
            query = query.filter(Workspace.organization_id == organization_id)
        return query.first()

    def get_by_organization(
        self, organization_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Workspace]:
        """
        Get all workspaces for an organization.

        Args:
            organization_id: Organization UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of workspaces
        """
        query = (
            self.session.query(Workspace)
            .filter(Workspace.organization_id == organization_id)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_active_by_organization(
        self, organization_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Workspace]:
        """
        Get active workspaces for an organization.

        Args:
            organization_id: Organization UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of active workspaces
        """
        query = (
            self.session.query(Workspace)
            .filter(
                Workspace.organization_id == organization_id,
                Workspace.is_active == True,
            )
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def search_by_name(self, name_pattern: str) -> List[Workspace]:
        """
        Search workspaces by name pattern.

        Args:
            name_pattern: SQL LIKE pattern (e.g., "%search%")

        Returns:
            List of matching workspaces
        """
        return (
            self.session.query(Workspace)
            .filter(Workspace.name.ilike(name_pattern))
            .all()
        )

    def get_or_create_by_slug(
        self, slug: str, name: str, organization_id: uuid.UUID, **kwargs
    ) -> Workspace:
        """
        Get existing workspace by slug or create new one.

        Args:
            slug: Workspace slug
            name: Workspace name
            organization_id: Organization UUID
            **kwargs: Additional workspace fields

        Returns:
            Workspace instance
        """
        workspace = self.get_by_slug(slug)
        if not workspace:
            workspace = self.create(
                slug=slug, name=name, organization_id=organization_id, **kwargs
            )
        return workspace

    def deactivate(self, id: uuid.UUID) -> Optional[Workspace]:
        """
        Deactivate a workspace (soft delete).

        Args:
            id: Workspace UUID

        Returns:
            Updated workspace or None
        """
        return self.update(id, is_active=False)

    def count_by_organization(self, organization_id: uuid.UUID) -> int:
        """
        Count workspaces in an organization.

        Args:
            organization_id: Organization UUID

        Returns:
            Number of workspaces
        """
        return (
            self.session.query(Workspace)
            .filter(Workspace.organization_id == organization_id)
            .count()
        )
