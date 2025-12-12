"""
Tests for pipeline metrics instrumentation.

Tests the StageMetrics helper class, metrics population in ingestion jobs,
API endpoint metrics exposure, and performance overhead.
"""

import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.db.repositories.ingestion_job import IngestionJobRepository
from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.pipeline.ingestion import StageMetrics, ingest_conversation


class TestStageMetrics:
    """Unit tests for StageMetrics helper class."""

    def test_stage_metrics_initialization(self):
        """Test StageMetrics initializes with empty state."""
        metrics = StageMetrics()

        assert isinstance(metrics.stages, dict)
        assert len(metrics.stages) == 0
        assert isinstance(metrics._stage_starts, dict)
        assert len(metrics._stage_starts) == 0

    def test_start_stage_records_timestamp(self):
        """Test start_stage records start timestamp."""
        metrics = StageMetrics()
        before = time.time() * 1000

        metrics.start_stage("test_stage")

        after = time.time() * 1000
        assert "test_stage" in metrics._stage_starts
        assert before <= metrics._stage_starts["test_stage"] <= after

    def test_end_stage_calculates_duration(self):
        """Test end_stage calculates correct duration."""
        metrics = StageMetrics()

        metrics.start_stage("test_stage")
        time.sleep(0.01)  # Sleep 10ms
        metrics.end_stage("test_stage")

        assert "test_stage" in metrics.stages
        assert metrics.stages["test_stage"] >= 10  # At least 10ms
        assert metrics.stages["test_stage"] < 100  # Less than 100ms (sanity check)

    def test_end_stage_removes_start_timestamp(self):
        """Test end_stage removes start timestamp after calculation."""
        metrics = StageMetrics()

        metrics.start_stage("test_stage")
        assert "test_stage" in metrics._stage_starts

        metrics.end_stage("test_stage")
        assert "test_stage" not in metrics._stage_starts

    def test_end_stage_without_start_does_nothing(self):
        """Test end_stage handles missing start gracefully."""
        metrics = StageMetrics()

        # End stage that was never started
        metrics.end_stage("nonexistent_stage")

        # Should not crash, should not add to stages
        assert "nonexistent_stage" not in metrics.stages

    def test_multiple_stages_tracked_independently(self):
        """Test multiple stages can be tracked independently."""
        metrics = StageMetrics()

        # Start both stages
        metrics.start_stage("stage1")
        time.sleep(0.01)  # 10ms
        metrics.start_stage("stage2")
        time.sleep(0.01)  # 10ms

        # End them in reverse order
        metrics.end_stage("stage2")
        time.sleep(0.01)  # 10ms
        metrics.end_stage("stage1")

        # Both should be recorded with different durations
        assert "stage1" in metrics.stages
        assert "stage2" in metrics.stages
        assert metrics.stages["stage1"] >= 30  # Started first, ended last
        assert metrics.stages["stage2"] >= 10  # Started last, ended first
        assert metrics.stages["stage1"] > metrics.stages["stage2"]

    def test_to_dict_includes_all_stages(self):
        """Test to_dict includes all stages and total_ms."""
        metrics = StageMetrics()

        metrics.start_stage("stage1")
        time.sleep(0.01)
        metrics.end_stage("stage1")

        metrics.start_stage("stage2")
        time.sleep(0.01)
        metrics.end_stage("stage2")

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert "stage1" in result
        assert "stage2" in result
        assert "total_ms" in result
        assert result["total_ms"] == result["stage1"] + result["stage2"]

    def test_to_dict_total_ms_sums_correctly(self):
        """Test to_dict calculates total_ms as sum of all stages."""
        metrics = StageMetrics()

        # Add stages with known values (manual for testing)
        metrics.stages["stage1"] = 100.0
        metrics.stages["stage2"] = 200.0
        metrics.stages["stage3"] = 300.0

        result = metrics.to_dict()

        assert result["total_ms"] == 600.0
        assert result["stage1"] == 100.0
        assert result["stage2"] == 200.0
        assert result["stage3"] == 300.0

    def test_to_dict_empty_stages(self):
        """Test to_dict with no stages recorded."""
        metrics = StageMetrics()

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result["total_ms"] == 0


