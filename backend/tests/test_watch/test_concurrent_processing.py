"""Tests for concurrent file processing prevention in FileWatcher."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from catsyphon.watch import ApiIngestionConfig, FileWatcher, RetryQueue, WatcherStats


@pytest.fixture
def mock_api_config():
    """API configuration with mock credentials for testing."""
    return ApiIngestionConfig(
        server_url="http://localhost:8000",
        api_key="test-api-key",
        collector_id="test-collector-id",
        batch_size=20,
    )


@pytest.fixture
def file_watcher(mock_api_config):
    """Create a FileWatcher instance for testing with mock API config."""
    # Mock the collector client to avoid actual HTTP connections
    with patch("catsyphon.collector_client.CollectorClient") as mock_client:
        mock_client.return_value = Mock()
        return FileWatcher(
            project_name="test-project",
            developer_username="test-user",
            retry_queue=RetryQueue(),
            stats=WatcherStats(),
            debounce_seconds=0.1,  # Short debounce for tests
            api_config=mock_api_config,
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

        # Mock _process_file_via_api to track calls (API-only mode)
        with patch.object(
            file_watcher, "_process_file_via_api", side_effect=mock_process
        ):
            with patch("catsyphon.watch.background_session"):
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=False):
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

        # Mock _process_file_via_api to track calls (API-only mode)
        with patch.object(
            file_watcher, "_process_file_via_api", side_effect=mock_process
        ):
            with patch("catsyphon.watch.background_session"):
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=False):
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

        # Mock _process_file_via_api to track calls (API-only mode)
        with patch.object(
            file_watcher, "_process_file_via_api", side_effect=mock_process
        ):
            with patch("catsyphon.watch.background_session"):
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=False):
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

        # Mock _process_file_via_api (API-only mode)
        with patch.object(file_watcher, "_process_file_via_api"):
            with patch("catsyphon.watch.background_session"):
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=False):
                        # Process file
                        file_watcher._process_file(test_file)

                        # Verify file was removed from processing set
                        assert path_str not in file_watcher.processing

    def test_processing_set_cleaned_up_after_error(self, file_watcher):
        """Test that files are removed from processing set even after errors."""
        test_file = Path("/test/conversation.jsonl")
        path_str = str(test_file)

        # Mock _process_file_via_api to raise an error (API-only mode)
        with patch.object(
            file_watcher, "_process_file_via_api", side_effect=Exception("Test error")
        ):
            with patch("catsyphon.watch.background_session"):
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_file", return_value=False):
                        # Also mock failure tracking to avoid database issues
                        with patch(
                            "catsyphon.pipeline.failure_tracking.track_failure"
                        ):
                            # Process file (will error)
                            file_watcher._process_file(test_file)

                            # Verify file was still removed from processing set
                            assert path_str not in file_watcher.processing
