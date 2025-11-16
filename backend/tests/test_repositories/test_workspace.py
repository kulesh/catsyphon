"""Tests for WorkspaceRepository."""


from sqlalchemy.orm import Session

from catsyphon.db.repositories.workspace import WorkspaceRepository
from catsyphon.models.db import Organization, Workspace


class TestWorkspaceRepository:
    """Test WorkspaceRepository CRUD operations."""

    def test_create_workspace(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test creating a workspace."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.create(
            organization_id=sample_organization.id,
            name="New Workspace",
            slug="new-workspace",
            settings={"retention_days": 60},
            is_active=True,
        )

        assert workspace.id is not None
        assert workspace.organization_id == sample_organization.id
        assert workspace.name == "New Workspace"
        assert workspace.slug == "new-workspace"
        assert workspace.settings == {"retention_days": 60}
        assert workspace.is_active is True
        assert workspace.created_at is not None
        assert workspace.updated_at is not None

    def test_get_by_slug(self, db_session: Session, sample_workspace: Workspace):
        """Test getting workspace by slug."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_by_slug("test-workspace")

        assert workspace is not None
        assert workspace.id == sample_workspace.id
        assert workspace.slug == "test-workspace"

    def test_get_by_slug_not_found(self, db_session: Session):
        """Test getting workspace by non-existent slug."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_by_slug("nonexistent-slug")

        assert workspace is None

    def test_get_by_name(
        self,
        db_session: Session,
        sample_organization: Organization,
        sample_workspace: Workspace,
    ):
        """Test getting workspace by name scoped to organization."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_by_name(
            "Test Workspace", organization_id=sample_organization.id
        )

        assert workspace is not None
        assert workspace.id == sample_workspace.id
        assert workspace.name == "Test Workspace"

    def test_get_by_name_without_org_scope(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test getting workspace by name without organization scope."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_by_name("Test Workspace")

        assert workspace is not None
        assert workspace.id == sample_workspace.id

    def test_get_by_organization(
        self,
        db_session: Session,
        sample_organization: Organization,
        sample_workspace: Workspace,
    ):
        """Test getting all workspaces for an organization."""
        repo = WorkspaceRepository(db_session)

        # Create additional workspace
        repo.create(
            organization_id=sample_organization.id,
            name="Second Workspace",
            slug="second-workspace",
        )

        workspaces = repo.get_by_organization(sample_organization.id)

        assert len(workspaces) == 2
        assert all(w.organization_id == sample_organization.id for w in workspaces)

    def test_get_by_organization_with_pagination(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test getting workspaces with pagination."""
        repo = WorkspaceRepository(db_session)

        # Create multiple workspaces
        for i in range(5):
            repo.create(
                organization_id=sample_organization.id,
                name=f"Workspace {i}",
                slug=f"workspace-{i}",
            )

        # Test limit
        results = repo.get_by_organization(sample_organization.id, limit=3)
        assert len(results) == 3

        # Test offset
        results = repo.get_by_organization(sample_organization.id, limit=2, offset=2)
        assert len(results) == 2

    def test_get_active_by_organization(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test getting active workspaces for an organization."""
        repo = WorkspaceRepository(db_session)

        # Create active and inactive workspaces
        repo.create(
            organization_id=sample_organization.id,
            name="Active WS 1",
            slug="active-ws-1",
            is_active=True,
        )
        repo.create(
            organization_id=sample_organization.id,
            name="Active WS 2",
            slug="active-ws-2",
            is_active=True,
        )
        repo.create(
            organization_id=sample_organization.id,
            name="Inactive WS",
            slug="inactive-ws",
            is_active=False,
        )

        active_workspaces = repo.get_active_by_organization(sample_organization.id)

        assert len(active_workspaces) >= 2  # At least our 2 active workspaces
        assert all(w.is_active for w in active_workspaces)
        assert all(
            w.organization_id == sample_organization.id for w in active_workspaces
        )

    def test_search_by_name(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test searching workspaces by name pattern."""
        repo = WorkspaceRepository(db_session)

        # Create workspaces with similar names
        repo.create(
            organization_id=sample_organization.id,
            name="Engineering Team",
            slug="eng-team",
        )
        repo.create(
            organization_id=sample_organization.id,
            name="Engineering Sandbox",
            slug="eng-sandbox",
        )
        repo.create(
            organization_id=sample_organization.id,
            name="Sales Team",
            slug="sales-team",
        )

        # Search for "Engineering"
        results = repo.search_by_name("%Engineering%")

        assert len(results) == 2
        assert all("Engineering" in w.name for w in results)

    def test_get_or_create_by_slug_existing(
        self,
        db_session: Session,
        sample_organization: Organization,
        sample_workspace: Workspace,
    ):
        """Test get_or_create with existing workspace."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_or_create_by_slug(
            slug="test-workspace",
            name="Should Not Change",
            organization_id=sample_organization.id,
        )

        # Should return existing workspace
        assert workspace.id == sample_workspace.id
        assert workspace.name == "Test Workspace"  # Original name unchanged

    def test_get_or_create_by_slug_new(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test get_or_create with new workspace."""
        repo = WorkspaceRepository(db_session)
        workspace = repo.get_or_create_by_slug(
            slug="new-slug",
            name="New Workspace",
            organization_id=sample_organization.id,
            settings={"feature_flags": ["beta"]},
        )

        # Should create new workspace
        assert workspace.id is not None
        assert workspace.slug == "new-slug"
        assert workspace.name == "New Workspace"
        assert workspace.settings == {"feature_flags": ["beta"]}

    def test_update_workspace(self, db_session: Session, sample_workspace: Workspace):
        """Test updating workspace."""
        repo = WorkspaceRepository(db_session)
        updated = repo.update(
            sample_workspace.id,
            name="Updated Workspace",
            settings={"retention_days": 180},
        )

        assert updated is not None
        assert updated.name == "Updated Workspace"
        assert updated.settings == {"retention_days": 180}
        assert updated.slug == "test-workspace"  # Unchanged

    def test_deactivate(self, db_session: Session, sample_workspace: Workspace):
        """Test soft delete (deactivation) of workspace."""
        repo = WorkspaceRepository(db_session)
        deactivated = repo.deactivate(sample_workspace.id)

        assert deactivated is not None
        assert deactivated.is_active is False

        # Verify it still exists in database
        workspace = repo.get(sample_workspace.id)
        assert workspace is not None
        assert workspace.is_active is False

    def test_count_by_organization(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test counting workspaces in an organization."""
        repo = WorkspaceRepository(db_session)

        initial_count = repo.count_by_organization(sample_organization.id)

        # Create additional workspaces
        repo.create(
            organization_id=sample_organization.id,
            name="Count Test 1",
            slug="count-1",
        )
        repo.create(
            organization_id=sample_organization.id,
            name="Count Test 2",
            slug="count-2",
        )

        new_count = repo.count_by_organization(sample_organization.id)
        assert new_count == initial_count + 2

    def test_delete_workspace(self, db_session: Session, sample_workspace: Workspace):
        """Test hard delete of workspace."""
        repo = WorkspaceRepository(db_session)
        deleted = repo.delete(sample_workspace.id)

        assert deleted is True

        # Verify it's gone
        workspace = repo.get(sample_workspace.id)
        assert workspace is None

    def test_workspace_cascade_delete(
        self, db_session: Session, sample_organization: Organization
    ):
        """Test that deleting organization cascades to workspaces."""
        from catsyphon.db.repositories.organization import OrganizationRepository

        workspace_repo = WorkspaceRepository(db_session)
        org_repo = OrganizationRepository(db_session)

        # Create workspace
        workspace = workspace_repo.create(
            organization_id=sample_organization.id,
            name="Cascade Test",
            slug="cascade-test",
        )

        # Delete organization
        org_repo.delete(sample_organization.id)
        db_session.commit()

        # Verify workspace was also deleted (CASCADE)
        deleted_workspace = workspace_repo.get(workspace.id)
        assert deleted_workspace is None
