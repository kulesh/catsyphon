"""
Ingestion job repository.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import IngestionJob


class IngestionJobRepository(BaseRepository[IngestionJob]):
    """Repository for IngestionJob model."""

    def __init__(self, session: Session):
        super().__init__(IngestionJob, session)

    def get_by_source_type(
        self,
        source_type: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs by source type.

        Args:
            source_type: Source type ('watch', 'upload', 'cli')
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ingestion jobs
        """
        query = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.source_type == source_type)
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_status(
        self,
        status: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs by status.

        Args:
            status: Status ('success', 'failed', 'duplicate', 'skipped')
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ingestion jobs
        """
        query = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.status == status)
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_recent(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get recent ingestion jobs.

        Args:
            limit: Maximum number of records (default: 50)
            offset: Number of records to skip

        Returns:
            List of recent ingestion jobs
        """
        return (
            self.session.query(IngestionJob)
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_watch_config(
        self,
        config_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs for a specific watch configuration.

        Args:
            config_id: Watch configuration UUID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ingestion jobs
        """
        query = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.source_config_id == config_id)
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_conversation(
        self,
        conversation_id: uuid.UUID,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs for a specific conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of ingestion jobs
        """
        return (
            self.session.query(IngestionJob)
            .filter(IngestionJob.conversation_id == conversation_id)
            .order_by(desc(IngestionJob.started_at))
            .all()
        )

    def get_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs within a date range.

        Args:
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ingestion jobs
        """
        query = self.session.query(IngestionJob)

        if start_date:
            query = query.filter(IngestionJob.started_at >= start_date)
        if end_date:
            query = query.filter(IngestionJob.started_at <= end_date)

        query = query.order_by(desc(IngestionJob.started_at)).offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_failed_jobs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get failed ingestion jobs.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of failed ingestion jobs
        """
        return self.get_by_status("failed", limit=limit, offset=offset)

    def count_by_status(self) -> dict[str, int]:
        """
        Count ingestion jobs by status.

        Returns:
            Dictionary with status counts
        """
        results = (
            self.session.query(IngestionJob.status, func.count(IngestionJob.id))
            .group_by(IngestionJob.status)
            .all()
        )
        return {status: count for status, count in results}

    def count_by_source_type(self) -> dict[str, int]:
        """
        Count ingestion jobs by source type.

        Returns:
            Dictionary with source type counts
        """
        results = (
            self.session.query(IngestionJob.source_type, func.count(IngestionJob.id))
            .group_by(IngestionJob.source_type)
            .all()
        )
        return {source_type: count for source_type, count in results}

    def get_stats(self) -> dict[str, int | dict[str, int] | float | None]:
        """
        Get overall ingestion statistics.

        Returns:
            Dictionary with statistics including stage-level metrics
        """
        total = self.count()
        by_status = self.count_by_status()
        by_source = self.count_by_source_type()

        # Average processing time
        avg_time = (
            self.session.query(func.avg(IngestionJob.processing_time_ms))
            .filter(IngestionJob.processing_time_ms.isnot(None))
            .scalar()
        )

        # Incremental parsing usage
        incremental_count = (
            self.session.query(func.count(IngestionJob.id))
            .filter(IngestionJob.incremental == True)  # noqa: E712
            .scalar()
        )

        # Calculate stage-level averages from metrics JSONB field
        # Fetch all jobs with metrics (successful jobs only for meaningful averages)
        jobs_with_metrics = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.status == "success")
            .filter(IngestionJob.metrics.isnot(None))
            .all()
        )

        # Calculate averages for each stage
        dedup_times = []
        db_times = []

        for job in jobs_with_metrics:
            if job.metrics:
                if "deduplication_check_ms" in job.metrics:
                    dedup_times.append(job.metrics["deduplication_check_ms"])
                if "database_operations_ms" in job.metrics:
                    db_times.append(job.metrics["database_operations_ms"])

        avg_dedup = sum(dedup_times) / len(dedup_times) if dedup_times else None
        avg_db = sum(db_times) / len(db_times) if db_times else None

        return {
            "total_jobs": total,
            "by_status": by_status,
            "by_source_type": by_source,
            "avg_processing_time_ms": float(avg_time) if avg_time else None,
            "incremental_jobs": incremental_count,
            "incremental_percentage": (
                (incremental_count / total * 100) if total > 0 else 0
            ),
            # Stage-level metrics
            "avg_deduplication_check_ms": avg_dedup,
            "avg_database_operations_ms": avg_db,
            "error_rates_by_stage": {},  # Placeholder for future error tracking
        }

    def search(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        collector_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Search ingestion jobs with multiple filters.

        Args:
            source_type: Filter by source type
            status: Filter by status
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            collector_id: Filter by collector
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of matching ingestion jobs
        """
        filters = []

        if source_type:
            filters.append(IngestionJob.source_type == source_type)
        if status:
            filters.append(IngestionJob.status == status)
        if start_date:
            filters.append(IngestionJob.started_at >= start_date)
        if end_date:
            filters.append(IngestionJob.started_at <= end_date)
        if collector_id:
            filters.append(IngestionJob.collector_id == collector_id)

        query = self.session.query(IngestionJob)

        if filters:
            query = query.filter(and_(*filters))

        return (
            query.order_by(desc(IngestionJob.started_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_collector(
        self,
        collector_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs for a specific collector.

        Args:
            collector_id: Collector UUID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ingestion jobs
        """
        query = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.collector_id == collector_id)
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_collector(self, collector_id: uuid.UUID) -> int:
        """
        Count ingestion jobs for a collector.

        Args:
            collector_id: Collector UUID

        Returns:
            Number of ingestion jobs
        """
        return (
            self.session.query(IngestionJob)
            .filter(IngestionJob.collector_id == collector_id)
            .count()
        )
