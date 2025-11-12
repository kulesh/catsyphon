"""
Directory watching daemon for automatic log ingestion.

Monitors a directory for new Claude Code conversation logs (.jsonl files)
and automatically ingests them into the database using the existing pipeline.
"""

import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.db.repositories.raw_log import RawLogRepository
from catsyphon.exceptions import DuplicateFileError
from catsyphon.parsers.registry import get_default_registry
from catsyphon.pipeline.ingestion import ingest_conversation
from catsyphon.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


@dataclass
class RetryEntry:
    """Represents a file that failed to process and needs retry."""

    file_path: Path
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    last_error: str = ""
    next_retry: Optional[datetime] = None


@dataclass
class WatcherStats:
    """Statistics for the watch daemon."""

    started_at: datetime = field(default_factory=datetime.now)
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_retried: int = 0
    last_activity: Optional[datetime] = None


class RetryQueue:
    """
    Manages retry logic for files that failed to process.

    Uses exponential backoff: 5min, 15min, 45min, then give up.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_interval: int = 300,  # 5 minutes
    ):
        self.max_retries = max_retries
        self.base_interval = base_interval
        self.queue: dict[str, RetryEntry] = {}

    def add(self, file_path: Path, error: str) -> None:
        """Add a failed file to the retry queue."""
        path_str = str(file_path)
        if path_str in self.queue:
            entry = self.queue[path_str]
            entry.attempts += 1
            entry.last_error = error
        else:
            entry = RetryEntry(file_path=file_path, last_error=error)
            entry.attempts = 1
            self.queue[path_str] = entry

        entry.last_attempt = datetime.now()
        entry.next_retry = self._calculate_next_retry(entry.attempts)

        logger.info(
            f"Added {file_path.name} to retry queue "
            f"(attempt {entry.attempts}/{self.max_retries})"
        )

    def _calculate_next_retry(self, attempts: int) -> datetime:
        """Calculate next retry time using exponential backoff."""
        # Exponential backoff: 5min, 15min, 45min
        delay_multiplier = 3 ** (attempts - 1)
        delay_seconds = self.base_interval * delay_multiplier
        return datetime.now() + timedelta(seconds=delay_seconds)

    def get_ready_files(self) -> list[RetryEntry]:
        """Get files that are ready for retry."""
        now = datetime.now()
        ready = []

        for entry in list(self.queue.values()):
            if entry.attempts >= self.max_retries:
                # Remove files that have exceeded max retries
                logger.warning(
                    f"Giving up on {entry.file_path.name} "
                    f"after {entry.attempts} attempts"
                )
                del self.queue[str(entry.file_path)]
                continue

            if entry.next_retry and entry.next_retry <= now:
                ready.append(entry)

        return ready

    def remove(self, file_path: Path) -> None:
        """Remove a file from the retry queue (after successful processing)."""
        path_str = str(file_path)
        if path_str in self.queue:
            del self.queue[path_str]

    def __len__(self) -> int:
        """Return the number of files in the retry queue."""
        return len(self.queue)


class FileWatcher(FileSystemEventHandler):
    """
    Watchdog event handler for monitoring .jsonl files.

    Processes new and modified .jsonl files automatically.
    """

    def __init__(
        self,
        project_name: Optional[str] = None,
        developer_username: Optional[str] = None,
        retry_queue: Optional[RetryQueue] = None,
        stats: Optional[WatcherStats] = None,
        debounce_seconds: float = 1.0,
    ):
        super().__init__()
        self.project_name = project_name
        self.developer_username = developer_username
        self.retry_queue = retry_queue or RetryQueue()
        self.stats = stats or WatcherStats()
        self.debounce_seconds = debounce_seconds

        # Track files being processed to avoid duplicate events
        self.processing: Set[str] = set()

        # In-memory cache of processed file hashes (for performance)
        self.processed_hashes: Set[str] = set()

        # Debounce tracking: file_path -> last_event_time
        self.last_events: dict[str, float] = {}

        # Parser registry
        self.parser_registry = get_default_registry()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self._handle_file_event(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self._handle_file_event(Path(event.src_path))

    def _handle_file_event(self, file_path: Path) -> None:
        """
        Handle a file event with debouncing.

        Debouncing prevents processing the same file multiple times
        when multiple rapid events are triggered (write, flush, close, etc.).
        """
        path_str = str(file_path)
        current_time = time.time()

        # Check if we recently processed an event for this file
        last_event_time = self.last_events.get(path_str, 0)
        if current_time - last_event_time < self.debounce_seconds:
            logger.debug(f"Debouncing event for {file_path.name}")
            return

        # Update last event time
        self.last_events[path_str] = current_time

        # Process the file in a separate thread to avoid blocking the observer
        thread = Thread(target=self._process_file, args=(file_path,), daemon=True)
        thread.start()

    def _process_file(self, file_path: Path) -> None:
        """Process a single file (called in background thread)."""
        path_str = str(file_path)

        # Check if already processing this file
        if path_str in self.processing:
            logger.debug(f"Already processing {file_path.name}, skipping")
            return

        self.processing.add(path_str)

        try:
            # Wait for file to finish writing (debounce at file level)
            time.sleep(self.debounce_seconds)

            # Check if file exists and is readable
            if not file_path.exists():
                logger.debug(f"File no longer exists: {file_path.name}")
                return

            logger.info(f"Detected file: {file_path.name}")

            # Calculate file hash
            try:
                file_hash = calculate_file_hash(file_path)
            except Exception as e:
                logger.error(f"Failed to calculate hash for {file_path.name}: {e}")
                return

            # Check if already processed (in-memory cache first)
            if file_hash in self.processed_hashes:
                logger.debug(f"Skipped {file_path.name} (already processed in session)")
                self.stats.files_skipped += 1
                self.stats.last_activity = datetime.now()
                return

            # Check database for duplicates
            with db_session() as session:
                raw_log_repo = RawLogRepository(session)

                if raw_log_repo.exists_by_file_hash(file_hash):
                    logger.debug(f"Skipped {file_path.name} (duplicate in database)")
                    self.stats.files_skipped += 1
                    self.stats.last_activity = datetime.now()
                    # Add to cache to avoid future database checks
                    self.processed_hashes.add(file_hash)
                    return

                # Parse and ingest the file
                try:
                    # Parse conversation (auto-detects format)
                    parsed = self.parser_registry.parse(file_path)

                    # Ingest into database
                    conversation_id = ingest_conversation(
                        session=session,
                        parsed=parsed,
                        project_name=self.project_name,
                        developer_username=self.developer_username,
                        file_path=file_path,
                        skip_duplicates=True,
                    )

                    logger.info(
                        f"✓ Processed {file_path.name} → conversation {conversation_id}"
                    )
                    self.stats.files_processed += 1
                    self.stats.last_activity = datetime.now()

                    # Add to cache
                    self.processed_hashes.add(file_hash)

                    # Remove from retry queue if present
                    if self.retry_queue:
                        self.retry_queue.remove(file_path)

                except DuplicateFileError:
                    # This can happen if file was added to DB by another process
                    logger.debug(f"Skipped {file_path.name} (duplicate detected)")
                    self.stats.files_skipped += 1
                    self.stats.last_activity = datetime.now()
                    self.processed_hashes.add(file_hash)

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    logger.error(f"✗ Failed to process {file_path.name}: {error_msg}")
                    self.stats.files_failed += 1
                    self.stats.last_activity = datetime.now()

                    # Add to retry queue
                    if self.retry_queue:
                        self.retry_queue.add(file_path, error_msg)

        finally:
            self.processing.discard(path_str)


class WatcherDaemon:
    """
    Main watch daemon controller.

    Manages the watchdog observer, retry queue, and graceful shutdown.
    """

    def __init__(
        self,
        directory: Path,
        project_name: Optional[str] = None,
        developer_username: Optional[str] = None,
        poll_interval: int = 2,
        retry_interval: int = 300,
        max_retries: int = 3,
        debounce_seconds: float = 1.0,
    ):
        self.directory = directory
        self.project_name = project_name
        self.developer_username = developer_username
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.debounce_seconds = debounce_seconds

        # Create components
        self.stats = WatcherStats()
        self.retry_queue = RetryQueue(
            max_retries=max_retries, base_interval=retry_interval
        )
        self.event_handler = FileWatcher(
            project_name=project_name,
            developer_username=developer_username,
            retry_queue=self.retry_queue,
            stats=self.stats,
            debounce_seconds=debounce_seconds,
        )

        # Watchdog observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(directory), recursive=True)

        # Shutdown event
        self.shutdown_event = Event()

        # Retry thread
        self.retry_thread: Optional[Thread] = None

    def start(self) -> None:
        """Start the watch daemon."""
        logger.info(f"Starting watch daemon for directory: {self.directory}")
        logger.info(f"Project: {self.project_name or 'default'}")
        logger.info(f"Developer: {self.developer_username or 'default'}")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start watchdog observer
        self.observer.start()
        logger.info("✓ Observer started")

        # Start retry thread
        self.retry_thread = Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.start()
        logger.info("✓ Retry thread started")

        # Main loop - just wait for shutdown
        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the watch daemon gracefully."""
        logger.info("Stopping watch daemon...")
        self.shutdown_event.set()

        # Stop observer
        self.observer.stop()
        self.observer.join(timeout=5)
        logger.info("✓ Observer stopped")

        logger.info("✓ Watch daemon stopped")

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def _retry_loop(self) -> None:
        """Background thread that retries failed files."""
        logger.info(f"Retry thread started (interval: {self.retry_interval}s)")

        while not self.shutdown_event.is_set():
            try:
                # Check for files ready to retry
                ready_files = self.retry_queue.get_ready_files()

                for entry in ready_files:
                    if self.shutdown_event.is_set():
                        break

                    logger.info(
                        f"Retrying {entry.file_path.name} "
                        f"(attempt {entry.attempts + 1})"
                    )

                    # Process the file
                    self.event_handler._process_file(entry.file_path)
                    self.stats.files_retried += 1

                # Sleep for a bit before checking again
                self.shutdown_event.wait(timeout=self.retry_interval)

            except Exception as e:
                logger.error(f"Error in retry loop: {e}", exc_info=True)
                self.shutdown_event.wait(timeout=60)  # Wait a minute before retrying


def start_watching(
    directory: Path,
    project_name: Optional[str] = None,
    developer_username: Optional[str] = None,
    poll_interval: int = 2,
    retry_interval: int = 300,
    max_retries: int = 3,
    debounce_seconds: float = 1.0,
    verbose: bool = False,
) -> None:
    """
    Start watching a directory for new conversation logs.

    Args:
        directory: Directory to watch
        project_name: Project name to assign to conversations
        developer_username: Developer username to assign to conversations
        poll_interval: File system polling interval in seconds
        retry_interval: Retry failed files every N seconds
        max_retries: Maximum number of retry attempts
        debounce_seconds: Wait time after file event before processing
        verbose: Enable verbose logging (includes SQL queries)
    """
    # Validate directory
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.watch_log_file),
        ],
    )

    # Suppress SQLAlchemy query logs unless in verbose mode
    if not verbose:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Create and start daemon
    daemon = WatcherDaemon(
        directory=directory,
        project_name=project_name,
        developer_username=developer_username,
        poll_interval=poll_interval,
        retry_interval=retry_interval,
        max_retries=max_retries,
        debounce_seconds=debounce_seconds,
    )

    daemon.start()
