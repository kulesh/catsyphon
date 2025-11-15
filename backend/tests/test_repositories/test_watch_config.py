"""
Tests for WatchConfigurationRepository.

Tests both inherited BaseRepository methods and WatchConfiguration-specific methods.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.models.db import Developer, Project, WatchConfiguration


@pytest.fixture
def watch_repo(db_session: Session) -> WatchConfigurationRepository:
    """Create a watch configuration repository."""
    return WatchConfigurationRepository(db_session)


@pytest.fixture
def sample_watch_config(
    db_session: Session, sample_project: Project, sample_developer: Developer
) -> WatchConfiguration:
    """Create a sample watch configuration for testing."""
    config = WatchConfiguration(
        id=uuid.uuid4(),
        directory="/path/to/watch",
        project_id=sample_project.id,
        developer_id=sample_developer.id,
        enable_tagging=True,
        is_active=False,
        stats={"files_processed": 10, "files_skipped": 2},
        extra_config={"poll_interval": 5},
        created_by="test_user",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


class TestBaseRepositoryMethods:
    """Test inherited BaseRepository CRUD methods."""

    def test_create_watch_config(
        self, watch_repo: WatchConfigurationRepository, sample_project: Project
    ):
        """Test creating a new watch configuration."""
        config = watch_repo.create(
            directory="/new/watch/path",
            project_id=sample_project.id,
            enable_tagging=False,
            is_active=False,
            stats={},
            extra_config={},
        )

        assert config.id is not None
        assert config.directory == "/new/watch/path"
        assert config.project_id == sample_project.id
        assert config.enable_tagging is False
        assert config.is_active is False
        assert config.stats == {}
        assert config.created_at is not None
        assert config.updated_at is not None

    def test_create_minimal_watch_config(
        self, watch_repo: WatchConfigurationRepository, db_session: Session
    ):
        """Test creating a watch configuration with minimal required fields."""
        # In real usage, Pydantic schemas provide defaults, so test with explicit values
        config = watch_repo.create(
            directory="/minimal/path",
            enable_tagging=False,
            is_active=False,
            stats={},
            extra_config={},
        )

        assert config.id is not None
        assert config.directory == "/minimal/path"
        assert config.project_id is None
        assert config.developer_id is None
        assert config.enable_tagging is False
        assert config.is_active is False
        assert config.stats == {}
        assert config.extra_config == {}

    def test_get_by_id(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test retrieving a watch configuration by ID."""
        config = watch_repo.get(sample_watch_config.id)

        assert config is not None
        assert config.id == sample_watch_config.id
        assert config.directory == sample_watch_config.directory
        assert config.project_id == sample_watch_config.project_id

    def test_get_by_id_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        config = watch_repo.get(non_existent_id)

        assert config is None

    def test_get_all(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test retrieving all watch configurations."""
        # Create additional configs
        watch_repo.create(directory="/path/one")
        watch_repo.create(directory="/path/two")

        configs = watch_repo.get_all()

        assert len(configs) >= 3  # At least the sample + 2 new ones
        directories = [c.directory for c in configs]
        assert "/path/to/watch" in directories  # sample_watch_config
        assert "/path/one" in directories
        assert "/path/two" in directories

    def test_get_all_with_limit(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving watch configurations with limit."""
        # Create multiple configs
        watch_repo.create(directory="/path/1")
        watch_repo.create(directory="/path/2")
        watch_repo.create(directory="/path/3")

        configs = watch_repo.get_all(limit=2)

        assert len(configs) == 2

    def test_get_all_with_offset(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving watch configurations with offset."""
        # Create configs
        watch_repo.create(directory="/path/1")
        watch_repo.create(directory="/path/2")
        watch_repo.create(directory="/path/3")

        all_configs = watch_repo.get_all()
        offset_configs = watch_repo.get_all(offset=1)

        assert len(offset_configs) == len(all_configs) - 1

    def test_update(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test updating a watch configuration."""
        updated = watch_repo.update(
            sample_watch_config.id,
            directory="/updated/path",
            enable_tagging=False,
        )

        assert updated is not None
        assert updated.id == sample_watch_config.id
        assert updated.directory == "/updated/path"
        assert updated.enable_tagging is False
        # Ensure other fields weren't changed
        assert updated.project_id == sample_watch_config.project_id

    def test_update_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test updating a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        updated = watch_repo.update(non_existent_id, directory="/new/path")

        assert updated is None

    def test_delete(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test deleting a watch configuration."""
        result = watch_repo.delete(sample_watch_config.id)

        assert result is True
        # Verify it's gone
        config = watch_repo.get(sample_watch_config.id)
        assert config is None

    def test_delete_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test deleting a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        result = watch_repo.delete(non_existent_id)

        assert result is False

    def test_count(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test counting watch configurations."""
        # Create additional configs
        watch_repo.create(directory="/path/one")
        watch_repo.create(directory="/path/two")

        count = watch_repo.count()

        assert count >= 3  # At least the sample + 2 new ones


class TestWatchConfigurationSpecificMethods:
    """Test WatchConfiguration-specific repository methods."""

    def test_get_by_directory(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test retrieving a watch configuration by directory path."""
        config = watch_repo.get_by_directory("/path/to/watch")

        assert config is not None
        assert config.id == sample_watch_config.id
        assert config.directory == "/path/to/watch"

    def test_get_by_directory_not_found(
        self, watch_repo: WatchConfigurationRepository
    ):
        """Test retrieving a watch configuration with non-existent directory."""
        config = watch_repo.get_by_directory("/non/existent/path")

        assert config is None

    def test_get_all_active(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving all active watch configurations."""
        # Create active and inactive configs
        active1 = watch_repo.create(directory="/active/one", is_active=True)
        active2 = watch_repo.create(directory="/active/two", is_active=True)
        watch_repo.create(directory="/inactive/one", is_active=False)
        watch_repo.create(directory="/inactive/two", is_active=False)

        active_configs = watch_repo.get_all_active()

        assert len(active_configs) == 2
        config_ids = [c.id for c in active_configs]
        assert active1.id in config_ids
        assert active2.id in config_ids
        # Verify all returned configs are active
        assert all(c.is_active for c in active_configs)

    def test_get_all_active_empty(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving active configs when none exist."""
        # Create only inactive configs
        watch_repo.create(directory="/inactive/one", is_active=False)
        watch_repo.create(directory="/inactive/two", is_active=False)

        active_configs = watch_repo.get_all_active()

        assert len(active_configs) == 0

    def test_get_all_inactive(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving all inactive watch configurations."""
        # Create active and inactive configs
        watch_repo.create(directory="/active/one", is_active=True)
        watch_repo.create(directory="/active/two", is_active=True)
        inactive1 = watch_repo.create(directory="/inactive/one", is_active=False)
        inactive2 = watch_repo.create(directory="/inactive/two", is_active=False)

        inactive_configs = watch_repo.get_all_inactive()

        assert len(inactive_configs) == 2
        config_ids = [c.id for c in inactive_configs]
        assert inactive1.id in config_ids
        assert inactive2.id in config_ids
        # Verify all returned configs are inactive
        assert all(not c.is_active for c in inactive_configs)

    def test_get_all_inactive_empty(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving inactive configs when none exist."""
        # Create only active configs
        watch_repo.create(directory="/active/one", is_active=True)
        watch_repo.create(directory="/active/two", is_active=True)

        inactive_configs = watch_repo.get_all_inactive()

        assert len(inactive_configs) == 0

    def test_activate(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test activating a watch configuration."""
        # Ensure it starts inactive
        assert sample_watch_config.is_active is False
        assert sample_watch_config.last_started_at is None

        # Activate it
        activated = watch_repo.activate(sample_watch_config.id)

        assert activated is not None
        assert activated.id == sample_watch_config.id
        assert activated.is_active is True
        assert activated.last_started_at is not None
        assert isinstance(activated.last_started_at, datetime)

    def test_activate_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test activating a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        result = watch_repo.activate(non_existent_id)

        assert result is None

    def test_deactivate(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test deactivating a watch configuration."""
        # First activate it
        watch_repo.activate(sample_watch_config.id)
        assert sample_watch_config.is_active is True

        # Now deactivate it
        deactivated = watch_repo.deactivate(sample_watch_config.id)

        assert deactivated is not None
        assert deactivated.id == sample_watch_config.id
        assert deactivated.is_active is False
        assert deactivated.last_stopped_at is not None
        assert isinstance(deactivated.last_stopped_at, datetime)

    def test_deactivate_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test deactivating a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        result = watch_repo.deactivate(non_existent_id)

        assert result is None

    def test_activate_deactivate_cycle(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test multiple activate/deactivate cycles."""
        # Start inactive
        assert sample_watch_config.is_active is False

        # Activate
        watch_repo.activate(sample_watch_config.id)
        config = watch_repo.get(sample_watch_config.id)
        assert config.is_active is True
        first_started = config.last_started_at

        # Deactivate
        watch_repo.deactivate(sample_watch_config.id)
        config = watch_repo.get(sample_watch_config.id)
        assert config.is_active is False
        first_stopped = config.last_stopped_at

        # Activate again
        watch_repo.activate(sample_watch_config.id)
        config = watch_repo.get(sample_watch_config.id)
        assert config.is_active is True
        second_started = config.last_started_at
        # Should have updated timestamp
        assert second_started >= first_started

    def test_update_stats(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test updating statistics for a watch configuration."""
        # Initial stats
        assert sample_watch_config.stats == {"files_processed": 10, "files_skipped": 2}

        # Update stats
        new_stats = {
            "files_processed": 25,
            "files_skipped": 5,
            "conversations_created": 20,
            "errors": 0,
        }
        updated = watch_repo.update_stats(sample_watch_config.id, new_stats)

        assert updated is not None
        assert updated.id == sample_watch_config.id
        assert updated.stats == new_stats
        assert updated.stats["files_processed"] == 25
        assert updated.stats["conversations_created"] == 20

    def test_update_stats_not_found(self, watch_repo: WatchConfigurationRepository):
        """Test updating stats for a non-existent watch configuration."""
        non_existent_id = uuid.uuid4()
        result = watch_repo.update_stats(non_existent_id, {"files_processed": 10})

        assert result is None

    def test_get_by_project(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_project: Project,
        sample_developer: Developer,
    ):
        """Test retrieving watch configurations by project."""
        # Create configs for the project
        config1 = watch_repo.create(
            directory="/project/path/one", project_id=sample_project.id
        )
        config2 = watch_repo.create(
            directory="/project/path/two", project_id=sample_project.id
        )

        # Create configs for other projects or no project
        other_project_id = uuid.uuid4()
        watch_repo.create(directory="/other/path", project_id=other_project_id)
        watch_repo.create(directory="/no/project/path")

        # Get configs for sample_project
        project_configs = watch_repo.get_by_project(sample_project.id)

        assert len(project_configs) >= 2
        config_ids = [c.id for c in project_configs]
        assert config1.id in config_ids
        assert config2.id in config_ids
        # Verify all returned configs belong to the project
        assert all(c.project_id == sample_project.id for c in project_configs)

    def test_get_by_project_empty(self, watch_repo: WatchConfigurationRepository):
        """Test retrieving configs for a project with no configs."""
        non_existent_project_id = uuid.uuid4()
        project_configs = watch_repo.get_by_project(non_existent_project_id)

        assert len(project_configs) == 0


class TestWatchConfigurationRelationships:
    """Test relationships with other models."""

    def test_project_relationship(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_project: Project,
    ):
        """Test that project relationship is properly loaded."""
        config = watch_repo.create(
            directory="/test/path",
            project_id=sample_project.id,
        )

        # Access the relationship
        assert config.project is not None
        assert config.project.id == sample_project.id
        assert config.project.name == sample_project.name

    def test_developer_relationship(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_developer: Developer,
    ):
        """Test that developer relationship is properly loaded."""
        config = watch_repo.create(
            directory="/test/path",
            developer_id=sample_developer.id,
        )

        # Access the relationship
        assert config.developer is not None
        assert config.developer.id == sample_developer.id
        assert config.developer.username == sample_developer.username

    def test_optional_relationships(self, watch_repo: WatchConfigurationRepository):
        """Test that project and developer relationships are optional."""
        config = watch_repo.create(
            directory="/test/path",
            # No project_id or developer_id
        )

        assert config.project_id is None
        assert config.developer_id is None
        assert config.project is None
        assert config.developer is None


class TestWatchConfigurationEdgeCases:
    """Test edge cases and error conditions."""

    def test_update_preserves_unmodified_fields(
        self,
        watch_repo: WatchConfigurationRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test that update only modifies specified fields."""
        original_directory = sample_watch_config.directory
        original_enable_tagging = sample_watch_config.enable_tagging
        original_project_id = sample_watch_config.project_id

        # Update only stats
        watch_repo.update_stats(
            sample_watch_config.id,
            {"files_processed": 100},
        )

        # Refresh and check
        updated = watch_repo.get(sample_watch_config.id)
        assert updated.directory == original_directory
        assert updated.enable_tagging == original_enable_tagging
        assert updated.project_id == original_project_id
        assert updated.stats == {"files_processed": 100}

    def test_empty_stats_and_config(self, watch_repo: WatchConfigurationRepository):
        """Test creating config with empty stats and extra_config."""
        config = watch_repo.create(
            directory="/test/path",
            stats={},
            extra_config={},
        )

        assert config.stats == {}
        assert config.extra_config == {}

    def test_complex_stats_and_config(self, watch_repo: WatchConfigurationRepository):
        """Test creating config with complex nested stats and config."""
        complex_stats = {
            "files_processed": 100,
            "by_type": {"json": 50, "txt": 30, "other": 20},
            "errors": {"permission_denied": 2, "parse_failed": 1},
        }
        complex_config = {
            "poll_interval": 5,
            "retry": {"max_attempts": 3, "backoff": "exponential"},
            "filters": {"extensions": [".json", ".txt"], "exclude": ["*.tmp"]},
        }

        config = watch_repo.create(
            directory="/test/path",
            stats=complex_stats,
            extra_config=complex_config,
        )

        assert config.stats == complex_stats
        assert config.extra_config == complex_config
        assert config.stats["by_type"]["json"] == 50
        assert config.extra_config["retry"]["max_attempts"] == 3
