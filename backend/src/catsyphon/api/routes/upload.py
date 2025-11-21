"""
Upload API routes.

Endpoints for uploading and ingesting conversation log files.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from catsyphon.api.schemas import UploadResponse, UploadResult
from catsyphon.db.connection import db_session
from catsyphon.exceptions import DuplicateFileError
from catsyphon.parsers import get_default_registry
from catsyphon.parsers.utils import is_conversational_log
from catsyphon.pipeline.failure_tracking import track_skip
from catsyphon.pipeline.ingestion import (
    ingest_conversation,
    link_orphaned_agents,
    _get_or_create_default_workspace,
)

router = APIRouter()


@router.post("/", response_model=UploadResponse)
async def upload_conversation_logs(
    files: list[UploadFile] = File(...),
    update_mode: str = Query(
        "skip",
        description="How to handle existing conversations: 'skip' (default), 'replace', or 'append'",
        regex="^(skip|replace|append)$",
    ),
) -> UploadResponse:
    """
    Upload and ingest one or more conversation log files.

    Accepts .jsonl files, parses them, and stores them in the database.
    Returns summary of successful and failed uploads with conversation IDs.

    Parameters:
    - files: One or more .jsonl conversation log files
    - update_mode: How to handle existing conversations (by session_id):
        - 'skip' (default): Skip updates for existing conversations
        - 'replace': Delete and recreate existing conversations with new data
        - 'append': Append new messages to existing conversations
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    registry = get_default_registry()
    results: list[UploadResult] = []
    success_count = 0
    failed_count = 0

    for uploaded_file in files:
        # Validate file extension
        if not uploaded_file.filename or not uploaded_file.filename.endswith(".jsonl"):
            results.append(
                UploadResult(
                    filename=uploaded_file.filename or "unknown",
                    status="error",
                    error="Invalid file type. Only .jsonl files are supported.",
                )
            )
            failed_count += 1
            continue

        try:
            # Read file content
            content = await uploaded_file.read()

            # Save to temporary file for parsing
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".jsonl", delete=False
            ) as temp_file:
                temp_file.write(content)
                temp_path = Path(temp_file.name)

            try:
                # Pre-filter: Check if file is a conversational log
                if not is_conversational_log(temp_path):
                    # Metadata-only file (no conversation messages)
                    skip_reason = (
                        "Metadata-only file (no conversation messages found). "
                        "These files typically contain only 'summary' or 'file-history-snapshot' "
                        "entries and are not meant to be parsed as conversations."
                    )

                    # Track skip in database
                    track_skip(
                        file_path=temp_path,
                        source_type="upload",
                        reason=skip_reason,
                    )

                    results.append(
                        UploadResult(
                            filename=uploaded_file.filename,
                            status="skipped",
                            error=skip_reason,
                        )
                    )
                    # Note: skipped files are counted as success (not failed)
                    success_count += 1
                    # Clean up and continue to next file
                    temp_path.unlink(missing_ok=True)
                    continue

                # Parse the file
                conversation = registry.parse(temp_path)

                # Store to database with specified update_mode
                try:
                    with db_session() as session:
                        db_conversation = ingest_conversation(
                            session=session,
                            parsed=conversation,
                            project_name=None,  # Auto-extract from log
                            developer_username=None,  # Auto-extract from log
                            file_path=temp_path,  # Pass temp path for hash calculation
                            skip_duplicates=True,  # Always skip file hash duplicates in API
                            update_mode=update_mode,  # Use provided update mode
                        )
                        session.commit()

                        # Refresh to load relationships from database
                        session.refresh(db_conversation)

                        # Count related records from database object
                        message_count = len(conversation.messages)  # Use parsed count
                        epoch_count = len(db_conversation.epochs)
                        files_count = len(db_conversation.files_touched)

                        results.append(
                            UploadResult(
                                filename=uploaded_file.filename,
                                status="success",
                                conversation_id=db_conversation.id,
                                message_count=message_count,
                                epoch_count=epoch_count,
                                files_count=files_count,
                            )
                        )
                        success_count += 1

                except DuplicateFileError:
                    # File is a duplicate, return status="duplicate"
                    results.append(
                        UploadResult(
                            filename=uploaded_file.filename,
                            status="duplicate",
                            error="File has already been processed",
                        )
                    )
                    success_count += 1  # Count duplicates as successful (not an error)

            finally:
                # Clean up temporary file
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            # Track parser/upload failures in ingestion_jobs table
            from catsyphon.pipeline.failure_tracking import track_failure

            track_failure(
                error=e,
                file_path=temp_path if 'temp_path' in locals() else None,
                source_type="upload",
            )

            results.append(
                UploadResult(
                    filename=uploaded_file.filename,
                    status="error",
                    error=str(e),
                )
            )
            failed_count += 1

    # Post-upload linking: Link orphaned agents to parents after all files processed
    # This handles cases where agents were uploaded before their parent conversations
    if success_count > 0:
        try:
            with db_session() as session:
                workspace_id = _get_or_create_default_workspace(session)
                linked_count = link_orphaned_agents(session, workspace_id)
                session.commit()
                # Note: We don't report linking failures to the user since the
                # conversations were successfully ingested. Linking is a post-processing step.
        except Exception:
            # Silently ignore linking errors - don't fail the upload
            pass

    return UploadResponse(
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )
