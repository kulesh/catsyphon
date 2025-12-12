"""Tests for OrganizationRepository."""

from sqlalchemy.orm import Session

from catsyphon.db.repositories.organization import OrganizationRepository
from catsyphon.models.db import Organization


class TestOrganizationRepository:
    """Test OrganizationRepository CRUD operations."""

    def test_create_organization(self, db_session: Session):
        """Test creating an organization."""
        repo = OrganizationRepository(db_session)
        org = repo.create(
            name="New Organization",
            slug="new-org",
            settings={"plan": "pro"},
            is_active=True,
        )

        assert org.id is not None
        assert org.name == "New Organization"
        assert org.slug == "new-org"
        assert org.settings == {"plan": "pro"}
        assert org.is_active is True
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_get_by_slug(self, db_session: Session, sample_organization: Organization):
        """Test getting organization by slug."""
        repo = OrganizationRepository(db_session)
        org = repo.get_by_slug("test-org")

        assert org is not None
        assert org.id == sample_organization.id
        assert org.slug == "test-org"

    def test_get_by_slug_not_found(self, db_session: Session):
        """Test getting organization by non-existent slug."""
        repo = OrganizationRepository(db_session)
        org = repo.get_by_slug("nonexistent-slug")

        assert org is None

    def test_get_by_name(self, db_session: Session, sample_organization: Organization):
        """Test getting organization by name."""
        repo = OrganizationRepository(db_session)
        org = repo.get_by_name("Test Organization")

        assert org is not None
        assert org.id == sample_organization.id
        assert org.name == "Test Organization"

    def test_get_by_name_not_found(self, db_session: Session):
        """Test getting organization by non-existent name."""
        repo = OrganizationRepository(db_session)
        org = repo.get_by_name("Nonexistent Organization")

        assert org is None

    def test_search_by_name(self, db_session: Session):
        """Test searching organizations by name pattern."""
        repo = OrganizationRepository(db_session)

        # Create multiple organizations
        repo.create(name="Alpha Corp", slug="alpha-corp")
        repo.create(name="Alpha Industries", slug="alpha-industries")
        repo.create(name="Beta Corp", slug="beta-corp")

        # Search for "Alpha"
        results = repo.search_by_name("%Alpha%")

        assert len(results) == 2
        assert all("Alpha" in org.name for org in results)

    def test_get_active(self, db_session: Session):
        """Test getting active organizations."""
        repo = OrganizationRepository(db_session)

        # Create active and inactive organizations
        repo.create(name="Active Org 1", slug="active-1", is_active=True)
        repo.create(name="Active Org 2", slug="active-2", is_active=True)
        repo.create(name="Inactive Org", slug="inactive-1", is_active=False)

        # Get active organizations
        active_orgs = repo.get_active()

        assert len(active_orgs) >= 2  # At least our 2 active orgs
        assert all(org.is_active for org in active_orgs)

    def test_get_active_with_pagination(self, db_session: Session):
        """Test getting active organizations with pagination."""
        repo = OrganizationRepository(db_session)

        # Create multiple active organizations
        for i in range(5):
            repo.create(name=f"Org {i}", slug=f"org-{i}", is_active=True)

        # Test limit
        results = repo.get_active(limit=3)
        assert len(results) == 3

        # Test offset
        results = repo.get_active(limit=2, offset=2)
        assert len(results) == 2

    def test_get_or_create_by_slug_existing(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test get_or_create with existing organization."""
        repo = OrganizationRepository(db_session)
        org = repo.get_or_create_by_slug(slug="test-org", name="Should Not Change")

        # Should return existing organization
        assert org.id == sample_organization.id
        assert org.name == "Test Organization"  # Original name unchanged

    def test_get_or_create_by_slug_new(self, db_session: Session):
        """Test get_or_create with new organization."""
        repo = OrganizationRepository(db_session)
        org = repo.get_or_create_by_slug(
            slug="new-slug", name="New Org", settings={"tier": "free"}
        )

        # Should create new organization
        assert org.id is not None
        assert org.slug == "new-slug"
        assert org.name == "New Org"
        assert org.settings == {"tier": "free"}

    def test_update_organization(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test updating organization."""
        repo = OrganizationRepository(db_session)
        updated = repo.update(
            sample_organization.id,
            name="Updated Organization",
            settings={"plan": "enterprise"},
        )

        assert updated is not None
        assert updated.name == "Updated Organization"
        assert updated.settings == {"plan": "enterprise"}
        assert updated.slug == "test-org"  # Unchanged

    def test_deactivate(self, db_session: Session, sample_organization: Organization):
        """Test soft delete (deactivation) of organization."""
        repo = OrganizationRepository(db_session)
        deactivated = repo.deactivate(sample_organization.id)

        assert deactivated is not None
        assert deactivated.is_active is False

        # Verify it still exists in database
        org = repo.get(sample_organization.id)
        assert org is not None
        assert org.is_active is False

    def test_delete_organization(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test hard delete of organization."""
        repo = OrganizationRepository(db_session)
        deleted = repo.delete(sample_organization.id)

        assert deleted is True

        # Verify it's gone
        org = repo.get(sample_organization.id)
        assert org is None

    def test_count(self, db_session: Session):
        """Test counting organizations."""
        repo = OrganizationRepository(db_session)

        initial_count = repo.count()

        repo.create(name="Count Test 1", slug="count-1")
        repo.create(name="Count Test 2", slug="count-2")

        new_count = repo.count()
        assert new_count == initial_count + 2

    def test_get_all(self, db_session: Session):
        """Test getting all organizations."""
        repo = OrganizationRepository(db_session)

        # Create some organizations
        repo.create(name="Org A", slug="org-a")
        repo.create(name="Org B", slug="org-b")

        all_orgs = repo.get_all()
        assert len(all_orgs) >= 2

    def test_get_all_with_pagination(self, db_session: Session):
        """Test getting all organizations with pagination."""
        repo = OrganizationRepository(db_session)

        # Create organizations
        for i in range(10):
            repo.create(name=f"Paginated Org {i}", slug=f"pag-org-{i}")

        # Test limit
        results = repo.get_all(limit=5)
        assert len(results) == 5

        # Test offset
        results = repo.get_all(limit=3, offset=5)
        assert len(results) == 3
