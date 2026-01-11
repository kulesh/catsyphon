"""
Unified ingestion orchestrator for parser ↔ ingestion pipeline.

Centralizes deduplication, change detection, parsing selection (full vs incremental),
and job lifecycle so CLI, upload API, and watch daemon share one code path.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import UUID

import catsyphon.pipeline.ingestion as ingestion_module
from catsyphon.analytics.cache import PROJECT_ANALYTICS_CACHE
from catsyphon.db.repositories import ConversationRepository, RawLogRepository
from catsyphon.exceptions import DuplicateFileError
from catsyphon.models.db import Conversation
from catsyphon.parsers.incremental import ChangeType, detect_file_change_type
from catsyphon.parsers.registry import ParserRegistry
from catsyphon.parsers.types import ParseResult
from catsyphon.pipeline.ingestion import (
    IngestionJobTracker,
    StageMetrics,
    ingest_messages_incremental,
)


@dataclass
class IngestOutcome:
    """Unified ingestion result for orchestrator callers."""

    conversation: Optional[Conversation]
    conversation_id: Optional[UUID]
    status: str
    job_id: UUID
    incremental: bool
    parser_name: Optional[str] = None
    parse_change_type: Optional[str] = None


def ingest_log_file(
    session,
    file_path: Path,
    registry: ParserRegistry,
    project_name: Optional[str] = None,
    developer_username: Optional[str] = None,
    tags: Optional[dict] = None,
    skip_duplicates: bool = True,
    update_mode: str = "skip",
    source_type: str = "cli",
    source_config_id: Optional[UUID] = None,
    created_by: Optional[str] = None,
    enable_incremental: bool = True,
) -> IngestOutcome:
    """
    Ingest a single log file with dedup + change detection + parser selection.

    .. deprecated::
        Use :class:`catsyphon.services.IngestionService.ingest_from_file` instead.
        This function will be removed in a future version.

    Returns:
        IngestOutcome containing conversation and job metadata
    """
    import warnings
    warnings.warn(
        "ingest_log_file is deprecated. Use IngestionService.ingest_from_file instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    metrics_metadata: dict[str, str] = {}
    metrics = StageMetrics()
    tracker = IngestionJobTracker(
        session=session,
        source_type=source_type,
        source_config_id=source_config_id,
        file_path=file_path,
        created_by=created_by,
        incremental=False,
    )

    raw_log_repo = RawLogRepository(session)
    conversation_repo = ConversationRepository(session)

    # Deduplication by content hash
    from catsyphon.utils.hashing import calculate_file_hash

    metrics.start_stage("deduplication_check_ms")
    file_hash = calculate_file_hash(file_path)
    if raw_log_repo.exists_by_file_hash(file_hash):
        metrics.end_stage("deduplication_check_ms")
        existing = raw_log_repo.get_by_file_hash(file_hash)
        if skip_duplicates:
            tracker.mark_duplicate(
                conversation_id=existing.conversation_id if existing else None,
                raw_log_id=existing.id if existing else None,
                metrics=metrics,
                metadata_fields=metrics_metadata,
            )
            conversation = None
            if existing and existing.conversation_id:
                conversation = conversation_repo.get(existing.conversation_id)
                if conversation:
                    session.refresh(conversation)

            return IngestOutcome(
                conversation=conversation,
                conversation_id=conversation.id if conversation else None,
                status=tracker.job.status,
                job_id=tracker.job.id,
                incremental=False,
                parser_name=None,
                parse_change_type=metrics_metadata.get("parse_change_type"),
            )

            tracker.mark_failed(
                error_message=f"Duplicate file (hash: {file_hash[:8]}...)",
                incremental=False,
                metrics=metrics,
                metadata_fields=metrics_metadata,
            )
            raise DuplicateFileError(file_hash, str(file_path))
    metrics.end_stage("deduplication_check_ms")

    existing_raw_log = raw_log_repo.get_by_file_path(str(file_path))
    change_type: Optional[ChangeType] = None

    if existing_raw_log and enable_incremental:
        change_type = detect_file_change_type(
            file_path,
            existing_raw_log.last_processed_offset or 0,
            existing_raw_log.file_size_bytes or 0,
            existing_raw_log.partial_hash,
        )
        metrics_metadata["parse_change_type"] = change_type.value

        if change_type == ChangeType.UNCHANGED:
            change_details = {
                "change_type": change_type.value,
                "last_processed_offset": existing_raw_log.last_processed_offset or 0,
                "last_file_size": existing_raw_log.file_size_bytes or 0,
                "current_file_size": file_path.stat().st_size,
            }
            metrics_metadata.update(change_details)
            tracker.mark_skipped(
                conversation_id=existing_raw_log.conversation_id,
                raw_log_id=existing_raw_log.id,
                metrics=metrics,
                metadata_fields=metrics_metadata,
                reason=(
                    "File unchanged since last ingest "
                    f"(change_type={change_type.value}, "
                    f"current_size={change_details['current_file_size']}, "
                    f"last_size={change_details['last_file_size']}, "
                    f"last_offset={change_details['last_processed_offset']})"
                ),
            )
            conversation = conversation_repo.get(existing_raw_log.conversation_id)
            if conversation:
                session.refresh(conversation)
            return IngestOutcome(
                conversation=conversation,
                conversation_id=existing_raw_log.conversation_id,
                status=tracker.job.status,
                job_id=tracker.job.id,
                incremental=False,
                parser_name=None,
                parse_change_type=change_type.value,
            )

        if change_type == ChangeType.APPEND:
            incremental_parser = registry.find_incremental_parser(file_path)
            if incremental_parser:
                # If this file was previously parsed, ensure the incremental parser matches
                # the original agent/parser type to avoid mis-matched parsers (e.g., Claude
                # incremental parser claiming a Codex log).
                parser_meta = getattr(incremental_parser, "metadata", None)
                if (
                    existing_raw_log
                    and existing_raw_log.agent_type
                    and parser_meta
                    and parser_meta.name != existing_raw_log.agent_type
                ):
                    incremental_parser = None

            if incremental_parser:
                parse_start = time.time() * 1000
                inc_result = incremental_parser.parse_incremental(
                    file_path,
                    existing_raw_log.last_processed_offset,
                    existing_raw_log.last_processed_line,
                )
                parse_duration_ms = (time.time() * 1000) - parse_start
                parse_metrics = {
                    "parse_method": "incremental",
                    "parse_change_type": change_type.value,
                    "parse_messages_count": len(inc_result.new_messages),
                    "parser_name": (
                        parser_meta.name
                        if parser_meta
                        else type(incremental_parser).__name__.lower()
                    ),
                    "parser_version": parser_meta.version if parser_meta else None,
                    "parse_duration_ms": parse_duration_ms,
                }
                conversation = ingest_messages_incremental(
                    session=session,
                    incremental_result=inc_result,
                    conversation_id=str(existing_raw_log.conversation_id),
                    raw_log_id=str(existing_raw_log.id),
                    tags=tags,
                    source_type=source_type,
                    source_config_id=source_config_id,
                    created_by=created_by,
                    parse_metrics=parse_metrics,
                    tracker=tracker,
                    stage_metrics=metrics,
                    stage_metadata=metrics_metadata,
                )
                if conversation and conversation.project_id:
                    PROJECT_ANALYTICS_CACHE.invalidate(conversation.project_id)
                return IngestOutcome(
                    conversation=conversation,
                    conversation_id=conversation.id if conversation else None,
                    status=tracker.job.status,
                    job_id=tracker.job.id,
                    incremental=True,
                    parser_name=parse_metrics.get("parser_name"),
                    parse_change_type=parse_metrics.get("parse_change_type"),
                )
            # fall through to full parse

        # Truncate/rewrite: force replace
        if change_type in (ChangeType.TRUNCATE, ChangeType.REWRITE):
            update_mode = "replace"

    # Full parse path
    parse_result: ParseResult = registry.parse_with_metadata(file_path)
    parse_metrics = {
        "parse_method": parse_result.parse_method,
        "parse_change_type": parse_result.change_type
        or metrics_metadata.get("parse_change_type"),
        "parse_messages_count": len(parse_result.conversation.messages),
        "parser_name": parse_result.parser_name,
        "parser_version": parse_result.parser_version,
        **(parse_result.metrics or {}),
    }
    if parse_result.warnings:
        parse_metrics["parse_warnings"] = parse_result.warnings
        parse_metrics["parse_warning_count"] = len(parse_result.warnings)

    # Skip metadata-only files (e.g., file-history-snapshot logs with no conversation messages)
    parsed_conv = parse_result.conversation
    if parsed_conv.conversation_type == "metadata" and len(parsed_conv.messages) == 0:
        reason = (
            f"Metadata-only file with no conversation messages "
            f"(type={parsed_conv.conversation_type}, messages=0)"
        )
        tracker.mark_skipped(
            conversation_id=None,
            raw_log_id=None,
            metrics=metrics,
            metadata_fields={**metrics_metadata, **parse_metrics},
            reason=reason,
        )
        return IngestOutcome(
            conversation=None,
            conversation_id=None,
            status="skipped",
            job_id=tracker.job.id,
            incremental=False,
            parser_name=parse_metrics.get("parser_name"),
            parse_change_type=parse_metrics.get("parse_change_type"),
        )

    conversation = ingestion_module.ingest_conversation(
        session=session,
        parsed=parse_result.conversation,
        parse_result=parse_result,
        parse_metrics=parse_metrics,
        project_name=project_name,
        developer_username=developer_username,
        file_path=file_path,
        tags=tags,
        skip_duplicates=skip_duplicates,
        update_mode=update_mode,
        source_type=source_type,
        source_config_id=source_config_id,
        created_by=created_by,
        tracker=tracker,
        stage_metrics=metrics,
        stage_metadata=metrics_metadata,
    )

    if conversation and conversation.project_id:
        PROJECT_ANALYTICS_CACHE.invalidate(conversation.project_id)

    return IngestOutcome(
        conversation=conversation,
        conversation_id=conversation.id if conversation else None,
        status=tracker.job.status,
        job_id=tracker.job.id,
        incremental=tracker.job.incremental,
        parser_name=parse_metrics.get("parser_name"),
        parse_change_type=parse_metrics.get("parse_change_type"),
    )
