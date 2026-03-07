"""Repository for immutable analytics provenance records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import AnalysisRun, BackingModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisRunRepository(BaseRepository[AnalysisRun]):
    """Repository for analytics provenance writes and lookups."""

    def __init__(self, session: Session):
        super().__init__(AnalysisRun, session)

    def get_or_create_backing_model(
        self,
        *,
        provider: str,
        model_id: str,
        display_name: str | None = None,
    ) -> BackingModel:
        stmt = select(BackingModel).where(
            BackingModel.provider == provider,
            BackingModel.model_id == model_id,
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            return existing

        backing_model = BackingModel(
            provider=provider,
            model_id=model_id,
            display_name=display_name,
        )
        self.session.add(backing_model)
        self.session.flush()
        self.session.refresh(backing_model)
        return backing_model

    def create_run(
        self,
        *,
        capability: str,
        artifact_type: str,
        artifact_id: Optional[UUID],
        conversation_id: Optional[UUID],
        provider: str,
        model_id: str,
        prompt_version: str,
        prompt_hash: Optional[str] = None,
        input_hash: Optional[str] = None,
        input_canonical_version: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[float] = None,
        finish_reason: Optional[str] = None,
        status: str = "succeeded",
        error_message: Optional[str] = None,
        source: str = "live",
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        extra_data: Optional[dict[str, Any]] = None,
    ) -> AnalysisRun:
        backing_model = self.get_or_create_backing_model(
            provider=provider,
            model_id=model_id,
        )

        run = AnalysisRun(
            capability=capability,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            conversation_id=conversation_id,
            backing_model_id=backing_model.id,
            provider=provider,
            model_id=model_id,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            input_canonical_version=input_canonical_version,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            status=status,
            error_message=error_message,
            source=source,
            started_at=started_at or _utc_now(),
            completed_at=completed_at,
            extra_data=extra_data or {},
        )

        self.session.add(run)
        self.session.flush()
        self.session.refresh(run)
        return run

