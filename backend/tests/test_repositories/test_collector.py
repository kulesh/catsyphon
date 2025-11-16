"""Tests for CollectorRepository."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from catsyphon.db.repositories.collector import CollectorRepository
from catsyphon.models.db import CollectorConfig, Workspace


class TestCollectorRepository:
    """Test CollectorRepository CRUD operations."""

    def test_create_collector(self, db_session: Session, sample_workspace: Workspace):
        """Test creating a collector."""
        repo = CollectorRepository(db_session)
        collector = repo.create(
            workspace_id=sample_workspace.id,
            name="Test Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hashed_key",
            api_key_prefix="cs_abc123",
            is_active=True,
            version="2.0.0",
            hostname="test-host.local",
            extra_data={"os": "Linux"},
            total_uploads=0,
            total_conversations=0,
        )

        assert collector.id is not None
        assert collector.workspace_id == sample_workspace.id
        assert collector.name == "Test Collector"
        assert collector.collector_type == "python-sdk"
        assert collector.api_key_hash == "$2b$12$hashed_key"
        assert collector.api_key_prefix == "cs_abc123"
        assert collector.is_active is True
        assert collector.version == "2.0.0"
        assert collector.hostname == "test-host.local"
        assert collector.total_uploads == 0
        assert collector.total_conversations == 0

    def test_get_by_workspace(
        self,
        db_session: Session,
        sample_workspace: Workspace,
        sample_collector: CollectorConfig,
    ):
        """Test getting all collectors for a workspace."""
        repo = CollectorRepository(db_session)

        # Create additional collector
        repo.create(
            workspace_id=sample_workspace.id,
            name="Second Collector",
            collector_type="cli",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_def456",
        )

        collectors = repo.get_by_workspace(sample_workspace.id)

        assert len(collectors) == 2
        assert all(c.workspace_id == sample_workspace.id for c in collectors)

    def test_get_by_workspace_with_pagination(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test getting collectors with pagination."""
        repo = CollectorRepository(db_session)

        # Create multiple collectors
        for i in range(5):
            repo.create(
                workspace_id=sample_workspace.id,
                name=f"Collector {i}",
                collector_type="python-sdk",
                api_key_hash=f"$2b$12$hash{i}",
                api_key_prefix=f"cs_test{i}",
            )

        # Test limit
        results = repo.get_by_workspace(sample_workspace.id, limit=3)
        assert len(results) == 3

        # Test offset
        results = repo.get_by_workspace(sample_workspace.id, limit=2, offset=2)
        assert len(results) == 2

    def test_get_active_by_workspace(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test getting active collectors for a workspace."""
        repo = CollectorRepository(db_session)

        # Create active and inactive collectors
        repo.create(
            workspace_id=sample_workspace.id,
            name="Active Collector 1",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash1",
            api_key_prefix="cs_active1",
            is_active=True,
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Active Collector 2",
            collector_type="cli",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_active2",
            is_active=True,
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Inactive Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash3",
            api_key_prefix="cs_inactive",
            is_active=False,
        )

        active_collectors = repo.get_active_by_workspace(sample_workspace.id)

        assert len(active_collectors) >= 2
        assert all(c.is_active for c in active_collectors)
        assert all(c.workspace_id == sample_workspace.id for c in active_collectors)

    def test_get_by_api_key_prefix(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test getting collector by API key prefix."""
        repo = CollectorRepository(db_session)
        collector = repo.get_by_api_key_prefix("cs_test123")

        assert collector is not None
        assert collector.id == sample_collector.id
        assert collector.api_key_prefix == "cs_test123"

    def test_get_by_api_key_prefix_inactive_not_found(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test that inactive collectors are not returned by API key prefix."""
        repo = CollectorRepository(db_session)

        # Create inactive collector
        repo.create(
            workspace_id=sample_workspace.id,
            name="Inactive",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash",
            api_key_prefix="cs_inactive",
            is_active=False,
        )

        # Should not find inactive collector
        collector = repo.get_by_api_key_prefix("cs_inactive")
        assert collector is None

    def test_get_by_name(
        self,
        db_session: Session,
        sample_workspace: Workspace,
        sample_collector: CollectorConfig,
    ):
        """Test getting collector by name within workspace."""
        repo = CollectorRepository(db_session)
        collector = repo.get_by_name("Test Collector", sample_workspace.id)

        assert collector is not None
        assert collector.id == sample_collector.id
        assert collector.name == "Test Collector"

    def test_get_by_name_workspace_scoped(
        self, db_session: Session, sample_organization
    ):
        """Test that get_by_name is properly scoped to workspace."""
        from catsyphon.db.repositories.workspace import WorkspaceRepository

        workspace_repo = WorkspaceRepository(db_session)
        collector_repo = CollectorRepository(db_session)

        # Create two workspaces
        ws1 = workspace_repo.create(
            organization_id=sample_organization.id,
            name="WS1",
            slug="ws1",
        )
        ws2 = workspace_repo.create(
            organization_id=sample_organization.id,
            name="WS2",
            slug="ws2",
        )

        # Create collectors with same name in different workspaces
        collector1 = collector_repo.create(
            workspace_id=ws1.id,
            name="Same Name",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash1",
            api_key_prefix="cs_ws1",
        )
        collector2 = collector_repo.create(
            workspace_id=ws2.id,
            name="Same Name",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_ws2",
        )

        # Should get different collectors for different workspaces
        found1 = collector_repo.get_by_name("Same Name", ws1.id)
        found2 = collector_repo.get_by_name("Same Name", ws2.id)

        assert found1.id == collector1.id
        assert found2.id == collector2.id
        assert found1.id != found2.id

    def test_update_heartbeat(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test updating collector heartbeat."""
        repo = CollectorRepository(db_session)

        # Update with explicit time (use utcnow to match SQLite behavior)
        heartbeat_time = datetime.utcnow()
        updated = repo.update_heartbeat(sample_collector.id, heartbeat_time)

        assert updated is not None
        assert updated.last_heartbeat is not None
        # Allow small time difference for test execution
        assert abs((updated.last_heartbeat - heartbeat_time).total_seconds()) < 1

    def test_update_heartbeat_default_time(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test updating collector heartbeat with default time (now)."""
        repo = CollectorRepository(db_session)

        # Use utcnow to match SQLite behavior
        before = datetime.utcnow()
        updated = repo.update_heartbeat(sample_collector.id)
        after = datetime.utcnow()

        assert updated is not None
        assert updated.last_heartbeat is not None
        assert before <= updated.last_heartbeat <= after

    def test_increment_uploads(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test incrementing collector upload statistics."""
        repo = CollectorRepository(db_session)

        initial_uploads = sample_collector.total_uploads
        initial_convos = sample_collector.total_conversations

        # Increment with 5 conversations
        updated = repo.increment_uploads(sample_collector.id, conversation_count=5)

        assert updated is not None
        assert updated.total_uploads == initial_uploads + 1
        assert updated.total_conversations == initial_convos + 5
        assert updated.last_upload_at is not None

    def test_increment_uploads_default_count(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test incrementing uploads with default conversation count."""
        repo = CollectorRepository(db_session)

        initial_uploads = sample_collector.total_uploads
        initial_convos = sample_collector.total_conversations

        # Increment with default (1 conversation)
        updated = repo.increment_uploads(sample_collector.id)

        assert updated is not None
        assert updated.total_uploads == initial_uploads + 1
        assert updated.total_conversations == initial_convos + 1

    def test_get_stale_collectors(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test getting collectors with stale heartbeats."""
        repo = CollectorRepository(db_session)

        # Create collector with old heartbeat (use utcnow for SQLite)
        stale_collector = repo.create(
            workspace_id=sample_workspace.id,
            name="Stale Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash",
            api_key_prefix="cs_stale",
            is_active=True,
            last_heartbeat=datetime.utcnow() - timedelta(minutes=10),
        )

        # Create collector with recent heartbeat
        fresh_collector = repo.create(
            workspace_id=sample_workspace.id,
            name="Fresh Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_fresh",
            is_active=True,
            last_heartbeat=datetime.utcnow() - timedelta(minutes=1),
        )

        # Get stale collectors (threshold: 5 minutes)
        stale_collectors = repo.get_stale_collectors(stale_threshold_minutes=5)

        # Should find stale collector but not fresh one
        stale_ids = [c.id for c in stale_collectors]
        assert stale_collector.id in stale_ids
        assert fresh_collector.id not in stale_ids

    def test_deactivate(self, db_session: Session, sample_collector: CollectorConfig):
        """Test deactivating a collector."""
        repo = CollectorRepository(db_session)
        deactivated = repo.deactivate(sample_collector.id)

        assert deactivated is not None
        assert deactivated.is_active is False

        # Verify it still exists
        collector = repo.get(sample_collector.id)
        assert collector is not None
        assert collector.is_active is False

    def test_count_by_workspace(self, db_session: Session, sample_workspace: Workspace):
        """Test counting collectors in a workspace."""
        repo = CollectorRepository(db_session)

        initial_count = repo.count_by_workspace(sample_workspace.id)

        # Create additional collectors
        repo.create(
            workspace_id=sample_workspace.id,
            name="Count Test 1",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash1",
            api_key_prefix="cs_count1",
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Count Test 2",
            collector_type="cli",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_count2",
        )

        new_count = repo.count_by_workspace(sample_workspace.id)
        assert new_count == initial_count + 2

    def test_count_active_by_workspace(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test counting active collectors in a workspace."""
        repo = CollectorRepository(db_session)

        # Create active and inactive collectors
        repo.create(
            workspace_id=sample_workspace.id,
            name="Active 1",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash1",
            api_key_prefix="cs_active1",
            is_active=True,
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Active 2",
            collector_type="cli",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_active2",
            is_active=True,
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Inactive",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash3",
            api_key_prefix="cs_inactive",
            is_active=False,
        )

        active_count = repo.count_active_by_workspace(sample_workspace.id)
        total_count = repo.count_by_workspace(sample_workspace.id)

        # Should count only active collectors
        assert active_count >= 2
        assert total_count >= 3
        assert active_count < total_count

    def test_search_by_name(self, db_session: Session, sample_workspace: Workspace):
        """Test searching collectors by name pattern."""
        repo = CollectorRepository(db_session)

        # Create collectors with similar names
        repo.create(
            workspace_id=sample_workspace.id,
            name="Production Server 1",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash1",
            api_key_prefix="cs_prod1",
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Production Server 2",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_prod2",
        )
        repo.create(
            workspace_id=sample_workspace.id,
            name="Development Server",
            collector_type="cli",
            api_key_hash="$2b$12$hash3",
            api_key_prefix="cs_dev",
        )

        # Search for "Production"
        results = repo.search_by_name("%Production%")
        assert len(results) == 2
        assert all("Production" in c.name for c in results)

        # Search scoped to workspace
        results = repo.search_by_name("%Server%", workspace_id=sample_workspace.id)
        assert len(results) == 3
        assert all("Server" in c.name for c in results)

    def test_update_collector(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test updating collector fields."""
        repo = CollectorRepository(db_session)

        updated = repo.update(
            sample_collector.id,
            name="Updated Collector",
            version="3.0.0",
            extra_data={"os": "Windows", "feature": "beta"},
        )

        assert updated is not None
        assert updated.name == "Updated Collector"
        assert updated.version == "3.0.0"
        assert updated.extra_data == {"os": "Windows", "feature": "beta"}
        assert updated.api_key_hash == "$2b$12$hashed_key_here"  # Unchanged

    def test_delete_collector(
        self, db_session: Session, sample_collector: CollectorConfig
    ):
        """Test hard delete of collector."""
        repo = CollectorRepository(db_session)
        deleted = repo.delete(sample_collector.id)

        assert deleted is True

        # Verify it's gone
        collector = repo.get(sample_collector.id)
        assert collector is None
