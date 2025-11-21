"""
Shared failure tracking utilities for ingestion pipeline.

Centralizes the logic for persisting ingestion/parser failures to the database.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from catsyphon.db.connection import db_session
from catsyphon.db.repositories import IngestionJobRepository

logger = logging.getLogger(__name__)


def track_failure(
    error: Exception,
    file_path: Optional[Path],
    source_type: str,
    source_config_id: Optional[UUID] = None,
) -> None:
    """
    Track an ingestion or parser failure in the ingestion_jobs table.

    Args:
        error: The exception that occurred
        file_path: Path to the file that failed (can be None)
        source_type: Source of the ingestion ('upload', 'watch', 'cli')
        source_config_id: Optional watch config ID (for watch source)

    This function is safe to call - it will log but not raise if tracking fails.
    """
    try:
        error_msg = f"{type(error).__name__}: {str(error)}"

        with db_session() as session:
            ingestion_repo = IngestionJobRepository(session)
            ingestion_repo.create(
                source_type=source_type,
                source_config_id=source_config_id,
                file_path=str(file_path) if file_path else None,
                status="failed",
                error_message=error_msg,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                processing_time_ms=0,  # Failed immediately
                incremental=False,
                messages_added=0,
            )
            session.commit()

        logger.debug(f"Tracked failure for {file_path}: {error_msg}")

    except Exception as tracking_error:
        # Don't let failure tracking errors break the main flow
        logger.debug(f"Could not track failure in DB: {tracking_error}")
