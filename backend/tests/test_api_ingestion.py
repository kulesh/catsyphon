"""
Tests for Ingestion Jobs API endpoints.

Tests all /ingestion/* API routes for ingestion job querying and statistics.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories.ingestion_job import IngestionJobRepository
from catsyphon.models.db import (
    Conversation,
    IngestionJob,
    Project,
    WatchConfiguration,
)


@pytest.fixture
def watch_config(db_session: Session, sample_project: Project) -> WatchConfiguration:
    """Create a watch configuration for testing."""
    from catsyphon.db.repositories.watch_config import WatchConfigurationRepository

    repo = WatchConfigurationRepository(db_session)
    config = repo.create(
        directory="/test/watch",
        project_id=sample_project.id,
        is_active=True,
    )
    db_session.commit()
    return config


@pytest.fixture
def ingestion_jobs(
    db_session: Session,
    watch_config: WatchConfiguration,
    sample_conversation: Conversation,
) -> list[IngestionJob]:
    """Create multiple ingestion jobs for testing."""
    repo = IngestionJobRepository(db_session)
    started = datetime.now(UTC)

    jobs = [
        repo.create(
            source_type="watch",
            source_config_id=watch_config.id,
            conversation_id=sample_conversation.id,
            status="success",
            processing_time_ms=1000,
            incremental=True,
            messages_added=10,
            started_at=started,
        ),
        repo.create(
            source_type="upload",
            conversation_id=sample_conversation.id,
            status="success",
            processing_time_ms=2000,
            incremental=False,
            messages_added=20,
            started_at=started,
        ),
        repo.create(
            source_type="cli",
            status="failed",
            error_message="Parse error",
            processing_time_ms=500,
            incremental=False,
            messages_added=0,
            started_at=started,
        ),
        repo.create(
            source_type="watch",
            source_config_id=watch_config.id,
            status="duplicate",
            processing_time_ms=100,
            incremental=False,
            messages_added=0,
            started_at=started,
        ),
    ]

    db_session.commit()
    return jobs


class TestListIngestionJobs:
    """Test GET /ingestion/jobs endpoint."""

    def test_list_all_jobs(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test listing all ingestion jobs."""
        response = api_client.get("/ingestion/jobs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4

        # Verify our test jobs are included
        job_ids = [j["id"] for j in data]
        for job in ingestion_jobs:
            assert str(job.id) in job_ids

    def test_list_filter_by_source_type(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test filtering by source type."""
        response = api_client.get("/ingestion/jobs?source_type=watch")

        assert response.status_code == 200
        data = response.json()

        # Should only include watch jobs
        assert all(j["source_type"] == "watch" for j in data)
        assert len(data) == 2  # We created 2 watch jobs

    def test_list_filter_by_status(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test filtering by status."""
        response = api_client.get("/ingestion/jobs?status=success")

        assert response.status_code == 200
        data = response.json()

        # Should only include success jobs
        assert all(j["status"] == "success" for j in data)
        assert len(data) == 2  # We created 2 success jobs

    def test_list_filter_by_both(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test filtering by both source_type and status."""
        response = api_client.get("/ingestion/jobs?source_type=watch&status=success")

        assert response.status_code == 200
        data = response.json()

        # Should only include watch + success jobs
        assert all(j["source_type"] == "watch" and j["status"] == "success" for j in data)
        assert len(data) == 1

    def test_list_pagination(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test pagination."""
        # First page
        response = api_client.get("/ingestion/jobs?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

        # Second page
        response = api_client.get("/ingestion/jobs?page=2&page_size=2")

        assert response.status_code == 200
        data = response.json()
        # Should have remaining jobs
        assert isinstance(data, list)

    def test_list_empty(self, api_client: TestClient):
        """Test listing when no jobs exist."""
        response = api_client.get("/ingestion/jobs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestGetIngestionJob:
    """Test GET /ingestion/jobs/{job_id} endpoint."""

    def test_get_existing_job(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test retrieving an existing ingestion job."""
        job = ingestion_jobs[0]
        response = api_client.get(f"/ingestion/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["source_type"] == job.source_type
        assert data["status"] == job.status
        assert data["processing_time_ms"] == job.processing_time_ms
        assert data["messages_added"] == job.messages_added
        assert data["incremental"] == job.incremental

    def test_get_nonexistent_job(self, api_client: TestClient):
        """Test retrieving a non-existent job."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/ingestion/jobs/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_invalid_uuid(self, api_client: TestClient):
        """Test with an invalid UUID format."""
        response = api_client.get("/ingestion/jobs/not-a-uuid")

        assert response.status_code == 422  # Validation error

    def test_get_job_with_error(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test retrieving a failed job with error message."""
        failed_job = next(j for j in ingestion_jobs if j.status == "failed")
        response = api_client.get(f"/ingestion/jobs/{failed_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] is not None


class TestGetIngestionStats:
    """Test GET /ingestion/stats endpoint."""

    def test_get_stats_with_jobs(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test retrieving statistics with jobs."""
        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        assert "total_jobs" in data
        assert "by_status" in data
        assert "by_source_type" in data
        assert "avg_processing_time_ms" in data
        assert "incremental_jobs" in data
        assert "incremental_percentage" in data

        assert data["total_jobs"] >= 4
        assert data["by_status"]["success"] == 2
        assert data["by_status"]["failed"] == 1
        assert data["by_status"]["duplicate"] == 1
        assert data["by_source_type"]["watch"] == 2
        assert data["by_source_type"]["upload"] == 1
        assert data["by_source_type"]["cli"] == 1
        assert data["incremental_jobs"] == 1
        assert data["incremental_percentage"] == 25.0

    def test_get_stats_empty(self, api_client: TestClient):
        """Test getting stats when no jobs exist."""
        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_jobs"] == 0
        assert data["by_status"] == {}
        assert data["by_source_type"] == {}
        assert data["avg_processing_time_ms"] is None
        assert data["incremental_jobs"] == 0
        assert data["incremental_percentage"] == 0

    def test_stats_avg_processing_time(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test that average processing time is calculated correctly."""
        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        # Average of 1000, 2000, 500, 100 = 900
        assert data["avg_processing_time_ms"] is not None
        assert 850 < data["avg_processing_time_ms"] < 950


class TestGetConversationIngestionJobs:
    """Test GET /ingestion/jobs/conversation/{conversation_id} endpoint."""

    def test_get_jobs_for_conversation(
        self,
        api_client: TestClient,
        sample_conversation: Conversation,
        ingestion_jobs: list[IngestionJob],
    ):
        """Test retrieving jobs for a specific conversation."""
        response = api_client.get(
            f"/ingestion/jobs/conversation/{sample_conversation.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should include jobs with this conversation_id
        assert isinstance(data, list)
        assert len(data) == 2  # watch and upload jobs have conversation_id
        assert all(j["conversation_id"] == str(sample_conversation.id) for j in data)

    def test_get_jobs_for_nonexistent_conversation(self, api_client: TestClient):
        """Test retrieving jobs for a non-existent conversation."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/ingestion/jobs/conversation/{fake_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0  # No jobs found

    def test_get_jobs_ordered_by_recent(
        self,
        api_client: TestClient,
        db_session: Session,
        sample_conversation: Conversation,
    ):
        """Test that jobs are ordered by most recent first."""
        repo = IngestionJobRepository(db_session)
        base_time = datetime.now(UTC)

        # Create jobs at different times
        from datetime import timedelta

        job1 = repo.create(
            source_type="upload",
            conversation_id=sample_conversation.id,
            status="success",
            started_at=base_time - timedelta(hours=2),
        )
        job2 = repo.create(
            source_type="upload",
            conversation_id=sample_conversation.id,
            status="success",
            started_at=base_time - timedelta(hours=1),
        )
        db_session.commit()

        response = api_client.get(
            f"/ingestion/jobs/conversation/{sample_conversation.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should be ordered by most recent first
        job_ids = [j["id"] for j in data]
        # job2 is more recent, so it should come first
        assert job_ids.index(str(job2.id)) < job_ids.index(str(job1.id))


class TestGetWatchConfigIngestionJobs:
    """Test GET /ingestion/jobs/watch-config/{config_id} endpoint."""

    def test_get_jobs_for_watch_config(
        self,
        api_client: TestClient,
        watch_config: WatchConfiguration,
        ingestion_jobs: list[IngestionJob],
    ):
        """Test retrieving jobs for a specific watch configuration."""
        response = api_client.get(f"/ingestion/jobs/watch-config/{watch_config.id}")

        assert response.status_code == 200
        data = response.json()

        # Should include jobs with this source_config_id
        assert isinstance(data, list)
        assert len(data) == 2  # We created 2 watch jobs with this config
        assert all(j["source_config_id"] == str(watch_config.id) for j in data)

    def test_get_jobs_for_nonexistent_config(self, api_client: TestClient):
        """Test retrieving jobs for a non-existent watch config."""
        fake_id = uuid.uuid4()
        response = api_client.get(f"/ingestion/jobs/watch-config/{fake_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0  # No jobs found

    def test_get_jobs_pagination(
        self,
        api_client: TestClient,
        db_session: Session,
        watch_config: WatchConfiguration,
    ):
        """Test pagination for watch config jobs."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create multiple jobs
        for i in range(5):
            repo.create(
                source_type="watch",
                source_config_id=watch_config.id,
                status="success",
                started_at=started,
            )
        db_session.commit()

        # First page
        response = api_client.get(
            f"/ingestion/jobs/watch-config/{watch_config.id}?page=1&page_size=3"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

        # Second page
        response = api_client.get(
            f"/ingestion/jobs/watch-config/{watch_config.id}?page=2&page_size=3"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestIngestionJobsIntegration:
    """Integration tests for ingestion jobs workflows."""

    def test_job_lifecycle_tracking(
        self,
        api_client: TestClient,
        db_session: Session,
        watch_config: WatchConfiguration,
    ):
        """Test tracking a job through its lifecycle."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create job in processing state
        job = repo.create(
            source_type="watch",
            source_config_id=watch_config.id,
            status="processing",
            started_at=started,
            messages_added=0,
        )
        db_session.commit()

        # Retrieve and verify
        response = api_client.get(f"/ingestion/jobs/{job.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "processing"

        # Update to success
        from datetime import timedelta

        completed = datetime.now(UTC)
        repo.update(
            job.id,
            status="success",
            completed_at=completed,
            processing_time_ms=1500,
            messages_added=25,
        )
        db_session.commit()

        # Verify updated
        response = api_client.get(f"/ingestion/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["processing_time_ms"] == 1500
        assert data["messages_added"] == 25

    def test_filter_combinations(
        self, api_client: TestClient, db_session: Session
    ):
        """Test various filter combinations."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create diverse jobs
        repo.create(source_type="watch", status="success", started_at=started)
        repo.create(source_type="watch", status="failed", started_at=started)
        repo.create(source_type="upload", status="success", started_at=started)
        repo.create(source_type="cli", status="duplicate", started_at=started)
        db_session.commit()

        # Test watch + success
        response = api_client.get("/ingestion/jobs?source_type=watch&status=success")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Test upload only
        response = api_client.get("/ingestion/jobs?source_type=upload")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Test failed only
        response = api_client.get("/ingestion/jobs?status=failed")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_stats_accuracy(
        self, api_client: TestClient, db_session: Session
    ):
        """Test that statistics are accurate across multiple queries."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create jobs with specific characteristics
        repo.create(
            source_type="watch",
            status="success",
            started_at=started,
            processing_time_ms=1000,
            incremental=True,
        )
        repo.create(
            source_type="watch",
            status="success",
            started_at=started,
            processing_time_ms=2000,
            incremental=True,
        )
        repo.create(
            source_type="upload",
            status="failed",
            started_at=started,
            processing_time_ms=500,
            incremental=False,
        )
        db_session.commit()

        # Get stats
        response = api_client.get("/ingestion/stats")
        assert response.status_code == 200
        data = response.json()

        # Verify counts
        assert data["total_jobs"] == 3
        assert data["by_status"]["success"] == 2
        assert data["by_status"]["failed"] == 1
        assert data["by_source_type"]["watch"] == 2
        assert data["by_source_type"]["upload"] == 1

        # Verify incremental stats
        assert data["incremental_jobs"] == 2
        # 2 out of 3 = 66.67%
        assert 66 < data["incremental_percentage"] < 67

        # Verify average (1000 + 2000 + 500) / 3 = 1166.67
        assert 1150 < data["avg_processing_time_ms"] < 1180


class TestIngestionJobsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_large_page_size(
        self, api_client: TestClient, ingestion_jobs: list[IngestionJob]
    ):
        """Test requesting a very large page size."""
        response = api_client.get("/ingestion/jobs?page_size=1000")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_page_beyond_results(self, api_client: TestClient):
        """Test requesting a page beyond available results."""
        response = api_client.get("/ingestion/jobs?page=999&page_size=50")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_invalid_source_type(self, api_client: TestClient):
        """Test filtering by invalid source type."""
        response = api_client.get("/ingestion/jobs?source_type=invalid")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # No matching jobs

    def test_invalid_status(self, api_client: TestClient):
        """Test filtering by invalid status."""
        response = api_client.get("/ingestion/jobs?status=invalid")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # No matching jobs

    def test_job_without_optional_fields(
        self, api_client: TestClient, db_session: Session
    ):
        """Test retrieving a job with minimal fields."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        job = repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            # No conversation_id, source_config_id, etc.
        )
        db_session.commit()

        response = api_client.get(f"/ingestion/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["source_config_id"] is None
        assert data["conversation_id"] is None
        assert data["raw_log_id"] is None
        assert data["file_path"] is None
