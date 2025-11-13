"""Tests for WatcherDaemon lifecycle and integration."""

import logging
import signal
from unittest.mock import Mock, patch

import pytest

from catsyphon.watch import RetryEntry, WatcherDaemon, start_watching


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create a temporary directory for watching."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return watch_dir


class TestWatcherDaemonInitialization:
    """Tests for WatcherDaemon initialization."""

    def test_init_with_minimal_params(self, temp_watch_dir):
        """Test daemon initialization with minimal parameters."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        assert daemon.directory == temp_watch_dir
        assert daemon.project_name is None
        assert daemon.developer_username is None
        assert daemon.poll_interval == 2
        assert daemon.retry_interval == 300
        assert daemon.debounce_seconds == 1.0
        assert daemon.enable_tagging is False
        assert daemon.stats is not None
        assert daemon.retry_queue is not None
        assert daemon.event_handler is not None
        assert daemon.observer is not None
        assert daemon.shutdown_event is not None
        assert daemon.retry_thread is None

    def test_init_with_all_params(self, temp_watch_dir):
        """Test daemon initialization with all parameters."""
        daemon = WatcherDaemon(
            directory=temp_watch_dir,
            project_name="test-project",
            developer_username="test-user",
            poll_interval=5,
            retry_interval=600,
            max_retries=5,
            debounce_seconds=2.0,
            enable_tagging=False,
        )

        assert daemon.project_name == "test-project"
        assert daemon.developer_username == "test-user"
        assert daemon.poll_interval == 5
        assert daemon.retry_interval == 600
        assert daemon.debounce_seconds == 2.0
        assert daemon.enable_tagging is False

    @patch("catsyphon.watch.settings")
    def test_init_with_tagging_enabled(self, mock_settings, temp_watch_dir):
        """Test daemon initialization with tagging enabled."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.tagging_cache_dir = "/tmp/cache"
        mock_settings.tagging_cache_ttl_days = 7
        mock_settings.tagging_enable_cache = True

        with patch("catsyphon.tagging.TaggingPipeline") as mock_tagging_pipeline:
            daemon = WatcherDaemon(directory=temp_watch_dir, enable_tagging=True)

            assert daemon.enable_tagging is True
            # Tagging pipeline should be initialized
            mock_tagging_pipeline.assert_called_once()

    def test_observer_scheduled_for_directory(self, temp_watch_dir):
        """Test that observer is scheduled to watch the directory."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        # Verify observer has a watch scheduled
        # (watchdog library doesn't expose watches directly, so we verify it doesn't error)
        assert daemon.observer is not None
        assert daemon.event_handler is not None


class TestWatcherDaemonLifecycle:
    """Tests for daemon start/stop lifecycle."""

    @patch("catsyphon.watch.signal.signal")
    def test_start_initializes_components(self, mock_signal, temp_watch_dir):
        """Test that start() initializes all components."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        # Mock observer and thread to prevent actual start
        daemon.observer = Mock()
        daemon.shutdown_event = Mock()
        daemon.shutdown_event.is_set.return_value = True  # Exit immediately

        daemon.start()

        # Verify signal handlers registered
        assert mock_signal.call_count == 2
        mock_signal.assert_any_call(signal.SIGINT, daemon._signal_handler)
        mock_signal.assert_any_call(signal.SIGTERM, daemon._signal_handler)

        # Verify observer started
        daemon.observer.start.assert_called_once()

        # Verify retry thread was created
        assert daemon.retry_thread is not None

    def test_stop_shuts_down_gracefully(self, temp_watch_dir):
        """Test that stop() shuts down all components."""
        daemon = WatcherDaemon(directory=temp_watch_dir)

        # Mock observer
        daemon.observer = Mock()

        daemon.stop()

        # Verify shutdown event set
        assert daemon.shutdown_event.is_set()

        # Verify observer stopped
        daemon.observer.stop.assert_called_once()
        daemon.observer.join.assert_called_once_with(timeout=5)

    @patch("catsyphon.watch.sys.exit")
    def test_signal_handler_stops_daemon(self, mock_exit, temp_watch_dir):
        """Test that signal handler triggers graceful shutdown."""
        daemon = WatcherDaemon(directory=temp_watch_dir)
        daemon.observer = Mock()

        # Simulate signal
        daemon._signal_handler(signal.SIGTERM, None)

        # Verify shutdown
        assert daemon.shutdown_event.is_set()
        daemon.observer.stop.assert_called_once()
        mock_exit.assert_called_once_with(0)


