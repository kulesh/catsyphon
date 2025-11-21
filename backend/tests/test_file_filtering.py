"""Tests for file filtering functionality.

Tests the pre-filter that skips metadata-only files during ingestion.
"""

import json
import tempfile
from pathlib import Path

import pytest

from catsyphon.parsers.utils import is_conversational_log


class TestIsConversationalLog:
    """Tests for is_conversational_log() helper function."""

    def test_conversational_log_detected(self, tmp_path: Path) -> None:
        """Test that files with sessionId + version are detected as conversational."""
        log_file = tmp_path / "conversation.jsonl"
        with log_file.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "test-session-001",
                        "version": "2.0.17",
                        "type": "user",
                        "message": {"role": "user", "content": "Hello"},
                    }
                )
                + "\n"
            )

        assert is_conversational_log(log_file) is True

    def test_metadata_only_file_rejected(self, tmp_path: Path) -> None:
        """Test that files with only summary/snapshot are rejected."""
        log_file = tmp_path / "metadata.jsonl"
        with log_file.open("w") as f:
            f.write(json.dumps({"type": "summary", "summary": "Test"}) + "\n")
            f.write(
                json.dumps({"type": "file-history-snapshot", "snapshot": {}}) + "\n"
            )

        assert is_conversational_log(log_file) is False

    def test_empty_file_rejected(self, tmp_path: Path) -> None:
        """Test that empty files are rejected."""
        log_file = tmp_path / "empty.jsonl"
        log_file.touch()

        assert is_conversational_log(log_file) is False

    def test_malformed_json_rejected(self, tmp_path: Path) -> None:
        """Test that malformed JSON is rejected."""
        log_file = tmp_path / "malformed.jsonl"
        with log_file.open("w") as f:
            f.write("not json\n")
            f.write("{incomplete\n")

        assert is_conversational_log(log_file) is False

    def test_partial_markers_rejected(self, tmp_path: Path) -> None:
        """Test that files with only sessionId OR version are rejected."""
        # Only sessionId
        log_file = tmp_path / "partial1.jsonl"
        with log_file.open("w") as f:
            f.write(json.dumps({"sessionId": "test", "type": "user"}) + "\n")

        assert is_conversational_log(log_file) is False

        # Only version
        log_file2 = tmp_path / "partial2.jsonl"
        with log_file2.open("w") as f:
            f.write(json.dumps({"version": "2.0.17", "type": "user"}) + "\n")

        assert is_conversational_log(log_file2) is False

    def test_markers_beyond_first_n_lines(self, tmp_path: Path) -> None:
        """Test that markers beyond max_lines (default 5) are not detected."""
        log_file = tmp_path / "late_markers.jsonl"
        with log_file.open("w") as f:
            # Write 10 lines without markers
            for i in range(10):
                f.write(json.dumps({"type": "summary", "summary": f"Line {i}"}) + "\n")
            # Then add markers on line 11
            f.write(
                json.dumps(
                    {"sessionId": "test", "version": "2.0.17", "type": "user"}
                )
                + "\n"
            )

        # Should not detect markers (beyond first 5 lines)
        assert is_conversational_log(log_file, max_lines=5) is False

        # But should detect with larger max_lines
        assert is_conversational_log(log_file, max_lines=15) is True

    def test_markers_in_first_line(self, tmp_path: Path) -> None:
        """Test that markers in the very first line are detected."""
        log_file = tmp_path / "first_line.jsonl"
        with log_file.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "test-001",
                        "version": "2.0.17",
                        "type": "user",
                        "message": {"role": "user", "content": "Test"},
                    }
                )
                + "\n"
            )
            # Add more lines without markers
            for i in range(10):
                f.write(json.dumps({"type": "message", "content": f"Msg {i}"}) + "\n")

        assert is_conversational_log(log_file) is True

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped when scanning."""
        log_file = tmp_path / "with_empty_lines.jsonl"
        with log_file.open("w") as f:
            f.write("\n")  # Empty line
            f.write("   \n")  # Whitespace only
            f.write(
                json.dumps(
                    {"sessionId": "test", "version": "2.0.17", "type": "user"}
                )
                + "\n"
            )

        assert is_conversational_log(log_file) is True

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that nonexistent files return False."""
        log_file = tmp_path / "nonexistent.jsonl"
        assert is_conversational_log(log_file) is False

    def test_unicode_decode_error(self, tmp_path: Path) -> None:
        """Test that files with encoding issues return False."""
        log_file = tmp_path / "binary.jsonl"
        with log_file.open("wb") as f:
            f.write(b"\xff\xfe invalid utf-8")

        assert is_conversational_log(log_file) is False

    def test_mixed_content_conversational_wins(self, tmp_path: Path) -> None:
        """Test that files with both conversational and metadata are detected."""
        log_file = tmp_path / "mixed.jsonl"
        with log_file.open("w") as f:
            # Start with summary
            f.write(json.dumps({"type": "summary", "summary": "Overview"}) + "\n")
            # Then add conversational markers
            f.write(
                json.dumps(
                    {"sessionId": "test", "version": "2.0.17", "type": "user"}
                )
                + "\n"
            )
            # More metadata
            f.write(
                json.dumps({"type": "file-history-snapshot", "snapshot": {}}) + "\n"
            )

        # Should be detected as conversational (markers present)
        assert is_conversational_log(log_file) is True

    def test_custom_max_lines(self, tmp_path: Path) -> None:
        """Test that max_lines parameter works correctly."""
        log_file = tmp_path / "custom_max.jsonl"
        with log_file.open("w") as f:
            # Write 3 lines without markers
            for i in range(3):
                f.write(json.dumps({"type": "summary", "summary": f"Line {i}"}) + "\n")
            # Add markers on line 4
            f.write(
                json.dumps(
                    {"sessionId": "test", "version": "2.0.17", "type": "user"}
                )
                + "\n"
            )

        # Should not detect with max_lines=3
        assert is_conversational_log(log_file, max_lines=3) is False

        # Should detect with max_lines=4
        assert is_conversational_log(log_file, max_lines=4) is True

        # Should detect with max_lines=10
        assert is_conversational_log(log_file, max_lines=10) is True


