"""Tests for RetryQueue retry logic with exponential backoff."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from catsyphon.watch import RetryQueue, RetryEntry


class TestRetryQueue:
    """Tests for RetryQueue class."""

    def test_add_file_first_attempt(self):
        """Test adding a file to retry queue for first time."""
        queue = RetryQueue(max_retries=3, base_interval=300)
        file_path = Path("/test/file.jsonl")

        queue.add(file_path, "Test error")

        assert len(queue) == 1
        assert str(file_path) in queue.queue
        entry = queue.queue[str(file_path)]
        assert entry.attempts == 1
        assert entry.last_error == "Test error"
        assert entry.next_retry is not None

    def test_add_same_file_increments_attempts(self):
        """Test adding same file multiple times increments attempts."""
        queue = RetryQueue(max_retries=3, base_interval=300)
        file_path = Path("/test/file.jsonl")

        queue.add(file_path, "Error 1")
        queue.add(file_path, "Error 2")
        queue.add(file_path, "Error 3")

        assert len(queue) == 1
        entry = queue.queue[str(file_path)]
        assert entry.attempts == 3
        assert entry.last_error == "Error 3"

    def test_remove_file_from_queue(self):
        """Test removing a file from the retry queue."""
        queue = RetryQueue()
        file_path = Path("/test/file.jsonl")

        queue.add(file_path, "Test error")
        assert len(queue) == 1

        queue.remove(file_path)
        assert len(queue) == 0
        assert str(file_path) not in queue.queue

    def test_queue_length_tracking(self):
        """Test queue length is tracked correctly."""
        queue = RetryQueue()

        assert len(queue) == 0

        queue.add(Path("/test/file1.jsonl"), "Error 1")
        assert len(queue) == 1

        queue.add(Path("/test/file2.jsonl"), "Error 2")
        assert len(queue) == 2

        queue.remove(Path("/test/file1.jsonl"))
        assert len(queue) == 1


class TestExponentialBackoff:
    """Tests for exponential backoff calculation."""

    def test_calculate_backoff_first_attempt(self):
        """Test backoff calculation for first attempt (5 minutes)."""
        queue = RetryQueue(base_interval=300)

        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            next_retry = queue._calculate_next_retry(attempts=1)

            expected = mock_now + timedelta(seconds=300)  # 5 minutes
            assert next_retry == expected

    def test_calculate_backoff_second_attempt(self):
        """Test backoff calculation for second attempt (15 minutes)."""
        queue = RetryQueue(base_interval=300)

        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            next_retry = queue._calculate_next_retry(attempts=2)

            expected = mock_now + timedelta(seconds=900)  # 15 minutes
            assert next_retry == expected

    def test_calculate_backoff_third_attempt(self):
        """Test backoff calculation for third attempt (45 minutes)."""
        queue = RetryQueue(base_interval=300)

        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            next_retry = queue._calculate_next_retry(attempts=3)

            expected = mock_now + timedelta(seconds=2700)  # 45 minutes
            assert next_retry == expected

    def test_custom_base_interval(self):
        """Test backoff with custom base interval."""
        queue = RetryQueue(base_interval=60)  # 1 minute base

        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            next_retry = queue._calculate_next_retry(attempts=1)

            expected = mock_now + timedelta(seconds=60)  # 1 minute
            assert next_retry == expected


class TestGetReadyFiles:
    """Tests for getting files ready for retry."""

    def test_get_ready_files_when_time_reached(self):
        """Test getting files when retry time has been reached."""
        queue = RetryQueue(max_retries=3, base_interval=1)
        file_path = Path("/test/file.jsonl")

        # Add file with next_retry in the past
        with patch("catsyphon.watch.datetime") as mock_datetime:
            past_time = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = past_time
            queue.add(file_path, "Test error")

        # Check for ready files (now is later)
        with patch("catsyphon.watch.datetime") as mock_datetime:
            current_time = datetime(2025, 1, 1, 12, 5, 0)  # 5 minutes later
            mock_datetime.now.return_value = current_time

            ready = queue.get_ready_files()

            assert len(ready) == 1
            assert ready[0].file_path == file_path

    def test_get_ready_files_skips_not_ready(self):
        """Test that files not yet ready for retry are skipped."""
        queue = RetryQueue(max_retries=3, base_interval=300)
        file_path = Path("/test/file.jsonl")

        # Add file
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            queue.add(file_path, "Test error")

        # Check immediately (not enough time passed)
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 1, 0
            )  # Only 1 min

            ready = queue.get_ready_files()

            assert len(ready) == 0

    def test_get_ready_files_removes_max_retries_exceeded(self):
        """Test that files exceeding max retries are removed."""
        queue = RetryQueue(max_retries=3, base_interval=1)
        file_path = Path("/test/file.jsonl")

        # Add file and increment to max attempts
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0)
            queue.add(file_path, "Error 1")
            queue.add(file_path, "Error 2")
            queue.add(file_path, "Error 3")

        assert len(queue) == 1
        assert queue.queue[str(file_path)].attempts == 3

        # Get ready files - should remove the file
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 10, 0)

            ready = queue.get_ready_files()

            assert len(ready) == 0  # Not returned as ready
            assert len(queue) == 0  # Removed from queue
            assert str(file_path) not in queue.queue

    def test_get_ready_files_with_multiple_files(self):
        """Test getting ready files when multiple files in queue."""
        queue = RetryQueue(max_retries=3, base_interval=1)
        file1 = Path("/test/file1.jsonl")
        file2 = Path("/test/file2.jsonl")
        file3 = Path("/test/file3.jsonl")

        # Add files at different times
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0)
            queue.add(file1, "Error 1")  # Ready soon

            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 1, 0)
            queue.add(file2, "Error 2")  # Ready later

            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 2, 0)
            queue.add(file3, "Error 3")  # Ready even later

        # Check at time when only file1 is ready
        with patch("catsyphon.watch.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 0, 2
            )  # 2 seconds later

            ready = queue.get_ready_files()

            assert len(ready) == 1
            assert ready[0].file_path == file1
