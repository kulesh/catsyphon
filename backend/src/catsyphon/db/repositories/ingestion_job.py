"""
Ingestion job repository.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, desc, func, text
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

        # Peak processing time
        peak_time = (
            self.session.query(func.max(IngestionJob.processing_time_ms))
            .filter(IngestionJob.processing_time_ms.isnot(None))
            .scalar()
        )

        # Percentiles for processing time (p50, p75, p90, p99)
        # Use database-specific approach for percentile calculation
        bind = self.session.bind
        if bind is None:
            raise RuntimeError("Session has no bind")
        dialect_name = bind.dialect.name

        if dialect_name == "postgresql":
            # Use PostgreSQL's native percentile_cont function
            percentiles_query = text(
                """
                SELECT
                    percentile_cont(0.5) WITHIN GROUP (
                        ORDER BY processing_time_ms
                    ) as p50,
                    percentile_cont(0.75) WITHIN GROUP (
                        ORDER BY processing_time_ms
                    ) as p75,
                    percentile_cont(0.9) WITHIN GROUP (
                        ORDER BY processing_time_ms
                    ) as p90,
                    percentile_cont(0.99) WITHIN GROUP (
                        ORDER BY processing_time_ms
                    ) as p99
                FROM ingestion_jobs
                WHERE processing_time_ms IS NOT NULL
                """
            )
            percentiles_result = self.session.execute(percentiles_query).first()
            processing_time_percentiles = {
                "p50": (
                    float(percentiles_result[0])
                    if percentiles_result and percentiles_result[0]
                    else None
                ),
                "p75": (
                    float(percentiles_result[1])
                    if percentiles_result and percentiles_result[1]
                    else None
                ),
                "p90": (
                    float(percentiles_result[2])
                    if percentiles_result and percentiles_result[2]
                    else None
                ),
                "p99": (
                    float(percentiles_result[3])
                    if percentiles_result and percentiles_result[3]
                    else None
                ),
            }
        else:
            # For SQLite and other databases: calculate percentiles in Python
            all_times = (
                self.session.query(IngestionJob.processing_time_ms)
                .filter(IngestionJob.processing_time_ms.isnot(None))
                .order_by(IngestionJob.processing_time_ms)
                .all()
            )

            if all_times:
                times_list = [float(t[0]) for t in all_times]
                n = len(times_list)

                def percentile(data: list[float], p: float) -> float | None:
                    """Calculate percentile using linear interpolation."""
                    if not data:
                        return None
                    k = (n - 1) * p
                    f = int(k)
                    c = k - f
                    if f + 1 < n:
                        return data[f] + c * (data[f + 1] - data[f])
                    return data[f]

                processing_time_percentiles = {
                    "p50": percentile(times_list, 0.5),
                    "p75": percentile(times_list, 0.75),
                    "p90": percentile(times_list, 0.9),
                    "p99": percentile(times_list, 0.99),
                }
            else:
                processing_time_percentiles = {
                    "p50": None,
                    "p75": None,
                    "p90": None,
                    "p99": None,
                }

        # Recent activity metrics
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        jobs_last_hour = (
            self.session.query(func.count(IngestionJob.id))
            .filter(IngestionJob.started_at >= one_hour_ago)
            .scalar()
        )

        jobs_last_24h = (
            self.session.query(func.count(IngestionJob.id))
            .filter(IngestionJob.started_at >= one_day_ago)
            .scalar()
        )

        # Processing rate (jobs per minute over last hour)
        processing_rate = jobs_last_hour / 60.0 if jobs_last_hour > 0 else 0.0

        # Time-series data for sparklines (last 24 hours, hourly buckets)
        # Use database-specific approach for date truncation
        if dialect_name == "postgresql":
            timeseries_query = text(
                """
                SELECT
                    date_trunc('hour', started_at) as hour,
                    COUNT(*) as job_count,
                    AVG(processing_time_ms) as avg_time,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
                FROM ingestion_jobs
                WHERE started_at >= :one_day_ago
                GROUP BY hour
                ORDER BY hour ASC
                """
            )
            timeseries_result = self.session.execute(
                timeseries_query, {"one_day_ago": one_day_ago}
            ).fetchall()

            timeseries_data = [
                {
                    "timestamp": row[0].isoformat(),
                    "job_count": row[1],
                    "avg_processing_time_ms": float(row[2]) if row[2] else None,
                    "success_count": row[3],
                    "failed_count": row[4],
                }
                for row in timeseries_result
            ]
        else:
            # For SQLite: use strftime for date truncation
            timeseries_query = text(
                """
                SELECT
                    strftime('%Y-%m-%d %H:00:00', started_at) as hour,
                    COUNT(*) as job_count,
                    AVG(processing_time_ms) as avg_time,
                    SUM(
                        CASE WHEN status = 'success' THEN 1 ELSE 0 END
                    ) as success_count,
                    SUM(
                        CASE WHEN status = 'failed' THEN 1 ELSE 0 END
                    ) as failed_count
                FROM ingestion_jobs
                WHERE started_at >= :one_day_ago
                GROUP BY hour
                ORDER BY hour ASC
                """
            )
            timeseries_result = self.session.execute(
                timeseries_query, {"one_day_ago": one_day_ago}
            ).fetchall()

            timeseries_data = [
                {
                    "timestamp": row[0],
                    "job_count": row[1],
                    "avg_processing_time_ms": float(row[2]) if row[2] else None,
                    "success_count": row[3],
                    "failed_count": row[4],
                }
                for row in timeseries_result
            ]

        # Time since last failure
        last_failure = (
            self.session.query(IngestionJob.started_at)
            .filter(IngestionJob.status == "failed")
            .order_by(IngestionJob.started_at.desc())
            .first()
        )
        time_since_last_failure_minutes = None
        if last_failure:
            failure_time = last_failure[0]
            # Ensure timezone-aware comparison (SQLite returns offset-naive datetimes)
            if failure_time.tzinfo is None:
                failure_time = failure_time.replace(tzinfo=timezone.utc)
            delta = now - failure_time
            time_since_last_failure_minutes = delta.total_seconds() / 60.0

        # Success and failure rates
        success_rate = (
            (by_status.get("success", 0) / total * 100) if total > 0 else None
        )
        failure_rate = (by_status.get("failed", 0) / total * 100) if total > 0 else None

        # Incremental parsing usage
        incremental_count = (
            self.session.query(func.count(IngestionJob.id))
            .filter(IngestionJob.incremental == True)  # noqa: E712
            .scalar()
        )

        # Incremental speedup calculation
        avg_incremental_time = (
            self.session.query(func.avg(IngestionJob.processing_time_ms))
            .filter(IngestionJob.incremental == True)  # noqa: E712
            .filter(IngestionJob.processing_time_ms.isnot(None))
            .scalar()
        )
        avg_full_parse_time = (
            self.session.query(func.avg(IngestionJob.processing_time_ms))
            .filter(IngestionJob.incremental == False)  # noqa: E712
            .filter(IngestionJob.processing_time_ms.isnot(None))
            .scalar()
        )
        incremental_speedup = None
        if avg_incremental_time and avg_full_parse_time and avg_incremental_time > 0:
            incremental_speedup = avg_full_parse_time / avg_incremental_time

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
        parse_times = []
        tagging_times = []
        llm_tagging_times = []
        llm_prompt_tokens = []
        llm_completion_tokens = []
        llm_total_tokens = []
        llm_costs = []
        llm_cache_hits = 0
        llm_total_calls = 0

        for job in jobs_with_metrics:
            if job.metrics:
                if "deduplication_check_ms" in job.metrics:
                    dedup_times.append(job.metrics["deduplication_check_ms"])
                if "database_operations_ms" in job.metrics:
                    db_times.append(job.metrics["database_operations_ms"])
                if "parse_duration_ms" in job.metrics:
                    parse_times.append(job.metrics["parse_duration_ms"])
                if "tagging_duration_ms" in job.metrics:
                    tagging_times.append(job.metrics["tagging_duration_ms"])

                # LLM metrics (only present if tagging was enabled)
                if "llm_tagging_ms" in job.metrics:
                    llm_total_calls += 1
                    if job.metrics.get("llm_cache_hit", False):
                        llm_cache_hits += 1
                    else:
                        # Only count non-cache hits for averages (cache hits are 0)
                        llm_tagging_times.append(job.metrics["llm_tagging_ms"])
                        if "llm_prompt_tokens" in job.metrics:
                            llm_prompt_tokens.append(job.metrics["llm_prompt_tokens"])
                        if "llm_completion_tokens" in job.metrics:
                            llm_completion_tokens.append(
                                job.metrics["llm_completion_tokens"]
                            )
                        if "llm_total_tokens" in job.metrics:
                            llm_total_tokens.append(job.metrics["llm_total_tokens"])
                        if "llm_cost_usd" in job.metrics:
                            llm_costs.append(job.metrics["llm_cost_usd"])

        avg_dedup = sum(dedup_times) / len(dedup_times) if dedup_times else None
        avg_db = sum(db_times) / len(db_times) if db_times else None
        avg_parse = sum(parse_times) / len(parse_times) if parse_times else None
        avg_tagging = sum(tagging_times) / len(tagging_times) if tagging_times else None

        # LLM aggregates
        avg_llm_tagging = (
            sum(llm_tagging_times) / len(llm_tagging_times)
            if llm_tagging_times
            else None
        )
        avg_llm_prompt = (
            sum(llm_prompt_tokens) / len(llm_prompt_tokens)
            if llm_prompt_tokens
            else None
        )
        avg_llm_completion = (
            sum(llm_completion_tokens) / len(llm_completion_tokens)
            if llm_completion_tokens
            else None
        )
        avg_llm_total = (
            sum(llm_total_tokens) / len(llm_total_tokens) if llm_total_tokens else None
        )
        avg_llm_cost = sum(llm_costs) / len(llm_costs) if llm_costs else None
        total_llm_cost = sum(llm_costs) if llm_costs else None
        llm_cache_rate = (
            llm_cache_hits / llm_total_calls if llm_total_calls > 0 else None
        )

        return {
            "total_jobs": total,
            "by_status": by_status,
            "by_source_type": by_source,
            "avg_processing_time_ms": float(avg_time) if avg_time else None,
            "peak_processing_time_ms": float(peak_time) if peak_time else None,
            "processing_time_percentiles": processing_time_percentiles,
            "incremental_jobs": incremental_count,
            "incremental_percentage": (
                (incremental_count / total * 100) if total > 0 else 0
            ),
            "incremental_speedup": incremental_speedup,
            # Recent activity metrics
            "jobs_last_hour": jobs_last_hour,
            "jobs_last_24h": jobs_last_24h,
            "processing_rate_per_minute": processing_rate,
            # Success/failure metrics
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "time_since_last_failure_minutes": time_since_last_failure_minutes,
            # Time-series data for sparklines
            "timeseries_24h": timeseries_data,
            # Stage-level metrics
            "avg_parse_duration_ms": avg_parse,
            "avg_deduplication_check_ms": avg_dedup,
            "avg_database_operations_ms": avg_db,
            # Tagging metrics
            "avg_tagging_duration_ms": avg_tagging,
            "avg_llm_tagging_ms": avg_llm_tagging,
            "avg_llm_prompt_tokens": avg_llm_prompt,
            "avg_llm_completion_tokens": avg_llm_completion,
            "avg_llm_total_tokens": avg_llm_total,
            "avg_llm_cost_usd": avg_llm_cost,
            "total_llm_cost_usd": total_llm_cost,
            "llm_cache_hit_rate": llm_cache_rate,
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
