"""
Directory watching daemon for automatic log ingestion.

Monitors a directory for new Claude Code conversation logs (.jsonl files)
and automatically ingests them into the database using the existing pipeline.
"""

import logging
import os
import platform
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from multiprocessing import Queue
from pathlib import Path
from queue import Empty
from threading import Event, Thread
from typing import TYPE_CHECKING, Any, Optional, Set
from uuid import UUID

if TYPE_CHECKING:
    from catsyphon.tagging.pipeline import TaggingPipeline

from watchdog.events import FileSystemEvent, FileSystemEventHandler

# Use PollingObserver on macOS to avoid fsevents C extension crashes
# See bug catsyphon-7ri: fsevents has thread safety issues that cause
# "Fatal Python error: Bus error" during rapid observer start/stop cycles
if platform.system() == "Darwin":  # macOS
    from watchdog.observers.polling import PollingObserver as Observer
else:
    from watchdog.observers import Observer

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.db.repositories.raw_log import RawLogRepository
from catsyphon.exceptions import DuplicateFileError
from catsyphon.parsers.incremental import ChangeType, detect_file_change_type
from catsyphon.parsers.registry import get_default_registry
from catsyphon.pipeline.ingestion import (
    ingest_conversation,
    ingest_messages_incremental,
)

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

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for serialization."""
        return {
            "started_at": self.started_at.isoformat(),
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "files_retried": self.files_retried,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
        }


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
        tagging_pipeline: Optional["TaggingPipeline"] = None,
        config_id: Optional[UUID] = None,
        stats_lock: Optional[threading.Lock] = None,
    ):
        super().__init__()
        self.project_name = project_name
        self.developer_username = developer_username
        self.retry_queue = retry_queue or RetryQueue()
        self.stats = stats or WatcherStats()
        self.debounce_seconds = debounce_seconds
        self.tagging_pipeline = tagging_pipeline
        self.config_id = config_id  # Watch configuration ID for tracking
        self._stats_lock = stats_lock or threading.Lock()

        # Track files being processed to avoid duplicate events
        self.processing: Set[str] = set()
        self._processing_lock = threading.Lock()  # Protects processing set

        # In-memory cache of processed file hashes (for performance)
        self.processed_hashes: Set[str] = set()

        # Debounce tracking: file_path -> last_event_time
        self.last_events: dict[str, float] = {}

        # Parser registry
        self.parser_registry = get_default_registry()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        path = str(event.src_path)
        if not event.is_directory and path.endswith(".jsonl"):
            self._handle_file_event(Path(path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        path = str(event.src_path)
        if not event.is_directory and path.endswith(".jsonl"):
            self._handle_file_event(Path(path))

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename events."""
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        dest_path = Path(event.dest_path)

        # Only handle .jsonl files
        if not (src_path.suffix == ".jsonl" or dest_path.suffix == ".jsonl"):
            return

        # Update database file_path from src to dest
        self._handle_file_rename(src_path, dest_path)

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

        # Atomically check if already processing this file and mark as processing
        # This prevents race condition where multiple threads try to process same file
        with self._processing_lock:
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

            # Check database for existing raw_log
            with db_session() as session:
                raw_log_repo = RawLogRepository(session)

                # Check if we've seen this file before (by path)
                existing_raw_log = raw_log_repo.get_by_file_path(str(file_path))

                if existing_raw_log:
                    # File exists in database - detect change type
                    try:
                        change_type = detect_file_change_type(
                            file_path,
                            existing_raw_log.last_processed_offset,
                            existing_raw_log.file_size_bytes,
                            existing_raw_log.partial_hash,
                        )

                        logger.debug(
                            f"Change detection: {change_type.value} "
                            f"for {file_path.name}"
                        )

                        if change_type == ChangeType.UNCHANGED:
                            logger.debug(
                                f"Skipped {file_path.name} (no changes detected)"
                            )
                            with self._stats_lock:
                                self.stats.files_skipped += 1
                                self.stats.last_activity = datetime.now()
                            return

                        elif change_type == ChangeType.APPEND:
                            # Incremental update: parse only new content
                            logger.info(f"Incremental update for {file_path.name}")
                            try:
                                self._process_incremental_update(
                                    session, file_path, existing_raw_log
                                )
                                with self._stats_lock:
                                    self.stats.files_processed += 1
                                    self.stats.last_activity = datetime.now()
                                return
                            except Exception as e:
                                # Fall back to full reparse on error
                                logger.warning(
                                    f"Incremental update failed for "
                                    f"{file_path.name}: {e}, "
                                    f"falling back to full reparse"
                                )
                                # Continue to full reparse below

                        # TRUNCATE or REWRITE: full reparse required
                        logger.info(
                            f"Full reparse required for {file_path.name} "
                            f"({change_type.value})"
                        )
                    except Exception as e:
                        # Change detection failed - fall back to full reparse
                        logger.warning(
                            f"Change detection failed for {file_path.name}: {e}, "
                            "falling back to full reparse"
                        )
                        # Continue to full reparse below

                # Parse and ingest the file (full parse)
                try:
                    # Parse conversation (auto-detects format)
                    parsed = self.parser_registry.parse(file_path)

                    # Run tagging if enabled
                    tags = None
                    if self.tagging_pipeline:
                        try:
                            tags = self.tagging_pipeline.tag_conversation(parsed)
                            logger.debug(
                                f"Tagged {file_path.name}: "
                                f"intent={tags.get('intent')}, "
                                f"outcome={tags.get('outcome')}, "
                                f"sentiment={tags.get('sentiment')}"
                            )
                        except Exception as tag_error:
                            logger.warning(
                                f"Tagging failed for {file_path.name}: {tag_error}"
                            )
                            tags = None  # Continue without tags

                    # Determine update mode
                    # - If raw_log exists: use "replace" to update existing tracking
                    # - If no raw_log: use "replace" to create raw_log (don't skip!)
                    # This ensures files are always ingested, even on fresh DB
                    update_mode = "replace"

                    # Ingest into database
                    conversation = ingest_conversation(
                        session=session,
                        parsed=parsed,
                        project_name=self.project_name,
                        developer_username=self.developer_username,
                        file_path=file_path,
                        tags=tags,
                        skip_duplicates=True,
                        update_mode=update_mode,
                        source_type="watch",
                        source_config_id=self.config_id,
                        created_by=None,  # System-triggered
                    )

                    logger.info(
                        f"✓ Processed {file_path.name} → conversation {conversation.id}"
                    )
                    with self._stats_lock:
                        self.stats.files_processed += 1
                        self.stats.last_activity = datetime.now()

                    # Remove from retry queue if present
                    if self.retry_queue:
                        self.retry_queue.remove(file_path)

                except DuplicateFileError:
                    # This can happen if file was added to DB by another process
                    logger.debug(f"Skipped {file_path.name} (duplicate detected)")
                    with self._stats_lock:
                        self.stats.files_skipped += 1
                        self.stats.last_activity = datetime.now()

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    logger.error(f"✗ Failed to process {file_path.name}: {error_msg}")
                    with self._stats_lock:
                        self.stats.files_failed += 1
                        self.stats.last_activity = datetime.now()

                    # Add to retry queue
                    if self.retry_queue:
                        self.retry_queue.add(file_path, error_msg)

        finally:
            self.processing.discard(path_str)

    def _process_incremental_update(
        self, session: Any, file_path: Path, existing_raw_log: Any
    ) -> None:
        """
        Process incremental update using parse_incremental().

        This method implements the fast path for file appends, parsing
        only NEW content and updating the database incrementally.

        Args:
            session: Database session
            file_path: Path to the log file
            existing_raw_log: Existing RawLog with state tracking

        Raises:
            Exception: If incremental parsing fails (caller will fall back to full reparse)
        """
        logger.debug(
            f"Incremental parse: offset={existing_raw_log.last_processed_offset}, "
            f"line={existing_raw_log.last_processed_line}"
        )

        # Find parser that supports incremental parsing for this file
        parser = self.parser_registry.find_incremental_parser(file_path)

        if parser is None:
            # No incremental parser available, raise to trigger full reparse
            logger.warning(
                f"No incremental parser found for {file_path.name}, falling back to full parse"
            )
            raise ValueError("No incremental parser available for this file format")

        # Parse only NEW content
        incremental_result = parser.parse_incremental(
            file_path,
            existing_raw_log.last_processed_offset,
            existing_raw_log.last_processed_line,
        )

        if not incremental_result.new_messages:
            logger.debug(f"No new messages in {file_path.name}")
            return

        logger.info(
            f"Incremental parse: {len(incremental_result.new_messages)} new messages "
            f"in {file_path.name}"
        )

        # Ingest only new messages
        conversation = ingest_messages_incremental(
            session=session,
            incremental_result=incremental_result,
            conversation_id=str(existing_raw_log.conversation_id),
            raw_log_id=str(existing_raw_log.id),
            tags=None,  # TODO: Support tagging for incremental updates
            source_type="watch",
            source_config_id=self.config_id,
            created_by=None,  # System-triggered
        )

        logger.info(
            f"✓ Incremental update: {file_path.name} → conversation {conversation.id} "
            f"(+{len(incremental_result.new_messages)} messages)"
        )

    def _handle_file_rename(self, src_path: Path, dest_path: Path) -> None:
        """
        Update raw_log.file_path when a file is renamed.

        Args:
            src_path: Original file path before rename
            dest_path: New file path after rename
        """
        from catsyphon.db.connection import db_session
        from catsyphon.db.repositories.raw_log import RawLogRepository

        try:
            with db_session() as session:
                raw_log_repo = RawLogRepository(session)

                # Find raw_log by old path
                raw_log = raw_log_repo.get_by_file_path(str(src_path))

                if raw_log:
                    logger.info(
                        f"File renamed: {src_path.name} → {dest_path.name}"
                    )
                    # Update to new path
                    raw_log.file_path = str(dest_path)
                    session.commit()

                    # Process the renamed file to catch any pending changes
                    self._handle_file_event(dest_path)
                else:
                    logger.debug(
                        f"Rename detected but no raw_log found for {src_path.name}, "
                        f"treating {dest_path.name} as new file"
                    )
                    # Not tracked yet - process as new file
                    self._handle_file_event(dest_path)

        except Exception as e:
            logger.error(f"Error handling file rename: {e}")
            # Fallback: process as new file
            self._handle_file_event(dest_path)


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
        enable_tagging: bool = False,
        config_id: Optional[UUID] = None,
        stats_queue: Optional["Queue[dict[str, Any]]"] = None,
    ):
        self.directory = directory
        self.project_name = project_name
        self.developer_username = developer_username
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.debounce_seconds = debounce_seconds
        self.enable_tagging = enable_tagging
        self.config_id = config_id
        self.stats_queue = stats_queue
        self._stats_lock = threading.Lock()  # Protects stats from concurrent updates

        # Initialize tagging pipeline if enabled
        tagging_pipeline = None
        if enable_tagging:
            from pathlib import Path

            from catsyphon.tagging import TaggingPipeline

            tagging_pipeline = TaggingPipeline(
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
                cache_dir=Path(settings.tagging_cache_dir),
                cache_ttl_days=settings.tagging_cache_ttl_days,
                enable_cache=settings.tagging_enable_cache,
            )
            logger.info("✓ LLM tagging pipeline initialized")

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
            tagging_pipeline=tagging_pipeline,
            config_id=config_id,
            stats_lock=self._stats_lock,
        )

        # Watchdog observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(directory), recursive=True)

        # Shutdown event
        self.shutdown_event = Event()

        # Background threads
        self.retry_thread: Optional[Thread] = None
        self.stats_push_thread: Optional[Thread] = None

    def start(self, blocking: bool = True) -> None:
        """
        Start the watch daemon.

        Args:
            blocking: If True, blocks until shutdown. If False, returns immediately.
        """
        logger.info(f"Starting watch daemon for directory: {self.directory}")
        logger.info(f"Project: {self.project_name or 'default'}")
        logger.info(f"Developer: {self.developer_username or 'default'}")

        # Setup signal handlers only in blocking mode
        # (DaemonManager handles signals when running multiple daemons)
        if blocking:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

        # Start watchdog observer
        self.observer.start()
        logger.info("✓ Observer started")

        # Scan existing files for changes during downtime
        self._scan_existing_files()

        # Start retry thread (not daemon - we want clean shutdown)
        self.retry_thread = Thread(target=self._retry_loop, daemon=False)
        self.retry_thread.start()
        logger.info("✓ Retry thread started")

        # Start stats push thread if queue is provided
        if self.stats_queue:
            self.stats_push_thread = Thread(target=self._stats_push_loop, daemon=False)
            self.stats_push_thread.start()
            logger.info("✓ Stats push thread started")

        # Main loop - only block if requested
        if blocking:
            try:
                while not self.shutdown_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
        else:
            logger.info("Daemon started in non-blocking mode")

    def stop(self) -> None:
        """Stop the watch daemon gracefully."""
        logger.info("Stopping watch daemon...")
        self.shutdown_event.set()

        # Stop observer with proper error handling
        try:
            self.observer.stop()
            # Reduced timeout for faster test execution
            self.observer.join(timeout=3)
            if self.observer.is_alive():
                logger.warning("Observer thread did not stop cleanly")
            else:
                logger.info("✓ Observer stopped")
        except Exception as e:
            logger.error(f"Error stopping observer: {e}", exc_info=True)

        # Wait for retry thread to finish
        if self.retry_thread and self.retry_thread.is_alive():
            self.retry_thread.join(timeout=2)
            logger.info("✓ Retry thread stopped")

        # Wait for stats push thread to finish
        if self.stats_push_thread and self.stats_push_thread.is_alive():
            self.stats_push_thread.join(timeout=2)
            logger.info("✓ Stats push thread stopped")

        logger.info("✓ Watch daemon stopped")

    def is_running(self) -> bool:
        """
        Check if daemon is running.

        Returns:
            True if observer is running, False otherwise
        """
        return self.observer.is_alive() if self.observer else False

    def get_stats_snapshot(self) -> dict[str, Any]:
        """
        Get current statistics snapshot (thread-safe).

        Returns:
            Dictionary with current stats
        """
        with self._stats_lock:
            return {
                "started_at": self.stats.started_at.isoformat(),
                "files_processed": self.stats.files_processed,
                "files_skipped": self.stats.files_skipped,
                "files_failed": self.stats.files_failed,
                "files_retried": self.stats.files_retried,
                "last_activity": (
                    self.stats.last_activity.isoformat()
                    if self.stats.last_activity
                    else None
                ),
                "retry_queue_size": len(self.retry_queue),
            }

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def _stats_push_loop(self) -> None:
        """
        Background thread that pushes stats to queue every 30 seconds.

        Stats are sent to parent process via multiprocessing.Queue for persistence.
        """
        logger.info("Stats push thread started (interval: 30s)")

        while not self.shutdown_event.is_set():
            try:
                if self.stats_queue:
                    # Get thread-safe snapshot of stats
                    with self._stats_lock:
                        stats_snapshot = self.stats.to_dict()

                    # Push to queue (non-blocking)
                    try:
                        self.stats_queue.put_nowait(stats_snapshot)
                        logger.debug(f"Pushed stats to queue: {stats_snapshot}")
                    except Exception as e:
                        logger.error(f"Failed to push stats to queue: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error in stats push loop: {e}", exc_info=True)

            # Wait 30 seconds before next push
            self.shutdown_event.wait(timeout=30)

        logger.info("Stats push thread stopped")

    def _scan_existing_files(self) -> None:
        """
        Scan directory for all .jsonl files and process as needed.

        This method handles two scenarios during daemon startup:
        1. Files already tracked in database - check for changes (APPEND/TRUNCATE/etc)
        2. Files on disk not yet in database - ingest as new files

        Called once during daemon startup to detect changes that occurred
        while the daemon was not running.
        """
        logger.info(f"Scanning directory: {self.directory}...")

        from catsyphon.db.connection import db_session
        from catsyphon.db.repositories.raw_log import RawLogRepository
        from catsyphon.parsers.incremental import ChangeType, detect_file_change_type

        try:
            with db_session() as session:
                raw_log_repo = RawLogRepository(session)

                # Resolve symlinks to match how files are stored in database
                resolved_dir = self.directory.resolve()

                # PHASE 1: Get all tracked files from database
                tracked_files = raw_log_repo.get_files_in_directory(str(resolved_dir))
                tracked_paths = {Path(raw_log.file_path) for raw_log in tracked_files}

                logger.info(f"Found {len(tracked_files)} tracked files in database")

                # PHASE 2: Scan filesystem for all .jsonl files
                all_jsonl_files = list(resolved_dir.rglob("*.jsonl"))
                logger.info(f"Found {len(all_jsonl_files)} .jsonl files on disk")

                # PHASE 3: Identify new files not yet tracked
                new_files = [f for f in all_jsonl_files if f not in tracked_paths]

                if new_files:
                    logger.info(f"Found {len(new_files)} new files to ingest")
                    # Process new files asynchronously to avoid blocking daemon startup
                    # Spawn threads for each file to process them concurrently
                    for file_path in new_files:
                        logger.info(f"Startup scan: queueing new file {file_path.name}")
                        # Use _handle_file_event to process in background thread
                        self.event_handler._handle_file_event(file_path)

                # PHASE 4: Check tracked files for changes
                changed_count = 0
                for raw_log in tracked_files:
                    file_path = Path(raw_log.file_path)

                    if not file_path.exists():
                        logger.debug(f"Tracked file no longer exists: {file_path.name}")
                        continue

                    # Detect change type
                    change_type = detect_file_change_type(
                        file_path,
                        raw_log.last_processed_offset or 0,
                        raw_log.file_size_bytes or 0,
                        raw_log.partial_hash,
                    )

                    if change_type == ChangeType.UNCHANGED:
                        logger.debug(f"No changes: {file_path.name}")
                        continue

                    logger.info(
                        f"Startup scan detected {change_type.value}: {file_path.name}"
                    )
                    changed_count += 1

                    # Process file using existing handler
                    # This will handle both incremental and full reparse
                    self.event_handler._process_file(file_path)

                logger.info(
                    f"Startup scan complete: "
                    f"{len(new_files)} new files ingested, "
                    f"{changed_count}/{len(tracked_files)} tracked files changed"
                )

        except Exception as e:
            logger.error(f"Startup scan failed: {e}", exc_info=True)
            # Don't fail daemon startup on scan error

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
                    with self._stats_lock:
                        self.stats.files_retried += 1

                # Sleep for a bit before checking again
                self.shutdown_event.wait(timeout=self.retry_interval)

            except Exception as e:
                logger.error(f"Error in retry loop: {e}", exc_info=True)
                self.shutdown_event.wait(timeout=60)  # Wait a minute before retrying


