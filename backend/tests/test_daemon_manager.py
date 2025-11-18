"""Tests for DaemonManager multi-directory watch daemon management."""

import time
from threading import Thread
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from catsyphon.daemon_manager import DaemonEntry, DaemonManager, RestartPolicy
from catsyphon.models.db import Developer, Project, WatchConfiguration


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create a temporary directory for watching."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return watch_dir


@pytest.fixture
def watch_config(db_session, sample_workspace, temp_watch_dir):
    """Create a test watch configuration in database."""
    # Create project and developer
    project = Project(
        workspace_id=sample_workspace.id,
        name="test-project",
        directory_path=str(temp_watch_dir),
    )
    developer = Developer(
        workspace_id=sample_workspace.id, username="test-user", email="test@example.com"
    )
    db_session.add(project)
    db_session.add(developer)
    db_session.flush()

    # Create watch configuration
    config = WatchConfiguration(
        workspace_id=sample_workspace.id,
        directory=str(temp_watch_dir),
        project_id=project.id,
        developer_id=developer.id,
        enable_tagging=False,
        is_active=False,
        stats={},
        extra_config={},
    )
    db_session.add(config)
    db_session.commit()

    return config


@pytest.fixture
def daemon_manager():
    """Create a DaemonManager with automatic cleanup.

    Ensures background threads are properly stopped even if tests fail or are interrupted.
    """
    manager = DaemonManager()
    yield manager

    # Cleanup: shutdown manager and wait for threads to stop
    try:
        manager.shutdown(timeout=5)
    except Exception as e:
        # Log but don't fail - cleanup is best-effort
        print(f"Warning: DaemonManager cleanup error: {e}")


class TestRestartPolicy:
    """Tests for RestartPolicy dataclass."""

    def test_initial_state(self):
        """Test restart policy initial state."""
        policy = RestartPolicy()

        assert policy.crash_count == 0
        assert policy.restart_attempts == 0
        assert policy.last_crash_at is None
        assert policy.next_restart_at is None

    def test_should_restart_first_time(self):
        """Test should_restart returns True initially."""
        policy = RestartPolicy()
        assert policy.should_restart() is True

    def test_should_restart_within_backoff_interval(self):
        """Test should_restart returns False during backoff."""
        policy = RestartPolicy()
        policy.record_crash()

        # Should not restart immediately
        assert policy.should_restart() is False

    def test_should_restart_after_backoff(self):
        """Test should_restart returns True after backoff expires."""
        policy = RestartPolicy(backoff_intervals=[0])  # 0 second backoff
        policy.record_crash()

        # Wait a tiny bit
        time.sleep(0.01)

        assert policy.should_restart() is True

    def test_should_restart_max_attempts_exceeded(self):
        """Test should_restart returns False after max attempts."""
        policy = RestartPolicy(backoff_intervals=[0, 0])  # 2 attempts max

        policy.record_crash()
        time.sleep(0.01)
        assert policy.should_restart() is True

        policy.record_crash()
        time.sleep(0.01)
        assert policy.should_restart() is True

        policy.record_crash()
        # Exceeded max attempts (3 crashes = 2 restart attempts)
        assert policy.should_restart() is False

    def test_reset(self):
        """Test reset clears restart attempts."""
        policy = RestartPolicy()
        policy.record_crash()

        assert policy.restart_attempts == 1

        policy.reset()

        assert policy.restart_attempts == 0
        assert policy.next_restart_at is None


