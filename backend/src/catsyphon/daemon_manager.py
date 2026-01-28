"""
Multi-directory watch daemon manager.

Manages multiple WatcherDaemon instances, allowing the web UI to control
watch operations across multiple directories.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from multiprocessing import Process, Queue
from pathlib import Path
from queue import Empty
from threading import Event, Lock, Thread
from typing import Any, Dict, Optional
from uuid import UUID

import psutil
import requests
from sqlalchemy.exc import OperationalError

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.db.repositories.workspace import WorkspaceRepository
from catsyphon.models.db import WatchConfiguration
from catsyphon.watch import run_daemon_process

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

    process: Process
    config_id: UUID
    pid: Optional[int] = None
    started_at: datetime = field(default_factory=datetime.now)
    restart_policy: RestartPolicy = field(default_factory=RestartPolicy)


def _fetch_credentials_http(workspace_id: UUID, api_url: str) -> tuple[str, str]:
    """
    Make the actual HTTP request to fetch credentials.

    This is run in a thread pool to avoid blocking the main request handler.
    """
    url = f"{api_url}/collectors/builtin/credentials"
    params = {"workspace_id": str(workspace_id)}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["collector_id"], data["api_key"]


def fetch_builtin_credentials(
    workspace_id: UUID,
    api_url: str = "http://localhost:8000",
    max_retries: int = 5,
    initial_delay: float = 0.5,
) -> tuple[str, str]:
    """
    Fetch built-in collector credentials via HTTP API with retry.

    Uses a ThreadPoolExecutor to avoid blocking the main request handler
    when the server makes a request to itself. Retries with exponential
    backoff to handle server startup race conditions.

    Args:
        workspace_id: Workspace UUID
        api_url: Base URL of the CatSyphon API
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before first retry (default: 0.5)

    Returns:
        Tuple of (collector_id, api_key)

    Raises:
        ValueError: If credentials cannot be fetched after all retries
    """
    from concurrent.futures import (
        ThreadPoolExecutor,
    )
    from concurrent.futures import (
        TimeoutError as FuturesTimeoutError,
    )

    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            # Run HTTP request in a separate thread to avoid blocking the main worker
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_fetch_credentials_http, workspace_id, api_url)
                return future.result(timeout=10)  # Shorter timeout for faster retries
        except FuturesTimeoutError:
            last_error = Exception(
                f"Timeout fetching builtin credentials from {api_url}"
            )
        except requests.exceptions.RequestException as e:
            last_error = e
        except Exception as e:
            last_error = e

        # Log retry attempt (but not after final attempt)
        if attempt < max_retries:
            logger.warning(
                f"Failed to fetch credentials (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.1f}s: {last_error}"
            )
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        else:
            logger.error(
                f"Failed to fetch credentials after {max_retries + 1} attempts: {last_error}"
            )

    raise ValueError(
        f"Could not fetch builtin credentials after {max_retries + 1} attempts: {last_error}"
    )


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

    def __init__(
        self,
        stats_sync_interval: int | None = None,
        health_check_interval: int | None = None,
    ):
        """
        Initialize the daemon manager.

        Args:
            stats_sync_interval: How often to sync stats to DB (seconds).
                Defaults to settings.daemon_stats_sync_interval.
            health_check_interval: How often to check daemon health (seconds).
                Defaults to settings.daemon_health_check_interval.
        """
        self._daemons: Dict[UUID, DaemonEntry] = {}
        self._stats_queues: Dict[UUID, "Queue[dict[str, Any]]"] = (
            {}
        )  # config_id -> stats queue
        self._lock = Lock()
        self._shutdown_event = Event()
        self._stats_sync_interval = (
            stats_sync_interval
            if stats_sync_interval is not None
            else settings.daemon_stats_sync_interval
        )
        self._health_check_interval = (
            health_check_interval
            if health_check_interval is not None
            else settings.daemon_health_check_interval
        )

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
            # Get default workspace
            workspace_repo = WorkspaceRepository(session)
            workspaces = workspace_repo.get_all(limit=1)

            if not workspaces:
                logger.info("No workspace found - skipping watch configuration loading")
                return

            workspace_id = workspaces[0].id

            repo = WatchConfigurationRepository(session)
            active_configs = repo.get_all_active(workspace_id)

            if not active_configs:
                logger.info("No active watch configurations found")
                return

            logger.info(f"Found {len(active_configs)} active configuration(s)")

            # Reconcile PIDs: clear stale PIDs before starting daemons
            stale_pids_cleared = 0
            for config in active_configs:
                if config.daemon_pid is not None:
                    # Check if PID still exists
                    if not psutil.pid_exists(config.daemon_pid):
                        logger.warning(
                            f"Stale PID {config.daemon_pid} found for config {config.id}, "
                            "clearing (process was killed externally)"
                        )
                        try:
                            repo.clear_daemon_pid(config.id)
                            stale_pids_cleared += 1
                        except Exception as e:
                            logger.error(
                                f"Failed to clear stale PID for {config.id}: {e}",
                                exc_info=True,
                            )

            if stale_pids_cleared > 0:
                session.commit()
                logger.info(f"Cleared {stale_pids_cleared} stale PID(s)")

            # Start daemons for all active configs
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

        # Extract API configuration (all watch daemons use API mode)
        api_url = extra_config.get("api_url", "http://localhost:8000")
        api_key = extra_config.get("api_key", "")
        collector_id = extra_config.get("collector_id", "")
        api_batch_size = extra_config.get("api_batch_size", 20)

        # Always fetch builtin credentials if not provided
        if not api_key or not collector_id:
            logger.info(f"Fetching API credentials for {config.directory}")
            try:
                collector_id, api_key = fetch_builtin_credentials(
                    workspace_id=config.workspace_id,
                    api_url=api_url,
                )
                logger.info(
                    f"✓ Fetched builtin collector credentials (id: {collector_id[:8]}...)"
                )
            except Exception as e:
                logger.error(f"Failed to fetch builtin credentials: {e}")
                raise ValueError(f"Watch daemon requires API credentials: {e}") from e

        # Create stats queue for IPC
        stats_queue: "Queue[dict[str, Any]]" = Queue()

        # Create daemon process
        process = Process(
            target=run_daemon_process,
            args=(
                config_id,
                directory,
                config.project.name if config.project else None,
                config.developer.username if config.developer else None,
                poll_interval,
                retry_interval,
                max_retries,
                debounce_seconds,
                config.enable_tagging,
                stats_queue,
                # API configuration
                api_url,
                api_key,
                collector_id,
                api_batch_size,
                # Multi-tenancy workspace
                config.workspace_id,
            ),
            name=f"watcher-{config_id}",
            daemon=False,  # Not a daemon process - we want clean shutdown
        )

        # Start process
        process.start()

        # Wait for process to actually start and get PID
        time.sleep(0.5)  # Brief wait for process to initialize

        if not process.is_alive():
            raise Exception("Daemon process failed to start")

        pid = process.pid
        if pid is None:
            raise Exception("Daemon process started but PID is None")

        logger.info(f"Daemon process started with PID {pid}")

        # Store PID in database
        try:
            with db_session() as session:
                repo = WatchConfigurationRepository(session)
                repo.set_daemon_pid(config_id, pid)
                session.commit()
                logger.debug(f"Stored PID {pid} in database for config {config_id}")
        except Exception as e:
            # In test/sandbox environments DB may be unavailable; continue with in-memory tracking
            logger.error(f"Failed to store PID in database: {e}", exc_info=True)

        # Track daemon
        with self._lock:
            self._daemons[config_id] = DaemonEntry(
                process=process,
                config_id=config_id,
                pid=pid,
            )
            self._stats_queues[config_id] = stats_queue

        logger.info(
            f"✓ Started daemon for {config.directory} (config {config_id}, PID {pid})"
        )

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

        logger.info(f"Stopping daemon for config {config_id} (PID {entry.pid})...")

        # Terminate process gracefully (sends SIGTERM)
        entry.process.terminate()

        # Wait for process to finish (with timeout from settings)
        entry.process.join(timeout=settings.daemon_termination_timeout)

        if entry.process.is_alive():
            logger.warning(
                f"Daemon process did not stop gracefully for config {config_id}, "
                "sending SIGKILL"
            )
            entry.process.kill()
            entry.process.join(timeout=5)  # Fixed short timeout for SIGKILL
        else:
            logger.info(f"✓ Daemon stopped for config {config_id}")

        # Drain stats queue and save final stats
        if save_stats:
            with self._lock:
                stats_queue = self._stats_queues.get(config_id)

            if stats_queue:
                try:
                    # Drain all remaining stats from queue
                    while True:
                        try:
                            stats_snapshot = stats_queue.get_nowait()
                            self._save_daemon_stats(config_id, stats_snapshot)
                        except Empty:
                            break  # Queue is empty
                except Exception as e:
                    logger.error(
                        f"Failed to drain stats queue for {config_id}: {e}",
                        exc_info=True,
                    )

        # Clear PID from database
        try:
            with db_session() as session:
                repo = WatchConfigurationRepository(session)
                repo.clear_daemon_pid(config_id)
                session.commit()
                logger.debug(f"Cleared PID from database for config {config_id}")
        except OperationalError as e:
            logger.warning(
                "Failed to clear PID from database (database unavailable): %s", e
            )
        except Exception as e:
            logger.error(f"Failed to clear PID from database: {e}", exc_info=True)

        # Remove from tracking
        with self._lock:
            del self._daemons[config_id]
            if config_id in self._stats_queues:
                del self._stats_queues[config_id]

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

    def _format_daemon_status(
        self, entry: DaemonEntry, config_id: UUID
    ) -> dict[str, Any]:
        """
        Format daemon status dictionary (lock-free helper).

        Args:
            entry: Daemon entry to format
            config_id: Watch configuration ID

        Returns:
            Status dictionary
        """
        uptime = (datetime.now() - entry.started_at).total_seconds()
        is_running = entry.process.is_alive() if entry.process else False
        pid_exists = psutil.pid_exists(entry.pid) if entry.pid else False

        # Get stats from database (latest synced values)
        stats = None
        try:
            with db_session() as session:
                repo = WatchConfigurationRepository(session)
                config = repo.get(config_id)
                if config and config.stats:
                    stats = config.stats
        except Exception as e:
            logger.error(f"Failed to fetch stats for {config_id}: {e}", exc_info=True)

        return {
            "config_id": str(config_id),
            "is_running": is_running and pid_exists,
            "pid": entry.pid,
            "uptime_seconds": int(uptime),
            "started_at": entry.started_at.isoformat(),
            "restart_policy": {
                "crash_count": entry.restart_policy.crash_count,
                "restart_attempts": entry.restart_policy.restart_attempts,
                "last_crash_at": (
                    entry.restart_policy.last_crash_at.isoformat()
                    if entry.restart_policy.last_crash_at
                    else None
                ),
            },
            "stats": stats,  # Stats from database (synced periodically)
        }

    def get_daemon_status(self, config_id: UUID) -> Optional[dict[str, Any]]:
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

    def get_all_status(self) -> dict[str, Any]:
        """
        Get status for all daemons.

        Returns:
            Dictionary with overall status and per-daemon status
        """
        # Get snapshot of all daemon entries with lock held (quick operation)
        with self._lock:
            entries = {config_id: entry for config_id, entry in self._daemons.items()}

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
                # Get snapshot of config_ids and queues
                with self._lock:
                    queue_items = list(self._stats_queues.items())

                # Read stats from all queues (non-blocking)
                for config_id, stats_queue in queue_items:
                    try:
                        # Drain all available stats snapshots from queue
                        while True:
                            try:
                                stats_snapshot = stats_queue.get_nowait()
                                self._save_daemon_stats(config_id, stats_snapshot)
                            except Empty:
                                break  # No more stats in queue
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
        logger.info(
            f"Health check thread started (interval: {self._health_check_interval}s)"
        )

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

            # Check if process is alive AND PID exists
            process_alive = entry.process.is_alive()
            pid_exists = psutil.pid_exists(entry.pid) if entry.pid else False

            if not process_alive or not pid_exists:
                if not process_alive:
                    logger.warning(
                        f"Daemon process crashed for config {config_id} (process not alive)"
                    )
                elif not pid_exists:
                    logger.warning(
                        f"Daemon process killed externally for config {config_id} (PID {entry.pid} not found)"
                    )

                # Record crash
                entry.restart_policy.record_crash()

                # Attempt restart if policy allows
                if entry.restart_policy.should_restart():
                    logger.info(
                        f"Attempting to restart daemon for config {config_id}..."
                    )

                    try:
                        # Clear PID and remove dead daemon
                        with db_session() as session:
                            repo = WatchConfigurationRepository(session)
                            repo.clear_daemon_pid(config_id)
                            session.commit()

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

                    # Mark as inactive and clear PID in DB
                    try:
                        with db_session() as session:
                            repo = WatchConfigurationRepository(session)
                            repo.deactivate(config_id)
                            repo.clear_daemon_pid(config_id)
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
            logger.error(f"Error checking health for {config_id}: {e}", exc_info=True)

    def _save_daemon_stats(
        self, config_id: UUID, stats_snapshot: dict[str, Any]
    ) -> None:
        """
        Save daemon stats snapshot to database.

        Args:
            config_id: Watch configuration ID
            stats_snapshot: Stats dictionary from WatcherStats.to_dict()
        """
        try:
            with db_session() as session:
                repo = WatchConfigurationRepository(session)
                repo.update_stats(config_id, stats_snapshot)
                session.commit()
                logger.debug(f"Saved stats for config {config_id}: {stats_snapshot}")
        except Exception as e:
            logger.error(f"Failed to save stats for {config_id}: {e}", exc_info=True)