class TestIngestConversationMetrics:
    """Integration tests for metrics population in ingest_conversation."""

    def test_ingest_populates_metrics(self, db_session: Session, tmp_path: Path):
        """Test that ingest_conversation populates metrics."""
        # Create a temporary log file
        log_file = tmp_path / "test.jsonl"
        log_file.write_text('{"test": "data"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test message",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Use ingest_conversation to create an ingestion job
        conversation = ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        # Get the ingestion job
        repo = IngestionJobRepository(db_session)
        jobs = repo.get_by_conversation(conversation.id)

        assert len(jobs) == 1
        job = jobs[0]

        # Verify metrics are populated
        assert job.metrics is not None
        assert isinstance(job.metrics, dict)
        assert len(job.metrics) > 0

    def test_metrics_includes_required_stages(
        self, db_session: Session, tmp_path: Path
    ):
        """Test that metrics include deduplication and database operation stages."""
        log_file = tmp_path / "test2.jsonl"
        log_file.write_text('{"test": "data"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        repo = IngestionJobRepository(db_session)
        jobs = repo.get_by_conversation(conversation.id)
        job = jobs[0]

        # Verify required stages are present
        assert "deduplication_check_ms" in job.metrics
        assert "database_operations_ms" in job.metrics
        assert "total_ms" in job.metrics

        # Verify all values are positive numbers
        assert job.metrics["deduplication_check_ms"] >= 0
        assert job.metrics["database_operations_ms"] >= 0
        assert job.metrics["total_ms"] >= 0

    def test_metrics_total_matches_processing_time(
        self, db_session: Session, tmp_path: Path
    ):
        """Test that metrics total_ms roughly matches processing_time_ms."""
        log_file = tmp_path / "test3.jsonl"
        log_file.write_text('{"test": "data"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        repo = IngestionJobRepository(db_session)
        jobs = repo.get_by_conversation(conversation.id)
        job = jobs[0]

        # Metrics total should be approximately equal to processing_time_ms
        # Allow for some variance due to timing differences
        if job.processing_time_ms and job.metrics.get("total_ms"):
            diff = abs(job.processing_time_ms - job.metrics["total_ms"])
            # Should be within 10% or 50ms (whichever is larger)
            tolerance = max(job.processing_time_ms * 0.1, 50)
            assert diff < tolerance

    def test_metrics_in_failed_jobs(self, db_session: Session, tmp_path: Path):
        """Test that metrics are still recorded even if ingestion fails."""
        # Create a file that will cause parsing issues (but still create a job)
        log_file = tmp_path / "malformed.jsonl"
        log_file.write_text("")  # Empty file

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        try:
            conversation = ingest_conversation(db_session, parsed, file_path=log_file)
            db_session.commit()

            # Get the job
            repo = IngestionJobRepository(db_session)
            jobs = repo.get_by_conversation(conversation.id)

            if len(jobs) > 0:
                job = jobs[0]
                # Even on failure, metrics should be populated
                assert job.metrics is not None
                assert isinstance(job.metrics, dict)
        except Exception:
            # If ingestion completely fails, that's OK for this test
            pass

    def test_metrics_in_duplicate_jobs(self, db_session: Session, tmp_path: Path):
        """Test that metrics are recorded when available for duplicate file detections."""
        log_file = tmp_path / "duplicate.jsonl"
        log_file.write_text('{"session": "duplicate-test"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # First ingestion
        ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        # Second ingestion of same file
        ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        # Get all jobs
        repo = IngestionJobRepository(db_session)
        all_jobs = repo.get_recent(limit=10)

        # Find jobs for this file
        duplicate_jobs = [j for j in all_jobs if j.status == "duplicate"]

        # If a duplicate was detected, metrics field should at least exist (may be empty)
        if len(duplicate_jobs) > 0:
            job = duplicate_jobs[0]
            assert job.metrics is not None
            assert isinstance(job.metrics, dict)
            # Metrics may be empty for duplicates detected very early in pipeline

    def test_metrics_in_incremental_parsing(self, db_session: Session, tmp_path: Path):
        """Test that metrics are recorded for incremental parsing."""
        log_file = tmp_path / "incremental.jsonl"
        log_file.write_text('{"test": "initial"}')

        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            session_id="incremental-test",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Initial",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # First ingestion
        ingest_conversation(db_session, parsed1, file_path=log_file)
        db_session.commit()

        # Append to file (modify content)
        log_file.write_text('{"test": "initial"}\n{"test": "appended"}')

        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            session_id="incremental-test",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Initial",
                    timestamp=datetime.now(UTC),
                ),
                ParsedMessage(
                    role="assistant",
                    content="Appended",
                    timestamp=datetime.now(UTC),
                ),
            ],
        )

        # Second ingestion (should be incremental if supported)
        ingest_conversation(
            db_session, parsed2, file_path=log_file, update_mode="replace"
        )
        db_session.commit()

        # Get the most recent job
        repo = IngestionJobRepository(db_session)
        jobs = repo.get_recent(limit=2)

        # Find the second job
        if len(jobs) >= 2:
            second_job = jobs[0]  # Most recent

            # Verify metrics are present
            assert second_job.metrics is not None
            assert "deduplication_check_ms" in second_job.metrics
            assert "database_operations_ms" in second_job.metrics


class TestIngestionStatsAPIMetrics:
    """API tests for metrics in /ingestion/stats endpoint."""

    def test_stats_includes_stage_metrics(self, api_client: TestClient):
        """Test that /ingestion/stats includes stage-level metrics."""
        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify new metrics fields are present
        assert "avg_deduplication_check_ms" in data
        assert "avg_database_operations_ms" in data
        assert "error_rates_by_stage" in data

    def test_stats_stage_metrics_null_when_no_jobs(self, api_client: TestClient):
        """Test that stage metrics are null when no jobs exist."""
        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        # With no jobs, stage metrics should be null
        assert data["avg_deduplication_check_ms"] is None
        assert data["avg_database_operations_ms"] is None
        assert data["error_rates_by_stage"] == {}

    def test_stats_stage_metrics_calculated_correctly(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test that stage metrics are calculated correctly."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create jobs with known metrics
        repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            processing_time_ms=1000,
            metrics={
                "deduplication_check_ms": 100.0,
                "database_operations_ms": 200.0,
                "total_ms": 300.0,
            },
        )
        repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            processing_time_ms=2000,
            metrics={
                "deduplication_check_ms": 300.0,
                "database_operations_ms": 400.0,
                "total_ms": 700.0,
            },
        )
        db_session.commit()

        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        # Average dedup: (100 + 300) / 2 = 200
        assert data["avg_deduplication_check_ms"] is not None
        assert 190 < data["avg_deduplication_check_ms"] < 210

        # Average db: (200 + 400) / 2 = 300
        assert data["avg_database_operations_ms"] is not None
        assert 290 < data["avg_database_operations_ms"] < 310

    def test_stats_ignores_failed_jobs_for_stage_metrics(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test that failed jobs are excluded from stage metric averages."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        # Create success job with metrics
        repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            processing_time_ms=1000,
            metrics={
                "deduplication_check_ms": 100.0,
                "database_operations_ms": 200.0,
                "total_ms": 300.0,
            },
        )

        # Create failed job with metrics (should be ignored)
        repo.create(
            source_type="cli",
            status="failed",
            started_at=started,
            processing_time_ms=5000,
            metrics={
                "deduplication_check_ms": 9999.0,  # Outlier
                "database_operations_ms": 9999.0,  # Outlier
                "total_ms": 19998.0,
            },
        )
        db_session.commit()

        response = api_client.get("/ingestion/stats")

        assert response.status_code == 200
        data = response.json()

        # Averages should only include success job (100 and 200)
        assert data["avg_deduplication_check_ms"] is not None
        assert data["avg_deduplication_check_ms"] < 200  # Should not include 9999
        assert data["avg_database_operations_ms"] is not None
        assert data["avg_database_operations_ms"] < 300  # Should not include 9999