class TestRetryLoop:
    """Tests for background retry loop."""

    def test_retry_loop_processes_ready_files(self, temp_watch_dir):
        """Test that retry loop processes files ready for retry."""
        daemon = WatcherDaemon(directory=temp_watch_dir, retry_interval=1)

        # Create a test file to retry
        test_file = temp_watch_dir / "test.jsonl"
        test_file.write_text('{"test": "data"}')

        # Add to retry queue
        entry = RetryEntry(
            file_path=test_file,
            attempts=1,
            last_error="Test error",
            next_retry=None,  # Will be set by RetryQueue
        )

        # Mock event handler to avoid actual processing and set shutdown after call
        def mock_process_file(path):
            daemon.shutdown_event.set()  # Stop after processing

        daemon.event_handler._process_file = Mock(side_effect=mock_process_file)

        # Manually call retry loop once
        daemon.retry_queue.queue[str(test_file)] = entry

        # Mock get_ready_files to return our entry
        with patch.object(daemon.retry_queue, "get_ready_files", return_value=[entry]):
            # Run one iteration
            daemon._retry_loop()

            # Verify file was processed
            daemon.event_handler._process_file.assert_called_once_with(test_file)
            assert daemon.stats.files_retried == 1

    def test_retry_loop_handles_errors_gracefully(self, temp_watch_dir):
        """Test that retry loop handles errors without crashing."""
        daemon = WatcherDaemon(directory=temp_watch_dir, retry_interval=1)

        # Mock get_ready_files to raise an exception
        with patch.object(
            daemon.retry_queue, "get_ready_files", side_effect=Exception("Test error")
        ):
            # Set shutdown event to exit after one iteration
            daemon.shutdown_event.set()

            # Should not raise - error is caught
            daemon._retry_loop()

            # Verify stats not incremented on error
            assert daemon.stats.files_retried == 0

    def test_retry_loop_respects_shutdown_event(self, temp_watch_dir):
        """Test that retry loop stops when shutdown event is set."""
        daemon = WatcherDaemon(directory=temp_watch_dir, retry_interval=1)

        # Set shutdown immediately
        daemon.shutdown_event.set()

        # Mock to verify it doesn't process
        daemon.event_handler._process_file = Mock()

        # Run retry loop
        daemon._retry_loop()

        # Should exit immediately without processing
        daemon.event_handler._process_file.assert_not_called()

    def test_retry_loop_skips_files_on_shutdown(self, temp_watch_dir):
        """Test that retry loop stops processing when shutdown during iteration."""
        daemon = WatcherDaemon(directory=temp_watch_dir, retry_interval=1)

        # Create multiple test files
        files = [temp_watch_dir / f"test{i}.jsonl" for i in range(3)]
        for f in files:
            f.write_text('{"test": "data"}')

        entries = [
            RetryEntry(file_path=f, attempts=1, last_error="Test", next_retry=None)
            for f in files
        ]

        # Mock event handler
        def process_side_effect(path):
            # Set shutdown after first file
            if path == files[0]:
                daemon.shutdown_event.set()

        daemon.event_handler._process_file = Mock(side_effect=process_side_effect)

        # Mock get_ready_files
        with patch.object(daemon.retry_queue, "get_ready_files", return_value=entries):
            daemon._retry_loop()

            # Should only process first file before shutdown
            assert daemon.event_handler._process_file.call_count <= 1


