"""
Tests for Watch Configuration API endpoints.

Tests all /watch/* API routes for watch directory configuration management.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.models.db import Project, WatchConfiguration


@pytest.fixture
def watch_config(db_session: Session, sample_project: Project) -> WatchConfiguration:
    """Create a sample watch configuration for testing."""
    repo = WatchConfigurationRepository(db_session)
    config = repo.create(
        directory="/test/watch/path",
        project_id=sample_project.id,
        enable_tagging=True,
        is_active=False,
        stats={"files_processed": 10},
        extra_config={"poll_interval": 5},
        created_by="test_user",
    )
    db_session.commit()
    return config


@pytest.fixture
def active_watch_config(
    db_session: Session, sample_project: Project
) -> WatchConfiguration:
    """Create an active watch configuration for testing."""
    repo = WatchConfigurationRepository(db_session)
    config = repo.create(
        directory="/active/watch/path",
        project_id=sample_project.id,
        enable_tagging=False,
        is_active=True,
        stats={},
        extra_config={},
    )
    db_session.commit()
    return config


class TestListWatchConfigs:
    """Test GET /watch/configs endpoint."""

    def test_list_all_configs(
        self,
        api_client: TestClient,
        watch_config: WatchConfiguration,
        active_watch_config: WatchConfiguration,
    ):
        """Test listing all watch configurations."""
        response = api_client.get("/watch/configs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        # Find our test configs
        config_ids = [c["id"] for c in data]
        assert str(watch_config.id) in config_ids
        assert str(active_watch_config.id) in config_ids

    def test_list_active_only(
        self,
        api_client: TestClient,
        watch_config: WatchConfiguration,
        active_watch_config: WatchConfiguration,
    ):
        """Test listing only active configurations."""
        response = api_client.get("/watch/configs?active_only=true")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Should only include active configs
        config_ids = [c["id"] for c in data]
        assert str(active_watch_config.id) in config_ids
        assert str(watch_config.id) not in config_ids

        # Verify all returned configs are active
        assert all(c["is_active"] for c in data)

    def test_list_inactive_only(
        self,
        api_client: TestClient,
        watch_config: WatchConfiguration,
        active_watch_config: WatchConfiguration,
    ):
        """Test listing inactive configurations (active_only=false)."""
        response = api_client.get("/watch/configs?active_only=false")

        assert response.status_code == 200
        data = response.json()

        # Should include both active and inactive
        config_ids = [c["id"] for c in data]
        assert str(watch_config.id) in config_ids
        assert str(active_watch_config.id) in config_ids

    def test_list_empty(self, api_client: TestClient):
        """Test listing when no configurations exist."""
        response = api_client.get("/watch/configs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestGetWatchConfig:
    """Test GET /watch/configs/{config_id} endpoint."""

    def test_get_existing_config(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test retrieving an existing watch configuration."""
        response = api_client.get(f"/watch/configs/{watch_config.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(watch_config.id)
        assert data["directory"] == watch_config.directory
        assert data["enable_tagging"] == watch_config.enable_tagging
        assert data["is_active"] == watch_config.is_active
        assert data["stats"] == watch_config.stats

    def test_get_nonexistent_config(self, api_client: TestClient):
        """Test retrieving a non-existent configuration."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/watch/configs/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_invalid_uuid(self, api_client: TestClient):
        """Test with an invalid UUID format."""
        response = api_client.get("/watch/configs/not-a-uuid")

        assert response.status_code == 422  # Validation error


class TestCreateWatchConfig:
    """Test POST /watch/configs endpoint."""

    def test_create_config_minimal(self, api_client: TestClient):
        """Test creating a config with minimal required fields."""
        payload = {
            "directory": "/new/watch/path",
        }

        response = api_client.post("/watch/configs", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["directory"] == "/new/watch/path"
        assert data["is_active"] is False  # Should start inactive
        assert data["enable_tagging"] is False  # Default
        assert data["stats"] == {}
        assert data["id"] is not None

    def test_create_config_full(
        self, api_client: TestClient, sample_project: Project
    ):
        """Test creating a config with all fields."""
        payload = {
            "directory": "/full/watch/path",
            "project_id": str(sample_project.id),
            "enable_tagging": True,
            "extra_config": {"poll_interval": 10},
            "created_by": "api_user",
        }

        response = api_client.post("/watch/configs", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["directory"] == "/full/watch/path"
        assert data["project_id"] == str(sample_project.id)
        assert data["enable_tagging"] is True
        assert data["extra_config"] == {"poll_interval": 10}
        assert data["created_by"] == "api_user"

    def test_create_duplicate_directory(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test creating a config for an already-watched directory."""
        payload = {
            "directory": watch_config.directory,  # Same directory
        }

        response = api_client.post("/watch/configs", json=payload)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_invalid_project_id(self, api_client: TestClient):
        """Test creating a config with invalid project_id."""
        payload = {
            "directory": "/test/path",
            "project_id": "not-a-uuid",
        }

        response = api_client.post("/watch/configs", json=payload)

        assert response.status_code == 422  # Validation error


class TestUpdateWatchConfig:
    """Test PUT /watch/configs/{config_id} endpoint."""

    def test_update_directory(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test updating the directory path."""
        payload = {
            "directory": "/updated/path",
        }

        response = api_client.put(f"/watch/configs/{watch_config.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(watch_config.id)
        assert data["directory"] == "/updated/path"

    def test_update_enable_tagging(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test updating the enable_tagging flag."""
        original_tagging = watch_config.enable_tagging
        payload = {
            "enable_tagging": not original_tagging,
        }

        response = api_client.put(f"/watch/configs/{watch_config.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["enable_tagging"] == (not original_tagging)

    def test_update_extra_config(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test updating extra_config."""
        payload = {
            "extra_config": {"new_setting": "value"},
        }

        response = api_client.put(f"/watch/configs/{watch_config.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["extra_config"] == {"new_setting": "value"}

    def test_update_nonexistent_config(self, api_client: TestClient):
        """Test updating a non-existent configuration."""
        fake_id = uuid.uuid4()
        payload = {
            "directory": "/new/path",
        }

        response = api_client.put(f"/watch/configs/{fake_id}", json=payload)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_partial(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test partial update (only some fields)."""
        original_directory = watch_config.directory
        payload = {
            "enable_tagging": False,
            # directory not updated
        }

        response = api_client.put(f"/watch/configs/{watch_config.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["directory"] == original_directory  # Unchanged
        assert data["enable_tagging"] is False  # Changed


class TestDeleteWatchConfig:
    """Test DELETE /watch/configs/{config_id} endpoint."""

    def test_delete_inactive_config(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test deleting an inactive configuration."""
        response = api_client.delete(f"/watch/configs/{watch_config.id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = api_client.get(f"/watch/configs/{watch_config.id}")
        assert get_response.status_code == 404

    def test_delete_active_config(
        self, api_client: TestClient, active_watch_config: WatchConfiguration
    ):
        """Test deleting an active configuration (should fail)."""
        response = api_client.delete(f"/watch/configs/{active_watch_config.id}")

        assert response.status_code == 400
        assert "active" in response.json()["detail"].lower()
        assert "stop" in response.json()["detail"].lower()

    def test_delete_nonexistent_config(self, api_client: TestClient):
        """Test deleting a non-existent configuration."""
        fake_id = uuid.uuid4()
        response = api_client.delete(f"/watch/configs/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestStartWatching:
    """Test POST /watch/configs/{config_id}/start endpoint."""

    def test_start_inactive_config(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test activating an inactive configuration."""
        assert watch_config.is_active is False

        response = api_client.post(f"/watch/configs/{watch_config.id}/start")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(watch_config.id)
        assert data["is_active"] is True
        assert data["last_started_at"] is not None

    def test_start_already_active_config(
        self, api_client: TestClient, active_watch_config: WatchConfiguration
    ):
        """Test activating an already-active configuration."""
        assert active_watch_config.is_active is True

        response = api_client.post(f"/watch/configs/{active_watch_config.id}/start")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_start_nonexistent_config(self, api_client: TestClient):
        """Test activating a non-existent configuration."""
        fake_id = uuid.uuid4()
        response = api_client.post(f"/watch/configs/{fake_id}/start")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestStopWatching:
    """Test POST /watch/configs/{config_id}/stop endpoint."""

    def test_stop_active_config(
        self, api_client: TestClient, active_watch_config: WatchConfiguration
    ):
        """Test deactivating an active configuration."""
        assert active_watch_config.is_active is True

        response = api_client.post(f"/watch/configs/{active_watch_config.id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(active_watch_config.id)
        assert data["is_active"] is False
        assert data["last_stopped_at"] is not None

    def test_stop_inactive_config(
        self, api_client: TestClient, watch_config: WatchConfiguration
    ):
        """Test deactivating an already-inactive configuration."""
        assert watch_config.is_active is False

        response = api_client.post(f"/watch/configs/{watch_config.id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_stop_nonexistent_config(self, api_client: TestClient):
        """Test deactivating a non-existent configuration."""
        fake_id = uuid.uuid4()
        response = api_client.post(f"/watch/configs/{fake_id}/stop")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetWatchStatus:
    """Test GET /watch/status endpoint."""

    def test_get_status_with_configs(
        self,
        api_client: TestClient,
        watch_config: WatchConfiguration,
        active_watch_config: WatchConfiguration,
    ):
        """Test getting watch status with configurations."""
        response = api_client.get("/watch/status")

        assert response.status_code == 200
        data = response.json()

        assert "total_configs" in data
        assert "active_count" in data
        assert "inactive_count" in data
        assert "active_configs" in data

        assert data["total_configs"] >= 2
        assert data["active_count"] >= 1
        assert data["inactive_count"] >= 1

        # active_configs should be a list
        assert isinstance(data["active_configs"], list)
        active_config_ids = [c["id"] for c in data["active_configs"]]
        assert str(active_watch_config.id) in active_config_ids
        assert str(watch_config.id) not in active_config_ids  # Inactive

    def test_get_status_empty(self, api_client: TestClient):
        """Test getting watch status when no configurations exist."""
        response = api_client.get("/watch/status")

        assert response.status_code == 200
        data = response.json()

        assert data["total_configs"] == 0
        assert data["active_count"] == 0
        assert data["inactive_count"] == 0
        assert data["active_configs"] == []

    def test_get_status_all_active(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_project: Project,
    ):
        """Test status when all configurations are active."""
        repo = WatchConfigurationRepository(db_session)

        # Create multiple active configs
        for i in range(3):
            repo.create(
                directory=f"/active/{i}",
                project_id=sample_project.id,
                is_active=True,
            )
        db_session.commit()

        response = api_client.get("/watch/status")

        assert response.status_code == 200
        data = response.json()

        assert data["total_configs"] == 3
        assert data["active_count"] == 3
        assert data["inactive_count"] == 0
        assert len(data["active_configs"]) == 3


class TestWatchConfigIntegration:
    """Integration tests for watch configuration workflows."""

    def test_full_lifecycle(self, api_client: TestClient, sample_project: Project):
        """Test complete lifecycle: create -> start -> stop -> delete."""
        # Create
        create_payload = {
            "directory": "/lifecycle/test",
            "project_id": str(sample_project.id),
            "enable_tagging": True,
        }
        create_response = api_client.post("/watch/configs", json=create_payload)
        assert create_response.status_code == 201
        config_id = create_response.json()["id"]

        # Start
        start_response = api_client.post(f"/watch/configs/{config_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["is_active"] is True

        # Stop
        stop_response = api_client.post(f"/watch/configs/{config_id}/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["is_active"] is False

        # Delete
        delete_response = api_client.delete(f"/watch/configs/{config_id}")
        assert delete_response.status_code == 204

    def test_stop_then_delete_workflow(self, api_client: TestClient):
        """Test stopping then deleting a configuration."""
        # Create
        create_payload = {
            "directory": "/stop-delete/path",
        }
        create_response = api_client.post("/watch/configs", json=create_payload)
        assert create_response.status_code == 201
        config_id = create_response.json()["id"]

        # Start
        start_response = api_client.post(f"/watch/configs/{config_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["is_active"] is True

        # Stop
        stop_response = api_client.post(f"/watch/configs/{config_id}/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["is_active"] is False

        # Delete should succeed now
        delete_response = api_client.delete(f"/watch/configs/{config_id}")
        assert delete_response.status_code == 204

    def test_update_while_active(
        self, api_client: TestClient, active_watch_config: WatchConfiguration
    ):
        """Test that active configs can be updated."""
        update_payload = {
            "enable_tagging": True,
        }

        response = api_client.put(
            f"/watch/configs/{active_watch_config.id}", json=update_payload
        )

        assert response.status_code == 200
        assert response.json()["enable_tagging"] is True
        assert response.json()["is_active"] is True  # Still active
