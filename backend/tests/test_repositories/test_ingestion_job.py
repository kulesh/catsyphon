"""
Tests for IngestionJobRepository.

Tests both inherited BaseRepository methods and IngestionJob-specific methods.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from catsyphon.db.repositories.ingestion_job import IngestionJobRepository
from catsyphon.models.db import (
    Conversation,
    IngestionJob,
    Project,
    WatchConfiguration,
)


@pytest.fixture
def job_repo(db_session: Session) -> IngestionJobRepository:
    """Create an ingestion job repository."""
    return IngestionJobRepository(db_session)


@pytest.fixture
def sample_watch_config(
    db_session: Session, sample_project: Project
) -> WatchConfiguration:
    """Create a sample watch configuration for testing."""
    config = WatchConfiguration(
        id=uuid.uuid4(),
        directory="/test/watch/path",
        project_id=sample_project.id,
        enable_tagging=False,
        is_active=True,
        stats={},
        extra_config={},
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture
def sample_ingestion_job(
    db_session: Session,
    sample_watch_config: WatchConfiguration,
    sample_conversation: Conversation,
) -> IngestionJob:
    """Create a sample ingestion job for testing."""
    job = IngestionJob(
        id=uuid.uuid4(),
        source_type="watch",
        source_config_id=sample_watch_config.id,
        file_path="/test/file.json",
        conversation_id=sample_conversation.id,
        status="success",
        processing_time_ms=1500,
        incremental=True,
        messages_added=25,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


class TestBaseRepositoryMethods:
    """Test inherited BaseRepository CRUD methods."""

    def test_create_ingestion_job(
        self, job_repo: IngestionJobRepository, sample_watch_config: WatchConfiguration
    ):
        """Test creating a new ingestion job."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="watch",
            source_config_id=sample_watch_config.id,
            file_path="/new/test.json",
            status="processing",
            incremental=False,
            messages_added=0,
            started_at=started,
        )

        assert job.id is not None
        assert job.source_type == "watch"
        assert job.source_config_id == sample_watch_config.id
        assert job.file_path == "/new/test.json"
        assert job.status == "processing"
        assert job.incremental is False
        assert job.messages_added == 0
        # SQLite doesn't preserve timezone info, so compare timestamp values
        assert job.started_at.replace(tzinfo=None) == started.replace(tzinfo=None)
        assert job.created_at is not None

    def test_create_minimal_job(self, job_repo: IngestionJobRepository):
        """Test creating a job with minimal required fields."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            incremental=False,
            messages_added=10,
        )

        assert job.id is not None
        assert job.source_type == "cli"
        assert job.status == "success"
        assert job.source_config_id is None
        assert job.file_path is None
        assert job.conversation_id is None

    def test_get_by_id(
        self, job_repo: IngestionJobRepository, sample_ingestion_job: IngestionJob
    ):
        """Test retrieving an ingestion job by ID."""
        job = job_repo.get(sample_ingestion_job.id)

        assert job is not None
        assert job.id == sample_ingestion_job.id
        assert job.source_type == sample_ingestion_job.source_type
        assert job.status == sample_ingestion_job.status

    def test_get_by_id_not_found(self, job_repo: IngestionJobRepository):
        """Test retrieving a non-existent ingestion job."""
        non_existent_id = uuid.uuid4()
        job = job_repo.get(non_existent_id)

        assert job is None

    def test_get_all(
        self, job_repo: IngestionJobRepository, sample_ingestion_job: IngestionJob
    ):
        """Test retrieving all ingestion jobs."""
        # Create additional jobs
        started = datetime.now(UTC)
        job_repo.create(
            source_type="upload", status="success", started_at=started, messages_added=5
        )
        job_repo.create(
            source_type="cli", status="failed", started_at=started, messages_added=0
        )

        jobs = job_repo.get_all()

        assert len(jobs) >= 3
        source_types = [j.source_type for j in jobs]
        assert "watch" in source_types
        assert "upload" in source_types
        assert "cli" in source_types

    def test_get_all_with_limit(self, job_repo: IngestionJobRepository):
        """Test retrieving ingestion jobs with limit."""
        started = datetime.now(UTC)
        for i in range(5):
            job_repo.create(
                source_type="cli",
                status="success",
                started_at=started,
                messages_added=i,
            )

        jobs = job_repo.get_all(limit=3)

        assert len(jobs) == 3

    def test_update(
        self, job_repo: IngestionJobRepository, sample_ingestion_job: IngestionJob
    ):
        """Test updating an ingestion job."""
        completed = datetime.now(UTC)
        updated = job_repo.update(
            sample_ingestion_job.id,
            status="success",
            completed_at=completed,
            processing_time_ms=2500,
        )

        assert updated is not None
        assert updated.id == sample_ingestion_job.id
        assert updated.status == "success"
        # SQLite doesn't preserve timezone info, so compare timestamp values
        assert updated.completed_at.replace(tzinfo=None) == completed.replace(
            tzinfo=None
        )
        assert updated.processing_time_ms == 2500

    def test_delete(
        self, job_repo: IngestionJobRepository, sample_ingestion_job: IngestionJob
    ):
        """Test deleting an ingestion job."""
        result = job_repo.delete(sample_ingestion_job.id)

        assert result is True
        job = job_repo.get(sample_ingestion_job.id)
        assert job is None

    def test_count(
        self, job_repo: IngestionJobRepository, sample_ingestion_job: IngestionJob
    ):
        """Test counting ingestion jobs."""
        started = datetime.now(UTC)
        job_repo.create(source_type="upload", status="success", started_at=started)
        job_repo.create(source_type="cli", status="failed", started_at=started)

        count = job_repo.count()

        assert count >= 3


class TestIngestionJobSpecificMethods:
    """Test IngestionJob-specific repository methods."""

    def test_get_by_source_type(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs by source type."""
        started = datetime.now(UTC)
        watch1 = job_repo.create(
            source_type="watch", status="success", started_at=started
        )
        watch2 = job_repo.create(
            source_type="watch", status="failed", started_at=started
        )
        job_repo.create(source_type="upload", status="success", started_at=started)
        job_repo.create(source_type="cli", status="success", started_at=started)

        watch_jobs = job_repo.get_by_source_type("watch")

        assert len(watch_jobs) == 2
        job_ids = [j.id for j in watch_jobs]
        assert watch1.id in job_ids
        assert watch2.id in job_ids
        assert all(j.source_type == "watch" for j in watch_jobs)

    def test_get_by_source_type_with_limit(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs by source type with limit."""
        started = datetime.now(UTC)
        for _ in range(5):
            job_repo.create(source_type="watch", status="success", started_at=started)

        watch_jobs = job_repo.get_by_source_type("watch", limit=3)

        assert len(watch_jobs) == 3

    def test_get_by_status(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs by status."""
        started = datetime.now(UTC)
        success1 = job_repo.create(
            source_type="watch", status="success", started_at=started
        )
        success2 = job_repo.create(
            source_type="upload", status="success", started_at=started
        )
        job_repo.create(source_type="cli", status="failed", started_at=started)
        job_repo.create(source_type="watch", status="duplicate", started_at=started)

        success_jobs = job_repo.get_by_status("success")

        assert len(success_jobs) == 2
        job_ids = [j.id for j in success_jobs]
        assert success1.id in job_ids
        assert success2.id in job_ids
        assert all(j.status == "success" for j in success_jobs)

    def test_get_recent(self, job_repo: IngestionJobRepository):
        """Test retrieving recent jobs ordered by started_at."""
        base_time = datetime.now(UTC)
        job1 = job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(hours=3),
        )
        job2 = job_repo.create(
            source_type="upload",
            status="success",
            started_at=base_time - timedelta(hours=2),
        )
        job3 = job_repo.create(
            source_type="cli", status="success", started_at=base_time - timedelta(hours=1)
        )

        recent_jobs = job_repo.get_recent(limit=10)

        assert len(recent_jobs) >= 3
        # Should be ordered by most recent first
        assert recent_jobs[0].id == job3.id
        assert recent_jobs[1].id == job2.id
        assert recent_jobs[2].id == job1.id

    def test_get_by_watch_config(
        self, job_repo: IngestionJobRepository, sample_watch_config: WatchConfiguration
    ):
        """Test retrieving jobs for a specific watch configuration."""
        started = datetime.now(UTC)
        job1 = job_repo.create(
            source_type="watch",
            source_config_id=sample_watch_config.id,
            status="success",
            started_at=started,
        )
        job2 = job_repo.create(
            source_type="watch",
            source_config_id=sample_watch_config.id,
            status="failed",
            started_at=started,
        )
        # Job for different config
        other_config_id = uuid.uuid4()
        job_repo.create(
            source_type="watch",
            source_config_id=other_config_id,
            status="success",
            started_at=started,
        )

        config_jobs = job_repo.get_by_watch_config(sample_watch_config.id)

        assert len(config_jobs) >= 2
        job_ids = [j.id for j in config_jobs]
        assert job1.id in job_ids
        assert job2.id in job_ids
        assert all(
            j.source_config_id == sample_watch_config.id for j in config_jobs
        )

    def test_get_by_conversation(
        self, job_repo: IngestionJobRepository, sample_conversation: Conversation
    ):
        """Test retrieving jobs for a specific conversation."""
        started = datetime.now(UTC)
        job1 = job_repo.create(
            source_type="watch",
            conversation_id=sample_conversation.id,
            status="success",
            started_at=started,
        )
        job2 = job_repo.create(
            source_type="upload",
            conversation_id=sample_conversation.id,
            status="success",
            started_at=started - timedelta(hours=1),
        )
        # Job for different conversation
        other_conv_id = uuid.uuid4()
        job_repo.create(
            source_type="cli",
            conversation_id=other_conv_id,
            status="success",
            started_at=started,
        )

        conv_jobs = job_repo.get_by_conversation(sample_conversation.id)

        assert len(conv_jobs) == 2
        job_ids = [j.id for j in conv_jobs]
        assert job1.id in job_ids
        assert job2.id in job_ids
        # Should be ordered by most recent first
        assert conv_jobs[0].id == job1.id
        assert conv_jobs[1].id == job2.id

    def test_get_by_date_range(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs within a date range."""
        base_time = datetime.now(UTC)
        # Jobs at different times
        job1 = job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(days=5),
        )
        job2 = job_repo.create(
            source_type="upload",
            status="success",
            started_at=base_time - timedelta(days=3),
        )
        job3 = job_repo.create(
            source_type="cli",
            status="success",
            started_at=base_time - timedelta(days=1),
        )
        job4 = job_repo.create(
            source_type="watch", status="success", started_at=base_time
        )

        # Get jobs from 4 days ago to 2 days ago
        start_date = base_time - timedelta(days=4)
        end_date = base_time - timedelta(days=2)
        jobs = job_repo.get_by_date_range(start_date=start_date, end_date=end_date)

        assert len(jobs) == 1
        assert jobs[0].id == job2.id

    def test_get_by_date_range_start_only(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs with only start date."""
        base_time = datetime.now(UTC)
        job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(days=5),
        )
        job2 = job_repo.create(
            source_type="upload",
            status="success",
            started_at=base_time - timedelta(days=2),
        )
        job3 = job_repo.create(
            source_type="cli", status="success", started_at=base_time
        )

        start_date = base_time - timedelta(days=3)
        jobs = job_repo.get_by_date_range(start_date=start_date)

        assert len(jobs) == 2
        job_ids = [j.id for j in jobs]
        assert job2.id in job_ids
        assert job3.id in job_ids

    def test_get_by_date_range_end_only(self, job_repo: IngestionJobRepository):
        """Test retrieving jobs with only end date."""
        base_time = datetime.now(UTC)
        job1 = job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(days=5),
        )
        job2 = job_repo.create(
            source_type="upload",
            status="success",
            started_at=base_time - timedelta(days=2),
        )
        job_repo.create(source_type="cli", status="success", started_at=base_time)

        end_date = base_time - timedelta(days=3)
        jobs = job_repo.get_by_date_range(end_date=end_date)

        assert len(jobs) == 1
        assert jobs[0].id == job1.id

    def test_get_failed_jobs(self, job_repo: IngestionJobRepository):
        """Test retrieving failed jobs."""
        started = datetime.now(UTC)
        job_repo.create(source_type="watch", status="success", started_at=started)
        failed1 = job_repo.create(
            source_type="upload",
            status="failed",
            error_message="Parse error",
            started_at=started,
        )
        failed2 = job_repo.create(
            source_type="cli",
            status="failed",
            error_message="File not found",
            started_at=started,
        )
        job_repo.create(source_type="watch", status="duplicate", started_at=started)

        failed_jobs = job_repo.get_failed_jobs()

        assert len(failed_jobs) == 2
        job_ids = [j.id for j in failed_jobs]
        assert failed1.id in job_ids
        assert failed2.id in job_ids
        assert all(j.status == "failed" for j in failed_jobs)

    def test_count_by_status(self, job_repo: IngestionJobRepository):
        """Test counting jobs by status."""
        started = datetime.now(UTC)
        job_repo.create(source_type="watch", status="success", started_at=started)
        job_repo.create(source_type="upload", status="success", started_at=started)
        job_repo.create(source_type="cli", status="success", started_at=started)
        job_repo.create(source_type="watch", status="failed", started_at=started)
        job_repo.create(source_type="upload", status="failed", started_at=started)
        job_repo.create(source_type="cli", status="duplicate", started_at=started)

        counts = job_repo.count_by_status()

        assert counts["success"] == 3
        assert counts["failed"] == 2
        assert counts["duplicate"] == 1

    def test_count_by_source_type(self, job_repo: IngestionJobRepository):
        """Test counting jobs by source type."""
        started = datetime.now(UTC)
        job_repo.create(source_type="watch", status="success", started_at=started)
        job_repo.create(source_type="watch", status="failed", started_at=started)
        job_repo.create(source_type="watch", status="success", started_at=started)
        job_repo.create(source_type="upload", status="success", started_at=started)
        job_repo.create(source_type="upload", status="success", started_at=started)
        job_repo.create(source_type="cli", status="success", started_at=started)

        counts = job_repo.count_by_source_type()

        assert counts["watch"] == 3
        assert counts["upload"] == 2
        assert counts["cli"] == 1

    def test_get_stats(self, job_repo: IngestionJobRepository):
        """Test retrieving overall statistics."""
        started = datetime.now(UTC)
        # Create jobs with various properties
        job_repo.create(
            source_type="watch",
            status="success",
            started_at=started,
            processing_time_ms=1000,
            incremental=True,
        )
        job_repo.create(
            source_type="upload",
            status="success",
            started_at=started,
            processing_time_ms=2000,
            incremental=False,
        )
        job_repo.create(
            source_type="cli",
            status="failed",
            started_at=started,
            processing_time_ms=500,
            incremental=True,
        )
        job_repo.create(
            source_type="watch",
            status="duplicate",
            started_at=started,
            incremental=False,
        )

        stats = job_repo.get_stats()

        assert stats["total_jobs"] == 4
        assert stats["by_status"]["success"] == 2
        assert stats["by_status"]["failed"] == 1
        assert stats["by_status"]["duplicate"] == 1
        assert stats["by_source_type"]["watch"] == 2
        assert stats["by_source_type"]["upload"] == 1
        assert stats["by_source_type"]["cli"] == 1
        # Average of 1000, 2000, 500 = 1166.67
        assert stats["avg_processing_time_ms"] is not None
        assert 1100 < stats["avg_processing_time_ms"] < 1200
        assert stats["incremental_jobs"] == 2
        assert stats["incremental_percentage"] == 50.0

    def test_get_stats_empty(self, job_repo: IngestionJobRepository):
        """Test getting stats when no jobs exist."""
        stats = job_repo.get_stats()

        assert stats["total_jobs"] == 0
        assert stats["by_status"] == {}
        assert stats["by_source_type"] == {}
        assert stats["avg_processing_time_ms"] is None
        assert stats["incremental_jobs"] == 0
        assert stats["incremental_percentage"] == 0

    def test_search_no_filters(self, job_repo: IngestionJobRepository):
        """Test search with no filters returns recent jobs."""
        started = datetime.now(UTC)
        job1 = job_repo.create(source_type="watch", status="success", started_at=started)
        job2 = job_repo.create(source_type="upload", status="failed", started_at=started)

        results = job_repo.search()

        assert len(results) >= 2
        job_ids = [j.id for j in results]
        assert job1.id in job_ids
        assert job2.id in job_ids

    def test_search_by_source_type(self, job_repo: IngestionJobRepository):
        """Test search filtering by source type."""
        started = datetime.now(UTC)
        watch1 = job_repo.create(
            source_type="watch", status="success", started_at=started
        )
        watch2 = job_repo.create(
            source_type="watch", status="failed", started_at=started
        )
        job_repo.create(source_type="upload", status="success", started_at=started)

        results = job_repo.search(source_type="watch")

        assert len(results) == 2
        job_ids = [j.id for j in results]
        assert watch1.id in job_ids
        assert watch2.id in job_ids

    def test_search_by_status(self, job_repo: IngestionJobRepository):
        """Test search filtering by status."""
        started = datetime.now(UTC)
        success1 = job_repo.create(
            source_type="watch", status="success", started_at=started
        )
        success2 = job_repo.create(
            source_type="upload", status="success", started_at=started
        )
        job_repo.create(source_type="cli", status="failed", started_at=started)

        results = job_repo.search(status="success")

        assert len(results) == 2
        job_ids = [j.id for j in results]
        assert success1.id in job_ids
        assert success2.id in job_ids

    def test_search_multiple_filters(self, job_repo: IngestionJobRepository):
        """Test search with multiple filters."""
        base_time = datetime.now(UTC)
        # Target job: watch + success + in date range
        target = job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(days=2),
        )
        # Wrong source type
        job_repo.create(
            source_type="upload",
            status="success",
            started_at=base_time - timedelta(days=2),
        )
        # Wrong status
        job_repo.create(
            source_type="watch",
            status="failed",
            started_at=base_time - timedelta(days=2),
        )
        # Wrong date
        job_repo.create(
            source_type="watch",
            status="success",
            started_at=base_time - timedelta(days=10),
        )

        start_date = base_time - timedelta(days=3)
        end_date = base_time - timedelta(days=1)
        results = job_repo.search(
            source_type="watch",
            status="success",
            start_date=start_date,
            end_date=end_date,
        )

        assert len(results) == 1
        assert results[0].id == target.id

    def test_search_with_pagination(self, job_repo: IngestionJobRepository):
        """Test search with limit and offset."""
        started = datetime.now(UTC)
        for i in range(10):
            job_repo.create(
                source_type="watch",
                status="success",
                started_at=started - timedelta(minutes=i),
            )

        # First page
        page1 = job_repo.search(source_type="watch", limit=3, offset=0)
        assert len(page1) == 3

        # Second page
        page2 = job_repo.search(source_type="watch", limit=3, offset=3)
        assert len(page2) == 3

        # No overlap
        page1_ids = {j.id for j in page1}
        page2_ids = {j.id for j in page2}
        assert len(page1_ids & page2_ids) == 0


