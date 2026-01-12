"""Tests for file rename handling in FileWatcher."""

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


class TestFileRenameHandling:
    """Tests for on_moved() event handler."""

    def test_on_moved_triggers_rename_handling_for_jsonl(self, file_watcher):
        """Test on_moved() triggers rename handling for .jsonl files."""
        event = Mock(
            is_directory=False,
            src_path="/test/old-name.jsonl",
            dest_path="/test/new-name.jsonl",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            mock_handle.assert_called_once()
            assert mock_handle.call_args[0][0] == Path("/test/old-name.jsonl")
            assert mock_handle.call_args[0][1] == Path("/test/new-name.jsonl")

    def test_on_moved_ignores_directory_renames(self, file_watcher):
        """Test that directory move events are ignored."""
        event = Mock(
            is_directory=True,
            src_path="/test/old-folder",
            dest_path="/test/new-folder",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            mock_handle.assert_not_called()

    def test_on_moved_ignores_non_jsonl_files(self, file_watcher):
        """Test that non-.jsonl file moves are ignored."""
        event = Mock(
            is_directory=False,
            src_path="/test/document.txt",
            dest_path="/test/document-renamed.txt",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            mock_handle.assert_not_called()

    def test_on_moved_handles_rename_to_jsonl(self, file_watcher):
        """Test that renaming a file TO .jsonl extension is handled."""
        event = Mock(
            is_directory=False,
            src_path="/test/conversation.log",
            dest_path="/test/conversation.jsonl",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            # Should be processed since dest has .jsonl extension
            mock_handle.assert_called_once()

    def test_on_moved_handles_rename_from_jsonl(self, file_watcher):
        """Test that renaming FROM .jsonl extension is handled."""
        event = Mock(
            is_directory=False,
            src_path="/test/conversation.jsonl",
            dest_path="/test/conversation.backup",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            # Should be processed since src has .jsonl extension
            mock_handle.assert_called_once()


class TestHandleFileRename:
    """Tests for _handle_file_rename() helper method."""

    def test_treats_as_new_file_when_raw_log_not_found(self, file_watcher):
        """Test that file is processed as new when no raw_log exists."""
        src_path = Path("/test/nonexistent.jsonl")
        dest_path = Path("/test/renamed.jsonl")

        with patch.object(file_watcher, "_handle_file_event") as mock_process:
            file_watcher._handle_file_rename(src_path, dest_path)

            # Should process dest_path as new file
            mock_process.assert_called_once_with(dest_path)

    def test_handles_database_errors_gracefully(self, file_watcher):
        """Test that database errors during rename are handled gracefully."""
        src_path = Path("/test/old.jsonl")
        dest_path = Path("/test/new.jsonl")

        with patch("catsyphon.watch.db_session") as mock_db_session:
            # Simulate database error
            mock_db_session.side_effect = Exception("Database connection failed")

            with patch.object(file_watcher, "_handle_file_event") as mock_process:
                # Should not raise exception
                file_watcher._handle_file_rename(src_path, dest_path)

                # Should fallback to processing as new file
                mock_process.assert_called_once_with(dest_path)


class TestCrossDirectoryMoves:
    """Tests for file moves across directories."""

    def test_handles_move_to_different_directory(self, file_watcher):
        """Test that moving file to different directory is handled."""
        event = Mock(
            is_directory=False,
            src_path="/test/dir1/conversation.jsonl",
            dest_path="/test/dir2/conversation.jsonl",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            # Should be handled same as rename
            mock_handle.assert_called_once()
            assert mock_handle.call_args[0][0] == Path("/test/dir1/conversation.jsonl")
            assert mock_handle.call_args[0][1] == Path("/test/dir2/conversation.jsonl")

    def test_handles_move_with_rename(self, file_watcher):
        """Test that moving AND renaming file is handled."""
        event = Mock(
            is_directory=False,
            src_path="/test/dir1/old-name.jsonl",
            dest_path="/test/dir2/new-name.jsonl",
        )

        with patch.object(file_watcher, "_handle_file_rename") as mock_handle:
            file_watcher.on_moved(event)

            mock_handle.assert_called_once()
