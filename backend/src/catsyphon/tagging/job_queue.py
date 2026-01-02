"""
Tagging job queue service.

Provides a PostgreSQL-based job queue for async tagging operations,
decoupling tagging from the request/response cycle to prevent
connection pool exhaustion.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from catsyphon.models.db import TaggingJob, TaggingJobStatus

logger = logging.getLogger(__name__)


@dataclass
class QueueStats:
    """Statistics about the tagging job queue."""

    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0

    @property
    def active(self) -> int:
        """Jobs that are pending or processing."""
        return self.pending + self.processing


class TaggingJobQueue:
    """
    PostgreSQL-based job queue for async tagging.

    Uses SELECT FOR UPDATE SKIP LOCKED for atomic job claiming,
    ensuring safe concurrent access from multiple workers.
    """

    def __init__(self, session: Session):
        self.session = session

    def enqueue(
        self,
        conversation_id: uuid.UUID,
        priority: int = 0,
    ) -> uuid.UUID:
        """
        Add a conversation to the tagging queue.

        Args:
            conversation_id: ID of conversation to tag
            priority: Job priority (0=highest, higher=lower priority)

        Returns:
            UUID of created job
        """
        # Check if job already exists for this conversation
        existing = (
            self.session.query(TaggingJob)
            .filter(
                TaggingJob.conversation_id == conversation_id,
                TaggingJob.status.in_(
                    [TaggingJobStatus.PENDING.value, TaggingJobStatus.PROCESSING.value]
                ),
            )
            .first()
        )

        if existing:
            logger.debug(
                f"Job already exists for conversation {conversation_id}: {existing.id}"
            )
            return existing.id

        job = TaggingJob(
            conversation_id=conversation_id,
            priority=priority,
            status=TaggingJobStatus.PENDING.value,
        )
        self.session.add(job)
        self.session.flush()  # Get the ID without committing

        logger.debug(f"Enqueued tagging job {job.id} for conversation {conversation_id}")
        return job.id

    def claim_next(self) -> Optional[TaggingJob]:
        """
        Atomically claim the next pending job.

        Uses SELECT FOR UPDATE SKIP LOCKED to safely claim jobs
        without blocking other workers.

        Returns:
            TaggingJob if one is available, None otherwise
        """
        # Find and lock the next pending job
        job = (
            self.session.query(TaggingJob)
            .filter(TaggingJob.status == TaggingJobStatus.PENDING.value)
            .order_by(TaggingJob.priority, TaggingJob.created_at)
            .with_for_update(skip_locked=True)
            .first()
        )

        if not job:
            return None

        # Mark as processing
        job.status = TaggingJobStatus.PROCESSING.value
        job.started_at = datetime.utcnow()
        job.attempts += 1
        self.session.flush()

        logger.debug(
            f"Claimed tagging job {job.id} (attempt {job.attempts}/{job.max_attempts})"
        )
        return job

    def complete(
        self,
        job_id: uuid.UUID,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Mark a job as completed or failed.

        Args:
            job_id: ID of the job
            success: Whether tagging succeeded
            error: Error message if failed
        """
        job = self.session.query(TaggingJob).filter(TaggingJob.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found when trying to complete")
            return

        job.completed_at = datetime.utcnow()

        if success:
            job.status = TaggingJobStatus.COMPLETED.value
            job.error_message = None
            logger.info(f"Tagging job {job_id} completed successfully")
        else:
            job.error_message = error
            if job.attempts >= job.max_attempts:
                job.status = TaggingJobStatus.FAILED.value
                logger.warning(
                    f"Tagging job {job_id} failed after {job.attempts} attempts: {error}"
                )
            else:
                # Reset to pending for retry
                job.status = TaggingJobStatus.PENDING.value
                job.started_at = None
                job.completed_at = None
                logger.info(
                    f"Tagging job {job_id} failed, will retry "
                    f"(attempt {job.attempts}/{job.max_attempts}): {error}"
                )

        self.session.flush()

    def get_stats(self) -> QueueStats:
        """
        Get queue statistics.

        Returns:
            QueueStats with counts by status
        """
        results = (
            self.session.query(TaggingJob.status, func.count(TaggingJob.id))
            .group_by(TaggingJob.status)
            .all()
        )

        stats = QueueStats()
        for status, count in results:
            if status == TaggingJobStatus.PENDING.value:
                stats.pending = count
            elif status == TaggingJobStatus.PROCESSING.value:
                stats.processing = count
            elif status == TaggingJobStatus.COMPLETED.value:
                stats.completed = count
            elif status == TaggingJobStatus.FAILED.value:
                stats.failed = count
            stats.total += count

        return stats

    def cleanup_stale_jobs(self, timeout_minutes: int = 30) -> int:
        """
        Reset jobs that have been processing for too long.

        This handles cases where a worker crashed mid-job.

        Args:
            timeout_minutes: Time after which a processing job is considered stale

        Returns:
            Number of jobs reset
        """
        stale_threshold = text(
            f"started_at < NOW() - INTERVAL '{timeout_minutes} minutes'"
        )

        result = (
            self.session.query(TaggingJob)
            .filter(
                TaggingJob.status == TaggingJobStatus.PROCESSING.value,
                stale_threshold,
            )
            .update(
                {
                    TaggingJob.status: TaggingJobStatus.PENDING.value,
                    TaggingJob.started_at: None,
                },
                synchronize_session=False,
            )
        )

        if result > 0:
            logger.warning(f"Reset {result} stale tagging jobs")

        return result

    def purge_completed(self, days: int = 7) -> int:
        """
        Delete completed jobs older than specified days.

        Args:
            days: Age threshold for deletion

        Returns:
            Number of jobs deleted
        """
        threshold = text(f"completed_at < NOW() - INTERVAL '{days} days'")

        result = (
            self.session.query(TaggingJob)
            .filter(
                TaggingJob.status.in_(
                    [TaggingJobStatus.COMPLETED.value, TaggingJobStatus.FAILED.value]
                ),
                threshold,
            )
            .delete(synchronize_session=False)
        )

        if result > 0:
            logger.info(f"Purged {result} completed tagging jobs older than {days} days")

        return result
