"""
Organization repository.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Organization


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization model."""

    def __init__(self, session: Session):
        super().__init__(Organization, session)

    def get_by_slug(self, slug: str) -> Optional[Organization]:
        """
        Get organization by slug.

        Args:
            slug: Organization slug (URL-friendly identifier)

        Returns:
            Organization instance or None
        """
        return (
            self.session.query(Organization).filter(Organization.slug == slug).first()
        )

    def get_by_name(self, name: str) -> Optional[Organization]:
        """
        Get organization by exact name.

        Args:
            name: Organization name

        Returns:
            Organization instance or None
        """
        return (
            self.session.query(Organization).filter(Organization.name == name).first()
        )

    def search_by_name(self, name_pattern: str) -> List[Organization]:
        """
        Search organizations by name pattern.

        Args:
            name_pattern: SQL LIKE pattern (e.g., "%search%")

        Returns:
            List of matching organizations
        """
        return (
            self.session.query(Organization)
            .filter(Organization.name.ilike(name_pattern))
            .all()
        )

    def get_active(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[Organization]:
        """
        Get all active organizations.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of active organizations
        """
        query = (
            self.session.query(Organization)
            .filter(Organization.is_active == True)
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_or_create_by_slug(self, slug: str, name: str, **kwargs) -> Organization:
        """
        Get existing organization by slug or create new one.

        Args:
            slug: Organization slug
            name: Organization name
            **kwargs: Additional organization fields

        Returns:
            Organization instance
        """
        org = self.get_by_slug(slug)
        if not org:
            org = self.create(slug=slug, name=name, **kwargs)
        return org

    def deactivate(self, id) -> Optional[Organization]:
        """
        Deactivate an organization (soft delete).

        Args:
            id: Organization UUID

        Returns:
            Updated organization or None
        """
        return self.update(id, is_active=False)
