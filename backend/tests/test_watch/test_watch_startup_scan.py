"""Tests for watch daemon startup scan functionality."""

import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from catsyphon.models.db import RawLog
from catsyphon.parsers.incremental import ChangeType
from catsyphon.watch import WatcherDaemon


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create a temporary directory for watching."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return watch_dir


@pytest.fixture
def mock_raw_logs(temp_watch_dir):
    """Create mock RawLog instances for testing."""
    file1 = temp_watch_dir / "file1.jsonl"
    file2 = temp_watch_dir / "file2.jsonl"
    file3 = temp_watch_dir / "file3.jsonl"

    # Create actual files
    file1.write_text("test content 1")
    file2.write_text("test content 2")
    file3.write_text("test content 3")

    return [
        RawLog(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            agent_type="claude-code",
            log_format="jsonl",
            file_path=str(file1),
            file_hash="hash1",
            last_processed_offset=14,
            file_size_bytes=14,
            partial_hash="partial_hash1",
            imported_at=datetime.now(),
        ),
        RawLog(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            agent_type="claude-code",
            log_format="jsonl",
            file_path=str(file2),
            file_hash="hash2",
            last_processed_offset=14,
            file_size_bytes=14,
            partial_hash="partial_hash2",
            imported_at=datetime.now(),
        ),
        RawLog(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            agent_type="claude-code",
            log_format="jsonl",
            file_path=str(file3),
            file_hash="hash3",
            last_processed_offset=14,
            file_size_bytes=14,
            partial_hash="partial_hash3",
            imported_at=datetime.now(),
        ),
    ]


class TestStartupScan:
    """Tests for _scan_existing_files() method."""

    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_no_tracked_files(
        self, mock_db_session, mock_repo_class, temp_watch_dir
    ):
        """Test scan when no files are tracked in database."""
        # Setup mock session
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        # Setup mock repository
        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = []
        mock_repo_class.return_value = mock_repo

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify
        mock_repo.get_files_in_directory.assert_called_once_with(str(temp_watch_dir))
        daemon.event_handler._process_file.assert_not_called()

    @patch("catsyphon.parsers.incremental.detect_file_change_type")
    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_unchanged_files(
        self,
        mock_db_session,
        mock_repo_class,
        mock_detect_change,
        temp_watch_dir,
        mock_raw_logs,
    ):
        """Test scan when all files are unchanged."""
        # Setup mock session
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        # Setup mock repository
        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = mock_raw_logs
        mock_repo_class.return_value = mock_repo

        mock_detect_change.return_value = ChangeType.UNCHANGED

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify
        assert mock_detect_change.call_count == 3
        daemon.event_handler._process_file.assert_not_called()

    @patch("catsyphon.parsers.incremental.detect_file_change_type")
    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_appended_files(
        self,
        mock_db_session,
        mock_repo_class,
        mock_detect_change,
        temp_watch_dir,
        mock_raw_logs,
    ):
        """Test scan when files have been appended."""
        # Setup mocks
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = [mock_raw_logs[0]]
        mock_repo_class.return_value = mock_repo

        mock_detect_change.return_value = ChangeType.APPEND

        # Append to file to simulate change
        file_path = Path(mock_raw_logs[0].file_path)
        file_path.write_text("test content 1\nmore content")

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify file was processed
        daemon.event_handler._process_file.assert_called_once()
        assert daemon.event_handler._process_file.call_args[0][0] == file_path

    @patch("catsyphon.parsers.incremental.detect_file_change_type")
    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_rewritten_files(
        self,
        mock_db_session,
        mock_repo_class,
        mock_detect_change,
        temp_watch_dir,
        mock_raw_logs,
    ):
        """Test scan when files have been rewritten."""
        # Setup mocks
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = [mock_raw_logs[0]]
        mock_repo_class.return_value = mock_repo

        mock_detect_change.return_value = ChangeType.REWRITE

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify file was processed
        daemon.event_handler._process_file.assert_called_once()

    @patch("catsyphon.parsers.incremental.detect_file_change_type")
    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_deleted_files(
        self,
        mock_db_session,
        mock_repo_class,
        mock_detect_change,
        temp_watch_dir,
        mock_raw_logs,
    ):
        """Test scan gracefully skips files deleted from filesystem."""
        # Setup mocks
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        # Delete the file
        file_path = Path(mock_raw_logs[0].file_path)
        file_path.unlink()

        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = [mock_raw_logs[0]]
        mock_repo_class.return_value = mock_repo

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify file was not processed (doesn't exist)
        daemon.event_handler._process_file.assert_not_called()
        mock_detect_change.assert_not_called()

    @patch("catsyphon.parsers.incremental.detect_file_change_type")
    @patch("catsyphon.db.repositories.raw_log.RawLogRepository")
    @patch("catsyphon.db.connection.db_session")
    def test_scan_with_mixed_changes(
        self,
        mock_db_session,
        mock_repo_class,
        mock_detect_change,
        temp_watch_dir,
        mock_raw_logs,
    ):
        """Test scan with mix of unchanged, appended, and rewritten files."""
        # Setup mocks
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_repo = Mock()
        mock_repo.get_files_in_directory.return_value = mock_raw_logs
        mock_repo_class.return_value = mock_repo

        # Return different change types for each file
        mock_detect_change.side_effect = [
            ChangeType.UNCHANGED,  # file1
            ChangeType.APPEND,  # file2
            ChangeType.REWRITE,  # file3
        ]

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan
        daemon._scan_existing_files()

        # Verify only changed files (2 and 3) were processed
        assert daemon.event_handler._process_file.call_count == 2

    @patch("catsyphon.db.connection.db_session")
    def test_scan_handles_exceptions_gracefully(self, mock_db_session, temp_watch_dir):
        """Test scan doesn't crash daemon on errors."""
        # Setup mock to raise exception
        mock_session = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_db_session.return_value.__enter__.side_effect = Exception("Database error")

        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.event_handler = Mock()

        # Run scan - should not raise
        daemon._scan_existing_files()

        # Verify processing didn't happen
        daemon.event_handler._process_file.assert_not_called()


class TestStartupScanIntegration:
    """Integration tests for startup scan in daemon lifecycle."""

    @patch("catsyphon.watch.WatcherDaemon._scan_existing_files")
    def test_start_calls_scan(self, mock_scan, temp_watch_dir):
        """Test that start() calls _scan_existing_files()."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        # Mock observer and shutdown to prevent actual start
        daemon.observer = Mock()
        daemon.shutdown_event = Mock()
        daemon.shutdown_event.is_set.return_value = True

        daemon.start(blocking=False)

        # Verify scan was called
        mock_scan.assert_called_once()

    @patch("catsyphon.watch.WatcherDaemon._scan_existing_files")
    def test_start_calls_scan_after_observer(self, mock_scan, temp_watch_dir):
        """Test scan is called after observer starts."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        # Track call order
        call_order = []

        def track_observer_start():
            call_order.append("observer")

        def track_scan():
            call_order.append("scan")

        daemon.observer = Mock()
        daemon.observer.start.side_effect = track_observer_start
        mock_scan.side_effect = track_scan

        daemon.shutdown_event = Mock()
        daemon.shutdown_event.is_set.return_value = True

        daemon.start(blocking=False)

        # Verify order: observer starts before scan
        assert call_order == ["observer", "scan"]