class TestStartWatchingFunction:
    """Tests for start_watching entry point function."""

    def test_start_watching_with_valid_directory(self, temp_watch_dir):
        """Test start_watching with a valid directory."""
        with (
            patch("catsyphon.watch.WatcherDaemon") as mock_daemon_class,
            patch("catsyphon.watch.logging.basicConfig") as mock_logging_config,
        ):
            mock_daemon = Mock()
            mock_daemon_class.return_value = mock_daemon

            # Call start_watching - it will block, so we need to mock daemon.start
            mock_daemon.start = Mock()

            start_watching(
                directory=temp_watch_dir,
                project_name="test-project",
                developer_username="test-user",
            )

            # Verify daemon created with correct params
            mock_daemon_class.assert_called_once_with(
                directory=temp_watch_dir,
                project_name="test-project",
                developer_username="test-user",
                poll_interval=2,
                retry_interval=300,
                max_retries=3,
                debounce_seconds=1.0,
                enable_tagging=False,
            )

            # Verify daemon started
            mock_daemon.start.assert_called_once()

            # Verify logging configured
            mock_logging_config.assert_called_once()

    def test_start_watching_raises_on_nonexistent_directory(self, tmp_path):
        """Test start_watching raises ValueError for non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ValueError) as exc_info:
            start_watching(directory=nonexistent)

        assert "does not exist" in str(exc_info.value).lower()

    def test_start_watching_raises_on_file_path(self, tmp_path):
        """Test start_watching raises ValueError when path is a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not a directory")

        with pytest.raises(ValueError) as exc_info:
            start_watching(directory=test_file)

        assert "not a directory" in str(exc_info.value).lower()

    @patch("catsyphon.watch.settings")
    @patch("catsyphon.watch.WatcherDaemon")
    @patch("catsyphon.watch.logging.basicConfig")
    def test_start_watching_verbose_mode(
        self, mock_logging_config, mock_daemon_class, mock_settings, temp_watch_dir
    ):
        """Test start_watching with verbose mode enabled."""
        mock_settings.watch_log_file = "/tmp/watch.log"
        mock_daemon = Mock()
        mock_daemon.start = Mock()
        mock_daemon_class.return_value = mock_daemon

        start_watching(directory=temp_watch_dir, verbose=True)

        # Verify logging configured with DEBUG level
        assert mock_logging_config.called
        call_kwargs = mock_logging_config.call_args[1]
        assert call_kwargs["level"] == logging.DEBUG

    @patch("catsyphon.watch.settings")
    @patch("catsyphon.watch.WatcherDaemon")
    @patch("catsyphon.watch.logging.basicConfig")
    @patch("catsyphon.watch.logging.getLogger")
    def test_start_watching_suppresses_sqlalchemy_logs(
        self,
        mock_get_logger,
        mock_logging_config,
        mock_daemon_class,
        mock_settings,
        temp_watch_dir,
    ):
        """Test that SQLAlchemy logs are suppressed in non-verbose mode."""
        mock_settings.watch_log_file = "/tmp/watch.log"
        mock_daemon = Mock()
        mock_daemon.start = Mock()
        mock_daemon_class.return_value = mock_daemon
        mock_sqlalchemy_logger = Mock()
        mock_get_logger.return_value = mock_sqlalchemy_logger

        start_watching(directory=temp_watch_dir, verbose=False)

        # Verify SQLAlchemy logger level set to WARNING
        mock_get_logger.assert_called_with("sqlalchemy.engine")
        mock_sqlalchemy_logger.setLevel.assert_called_once_with(logging.WARNING)

    @patch("catsyphon.watch.settings")
    @patch("catsyphon.watch.WatcherDaemon")
    @patch("catsyphon.watch.logging.basicConfig")
    def test_start_watching_with_tagging_enabled(
        self, mock_logging_config, mock_daemon_class, mock_settings, temp_watch_dir
    ):
        """Test start_watching with LLM tagging enabled."""
        mock_settings.watch_log_file = "/tmp/watch.log"
        mock_daemon = Mock()
        mock_daemon.start = Mock()
        mock_daemon_class.return_value = mock_daemon

        start_watching(
            directory=temp_watch_dir,
            enable_tagging=True,
            project_name="test-project",
        )

        # Verify daemon created with tagging enabled
        call_kwargs = mock_daemon_class.call_args[1]
        assert call_kwargs["enable_tagging"] is True
        assert call_kwargs["project_name"] == "test-project"

    @patch("catsyphon.watch.settings")
    @patch("catsyphon.watch.WatcherDaemon")
    @patch("catsyphon.watch.logging.basicConfig")
    def test_start_watching_with_custom_intervals(
        self, mock_logging_config, mock_daemon_class, mock_settings, temp_watch_dir
    ):
        """Test start_watching with custom retry and debounce intervals."""
        mock_settings.watch_log_file = "/tmp/watch.log"
        mock_daemon = Mock()
        mock_daemon.start = Mock()
        mock_daemon_class.return_value = mock_daemon

        start_watching(
            directory=temp_watch_dir,
            poll_interval=5,
            retry_interval=600,
            max_retries=5,
            debounce_seconds=2.0,
        )

        # Verify daemon created with custom intervals
        call_kwargs = mock_daemon_class.call_args[1]
        assert call_kwargs["poll_interval"] == 5
        assert call_kwargs["retry_interval"] == 600
        assert call_kwargs["max_retries"] == 5
        assert call_kwargs["debounce_seconds"] == 2.0
