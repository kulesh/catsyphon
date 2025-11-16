"""
Multi-directory watch daemon manager.

Manages multiple WatcherDaemon instances, allowing the web UI to control
watch operations across multiple directories.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Dict, Optional
from uuid import UUID

from catsyphon.db.connection import db_session
from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.models.db import WatchConfiguration
from catsyphon.watch import WatcherDaemon

logger = logging.getLogger(__name__)


@dataclass
class RestartPolicy:
    """Tracks daemon restart attempts with exponential backoff."""

    crash_count: int = 0
    last_crash_at: Optional[datetime] = None
    restart_attempts: int = 0
    next_restart_at: Optional[datetime] = None
    backoff_intervals: list[int] = field(default_factory=lambda: [5, 15, 45])  # seconds

    def should_restart(self) -> bool:
        """Check if daemon should be restarted."""
        if self.restart_attempts > len(self.backoff_intervals):
            return False  # Exceeded max restart attempts

        if self.next_restart_at is None:
            return True  # First restart

        return datetime.now() >= self.next_restart_at

    def record_crash(self) -> None:
        """Record a daemon crash and calculate next restart time."""
        self.crash_count += 1
        self.last_crash_at = datetime.now()

        # Calculate backoff delay
        interval_index = min(self.restart_attempts, len(self.backoff_intervals) - 1)
        backoff_seconds = self.backoff_intervals[interval_index]

        self.next_restart_at = datetime.now() + timedelta(seconds=backoff_seconds)
        self.restart_attempts += 1

        logger.info(
            f"Daemon crash recorded. Next restart attempt in {backoff_seconds}s "
            f"(attempt {self.restart_attempts}/{len(self.backoff_intervals)})"
        )

    def reset(self) -> None:
        """Reset restart policy after successful restart."""
        self.restart_attempts = 0
        self.next_restart_at = None


@dataclass
class DaemonEntry:
    """Tracks a running daemon instance."""

    daemon: WatcherDaemon
    config_id: UUID
    thread: Thread
    started_at: datetime = field(default_factory=datetime.now)
    restart_policy: RestartPolicy = field(default_factory=RestartPolicy)


class DaemonManager:
    """
    Manages multiple WatcherDaemon instances.

    Responsibilities:
    - Start/stop daemons for watch configurations
    - Auto-start active configs on startup
    - Monitor daemon health and auto-restart on crash
    - Sync stats to database periodically
    - Graceful shutdown of all daemons
    """

    def __init__(self, stats_sync_interval: int = 30, health_check_interval: int = 30):
        """
        Initialize the daemon manager.

        Args:
            stats_sync_interval: How often to sync stats to DB (seconds)
            health_check_interval: How often to check daemon health (seconds)
        """
        self._daemons: Dict[UUID, DaemonEntry] = {}
        self._lock = Lock()
        self._shutdown_event = Event()
        self._stats_sync_interval = stats_sync_interval
        self._health_check_interval = health_check_interval

        # Background threads
        self._stats_sync_thread: Optional[Thread] = None
        self._health_check_thread: Optional[Thread] = None

        logger.info("DaemonManager initialized")

    def start(self) -> None:
        """Start the daemon manager background threads."""
        logger.info("Starting DaemonManager background threads...")

        # Start stats sync thread
        self._stats_sync_thread = Thread(
            target=self._stats_sync_loop, name="stats-sync", daemon=False
        )
        self._stats_sync_thread.start()
        logger.info("✓ Stats sync thread started")

        # Start health check thread
        self._health_check_thread = Thread(
            target=self._health_check_loop, name="health-check", daemon=False
        )
        self._health_check_thread.start()
        logger.info("✓ Health check thread started")

    def load_active_configs(self) -> None:
        """
        Load and start all active watch configurations from database.

        Called during application startup.
        """
        logger.info("Loading active watch configurations...")

        with db_session() as session:
            repo = WatchConfigurationRepository(session)
            active_configs = repo.get_all_active()

            if not active_configs:
                logger.info("No active watch configurations found")
                return

            logger.info(f"Found {len(active_configs)} active configuration(s)")

            for config in active_configs:
                try:
                    self.start_daemon(config)
                except Exception as e:
                    logger.error(
                        f"Failed to start daemon for config {config.id}: {e}",
                        exc_info=True,
                    )
                    # Mark as inactive in DB
                    try:
                        repo.deactivate(config.id)
                        session.commit()
                    except Exception:
                        pass

    def start_daemon(self, config: WatchConfiguration) -> None:
        """
        Start a watch daemon for the given configuration.

        Args:
            config: Watch configuration

        Raises:
            ValueError: If directory doesn't exist or daemon already running
            Exception: If daemon fails to start
        """
        config_id = config.id

        with self._lock:
            # Check if already running
            if config_id in self._daemons:
                raise ValueError(f"Daemon already running for config {config_id}")

        # Validate directory (expand ~ and resolve)
        directory = Path(config.directory).expanduser().resolve()
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {config.directory}")
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {config.directory}")

        # Extract config options from extra_config
        extra_config = config.extra_config or {}
        poll_interval = extra_config.get("poll_interval", 2)
        retry_interval = extra_config.get("retry_interval", 300)
        max_retries = extra_config.get("max_retries", 3)
        debounce_seconds = extra_config.get("debounce_seconds", 1.0)

        # Create daemon instance
        daemon = WatcherDaemon(
            directory=directory,
            project_name=config.project.name if config.project else None,
            developer_username=config.developer.username if config.developer else None,
            poll_interval=poll_interval,
            retry_interval=retry_interval,
            max_retries=max_retries,
            debounce_seconds=debounce_seconds,
            enable_tagging=config.enable_tagging,
            config_id=config_id,
        )

        # Start daemon in non-blocking mode
        daemon.start(blocking=False)

        # Create a monitoring thread that tracks the daemon
        def monitor_thread_target():
            try:
                # Just keep the thread alive while daemon is running
                while daemon.is_running() and not self._shutdown_event.is_set():
                    time.sleep(1)
            except Exception as e:
                logger.error(
                    f"Monitor thread error for config {config_id}: {e}", exc_info=True
                )

        thread = Thread(
            target=monitor_thread_target,
            name=f"monitor-{config_id}",
            daemon=False,  # Not a daemon thread - we want clean shutdown
        )
        thread.start()

        # Track daemon
        with self._lock:
            self._daemons[config_id] = DaemonEntry(
                daemon=daemon,
                config_id=config_id,
                thread=thread,
            )

        logger.info(f"✓ Started daemon for {config.directory} (config {config_id})")

    def stop_daemon(self, config_id: UUID, save_stats: bool = True) -> None:
        """
        Stop a watch daemon.

        Args:
            config_id: Watch configuration ID
            save_stats: Whether to save final stats to database

        Raises:
            ValueError: If daemon not running
        """
        with self._lock:
            if config_id not in self._daemons:
                raise ValueError(f"No daemon running for config {config_id}")

            entry = self._daemons[config_id]

        logger.info(f"Stopping daemon for config {config_id}...")

        # Stop daemon gracefully
        entry.daemon.stop()

        # Wait for thread to finish (with timeout)
        entry.thread.join(timeout=10)

        if entry.thread.is_alive():
            logger.warning(
                f"Daemon thread did not stop gracefully for config {config_id}"
            )
        else:
            logger.info(f"✓ Daemon stopped for config {config_id}")

        # Save final stats if requested
        if save_stats:
            try:
                self._save_daemon_stats(config_id, entry)
            except Exception as e:
                logger.error(f"Failed to save final stats: {e}", exc_info=True)

        # Remove from tracking
        with self._lock:
            del self._daemons[config_id]

    def stop_all(self, timeout: float = 10) -> None:
        """
        Stop all running daemons gracefully.

        Args:
            timeout: Maximum time to wait for each daemon to stop
        """
        logger.info("Stopping all daemons...")

        with self._lock:
            config_ids = list(self._daemons.keys())

        for config_id in config_ids:
            try:
                self.stop_daemon(config_id, save_stats=True)
            except Exception as e:
                logger.error(f"Error stopping daemon {config_id}: {e}", exc_info=True)

        logger.info("✓ All daemons stopped")

    def shutdown(self, timeout: float = 10) -> None:
        """
        Shutdown the daemon manager and all daemons.

        Args:
            timeout: Maximum time to wait for shutdown
        """
        logger.info("Shutting down DaemonManager...")

        # Signal shutdown
        self._shutdown_event.set()

        # Stop all daemons
        self.stop_all(timeout=timeout)

        # Wait for background threads
        if self._stats_sync_thread:
            self._stats_sync_thread.join(timeout=5)
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

        logger.info("✓ DaemonManager shut down")

    def _format_daemon_status(self, entry: DaemonEntry, config_id: UUID) -> dict:
        """
        Format daemon status dictionary (lock-free helper).

        Args:
            entry: Daemon entry to format
            config_id: Watch configuration ID

        Returns:
            Status dictionary
        """
        stats = entry.daemon.stats
        uptime = (datetime.now() - entry.started_at).total_seconds()

        return {
            "config_id": str(config_id),
            "is_running": entry.thread.is_alive(),
            "uptime_seconds": int(uptime),
            "started_at": entry.started_at.isoformat(),
            "stats": {
                "files_processed": stats.files_processed,
                "files_skipped": stats.files_skipped,
                "files_failed": stats.files_failed,
                "files_retried": stats.files_retried,
                "last_activity": (
                    stats.last_activity.isoformat() if stats.last_activity else None
                ),
            },
            "restart_policy": {
                "crash_count": entry.restart_policy.crash_count,
                "restart_attempts": entry.restart_policy.restart_attempts,
                "last_crash_at": (
                    entry.restart_policy.last_crash_at.isoformat()
                    if entry.restart_policy.last_crash_at
                    else None
                ),
            },
            "retry_queue_size": len(entry.daemon.retry_queue),
        }

    def get_daemon_status(self, config_id: UUID) -> Optional[dict]:
        """
        Get runtime status for a specific daemon.

        Args:
            config_id: Watch configuration ID

        Returns:
            Status dictionary or None if not running
        """
        with self._lock:
            if config_id not in self._daemons:
                return None
            entry = self._daemons[config_id]

        # Format status outside the lock
        return self._format_daemon_status(entry, config_id)

    def get_all_status(self) -> dict:
        """
        Get status for all daemons.

        Returns:
            Dictionary with overall status and per-daemon status
        """
        # Get snapshot of all daemon entries with lock held (quick operation)
        with self._lock:
            entries = {
                config_id: entry for config_id, entry in self._daemons.items()
            }

        # Format statuses outside the lock to avoid nested locking
        daemon_statuses = {
            str(config_id): self._format_daemon_status(entry, config_id)
            for config_id, entry in entries.items()
        }

        running_count = sum(
            1 for status in daemon_statuses.values() if status["is_running"]
        )

        return {
            "total_daemons": len(daemon_statuses),
            "running_daemons": running_count,
            "daemons": daemon_statuses,
        }

    def _stats_sync_loop(self) -> None:
        """Background thread that syncs stats to database."""
        logger.info(
            f"Stats sync thread started (interval: {self._stats_sync_interval}s)"
        )

        while not self._shutdown_event.is_set():
            try:
                # Sync stats for all daemons
                with self._lock:
                    config_ids = list(self._daemons.keys())

                for config_id in config_ids:
                    try:
                        with self._lock:
                            if config_id not in self._daemons:
                                continue
                            entry = self._daemons[config_id]

                        self._save_daemon_stats(config_id, entry)
                    except Exception as e:
                        logger.error(
                            f"Failed to sync stats for {config_id}: {e}", exc_info=True
                        )

            except Exception as e:
                logger.error(f"Error in stats sync loop: {e}", exc_info=True)

            # Wait for next sync interval
            self._shutdown_event.wait(timeout=self._stats_sync_interval)

        logger.info("Stats sync thread stopped")

    def _health_check_loop(self) -> None:
        """Background thread that monitors daemon health and restarts crashed daemons."""
        logger.info(f"Health check thread started (interval: {self._health_check_interval}s)")

        while not self._shutdown_event.is_set():
            try:
                with self._lock:
                    config_ids = list(self._daemons.keys())

                for config_id in config_ids:
                    self._check_daemon_health(config_id)

            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)

            # Wait before next health check
            self._shutdown_event.wait(timeout=self._health_check_interval)

        logger.info("Health check thread stopped")

    def _check_daemon_health(self, config_id: UUID) -> None:
        """
        Check health of a single daemon and restart if crashed.

        Separated from _health_check_loop for testability.

        Args:
            config_id: Watch configuration ID to check
        """
        try:
            with self._lock:
                if config_id not in self._daemons:
                    return
                entry = self._daemons[config_id]

            # Check if thread is alive
            if not entry.thread.is_alive():
                logger.warning(f"Daemon crashed for config {config_id}")

                # Record crash
                entry.restart_policy.record_crash()

                # Attempt restart if policy allows
                if entry.restart_policy.should_restart():
                    logger.info(
                        f"Attempting to restart daemon for config {config_id}..."
                    )

                    try:
                        # Remove dead daemon
                        with self._lock:
                            del self._daemons[config_id]

                        # Load fresh config from DB
                        with db_session() as session:
                            repo = WatchConfigurationRepository(session)
                            config = repo.get(config_id)

                            if config and config.is_active:
                                self.start_daemon(config)
                                logger.info(
                                    f"✓ Restarted daemon for config {config_id}"
                                )
                            else:
                                logger.warning(
                                    f"Config {config_id} is no longer active, not restarting"
                                )
                    except Exception as e:
                        logger.error(
                            f"Failed to restart daemon for config {config_id}: {e}",
                            exc_info=True,
                        )
                else:
                    logger.error(
                        f"Exceeded restart attempts for config {config_id}, "
                        "marking as inactive"
                    )

                    # Mark as inactive in DB
                    try:
                        with db_session() as session:
                            repo = WatchConfigurationRepository(session)
                            repo.deactivate(config_id)
                            session.commit()
                    except Exception as e:
                        logger.error(
                            f"Failed to deactivate config: {e}",
                            exc_info=True,
                        )

                    # Remove from tracking
                    with self._lock:
                        if config_id in self._daemons:
                            del self._daemons[config_id]

        except Exception as e:
            logger.error(
                f"Error checking health for {config_id}: {e}", exc_info=True
            )

    def _save_daemon_stats(self, config_id: UUID, entry: DaemonEntry) -> None:
        """
        Save daemon stats to database.

        Args:
            config_id: Watch configuration ID
            entry: Daemon entry with stats
        """
        stats = entry.daemon.stats
        uptime = (datetime.now() - entry.started_at).total_seconds()

        stats_dict = {
            "started_at": entry.started_at.isoformat(),
            "files_processed": stats.files_processed,
            "files_skipped": stats.files_skipped,
            "files_failed": stats.files_failed,
            "files_retried": stats.files_retried,
            "last_activity": (
                stats.last_activity.isoformat() if stats.last_activity else None
            ),
            "uptime_seconds": int(uptime),
            "crash_count": entry.restart_policy.crash_count,
        }

        with db_session() as session:
            repo = WatchConfigurationRepository(session)
            repo.update_stats(config_id, stats_dict)
            session.commit()
