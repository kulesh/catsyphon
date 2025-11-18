"""Tests for concurrent file processing prevention in FileWatcher."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from catsyphon.watch import FileWatcher, RetryQueue, WatcherStats


@pytest.fixture
def file_watcher():
    """Create a FileWatcher instance for testing."""
    return FileWatcher(
        project_name="test-project",
        developer_username="test-user",
        retry_queue=RetryQueue(),
        stats=WatcherStats(),
        debounce_seconds=0.1,  # Short debounce for tests
    )


class TestConcurrentProcessing:
    """Tests for concurrent file processing prevention."""

    def test_prevents_concurrent_processing_of_same_file(self, file_watcher):
        """Test that _process_file prevents concurrent processing of the same file."""
        test_file = Path("/test/conversation.jsonl")

        # Track how many times the file actually gets processed
        process_count = 0
        process_lock = threading.Lock()

        def mock_process(*args, **kwargs):
            nonlocal process_count
            # Simulate processing taking some time
            time.sleep(0.2)
            with process_lock:
                process_count += 1

        # Mock ingest_conversation to track calls
        with patch("catsyphon.watch.ingest_conversation", side_effect=mock_process):
            with patch("catsyphon.watch.db_session"):
                with patch.object(Path, "exists", return_value=True):
                    # Mock parser to return a valid parsed conversation
                    mock_parsed = Mock()
                    mock_parsed.session_id = "test-session-123"
                    mock_parsed.start_time = None
                    mock_parsed.end_time = None
                    mock_parsed.git_branch = None
                    mock_parsed.working_directory = None
                    mock_parsed.metadata = {}

                    with patch.object(
                        file_watcher.parser_registry, "parse", return_value=mock_parsed
                    ):
                        # Launch 5 concurrent threads trying to process the same file
                        threads = []
                        for _ in range(5):
                            t = threading.Thread(
                                target=file_watcher._process_file, args=(test_file,)
                            )
                            threads.append(t)
                            t.start()

                        # Wait for all threads to complete
                        for t in threads:
                            t.join(timeout=2.0)

                        # Verify only one thread actually processed the file
                        assert process_count == 1

    def test_allows_sequential_processing_of_same_file(self, file_watcher):
        """Test that _process_file allows sequential processing of the same file."""
        test_file = Path("/test/conversation.jsonl")

        # Track how many times the file gets processed
        process_count = 0
        process_lock = threading.Lock()

        def mock_process(*args, **kwargs):
            nonlocal process_count
            time.sleep(0.05)
            with process_lock:
                process_count += 1

        with patch("catsyphon.watch.ingest_conversation", side_effect=mock_process):
            with patch("catsyphon.watch.db_session"):
                with patch.object(Path, "exists", return_value=True):
                    mock_parsed = Mock()
                    mock_parsed.session_id = "test-session-123"
                    mock_parsed.start_time = None
                    mock_parsed.end_time = None
                    mock_parsed.git_branch = None
                    mock_parsed.working_directory = None
                    mock_parsed.metadata = {}

                    with patch.object(
                        file_watcher.parser_registry, "parse", return_value=mock_parsed
                    ):
                        # Process file 3 times sequentially
                        for _ in range(3):
                            file_watcher._process_file(test_file)

                        # All 3 should have been processed
                        assert process_count == 3

    def test_allows_concurrent_processing_of_different_files(self, file_watcher):
        """Test that _process_file allows concurrent processing of different files."""
        files = [
            Path("/test/conversation1.jsonl"),
            Path("/test/conversation2.jsonl"),
            Path("/test/conversation3.jsonl"),
        ]

        # Track how many files get processed
        process_count = 0
        process_lock = threading.Lock()

        def mock_process(*args, **kwargs):
            nonlocal process_count
            time.sleep(0.1)
            with process_lock:
                process_count += 1

        with patch("catsyphon.watch.ingest_conversation", side_effect=mock_process):
            with patch("catsyphon.watch.db_session"):
                with patch.object(Path, "exists", return_value=True):
                    mock_parsed = Mock()
                    mock_parsed.session_id = "test-session-123"
                    mock_parsed.start_time = None
                    mock_parsed.end_time = None
                    mock_parsed.git_branch = None
                    mock_parsed.working_directory = None
                    mock_parsed.metadata = {}

                    with patch.object(
                        file_watcher.parser_registry, "parse", return_value=mock_parsed
                    ):
                        # Launch threads for different files concurrently
                        threads = []
                        for file in files:
                            t = threading.Thread(
                                target=file_watcher._process_file, args=(file,)
                            )
                            threads.append(t)
                            t.start()

                        # Wait for all threads
                        for t in threads:
                            t.join(timeout=2.0)

                        # All 3 different files should have been processed
                        assert process_count == 3

    def test_processing_set_cleaned_up_after_completion(self, file_watcher):
        """Test that files are removed from processing set after completion."""
        test_file = Path("/test/conversation.jsonl")
        path_str = str(test_file)

        with patch("catsyphon.watch.ingest_conversation"):
            with patch("catsyphon.watch.db_session"):
                with patch.object(Path, "exists", return_value=True):
                    mock_parsed = Mock()
                    mock_parsed.session_id = "test-session-123"
                    mock_parsed.start_time = None
                    mock_parsed.end_time = None
                    mock_parsed.git_branch = None
                    mock_parsed.working_directory = None
                    mock_parsed.metadata = {}

                    with patch.object(
                        file_watcher.parser_registry, "parse", return_value=mock_parsed
                    ):
                        # Process file
                        file_watcher._process_file(test_file)

                        # Verify file was removed from processing set
                        assert path_str not in file_watcher.processing

    def test_processing_set_cleaned_up_after_error(self, file_watcher):
        """Test that files are removed from processing set even after errors."""
        test_file = Path("/test/conversation.jsonl")
        path_str = str(test_file)

        with patch("catsyphon.watch.ingest_conversation", side_effect=Exception("Test error")):
            with patch("catsyphon.watch.db_session"):
                with patch.object(Path, "exists", return_value=True):
                    mock_parsed = Mock()
                    mock_parsed.session_id = "test-session-123"
                    mock_parsed.start_time = None
                    mock_parsed.end_time = None
                    mock_parsed.git_branch = None
                    mock_parsed.working_directory = None
                    mock_parsed.metadata = {}

                    with patch.object(
                        file_watcher.parser_registry, "parse", return_value=mock_parsed
                    ):
                        # Process file (will error)
                        file_watcher._process_file(test_file)

                        # Verify file was still removed from processing set
                        assert path_str not in file_watcher.processing
