"""Tests for CollectorRepository."""

from datetime import datetime, timedelta, timezone

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

        # Update with explicit time (timezone-aware for SQLite consistency)
        heartbeat_time = datetime.now(timezone.utc).replace(tzinfo=None)
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

        # Use timezone-aware now to match SQLite behavior
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        updated = repo.update_heartbeat(sample_collector.id)
        after = datetime.now(timezone.utc).replace(tzinfo=None)

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

        # Create collector with old heartbeat (timezone-aware for SQLite)
        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=10
        )
        stale_collector = repo.create(
            workspace_id=sample_workspace.id,
            name="Stale Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash",
            api_key_prefix="cs_stale",
            is_active=True,
            last_heartbeat=stale_time,
        )

        # Create collector with recent heartbeat
        fresh_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=1
        )
        fresh_collector = repo.create(
            workspace_id=sample_workspace.id,
            name="Fresh Collector",
            collector_type="python-sdk",
            api_key_hash="$2b$12$hash2",
            api_key_prefix="cs_fresh",
            is_active=True,
            last_heartbeat=fresh_time,
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


class TestBuiltinCollector:
    """Test builtin collector methods."""

    def test_get_builtin_returns_none_when_not_exists(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test get_builtin returns None when no builtin collector exists."""
        repo = CollectorRepository(db_session)
        builtin = repo.get_builtin(sample_workspace.id)
        assert builtin is None

    def test_create_builtin_collector(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test creating the builtin collector."""
        repo = CollectorRepository(db_session)

        builtin = repo.create_builtin(
            workspace_id=sample_workspace.id,
            api_key_hash="sha256_hash_here",
            api_key_prefix="cs_live_abc",
            api_key_plaintext="cs_live_abcdefg12345",
        )

        assert builtin is not None
        assert builtin.workspace_id == sample_workspace.id
        assert builtin.is_builtin is True
        assert builtin.is_active is True
        assert builtin.name == "CatSyphon Built-in Watcher"
        assert builtin.collector_type == "builtin-watcher"
        assert builtin.api_key_hash == "sha256_hash_here"
        assert builtin.api_key_prefix == "cs_live_abc"
        # Check plaintext key is stored in extra_data
        assert builtin.extra_data.get("_api_key_plaintext") == "cs_live_abcdefg12345"

    def test_get_builtin_returns_existing(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test get_builtin returns existing builtin collector."""
        repo = CollectorRepository(db_session)

        # Create builtin collector
        created = repo.create_builtin(
            workspace_id=sample_workspace.id,
            api_key_hash="sha256_hash",
            api_key_prefix="cs_live_xyz",
            api_key_plaintext="cs_live_xyz12345",
        )
        db_session.flush()

        # Retrieve it
        builtin = repo.get_builtin(sample_workspace.id)
        assert builtin is not None
        assert builtin.id == created.id
        assert builtin.is_builtin is True

    def test_get_or_create_builtin_creates_new(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test get_or_create_builtin creates new when none exists."""
        repo = CollectorRepository(db_session)

        # Generator returns (full_key, prefix, hash) - same order as generate_api_key()
        def api_key_generator():
            return ("cs_live_testkey123", "cs_live_tes", "sha256_hash")

        collector, created = repo.get_or_create_builtin(
            workspace_id=sample_workspace.id,
            api_key_generator=api_key_generator,
        )

        assert created is True
        assert collector is not None
        assert collector.is_builtin is True
        assert collector.api_key_hash == "sha256_hash"
        assert collector.extra_data.get("_api_key_plaintext") == "cs_live_testkey123"

    def test_get_or_create_builtin_returns_existing(
        self, db_session: Session, sample_workspace: Workspace
    ):
        """Test get_or_create_builtin returns existing when one exists."""
        repo = CollectorRepository(db_session)

        # Create builtin first
        existing = repo.create_builtin(
            workspace_id=sample_workspace.id,
            api_key_hash="existing_hash",
            api_key_prefix="cs_live_exi",
            api_key_plaintext="cs_live_existing_key",
        )
        db_session.flush()

        # Generator returns (full_key, prefix, hash) - same order as generate_api_key()
        def api_key_generator():
            # This should NOT be called
            return ("cs_live_newkey", "cs_live_new", "new_hash")

        collector, created = repo.get_or_create_builtin(
            workspace_id=sample_workspace.id,
            api_key_generator=api_key_generator,
        )

        assert created is False
        assert collector.id == existing.id
        assert collector.api_key_hash == "existing_hash"

    def test_builtin_scoped_to_workspace(
        self, db_session: Session, sample_organization
    ):
        """Test that builtin collectors are scoped to workspace."""
        from catsyphon.db.repositories.workspace import WorkspaceRepository

        workspace_repo = WorkspaceRepository(db_session)
        collector_repo = CollectorRepository(db_session)

        # Create two workspaces
        ws1 = workspace_repo.create(
            organization_id=sample_organization.id,
            name="WS1 Builtin Test",
            slug="ws1-builtin-test",
        )
        ws2 = workspace_repo.create(
            organization_id=sample_organization.id,
            name="WS2 Builtin Test",
            slug="ws2-builtin-test",
        )
        db_session.flush()

        # Create builtin for ws1
        builtin1 = collector_repo.create_builtin(
            workspace_id=ws1.id,
            api_key_hash="hash1",
            api_key_prefix="cs_ws1",
            api_key_plaintext="key1",
        )
        db_session.flush()

        # ws1 should have builtin, ws2 should not
        assert collector_repo.get_builtin(ws1.id) is not None
        assert collector_repo.get_builtin(ws2.id) is None

        # Create builtin for ws2
        builtin2 = collector_repo.create_builtin(
            workspace_id=ws2.id,
            api_key_hash="hash2",
            api_key_prefix="cs_ws2",
            api_key_plaintext="key2",
        )
        db_session.flush()

        # Both should have different builtins
        assert collector_repo.get_builtin(ws1.id).id == builtin1.id
        assert collector_repo.get_builtin(ws2.id).id == builtin2.id
