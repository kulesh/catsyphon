"""
Ingestion job repository.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import Boolean, Float, and_, desc, func, text
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Conversation, IngestionJob, WatchConfiguration


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
        limit: Optional[int] = 100,
    ) -> List[IngestionJob]:
        """
        Get ingestion jobs for a specific conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of records (default: 100, None for unlimited)

        Returns:
            List of ingestion jobs
        """
        query = (
            self.session.query(IngestionJob)
            .filter(IngestionJob.conversation_id == conversation_id)
            .order_by(desc(IngestionJob.started_at))
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

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

        # ===== OPTIMIZED: Use database aggregation instead of loading all jobs =====
        # Calculate stage-level averages from metrics JSONB field

        # Base filter for successful jobs with metrics
        base_filter = [
            IngestionJob.status == "success",
            IngestionJob.metrics.isnot(None),
        ]

        if dialect_name == "postgresql":
            # PostgreSQL: Use JSONB extraction with database aggregation
            # Stage-level averages using JSONB ->> operator (cast to Float)
            avg_dedup = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["deduplication_check_ms"].astext, Float
                        )
                    )
                )
                .filter(*base_filter)
                .scalar()
            )
            avg_db = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["database_operations_ms"].astext, Float
                        )
                    )
                )
                .filter(*base_filter)
                .scalar()
            )
            avg_parse = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["parse_duration_ms"].astext, Float
                        )
                    )
                )
                .filter(*base_filter)
                .scalar()
            )
            avg_tagging = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["tagging_duration_ms"].astext, Float
                        )
                    )
                )
                .filter(*base_filter)
                .scalar()
            )

            # LLM metrics - filter for non-cache-hit jobs
            # SQLAlchemy boolean expression - must use == for SQL comparison
            llm_filter = base_filter + [
                IngestionJob.metrics["llm_tagging_ms"].isnot(None),
                func.coalesce(
                    func.cast(IngestionJob.metrics["llm_cache_hit"].astext, Boolean),
                    False,
                ).is_(False),
            ]
            avg_llm_tagging = (
                self.session.query(
                    func.avg(
                        func.cast(IngestionJob.metrics["llm_tagging_ms"].astext, Float)
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )
            avg_llm_prompt = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["llm_prompt_tokens"].astext, Float
                        )
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )
            avg_llm_completion = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["llm_completion_tokens"].astext, Float
                        )
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )
            avg_llm_total = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["llm_total_tokens"].astext, Float
                        )
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )
            avg_llm_cost = (
                self.session.query(
                    func.avg(
                        func.cast(IngestionJob.metrics["llm_cost_usd"].astext, Float)
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )
            total_llm_cost = (
                self.session.query(
                    func.sum(
                        func.cast(IngestionJob.metrics["llm_cost_usd"].astext, Float)
                    )
                )
                .filter(*llm_filter)
                .scalar()
            )

            # LLM cache hit rate
            llm_total_calls = (
                self.session.query(func.count(IngestionJob.id))
                .filter(*base_filter)
                .filter(IngestionJob.metrics["llm_tagging_ms"].isnot(None))
                .scalar()
                or 0
            )
            llm_cache_hits = (
                self.session.query(func.count(IngestionJob.id))
                .filter(*base_filter)
                .filter(IngestionJob.metrics["llm_tagging_ms"].isnot(None))
                .filter(
                    func.cast(
                        IngestionJob.metrics["llm_cache_hit"].astext, Boolean
                    ).is_(True)
                )
                .scalar()
                or 0
            )
            llm_cache_rate = (
                llm_cache_hits / llm_total_calls if llm_total_calls > 0 else None
            )

            # Parser usage aggregates using GROUP BY
            parser_counts = (
                self.session.query(
                    IngestionJob.metrics["parser_name"].astext.label("name"),
                    func.count(IngestionJob.id),
                )
                .filter(*base_filter)
                .filter(IngestionJob.metrics["parser_name"].isnot(None))
                .group_by(IngestionJob.metrics["parser_name"].astext)
                .all()
            )
            parser_usage = {name: count for name, count in parser_counts if name}

            # Parser version usage
            parser_version_counts = (
                self.session.query(
                    func.concat(
                        IngestionJob.metrics["parser_name"].astext,
                        text("'@'"),
                        IngestionJob.metrics["parser_version"].astext,
                    ).label("version_key"),
                    func.count(IngestionJob.id),
                )
                .filter(*base_filter)
                .filter(IngestionJob.metrics["parser_name"].isnot(None))
                .filter(IngestionJob.metrics["parser_version"].isnot(None))
                .group_by(
                    IngestionJob.metrics["parser_name"].astext,
                    IngestionJob.metrics["parser_version"].astext,
                )
                .all()
            )
            parser_version_usage = {
                key: count for key, count in parser_version_counts if key
            }

            # Parse methods
            method_counts = (
                self.session.query(
                    IngestionJob.metrics["parse_method"].astext.label("method"),
                    func.count(IngestionJob.id),
                )
                .filter(*base_filter)
                .filter(IngestionJob.metrics["parse_method"].isnot(None))
                .group_by(IngestionJob.metrics["parse_method"].astext)
                .all()
            )
            parse_methods = {method: count for method, count in method_counts if method}

            # Change types
            change_counts = (
                self.session.query(
                    IngestionJob.metrics["parse_change_type"].astext.label("type"),
                    func.count(IngestionJob.id),
                )
                .filter(*base_filter)
                .filter(IngestionJob.metrics["parse_change_type"].isnot(None))
                .group_by(IngestionJob.metrics["parse_change_type"].astext)
                .all()
            )
            change_type_counts = {
                change_type: count
                for change_type, count in change_counts
                if change_type
            }

            # Warning stats
            avg_warning_count = (
                self.session.query(
                    func.avg(
                        func.cast(
                            IngestionJob.metrics["parse_warning_count"].astext, Float
                        )
                    )
                )
                .filter(*base_filter)
                .filter(IngestionJob.metrics["parse_warning_count"].isnot(None))
                .scalar()
            )
            jobs_with_warnings = (
                self.session.query(func.count(IngestionJob.id))
                .filter(*base_filter)
                .filter(
                    func.cast(IngestionJob.metrics["parse_warning_count"].astext, Float)
                    > 0
                )
                .scalar()
                or 0
            )
            jobs_with_metrics_count = (
                self.session.query(func.count(IngestionJob.id))
                .filter(*base_filter)
                .scalar()
                or 0
            )
            parse_warning_rate = (
                jobs_with_warnings / jobs_with_metrics_count * 100
                if jobs_with_metrics_count > 0
                else None
            )
        else:
            # SQLite fallback: Use limited scan (less efficient but compatible)
            # Cap to prevent OOM
            jobs_with_metrics = (
                self.session.query(IngestionJob.metrics)
                .filter(*base_filter)
                .limit(5000)
                .all()
            )

            # Calculate averages for each stage
            dedup_times: list[float] = []
            db_times: list[float] = []
            parse_times: list[float] = []
            tagging_times: list[float] = []
            llm_tagging_times: list[float] = []
            llm_prompt_tokens: list[float] = []
            llm_completion_tokens: list[float] = []
            llm_total_tokens: list[float] = []
            llm_costs: list[float] = []
            llm_cache_hits = 0
            llm_total_calls = 0

            parser_usage: dict[str, int] = {}
            parser_version_usage: dict[str, int] = {}
            parse_methods: dict[str, int] = {}
            change_type_counts: dict[str, int] = {}
            warning_counts: list[float] = []
            jobs_with_warnings = 0

            for (metrics,) in jobs_with_metrics:
                if not metrics:
                    continue
                if "deduplication_check_ms" in metrics:
                    dedup_times.append(float(metrics["deduplication_check_ms"]))
                if "database_operations_ms" in metrics:
                    db_times.append(float(metrics["database_operations_ms"]))
                if "parse_duration_ms" in metrics:
                    parse_times.append(float(metrics["parse_duration_ms"]))
                if "tagging_duration_ms" in metrics:
                    tagging_times.append(float(metrics["tagging_duration_ms"]))

                # LLM metrics
                if "llm_tagging_ms" in metrics:
                    llm_total_calls += 1
                    if metrics.get("llm_cache_hit", False):
                        llm_cache_hits += 1
                    else:
                        llm_tagging_times.append(float(metrics["llm_tagging_ms"]))
                        if "llm_prompt_tokens" in metrics:
                            llm_prompt_tokens.append(
                                float(metrics["llm_prompt_tokens"])
                            )
                        if "llm_completion_tokens" in metrics:
                            llm_completion_tokens.append(
                                float(metrics["llm_completion_tokens"])
                            )
                        if "llm_total_tokens" in metrics:
                            llm_total_tokens.append(float(metrics["llm_total_tokens"]))
                        if "llm_cost_usd" in metrics:
                            llm_costs.append(float(metrics["llm_cost_usd"]))

                # Parser aggregates
                parser_name = metrics.get("parser_name")
                parser_version = metrics.get("parser_version")
                parse_method = metrics.get("parse_method")
                change_type = metrics.get("parse_change_type")
                warning_count = metrics.get("parse_warning_count")
                warnings_list = metrics.get("parse_warnings")

                if parser_name:
                    parser_usage[parser_name] = parser_usage.get(parser_name, 0) + 1
                if parser_name and parser_version:
                    key = f"{parser_name}@{parser_version}"
                    parser_version_usage[key] = parser_version_usage.get(key, 0) + 1
                if parse_method:
                    parse_methods[parse_method] = parse_methods.get(parse_method, 0) + 1
                if change_type:
                    change_type_counts[change_type] = (
                        change_type_counts.get(change_type, 0) + 1
                    )
                if warning_count is not None:
                    warning_counts.append(float(warning_count))
                    if warning_count > 0:
                        jobs_with_warnings += 1
                elif warnings_list:
                    warning_counts.append(float(len(warnings_list)))
                    jobs_with_warnings += 1

            avg_dedup = sum(dedup_times) / len(dedup_times) if dedup_times else None
            avg_db = sum(db_times) / len(db_times) if db_times else None
            avg_parse = sum(parse_times) / len(parse_times) if parse_times else None
            avg_tagging = (
                sum(tagging_times) / len(tagging_times) if tagging_times else None
            )
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
                sum(llm_total_tokens) / len(llm_total_tokens)
                if llm_total_tokens
                else None
            )
            avg_llm_cost = sum(llm_costs) / len(llm_costs) if llm_costs else None
            total_llm_cost = sum(llm_costs) if llm_costs else None
            llm_cache_rate = (
                llm_cache_hits / llm_total_calls if llm_total_calls > 0 else None
            )
            avg_warning_count = (
                sum(warning_counts) / len(warning_counts) if warning_counts else None
            )
            jobs_with_metrics_count = len(jobs_with_metrics)
            parse_warning_rate = (
                jobs_with_warnings / jobs_with_metrics_count * 100
                if jobs_with_metrics_count > 0
                else None
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
            # Parser/change-type aggregates
            "parser_usage": parser_usage,
            "parser_version_usage": parser_version_usage,
            "parse_methods": parse_methods,
            "parse_change_types": change_type_counts,
            "avg_parse_warning_count": avg_warning_count,
            "parse_warning_rate": parse_warning_rate,
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

    # ==================== Workspace-Scoped Methods ====================
    # These methods filter ingestion jobs by workspace through related entities
    # (conversation, watch_configuration). Used for multi-tenant security.

    def get_by_id_workspace(
        self, id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[IngestionJob]:
        """
        Get a single ingestion job by ID with workspace validation.

        This validates the job belongs to the workspace via either:
        1. The conversation it created (conversation.workspace_id)
        2. The watch configuration that triggered it (watch_config.workspace_id)

        Args:
            id: IngestionJob UUID
            workspace_id: Workspace UUID for validation

        Returns:
            IngestionJob if found and belongs to workspace, None otherwise
        """
        # First try to validate via conversation
        job_via_conv = (
            self.session.query(IngestionJob)
            .join(Conversation, IngestionJob.conversation_id == Conversation.id)
            .filter(
                IngestionJob.id == id,
                Conversation.workspace_id == workspace_id,
            )
            .first()
        )
        if job_via_conv:
            return job_via_conv

        # Try via watch configuration
        job_via_config = (
            self.session.query(IngestionJob)
            .join(
                WatchConfiguration,
                IngestionJob.source_config_id == WatchConfiguration.id,
            )
            .filter(
                IngestionJob.id == id,
                WatchConfiguration.workspace_id == workspace_id,
            )
            .first()
        )
        return job_via_config

    def get_recent_by_workspace(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Get recent ingestion jobs for a specific workspace.

        Filters jobs that are associated with the workspace through either:
        - The conversation they created
        - The watch configuration that triggered them

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records (default: 50)
            offset: Number of records to skip

        Returns:
            List of recent ingestion jobs in the workspace
        """
        # Get job IDs via conversations (use label for union compatibility)
        conv_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(Conversation, IngestionJob.conversation_id == Conversation.id)
            .filter(Conversation.workspace_id == workspace_id)
        )

        # Get job IDs via watch configurations
        config_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(
                WatchConfiguration,
                IngestionJob.source_config_id == WatchConfiguration.id,
            )
            .filter(WatchConfiguration.workspace_id == workspace_id)
        )

        # Union of both
        all_job_ids = conv_job_ids.union(config_job_ids).subquery()

        return (
            self.session.query(IngestionJob)
            .filter(IngestionJob.id.in_(self.session.query(all_job_ids.c.job_id)))
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def search_by_workspace(
        self,
        workspace_id: uuid.UUID,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IngestionJob]:
        """
        Search ingestion jobs within a specific workspace.

        Args:
            workspace_id: Workspace UUID (required)
            source_type: Filter by source type
            status: Filter by status
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of matching ingestion jobs in the workspace
        """
        # Get workspace-scoped job IDs (use label for union compatibility)
        conv_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(Conversation, IngestionJob.conversation_id == Conversation.id)
            .filter(Conversation.workspace_id == workspace_id)
        )
        config_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(
                WatchConfiguration,
                IngestionJob.source_config_id == WatchConfiguration.id,
            )
            .filter(WatchConfiguration.workspace_id == workspace_id)
        )
        all_job_ids = conv_job_ids.union(config_job_ids).subquery()

        # Build filter conditions
        filters = [IngestionJob.id.in_(self.session.query(all_job_ids.c.job_id))]

        if source_type:
            filters.append(IngestionJob.source_type == source_type)
        if status:
            filters.append(IngestionJob.status == status)
        if start_date:
            filters.append(IngestionJob.started_at >= start_date)
        if end_date:
            filters.append(IngestionJob.started_at <= end_date)

        return (
            self.session.query(IngestionJob)
            .filter(and_(*filters))
            .order_by(desc(IngestionJob.started_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count ingestion jobs for a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of ingestion jobs in the workspace
        """
        # Get workspace-scoped job IDs (use label for union compatibility)
        conv_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(Conversation, IngestionJob.conversation_id == Conversation.id)
            .filter(Conversation.workspace_id == workspace_id)
        )
        config_job_ids = (
            self.session.query(IngestionJob.id.label("job_id"))
            .join(
                WatchConfiguration,
                IngestionJob.source_config_id == WatchConfiguration.id,
            )
            .filter(WatchConfiguration.workspace_id == workspace_id)
        )
        all_job_ids = conv_job_ids.union(config_job_ids).subquery()

        return (
            self.session.query(IngestionJob)
            .filter(IngestionJob.id.in_(self.session.query(all_job_ids.c.job_id)))
            .count()
        )