def run_daemon_process(
    config_id: UUID,
    directory: Path,
    project_name: Optional[str],
    developer_username: Optional[str],
    poll_interval: int,
    retry_interval: int,
    max_retries: int,
    debounce_seconds: float,
    enable_tagging: bool,
    stats_queue: Optional["Queue[dict[str, Any]]"] = None,
) -> None:
    """
    Entry point for running WatcherDaemon in a separate process.

    This function is called by multiprocessing.Process and runs the daemon
    in a completely isolated process with its own Python interpreter.

    Args:
        config_id: Watch configuration UUID
        directory: Directory to watch
        project_name: Project name for ingested conversations
        developer_username: Developer username for ingested conversations
        poll_interval: Polling interval for file system observer
        retry_interval: Interval between retry attempts
        max_retries: Maximum retry attempts for failed files
        debounce_seconds: Debounce time for file events
        enable_tagging: Whether to enable AI tagging
    """
    # Setup logging for child process
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

    logger.info(
        f"Watch daemon process starting (PID: {os.getpid()}, config: {config_id})"
    )

    # Create daemon instance
    daemon = WatcherDaemon(
        directory=directory,
        project_name=project_name,
        developer_username=developer_username,
        poll_interval=poll_interval,
        retry_interval=retry_interval,
        max_retries=max_retries,
        debounce_seconds=debounce_seconds,
        enable_tagging=enable_tagging,
        config_id=config_id,
        stats_queue=stats_queue,
    )

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Process received signal {signum}, shutting down...")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run daemon in blocking mode (will run until killed or signaled)
    try:
        daemon.start(blocking=True)
    except Exception as e:
        logger.error(f"Daemon process crashed: {e}", exc_info=True)
        sys.exit(1)