class TestIngestionJobRelationships:
    """Test relationships with other models."""

    def test_watch_config_relationship(
        self,
        job_repo: IngestionJobRepository,
        sample_watch_config: WatchConfiguration,
    ):
        """Test that watch_config relationship is properly loaded."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="watch",
            source_config_id=sample_watch_config.id,
            status="success",
            started_at=started,
        )

        assert job.watch_config is not None
        assert job.watch_config.id == sample_watch_config.id
        assert job.watch_config.directory == sample_watch_config.directory

    def test_conversation_relationship(
        self,
        job_repo: IngestionJobRepository,
        sample_conversation: Conversation,
    ):
        """Test that conversation relationship is properly loaded."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="upload",
            conversation_id=sample_conversation.id,
            status="success",
            started_at=started,
        )

        assert job.conversation is not None
        assert job.conversation.id == sample_conversation.id

    def test_optional_relationships(self, job_repo: IngestionJobRepository):
        """Test that relationships are optional."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="cli",
            status="success",
            started_at=started,
        )

        assert job.source_config_id is None
        assert job.conversation_id is None
        assert job.raw_log_id is None
        assert job.watch_config is None
        assert job.conversation is None


class TestIngestionJobEdgeCases:
    """Test edge cases and error conditions."""

    def test_job_with_error_message(self, job_repo: IngestionJobRepository):
        """Test creating a failed job with error message."""
        started = datetime.now(UTC)
        job = job_repo.create(
            source_type="upload",
            status="failed",
            error_message="File format not recognized",
            started_at=started,
        )

        assert job.status == "failed"
        assert job.error_message == "File format not recognized"

    def test_job_lifecycle(self, job_repo: IngestionJobRepository):
        """Test a job going through its full lifecycle."""
        started = datetime.now(UTC)
        # Create in processing state
        job = job_repo.create(
            source_type="watch",
            status="processing",
            started_at=started,
            messages_added=0,
        )

        assert job.status == "processing"
        assert job.completed_at is None
        assert job.processing_time_ms is None

        # Update to success
        completed = datetime.now(UTC)
        job_repo.update(
            job.id,
            status="success",
            completed_at=completed,
            processing_time_ms=1500,
            messages_added=25,
        )

        updated = job_repo.get(job.id)
        assert updated.status == "success"
        # SQLite doesn't preserve timezone info, so compare timestamp values
        assert updated.completed_at.replace(tzinfo=None) == completed.replace(
            tzinfo=None
        )
        assert updated.processing_time_ms == 1500
        assert updated.messages_added == 25

    def test_incremental_vs_full_parse(self, job_repo: IngestionJobRepository):
        """Test tracking incremental vs full parse jobs."""
        started = datetime.now(UTC)
        incremental = job_repo.create(
            source_type="watch",
            status="success",
            started_at=started,
            incremental=True,
            processing_time_ms=100,
        )
        full = job_repo.create(
            source_type="watch",
            status="success",
            started_at=started,
            incremental=False,
            processing_time_ms=1000,
        )

        assert incremental.incremental is True
        assert full.incremental is False

        stats = job_repo.get_stats()
        assert stats["incremental_jobs"] == 1
        assert stats["incremental_percentage"] == 50.0
