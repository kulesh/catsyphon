"""
Background worker for processing tagging jobs.

This worker polls the tagging job queue and processes conversations
sequentially, preventing connection pool exhaustion during high-throughput
ingestion.
"""

import logging
import threading
import time
from typing import Optional

from sqlalchemy.exc import OperationalError

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.db.repositories.conversation import ConversationRepository

from .job_queue import TaggingJobQueue
from .pipeline import TaggingPipeline

logger = logging.getLogger(__name__)


class TaggingWorker:
    """
    Background worker that processes tagging jobs from the queue.

    Features:
    - Single-threaded to prevent connection contention
    - Graceful shutdown support
    - Automatic retry on transient failures
    - Stale job cleanup
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        stale_job_timeout_minutes: int = 30,
        purge_completed_days: int = 7,
    ):
        """
        Initialize the tagging worker.

        Args:
            poll_interval: Seconds between queue polls when idle
            stale_job_timeout_minutes: Reset jobs processing longer than this
            purge_completed_days: Delete completed jobs older than this
        """
        self.poll_interval = poll_interval
        self.stale_job_timeout_minutes = stale_job_timeout_minutes
        self.purge_completed_days = purge_completed_days
        self._running = False
        self._stop_event = threading.Event()
        self._pipeline: Optional[TaggingPipeline] = None
        self._jobs_processed = 0
        self._jobs_succeeded = 0
        self._jobs_failed = 0
        self._last_job_time: Optional[float] = None

    def _get_pipeline(self) -> Optional[TaggingPipeline]:
        """Get or create the tagging pipeline (lazy initialization)."""
        if self._pipeline is None:
            if not settings.openai_api_key:
                logger.warning(
                    "OpenAI API key not configured - tagging worker disabled"
                )
                return None

            self._pipeline = TaggingPipeline(
                openai_api_key=settings.openai_api_key,
                openai_model=settings.openai_model,
                cache_ttl_days=settings.tagging_cache_ttl_days,
                enable_cache=settings.tagging_enable_cache,
            )

        return self._pipeline

    def run(self) -> None:
        """
        Main worker loop.

        Polls the job queue and processes jobs until stopped.
        """
        logger.info("Tagging worker starting")
        self._running = True

        # Initial cleanup
        self._cleanup()

        while not self._stop_event.is_set():
            try:
                job_processed = self._process_next_job()

                if not job_processed:
                    # No jobs available - wait before polling again
                    self._stop_event.wait(self.poll_interval)
            except OperationalError as e:
                logger.warning(f"Tagging worker DB unavailable: {e}")
                # Back off briefly before retrying
                self._stop_event.wait(5.0)
            except Exception as e:
                logger.error(f"Error in tagging worker loop: {e}", exc_info=True)
                # Brief pause before retrying
                self._stop_event.wait(1.0)

        logger.info(
            f"Tagging worker stopped. "
            f"Processed: {self._jobs_processed}, "
            f"Succeeded: {self._jobs_succeeded}, "
            f"Failed: {self._jobs_failed}"
        )
        self._running = False

    def stop(self) -> None:
        """Signal the worker to stop gracefully."""
        logger.info("Tagging worker stop requested")
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._running

    def _process_next_job(self) -> bool:
        """
        Process the next job from the queue.

        Returns:
            True if a job was processed, False if queue is empty
        """
        pipeline = self._get_pipeline()
        if not pipeline:
            return False

        with db_session() as session:
            queue = TaggingJobQueue(session)
            job = queue.claim_next()

            if not job:
                return False

            job_id = job.id
            conversation_id = job.conversation_id
            self._jobs_processed += 1
            logger.info(
                f"Processing tagging job {job_id} for conversation {conversation_id}"
            )

            # Persist claim state before processing so failed attempts are counted.
            # Without this commit, a rollback in the exception path resets attempts
            # and can cause infinite retry loops.
            session.commit()

            try:
                # Load conversation
                conv_repo = ConversationRepository(session)
                # Use workspace_id from conversation's workspace
                conversation = (
                    session.query(conv_repo.model)
                    .filter_by(id=conversation_id)
                    .first()
                )

                if not conversation:
                    raise ValueError(f"Conversation {conversation_id} not found")

                # Run tagging pipeline
                tags, metrics = pipeline.tag_from_canonical(
                    conversation=conversation,
                    session=session,
                    children=[],
                )

                # Update conversation with tags
                conversation.tags = tags
                session.flush()

                # Mark job complete
                queue.complete(job_id, success=True)
                session.commit()

                self._jobs_succeeded += 1
                self._last_job_time = time.time()

                logger.info(
                    f"Completed tagging job {job_id}: "
                    f"intent={tags.get('intent')}, outcome={tags.get('outcome')}, "
                    f"tokens={metrics.get('llm_total_tokens', 0)}"
                )

            except Exception as e:
                session.rollback()
                # Mark job failed (will be retried or marked permanently failed)
                queue.complete(job_id, success=False, error=str(e))
                session.commit()

                self._jobs_failed += 1

                logger.warning(
                    f"Failed tagging job {job_id} for conversation "
                    f"{conversation_id}: {e}"
                )

        return True

    def _cleanup(self) -> None:
        """Perform periodic cleanup tasks."""
        try:
            with db_session() as session:
                queue = TaggingJobQueue(session)

                # Reset any stale processing jobs
                stale_count = queue.cleanup_stale_jobs(self.stale_job_timeout_minutes)
                if stale_count:
                    logger.info(f"Reset {stale_count} stale tagging jobs")

                # Purge old completed jobs
                purged_count = queue.purge_completed(self.purge_completed_days)
                if purged_count:
                    logger.info(f"Purged {purged_count} old completed tagging jobs")

                session.commit()
        except OperationalError as e:
            logger.warning(f"Tagging worker cleanup skipped (DB unavailable): {e}")
        except Exception as e:
            logger.error(f"Error during tagging worker cleanup: {e}")


# Singleton worker instance for app lifecycle management
_worker: Optional[TaggingWorker] = None
_worker_thread: Optional[threading.Thread] = None


def start_worker() -> None:
    """Start the global tagging worker in a background thread."""
    global _worker, _worker_thread

    if _worker is not None and _worker.is_running:
        logger.warning("Tagging worker is already running")
        return

    _worker = TaggingWorker()
    _worker_thread = threading.Thread(
        target=_worker.run,
        daemon=True,
        name="tagging-worker",
    )
    _worker_thread.start()
    logger.info("Started tagging worker background thread")


def stop_worker(timeout: float = 10.0) -> None:
    """Stop the global tagging worker gracefully."""
    global _worker, _worker_thread

    if _worker is None:
        return

    _worker.stop()

    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=timeout)
        if _worker_thread.is_alive():
            logger.warning(
                f"Tagging worker thread did not stop within {timeout}s timeout"
            )

    _worker = None
    _worker_thread = None
    logger.info("Stopped tagging worker")


def get_worker_stats() -> dict[str, object]:
    """Get statistics from the tagging worker."""
    if _worker is None:
        return {"running": False}

    return {
        "running": _worker.is_running,
        "jobs_processed": _worker._jobs_processed,
        "jobs_succeeded": _worker._jobs_succeeded,
        "jobs_failed": _worker._jobs_failed,
        "last_job_time": _worker._last_job_time,
    }
