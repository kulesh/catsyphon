"""
Ingestion jobs API routes.

Endpoints for querying ingestion job history and statistics.

Security Note (Phase 1):
    All endpoints now use AuthContext for workspace isolation. Ingestion jobs
    are filtered by workspace through their related conversation or watch config.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    IngestionJobResponse,
    IngestionStatsResponse,
    TaggingQueueStatsResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    ConversationRepository,
    IngestionJobRepository,
    WatchConfigurationRepository,
)

router = APIRouter()


@router.get("/ingestion/jobs", response_model=list[IngestionJobResponse])
async def list_ingestion_jobs(
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[IngestionJobResponse]:
    """
    List ingestion jobs with optional filters.

    Args:
        source_type: Filter by source type ('watch', 'upload', 'cli')
        status: Filter by status ('success', 'failed', 'duplicate', 'skipped')
        page: Page number (1-indexed)
        page_size: Items per page (1-100)

    Returns:
        List of ingestion jobs in the current workspace
    """
    repo = IngestionJobRepository(session)

    # Calculate offset
    offset = (page - 1) * page_size

    # Use workspace-filtered search
    jobs = repo.search_by_workspace(
        workspace_id=auth.workspace_id,
        source_type=source_type,
        status=status,
        limit=page_size,
        offset=offset,
    )

    return [IngestionJobResponse.model_validate(j) for j in jobs]


@router.get("/ingestion/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> IngestionJobResponse:
    """
    Get a specific ingestion job by ID.

    Args:
        job_id: Ingestion job UUID

    Returns:
        Ingestion job details

    Raises:
        HTTPException: 404 if job not found or not in workspace
    """
    repo = IngestionJobRepository(session)
    job = repo.get_by_id_workspace(job_id, auth.workspace_id)

    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return IngestionJobResponse.model_validate(job)


@router.get("/ingestion/stats", response_model=IngestionStatsResponse)
async def get_ingestion_stats(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> IngestionStatsResponse:
    """
    Get overall ingestion statistics.

    Note: Currently returns global stats. In Phase 2, this should be filtered
    by workspace using repo.get_stats_by_workspace(auth.workspace_id).

    Returns:
        Ingestion statistics including counts by status, source type, and stage-level metrics
    """
    repo = IngestionJobRepository(session)
    # TODO (Phase 2): Filter stats by workspace
    # stats = repo.get_stats_by_workspace(auth.workspace_id)
    stats = repo.get_stats()

    return IngestionStatsResponse(
        total_jobs=stats["total_jobs"],  # type: ignore
        by_status=stats["by_status"],  # type: ignore
        by_source_type=stats["by_source_type"],  # type: ignore
        avg_processing_time_ms=stats["avg_processing_time_ms"],  # type: ignore
        peak_processing_time_ms=stats["peak_processing_time_ms"],  # type: ignore
        processing_time_percentiles=stats["processing_time_percentiles"],  # type: ignore
        incremental_jobs=stats["incremental_jobs"],  # type: ignore
        incremental_percentage=stats["incremental_percentage"],  # type: ignore
        incremental_speedup=stats["incremental_speedup"],  # type: ignore
        # Recent activity metrics
        jobs_last_hour=stats["jobs_last_hour"],  # type: ignore
        jobs_last_24h=stats["jobs_last_24h"],  # type: ignore
        processing_rate_per_minute=stats["processing_rate_per_minute"],  # type: ignore
        # Success/failure metrics
        success_rate=stats["success_rate"],  # type: ignore
        failure_rate=stats["failure_rate"],  # type: ignore
        time_since_last_failure_minutes=stats["time_since_last_failure_minutes"],  # type: ignore
        # Time-series data
        timeseries_24h=stats["timeseries_24h"],  # type: ignore
        # Stage-level metrics
        avg_parse_duration_ms=stats["avg_parse_duration_ms"],  # type: ignore
        avg_deduplication_check_ms=stats["avg_deduplication_check_ms"],  # type: ignore
        avg_database_operations_ms=stats["avg_database_operations_ms"],  # type: ignore
        # Tagging metrics
        avg_tagging_duration_ms=stats["avg_tagging_duration_ms"],  # type: ignore
        avg_llm_tagging_ms=stats["avg_llm_tagging_ms"],  # type: ignore
        avg_llm_prompt_tokens=stats["avg_llm_prompt_tokens"],  # type: ignore
        avg_llm_completion_tokens=stats["avg_llm_completion_tokens"],  # type: ignore
        avg_llm_total_tokens=stats["avg_llm_total_tokens"],  # type: ignore
        avg_llm_cost_usd=stats["avg_llm_cost_usd"],  # type: ignore
        total_llm_cost_usd=stats["total_llm_cost_usd"],  # type: ignore
        llm_cache_hit_rate=stats["llm_cache_hit_rate"],  # type: ignore
        error_rates_by_stage=stats["error_rates_by_stage"],  # type: ignore
        # Parser/change-type aggregates
        parser_usage=stats["parser_usage"],  # type: ignore
        parser_version_usage=stats["parser_version_usage"],  # type: ignore
        parse_methods=stats["parse_methods"],  # type: ignore
        parse_change_types=stats["parse_change_types"],  # type: ignore
        avg_parse_warning_count=stats["avg_parse_warning_count"],  # type: ignore
        parse_warning_rate=stats["parse_warning_rate"],  # type: ignore
    )


@router.get(
    "/ingestion/jobs/conversation/{conversation_id}",
    response_model=list[IngestionJobResponse],
)
async def get_conversation_ingestion_jobs(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[IngestionJobResponse]:
    """
    Get ingestion jobs for a specific conversation.

    Args:
        conversation_id: Conversation UUID

    Returns:
        List of ingestion jobs for the conversation

    Raises:
        HTTPException: 404 if conversation not found or not in workspace
    """
    # First validate conversation belongs to workspace
    conv_repo = ConversationRepository(session)
    conversation = conv_repo.get_by_id_workspace(conversation_id, auth.workspace_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get jobs for the validated conversation
    repo = IngestionJobRepository(session)
    jobs = repo.get_by_conversation(conversation_id)

    return [IngestionJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/ingestion/jobs/watch-config/{config_id}",
    response_model=list[IngestionJobResponse],
)
async def get_watch_config_ingestion_jobs(
    config_id: UUID,
    page: int = 1,
    page_size: int = 50,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> list[IngestionJobResponse]:
    """
    Get ingestion jobs for a specific watch configuration.

    Args:
        config_id: Watch configuration UUID
        page: Page number (1-indexed)
        page_size: Items per page (1-100)

    Returns:
        List of ingestion jobs for the watch configuration

    Raises:
        HTTPException: 404 if watch config not found or not in workspace
    """
    # First validate watch config belongs to workspace
    config_repo = WatchConfigurationRepository(session)
    config = config_repo.get(config_id)

    if not config or config.workspace_id != auth.workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Get jobs for the validated config
    repo = IngestionJobRepository(session)
    offset = (page - 1) * page_size
    jobs = repo.get_by_watch_config(config_id, limit=page_size, offset=offset)

    return [IngestionJobResponse.model_validate(j) for j in jobs]


@router.get("/ingestion/tagging-queue", response_model=TaggingQueueStatsResponse)
async def get_tagging_queue_stats(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> TaggingQueueStatsResponse:
    """
    Get statistics about the async tagging job queue.

    Returns:
        Tagging queue statistics including pending/processing/completed counts
        and worker status.
    """
    from catsyphon.tagging import TaggingJobQueue, get_worker_stats

    # Get queue stats from database
    queue = TaggingJobQueue(session)
    queue_stats = queue.get_stats()

    # Get worker stats (includes running status)
    worker_stats = get_worker_stats()

    return TaggingQueueStatsResponse(
        worker_running=worker_stats.get("running", False),
        pending=queue_stats.pending,
        processing=queue_stats.processing,
        completed=queue_stats.completed,
        failed=queue_stats.failed,
        total=queue_stats.total,
        jobs_processed=worker_stats.get("jobs_processed", 0),
        jobs_succeeded=worker_stats.get("jobs_succeeded", 0),
        jobs_failed=worker_stats.get("jobs_failed", 0),
    )
