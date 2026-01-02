"""Recap API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import ConversationRecapResponse
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository, RecapRepository

router = APIRouter()


@router.get("/{conversation_id}/recap", response_model=ConversationRecapResponse)
def get_conversation_recap(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    force_regenerate: bool = Query(
        default=False, description="Force regeneration if recap is cached"
    ),
    session: Session = Depends(get_db),
) -> ConversationRecapResponse:
    conversation_repo = ConversationRepository(session)
    recap_repo = RecapRepository(session)

    conversation = conversation_repo.get_by_id_workspace(conversation_id, auth.workspace_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if force_regenerate:
        recap_repo.invalidate(conversation_id)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Recap regeneration not implemented yet",
        )

    cached = recap_repo.get_latest(conversation_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Recap not found")

    return ConversationRecapResponse(
        conversation_id=cached.conversation_id,
        version=cached.version,
        summary=cached.summary,
        key_files=cached.key_files,
        blockers=cached.blockers,
        next_steps=cached.next_steps,
        metadata=cached.metadata,
        canonical_version=cached.canonical_version,
        generated_at=cached.generated_at,
    )


@router.post("/{conversation_id}/recap", response_model=ConversationRecapResponse)
def generate_conversation_recap(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ConversationRecapResponse:
    conversation_repo = ConversationRepository(session)
    recap_repo = RecapRepository(session)

    conversation = conversation_repo.get_by_id_workspace(conversation_id, auth.workspace_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    cached = recap_repo.get_latest(conversation_id)
    if cached:
        return ConversationRecapResponse(
            conversation_id=cached.conversation_id,
            version=cached.version,
            summary=cached.summary,
            key_files=cached.key_files,
            blockers=cached.blockers,
            next_steps=cached.next_steps,
            metadata=cached.metadata,
            canonical_version=cached.canonical_version,
            generated_at=cached.generated_at,
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Recap generation not implemented yet",
    )
