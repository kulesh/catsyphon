"""
Upload API routes.

Endpoints for uploading and ingesting conversation log files.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import UploadResponse, UploadResult
from catsyphon.db.connection import db_session, get_db
from catsyphon.exceptions import DuplicateFileError
from catsyphon.parsers import get_default_registry
from catsyphon.pipeline.ingestion import link_orphaned_agents

router = APIRouter()


@router.post("/", response_model=UploadResponse)
async def upload_conversation_logs(
    auth: AuthContext = Depends(get_auth_context),
    files: list[UploadFile] = File(...),
    update_mode: str = Query(
        "skip",
        description="How to handle existing conversations: 'skip' (default), 'replace', or 'append'",
        regex="^(skip|replace|append)$",
    ),
    session: Session = Depends(get_db),
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

    Requires X-Workspace-Id header.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    registry = get_default_registry()
    results: list[UploadResult] = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

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

                # Store to database with specified update_mode
                try:
                    from catsyphon.pipeline.orchestrator import ingest_log_file

                    outcome = ingest_log_file(
                        session=session,
                        file_path=temp_path,
                        registry=registry,
                        project_name=None,  # Auto-extract from log
                        developer_username=None,  # Auto-extract from log
                        tags=None,
                        skip_duplicates=True,  # Always skip file hash duplicates in API
                        update_mode=update_mode,  # Use provided update mode
                        source_type="upload",
                        source_config_id=None,
                        created_by=None,
                        enable_incremental=True,
                    )
                    session.commit()

                    db_conversation = outcome.conversation
                    status_label = outcome.status or "success"

                    if status_label == "duplicate":
                        results.append(
                            UploadResult(
                                filename=uploaded_file.filename,
                                status="duplicate",
                                conversation_id=(
                                    db_conversation.id if db_conversation else None
                                ),
                                message_count=(
                                    db_conversation.message_count
                                    if db_conversation
                                    else None
                                ),
                                epoch_count=(
                                    len(db_conversation.epochs)
                                    if db_conversation
                                    else None
                                ),
                                files_count=(
                                    len(db_conversation.files_touched)
                                    if db_conversation
                                    else None
                                ),
                            )
                        )
                        success_count += 1  # Duplicates are not treated as errors
                        continue

                    if status_label == "skipped":
                        results.append(
                            UploadResult(
                                filename=uploaded_file.filename,
                                status="skipped",
                                error="File unchanged or skipped",
                            )
                        )
                        skipped_count += 1
                        continue

                    if not db_conversation:
                        raise ValueError("Ingestion returned no conversation")

                    # Refresh to load relationships from database
                    session.refresh(db_conversation)

                    # Count related records from database object
                    message_count = db_conversation.message_count
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
                except Exception as parse_or_ingest_error:
                    # Treat parse errors as skipped to align with API contract
                    results.append(
                        UploadResult(
                            filename=uploaded_file.filename,
                            status="skipped",
                            error=str(parse_or_ingest_error),
                        )
                    )
                    skipped_count += 1
                    # Rollback any partial transaction
                    session.rollback()

            finally:
                # Clean up temporary file
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            # Track parser/upload failures in ingestion_jobs table
            from catsyphon.pipeline.failure_tracking import track_failure

            track_failure(
                error=e,
                file_path=temp_path if "temp_path" in locals() else None,
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
            with db_session() as link_session:
                linked_count = link_orphaned_agents(link_session, auth.workspace_id)
                link_session.commit()
                # Note: We don't report linking failures to the user since the
                # conversations were successfully ingested. Linking is a post-processing step.
        except Exception:
            # Silently ignore linking errors - don't fail the upload
            pass

    return UploadResponse(
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        results=results,
    )
