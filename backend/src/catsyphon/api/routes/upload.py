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
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository
from catsyphon.services import IngestionService

router = APIRouter()


@router.post("/", response_model=UploadResponse)
async def upload_conversation_logs(
    auth: AuthContext = Depends(get_auth_context),
    files: list[UploadFile] = File(...),
    update_mode: str = Query(
        "skip",
        description="How to handle existing conversations: 'skip' (default), 'replace', or 'append'",
        pattern="^(skip|replace|append)$",
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

    results: list[UploadResult] = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    # Create service and repository
    service = IngestionService(session)
    conv_repo = ConversationRepository(session)

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
                # Use unified ingestion service
                outcome = service.ingest_from_file(
                    file_path=temp_path,
                    workspace_id=auth.workspace_id,
                    source_type="upload",
                    enable_tagging=True,  # Enable tagging for uploads
                )

                if outcome.status == "error":
                    results.append(
                        UploadResult(
                            filename=uploaded_file.filename,
                            status="skipped",
                            error=outcome.error_message or "Ingestion failed",
                        )
                    )
                    skipped_count += 1
                    session.rollback()
                    continue

                if outcome.status == "duplicate":
                    # Get conversation details if we have an ID
                    if outcome.conversation_id:
                        conv = conv_repo.get(outcome.conversation_id)
                        results.append(
                            UploadResult(
                                filename=uploaded_file.filename,
                                status="duplicate",
                                conversation_id=outcome.conversation_id,
                                message_count=conv.message_count if conv else 0,
                                epoch_count=len(conv.epochs) if conv else 0,
                                files_count=len(conv.files_touched) if conv else 0,
                            )
                        )
                    else:
                        results.append(
                            UploadResult(
                                filename=uploaded_file.filename,
                                status="duplicate",
                                error="File has already been processed",
                            )
                        )
                    success_count += 1  # Duplicates are not treated as errors
                    continue

                if outcome.status == "skipped":
                    results.append(
                        UploadResult(
                            filename=uploaded_file.filename,
                            status="skipped",
                            error="File unchanged or skipped",
                        )
                    )
                    skipped_count += 1
                    continue

                # Success case
                session.commit()

                # Get conversation details
                message_count = outcome.messages_added
                epoch_count = 0
                files_count = 0
                if outcome.conversation_id:
                    conv = conv_repo.get(outcome.conversation_id)
                    if conv:
                        epoch_count = len(conv.epochs)
                        files_count = len(conv.files_touched)

                results.append(
                    UploadResult(
                        filename=uploaded_file.filename,
                        status="success",
                        conversation_id=outcome.conversation_id,
                        message_count=message_count,
                        epoch_count=epoch_count,
                        files_count=files_count,
                    )
                )
                success_count += 1

            finally:
                # Clean up temporary file
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            results.append(
                UploadResult(
                    filename=uploaded_file.filename,
                    status="error",
                    error=str(e),
                )
            )
            failed_count += 1

    # Orphan linking is handled by the service automatically

    return UploadResponse(
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        results=results,
    )
