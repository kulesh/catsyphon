"""Recap API routes."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import ConversationRecapResponse
from catsyphon.canonicalization import CanonicalType
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import (
    AnalysisRunRepository,
    CanonicalRepository,
    ConversationRepository,
    RecapRepository,
)
from catsyphon.llm import run_to_provenance_dict
from catsyphon.models.db import AnalysisRun
from catsyphon.recaps import RecapGenerator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{conversation_id}/recap", response_model=ConversationRecapResponse)
def get_conversation_recap(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> ConversationRecapResponse:
    conversation_repo = ConversationRepository(session)
    recap_repo = RecapRepository(session)

    conversation = conversation_repo.get_by_id_workspace(
        conversation_id, auth.workspace_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

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
        metadata=cached.recap_metadata,
        provenance=(
            run_to_provenance_dict(run)
            if (
                cached.latest_run_id
                and (run := session.get(AnalysisRun, cached.latest_run_id)) is not None
            )
            else {}
        ),
        canonical_version=cached.canonical_version,
        generated_at=cached.generated_at,
    )


@router.post("/{conversation_id}/recap", response_model=ConversationRecapResponse)
def generate_conversation_recap(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    force_regenerate: bool = Query(
        default=False, description="Force regeneration even if cached recap exists"
    ),
    session: Session = Depends(get_db),
) -> ConversationRecapResponse:
    conversation_repo = ConversationRepository(session)
    recap_repo = RecapRepository(session)
    canonical_repo = CanonicalRepository(session)

    conversation = conversation_repo.get_with_relations(
        conversation_id, auth.workspace_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    cached = recap_repo.get_latest(conversation_id)
    if cached and not force_regenerate:
        return ConversationRecapResponse(
            conversation_id=cached.conversation_id,
            version=cached.version,
            summary=cached.summary,
            key_files=cached.key_files,
            blockers=cached.blockers,
            next_steps=cached.next_steps,
            metadata=cached.recap_metadata,
            provenance=(
                run_to_provenance_dict(run)
                if (
                    cached.latest_run_id
                    and (
                        run := session.get(AnalysisRun, cached.latest_run_id)
                    ) is not None
                )
                else {}
            ),
            canonical_version=cached.canonical_version,
            generated_at=cached.generated_at,
        )

    if force_regenerate:
        recap_repo.invalidate(conversation_id)
        canonical_repo.invalidate(
            conversation_id=conversation_id,
            canonical_type=CanonicalType.INSIGHTS.value,
        )

    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"{settings.required_llm_api_key_env()} not configured. "
                "Recaps require AI analysis."
            ),
        )

    generator = RecapGenerator(
        api_key=settings.get_llm_api_key(),
        model=settings.active_llm_model,
        provider=settings.active_llm_provider,
    )
    children = conversation.children if hasattr(conversation, "children") else []
    logger.info("Generating recap for conversation %s", conversation_id)
    try:
        recap, llm_metrics = generator.generate(
            conversation,
            session,
            children=children,
        )
    except Exception as exc:
        logger.exception("Recap generation failed for conversation %s", conversation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recap generation failed. Check server logs for details.",
        ) from exc

    metadata = recap.get("metadata", {})
    metadata["llm_metrics"] = llm_metrics
    recap["metadata"] = metadata

    run_repo = AnalysisRunRepository(session)
    run = run_repo.create_run(
        capability="recap",
        artifact_type="conversation_recap",
        artifact_id=conversation_id,
        conversation_id=conversation_id,
        provider=str(llm_metrics.get("llm_provider", settings.active_llm_provider)),
        model_id=str(llm_metrics.get("llm_model", settings.active_llm_model)),
        prompt_version="recap-v1",
        input_canonical_version=int(llm_metrics.get("canonical_version", 1)),
        temperature=generator.temperature,
        max_tokens=generator.max_tokens,
        prompt_tokens=int(llm_metrics.get("llm_prompt_tokens", 0)),
        completion_tokens=int(llm_metrics.get("llm_completion_tokens", 0)),
        total_tokens=int(llm_metrics.get("llm_total_tokens", 0)),
        cost_usd=float(llm_metrics.get("llm_cost_usd", 0.0) or 0.0),
        latency_ms=float(llm_metrics.get("llm_recap_ms", 0.0) or 0.0),
        finish_reason=None,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )

    saved = recap_repo.save(
        conversation_id=conversation_id,
        recap=recap,
        canonical_version=llm_metrics.get("canonical_version", 1),
        latest_run_id=run.id,
    )
    session.commit()
    logger.info("Recap saved for conversation %s", conversation_id)

    return ConversationRecapResponse(
        conversation_id=saved.conversation_id,
        version=saved.version,
        summary=saved.summary,
        key_files=saved.key_files,
        blockers=saved.blockers,
        next_steps=saved.next_steps,
        metadata=saved.recap_metadata,
        provenance=run_to_provenance_dict(run),
        canonical_version=saved.canonical_version,
        generated_at=saved.generated_at,
    )