@pytest.mark.slow
class TestDaemonManager:
    """Tests for DaemonManager class."""

    def test_init(self):
        """Test daemon manager initialization."""
        manager = DaemonManager(stats_sync_interval=60)

        assert manager._stats_sync_interval == 60
        assert len(manager._daemons) == 0
        assert not manager._shutdown_event.is_set()

    def test_start_background_threads(self):
        """Test starting background threads."""
        manager = DaemonManager()
        manager.start()

        assert manager._stats_sync_thread is not None
        assert manager._stats_sync_thread.is_alive()

        assert manager._health_check_thread is not None
        assert manager._health_check_thread.is_alive()

        # Cleanup
        manager._shutdown_event.set()
        manager._stats_sync_thread.join(timeout=2)
        manager._health_check_thread.join(timeout=2)

    def test_start_daemon(self, watch_config):
        """Test starting a daemon."""
        manager = DaemonManager()

        # Start daemon
        manager.start_daemon(watch_config)

        # Verify daemon is tracked
        assert watch_config.id in manager._daemons
        entry = manager._daemons[watch_config.id]

        assert entry.config_id == watch_config.id
        assert entry.process is not None
        assert entry.pid is not None
        assert entry.process.is_alive()

        # Cleanup
        manager.stop_daemon(watch_config.id, save_stats=False)

    def test_start_daemon_already_running(self, watch_config):
        """Test starting daemon that's already running raises error."""
        manager = DaemonManager()
        manager.start_daemon(watch_config)

        with pytest.raises(ValueError, match="already running"):
            manager.start_daemon(watch_config)

        # Cleanup
        manager.stop_daemon(watch_config.id, save_stats=False)

    def test_start_daemon_directory_not_found(self, db_session, sample_workspace):
        """Test starting daemon with non-existent directory raises error."""
        config = WatchConfiguration(
            workspace_id=sample_workspace.id,
            directory="/nonexistent/path",
            is_active=False,
            enable_tagging=False,
            stats={},
            extra_config={},
        )
        db_session.add(config)
        db_session.commit()

        manager = DaemonManager()

        with pytest.raises(ValueError, match="does not exist"):
            manager.start_daemon(config)

    def test_start_daemon_with_extra_config(
        self, db_session, sample_workspace, temp_watch_dir
    ):
        """Test starting daemon with custom config options."""
        config = WatchConfiguration(
            workspace_id=sample_workspace.id,
            directory=str(temp_watch_dir),
            is_active=False,
            enable_tagging=False,
            stats={},
            extra_config={
                "poll_interval": 5,
                "retry_interval": 600,
                "max_retries": 5,
                "debounce_seconds": 2.0,
            },
        )
        db_session.add(config)
        db_session.commit()

        manager = DaemonManager()
        manager.start_daemon(config)

        # Verify daemon created and started successfully
        # Note: Can't check daemon properties directly due to multiprocessing isolation
        entry = manager._daemons[config.id]
        assert entry.process is not None
        assert entry.process.is_alive()
        assert entry.pid is not None

        # Cleanup
        manager.stop_daemon(config.id, save_stats=False)

    def test_stop_daemon(self, watch_config):
        """Test stopping a daemon."""
        manager = DaemonManager()
        manager.start_daemon(watch_config)

        # Wait a moment for daemon to fully start
        time.sleep(0.5)

        # Stop daemon
        manager.stop_daemon(watch_config.id, save_stats=False)

        # Verify daemon removed from tracking
        assert watch_config.id not in manager._daemons

    def test_stop_daemon_not_running(self):
        """Test stopping non-existent daemon raises error."""
        manager = DaemonManager()
        fake_id = uuid4()

        with pytest.raises(ValueError, match="No daemon running"):
            manager.stop_daemon(fake_id, save_stats=False)

    def test_stop_all_daemons(self, db_session, sample_workspace, temp_watch_dir):
        """Test stopping all daemons."""
        # Create multiple configs
        configs = []
        for i in range(3):
            dir_path = temp_watch_dir / f"dir{i}"
            dir_path.mkdir()

            config = WatchConfiguration(
                workspace_id=sample_workspace.id,
                directory=str(dir_path),
                is_active=False,
                enable_tagging=False,
                stats={},
                extra_config={},
            )
            db_session.add(config)
            configs.append(config)

        db_session.commit()

        manager = DaemonManager()

        # Start all daemons
        for config in configs:
            manager.start_daemon(config)

        assert len(manager._daemons) == 3

        # Stop all
        manager.stop_all(timeout=5)

        assert len(manager._daemons) == 0

    def test_get_daemon_status(self, watch_config):
        """Test getting daemon status."""
        manager = DaemonManager()
        manager.start_daemon(watch_config)

        # Wait for daemon to start
        time.sleep(0.5)

        status = manager.get_daemon_status(watch_config.id)

        assert status is not None
        assert status["config_id"] == str(watch_config.id)
        assert status["is_running"] is True
        assert "pid" in status
        assert status["pid"] is not None
        assert "uptime_seconds" in status
        # Note: stats removed in multiprocessing migration
        assert "restart_policy" in status

        # Cleanup
        manager.stop_daemon(watch_config.id, save_stats=False)

    def test_get_daemon_status_not_running(self):
        """Test getting status for non-running daemon."""
        manager = DaemonManager()
        fake_id = uuid4()

        status = manager.get_daemon_status(fake_id)
        assert status is None

    def test_get_all_status(self, db_session, sample_workspace, temp_watch_dir):
        """Test getting status for all daemons."""
        # Create multiple configs
        configs = []
        for i in range(2):
            dir_path = temp_watch_dir / f"dir{i}"
            dir_path.mkdir()

            config = WatchConfiguration(
                workspace_id=sample_workspace.id,
                directory=str(dir_path),
                is_active=False,
                enable_tagging=False,
                stats={},
                extra_config={},
            )
            db_session.add(config)
            configs.append(config)

        db_session.commit()

        manager = DaemonManager()

        # Start daemons
        for config in configs:
            manager.start_daemon(config)

        # Wait for daemons to start
        time.sleep(0.5)

        all_status = manager.get_all_status()

        assert all_status["total_daemons"] == 2
        assert all_status["running_daemons"] == 2
        assert len(all_status["daemons"]) == 2

        # Cleanup
        manager.stop_all(timeout=5)

    def test_shutdown(self, watch_config):
        """Test full daemon manager shutdown."""
        manager = DaemonManager()
        manager.start()
        manager.start_daemon(watch_config)

        # Wait for daemon to start
        time.sleep(0.5)

        # Shutdown
        manager.shutdown(timeout=5)

        # Verify everything stopped
        assert len(manager._daemons) == 0
        assert manager._shutdown_event.is_set()

    @patch("catsyphon.daemon_manager.db_session")
    def test_load_active_configs(self, mock_db_session, watch_config, sample_workspace):
        """Test loading active configs on startup."""
        # Mark config as active
        watch_config.is_active = True

        # Mock database session
        mock_session = Mock()
        mock_watch_repo = Mock()
        mock_watch_repo.get_all_active.return_value = [watch_config]

        mock_workspace_repo = Mock()
        mock_workspace_repo.get_all.return_value = [sample_workspace]

        mock_db_session.return_value.__enter__.return_value = mock_session

        manager = DaemonManager()

        with patch.object(
            manager,
            "start_daemon",
            side_effect=lambda config: setattr(
                manager._daemons,
                config.id,
                DaemonEntry(
                    daemon=Mock(),
                    config_id=config.id,
                    thread=Thread(target=lambda: None),
                ),
            ),
        ) as mock_start:
            with (
                patch(
                    "catsyphon.daemon_manager.WatchConfigurationRepository",
                    return_value=mock_watch_repo,
                ),
                patch(
                    "catsyphon.daemon_manager.WorkspaceRepository",
                    return_value=mock_workspace_repo,
                ),
            ):
                manager.load_active_configs()

            # Verify start_daemon was called
            mock_start.assert_called_once_with(watch_config)

    @patch("catsyphon.daemon_manager.db_session")
    def test_load_active_configs_handles_errors(
        self, mock_db_session, sample_workspace
    ):
        """Test load_active_configs handles daemon start errors gracefully."""
        # Create a config that will fail to start
        bad_config = WatchConfiguration(
            id=uuid4(),
            directory="/nonexistent",
            is_active=True,
            enable_tagging=False,
            stats={},
            extra_config={},
        )

        # Mock database
        mock_session = Mock()
        mock_watch_repo = Mock()
        mock_watch_repo.get_all_active.return_value = [bad_config]
        mock_watch_repo.deactivate.return_value = None

        mock_workspace_repo = Mock()
        mock_workspace_repo.get_all.return_value = [sample_workspace]

        mock_db_session.return_value.__enter__.return_value = mock_session

        manager = DaemonManager()

        with (
            patch(
                "catsyphon.daemon_manager.WatchConfigurationRepository",
                return_value=mock_watch_repo,
            ),
            patch(
                "catsyphon.daemon_manager.WorkspaceRepository",
                return_value=mock_workspace_repo,
            ),
        ):
            # Should not raise - errors are logged
            manager.load_active_configs()

            # Verify it tried to deactivate the failed config
            mock_watch_repo.deactivate.assert_called_once_with(bad_config.id)

    @patch("catsyphon.daemon_manager.db_session")
    def test_stats_sync_loop(self, mock_db_session, watch_config):
        """Test stats sync background thread with Queue-based IPC."""
        from multiprocessing import Queue

        # Mock database
        mock_session = Mock()
        mock_repo = Mock()

        mock_db_session.return_value.__enter__.return_value = mock_session

        manager = DaemonManager(stats_sync_interval=1)  # 1 second interval
        manager.start_daemon(watch_config)

        # Simulate child process pushing stats to queue
        config_id = watch_config.id
        if config_id in manager._stats_queues:
            stats_queue = manager._stats_queues[config_id]
            test_stats = {
                "files_processed": 5,
                "files_skipped": 2,
                "files_failed": 1,
                "files_retried": 0,
                "last_activity": "2025-11-17T21:00:00",
            }
            stats_queue.put_nowait(test_stats)

        with patch(
            "catsyphon.daemon_manager.WatchConfigurationRepository",
            return_value=mock_repo,
        ):
            # Start background thread
            manager.start()

            # Wait for at least one sync cycle
            time.sleep(2)

            # Stop manager
            manager.shutdown(timeout=5)

            # Verify stats were synced
            assert mock_repo.update_stats.called
            # Verify stats were saved with correct data
            call_args = mock_repo.update_stats.call_args
            assert call_args[0][0] == config_id  # First arg is config_id
            assert call_args[0][1]["files_processed"] == 5  # Second arg is stats dict

    def test_health_check_detects_crashed_daemon(
        self, db_session, sample_workspace, temp_watch_dir
    ):
        """Test health check thread detects crashed daemons."""
        config = WatchConfiguration(
            workspace_id=sample_workspace.id,
            directory=str(temp_watch_dir),
            is_active=True,
            enable_tagging=False,
            stats={},
            extra_config={},
        )
        db_session.add(config)
        db_session.commit()

        manager = DaemonManager(health_check_interval=1)  # 1 second for testing
        manager.start()

        # Manually create a dead daemon entry with mock process
        dead_process = Mock()
        dead_process.is_alive.return_value = False
        dead_process.pid = 99999  # Fake PID that won't exist

        entry = DaemonEntry(
            process=dead_process,
            config_id=config.id,
            pid=99999,
        )

        with manager._lock:
            manager._daemons[config.id] = entry

        # Wait for health check to run (only need 2s instead of 35s)
        time.sleep(2)

        # Verify restart policy recorded crash
        with manager._lock:
            if config.id in manager._daemons:
                assert manager._daemons[config.id].restart_policy.crash_count > 0

        # Cleanup
        manager.shutdown(timeout=5)

    def test_check_daemon_health_directly(
        self, db_session, sample_workspace, temp_watch_dir
    ):
        """Test _check_daemon_health method directly without background thread.

        This is a fast unit test that validates health check logic without
        waiting for the loop interval.
        """
        config = WatchConfiguration(
            workspace_id=sample_workspace.id,
            directory=str(temp_watch_dir),
            is_active=True,
            enable_tagging=False,
            stats={},
            extra_config={},
        )
        db_session.add(config)
        db_session.commit()

        manager = DaemonManager()

        # Manually create a dead daemon entry with mock process
        dead_process = Mock()
        dead_process.is_alive.return_value = False
        dead_process.pid = 99999  # Fake PID that won't exist

        entry = DaemonEntry(
            process=dead_process,
            config_id=config.id,
            pid=99999,
        )

        with manager._lock:
            manager._daemons[config.id] = entry

        # Call health check directly (no sleep needed!)
        manager._check_daemon_health(config.id)

        # Verify restart policy recorded crash
        with manager._lock:
            if config.id in manager._daemons:
                assert manager._daemons[config.id].restart_policy.crash_count > 0