class TestSkipTracking:
    """Tests for skip tracking in ingestion pipeline."""

    def test_track_skip_creates_ingestion_job(self, tmp_path: Path) -> None:
        """Test that track_skip creates an ingestion_job record."""
        from catsyphon.db.connection import db_session
        from catsyphon.db.repositories import IngestionJobRepository
        from catsyphon.pipeline.failure_tracking import track_skip

        log_file = tmp_path / "skipped.jsonl"
        log_file.touch()

        # Track skip
        track_skip(
            file_path=log_file,
            source_type="cli",
            reason="Test skip reason",
        )

        # Verify ingestion_job was created (query in new session)
        with db_session() as session:
            repo = IngestionJobRepository(session)
            # Query for jobs with this specific file path
            all_jobs = repo.get_recent(limit=1000)
            jobs = [j for j in all_jobs if str(log_file) in (j.file_path or "")]

            assert len(jobs) == 1, f"Expected 1 job with file_path containing {log_file}, found {len(jobs)}"
            assert jobs[0].status == "skipped"
            assert jobs[0].error_message == "Test skip reason"
            assert str(log_file) in jobs[0].file_path
            assert jobs[0].source_type == "cli"
            assert jobs[0].messages_added == 0
            assert jobs[0].incremental is False

    def test_track_skip_with_source_config(self, tmp_path: Path) -> None:
        """Test that track_skip stores source_config_id for watch source."""
        import uuid

        from catsyphon.db.connection import db_session
        from catsyphon.db.repositories import IngestionJobRepository
        from catsyphon.pipeline.failure_tracking import track_skip

        log_file = tmp_path / "skipped.jsonl"
        log_file.touch()

        config_id = uuid.uuid4()

        # Track skip
        track_skip(
            file_path=log_file,
            source_type="watch",
            reason="Metadata-only file",
            source_config_id=config_id,
        )

        # Verify source_config_id was stored
        with db_session() as session:
            repo = IngestionJobRepository(session)
            # Query for jobs with this specific file path
            all_jobs = repo.get_recent(limit=1000)
            jobs = [j for j in all_jobs if str(log_file) in (j.file_path or "")]

            assert len(jobs) == 1, f"Expected 1 job with file_path containing {log_file}, found {len(jobs)}"
            assert jobs[0].source_config_id == config_id

    def test_track_skip_with_created_by(self, tmp_path: Path) -> None:
        """Test that track_skip stores created_by for uploads."""
        from catsyphon.db.connection import db_session
        from catsyphon.db.repositories import IngestionJobRepository
        from catsyphon.pipeline.failure_tracking import track_skip

        log_file = tmp_path / "skipped.jsonl"
        log_file.touch()

        # Track skip
        track_skip(
            file_path=log_file,
            source_type="upload",
            reason="Metadata-only file",
            created_by="testuser",
        )

        # Verify created_by was stored
        with db_session() as session:
            repo = IngestionJobRepository(session)
            # Query for jobs with this specific file path
            all_jobs = repo.get_recent(limit=1000)
            jobs = [j for j in all_jobs if str(log_file) in (j.file_path or "")]

            assert len(jobs) == 1, f"Expected 1 job with file_path containing {log_file}, found {len(jobs)}"
            assert jobs[0].created_by == "testuser"


@pytest.fixture
def metadata_only_file(tmp_path: Path) -> Path:
    """Create a metadata-only file for testing."""
    file_path = tmp_path / "metadata-only.jsonl"
    with file_path.open("w") as f:
        f.write(json.dumps({"type": "summary", "summary": "Test summary"}) + "\n")
        f.write(
            json.dumps(
                {"type": "file-history-snapshot", "messageId": "msg-1", "snapshot": {}}
            )
            + "\n"
        )
    return file_path


@pytest.fixture
def conversational_file(tmp_path: Path) -> Path:
    """Create a valid conversational log file for testing."""
    file_path = tmp_path / "conversation.jsonl"
    with file_path.open("w") as f:
        f.write(
            json.dumps(
                {
                    "sessionId": "test-session-001",
                    "version": "2.0.17",
                    "type": "user",
                    "uuid": "msg-001",
                    "parentUuid": "00000000-0000-0000-0000-000000000000",
                    "timestamp": "2025-01-01T00:00:00.000Z",
                    "message": {"role": "user", "content": "Hello"},
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {
                    "sessionId": "test-session-001",
                    "version": "2.0.17",
                    "type": "assistant",
                    "uuid": "msg-002",
                    "parentUuid": "msg-001",
                    "timestamp": "2025-01-01T00:00:01.000Z",
                    "message": {"role": "assistant", "content": "Hi there!"},
                }
            )
            + "\n"
        )
    return file_path