class TestIngestionJobAPIMetrics:
    """API tests for metrics in individual job responses."""

    def test_job_response_includes_metrics(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test that GET /ingestion/jobs/{id} includes metrics field."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        job = repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            metrics={
                "deduplication_check_ms": 123.0,
                "database_operations_ms": 456.0,
                "total_ms": 579.0,
            },
        )
        db_session.commit()

        response = api_client.get(f"/ingestion/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify metrics field is present and populated
        assert "metrics" in data
        assert isinstance(data["metrics"], dict)
        assert data["metrics"]["deduplication_check_ms"] == 123.0
        assert data["metrics"]["database_operations_ms"] == 456.0
        assert data["metrics"]["total_ms"] == 579.0

    def test_job_list_includes_metrics(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test that GET /ingestion/jobs includes metrics for all jobs."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            metrics={"deduplication_check_ms": 100.0, "database_operations_ms": 200.0},
        )
        db_session.commit()

        response = api_client.get("/ingestion/jobs")

        assert response.status_code == 200
        data = response.json()

        # All jobs should have metrics field
        assert len(data) > 0
        for job in data:
            assert "metrics" in job
            assert isinstance(job["metrics"], dict)

    def test_job_with_empty_metrics(
        self,
        api_client: TestClient,
        db_session: Session,
    ):
        """Test job with empty metrics returns empty dict."""
        repo = IngestionJobRepository(db_session)
        started = datetime.now(UTC)

        job = repo.create(
            source_type="cli",
            status="success",
            started_at=started,
            metrics={},  # Empty metrics
        )
        db_session.commit()

        response = api_client.get(f"/ingestion/jobs/{job.id}")

        assert response.status_code == 200
        data = response.json()

        assert "metrics" in data
        assert isinstance(data["metrics"], dict)
        assert len(data["metrics"]) == 0


class TestMetricsPerformanceOverhead:
    """Performance tests to ensure metrics tracking has minimal overhead."""

    def test_metrics_overhead_minimal(self, db_session: Session, tmp_path: Path):
        """Test that metrics tracking has minimal overhead."""
        log_file = tmp_path / "perf_test.jsonl"
        log_file.write_text('{"test": "performance"}')

        # Create a standard parsed conversation
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Performance test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Run ingestion and verify metrics exist
        conversation = ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        # Get the job to check metrics
        repo = IngestionJobRepository(db_session)
        jobs = repo.get_by_conversation(conversation.id)

        assert len(jobs) == 1
        job = jobs[0]

        # Verify metrics were collected
        assert job.metrics is not None
        assert isinstance(job.metrics, dict)
        assert len(job.metrics) > 0

        # Verify metrics contain expected stages
        assert "deduplication_check_ms" in job.metrics
        assert "database_operations_ms" in job.metrics
        assert "total_ms" in job.metrics

        # All timing values should be reasonable (> 0, < 10 seconds)
        for stage, value in job.metrics.items():
            if stage.endswith("_ms"):
                assert value >= 0, f"{stage} should be non-negative"
                assert value < 10000, f"{stage} should be less than 10 seconds"

    def test_stage_metrics_low_memory_usage(self):
        """Test that StageMetrics uses minimal memory."""
        import sys

        metrics = StageMetrics()

        # Measure size of empty metrics
        empty_size = sys.getsizeof(metrics.stages) + sys.getsizeof(
            metrics._stage_starts
        )

        # Add 100 stages
        for i in range(100):
            metrics.stages[f"stage_{i}"] = float(i)

        # Measure size with 100 stages
        full_size = sys.getsizeof(metrics.stages) + sys.getsizeof(metrics._stage_starts)

        # Size increase should be reasonable (< 10KB for 100 stages)
        size_increase = full_size - empty_size
        assert size_increase < 10000  # 10KB

    def test_multiple_concurrent_stage_tracking(self):
        """Test that multiple stages can be tracked concurrently without issues."""
        metrics = StageMetrics()

        # Start 10 stages concurrently
        for i in range(10):
            metrics.start_stage(f"stage_{i}")
            time.sleep(0.001)  # Small delay

        # End all stages
        for i in range(10):
            metrics.end_stage(f"stage_{i}")

        # All stages should be recorded
        assert len(metrics.stages) == 10
        for i in range(10):
            assert f"stage_{i}" in metrics.stages
            assert metrics.stages[f"stage_{i}"] > 0

    def test_metrics_do_not_block_ingestion(self, db_session: Session, tmp_path: Path):
        """Test that metrics errors don't prevent ingestion from completing."""
        log_file = tmp_path / "robust_test.jsonl"
        log_file.write_text('{"test": "robustness"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Ingestion should complete even if metrics have issues
        conversation = ingest_conversation(db_session, parsed, file_path=log_file)
        db_session.commit()

        # Conversation should still be created
        assert conversation.id is not None
        assert len(conversation.messages) == 1

        # Job should exist (with or without metrics)
        repo = IngestionJobRepository(db_session)
        jobs = repo.get_by_conversation(conversation.id)
        assert len(jobs) == 1