@pytest.mark.slow
class TestDaemonManagerIntegration:
    """Integration tests for DaemonManager with real WatcherDaemon."""

    def test_end_to_end_daemon_lifecycle(
        self, db_session, sample_workspace, temp_watch_dir
    ):
        """Test complete daemon lifecycle: start, monitor, stop."""
        # Create configuration
        config = WatchConfiguration(
            workspace_id=sample_workspace.id,
            directory=str(temp_watch_dir),
            is_active=False,
            enable_tagging=False,
            stats={},
            extra_config={},
        )
        db_session.add(config)
        db_session.commit()

        manager = DaemonManager()

        # Start daemon
        manager.start_daemon(config)

        # Wait for daemon to start
        time.sleep(1)

        # Verify daemon is running
        status = manager.get_daemon_status(config.id)
        assert status["is_running"] is True

        # Create a test file to trigger processing
        test_file = temp_watch_dir / "test.jsonl"
        test_file.write_text(
            '{"sessionId":"test","version":"2.0.0","timestamp":"2025-01-14T12:00:00Z",'
            '"type":"user","message":{"role":"user","content":"test"}}\n'
        )

        # Wait for file to be processed
        time.sleep(2)

        # Stop daemon
        manager.stop_daemon(config.id, save_stats=False)

        # Verify daemon stopped
        assert config.id not in manager._daemons
