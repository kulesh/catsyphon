"""Digest API routes."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import WeeklyDigestRequest, WeeklyDigestResponse
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import DigestRepository
from catsyphon.digests import WeeklyDigestGenerator

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("/weekly", response_model=WeeklyDigestResponse)
def get_weekly_digest(
    auth: AuthContext = Depends(get_auth_context),
    period_start: datetime | None = Query(
        default=None, description="Start of the digest period"
    ),
    period_end: datetime | None = Query(
        default=None, description="End of the digest period"
    ),
    session: Session = Depends(get_db),
) -> WeeklyDigestResponse:
    digest_repo = DigestRepository(session)

    if not period_end:
        period_end = datetime.now().astimezone()
    if not period_start:
        period_start = period_end - timedelta(days=7)

    cached = digest_repo.get_latest(auth.workspace_id, period_start, period_end)
    if not cached:
        raise HTTPException(status_code=404, detail="Weekly digest not found")

    return WeeklyDigestResponse(
        workspace_id=cached.workspace_id,
        period_start=cached.period_start,
        period_end=cached.period_end,
        version=cached.version,
        summary=cached.summary,
        wins=cached.wins,
        blockers=cached.blockers,
        highlights=cached.highlights,
        metrics=cached.metrics,
        generated_at=cached.generated_at,
    )


@router.post("/weekly", response_model=WeeklyDigestResponse)
def generate_weekly_digest(
    payload: WeeklyDigestRequest,
    auth: AuthContext = Depends(get_auth_context),
    force_regenerate: bool = Query(
        default=False, description="Force regeneration even if cached digest exists"
    ),
    session: Session = Depends(get_db),
) -> WeeklyDigestResponse:
    digest_repo = DigestRepository(session)
    generator = WeeklyDigestGenerator(session)

    cached = digest_repo.get_latest(
        auth.workspace_id, payload.period_start, payload.period_end
    )
    if cached and not force_regenerate:
        return WeeklyDigestResponse(
            workspace_id=cached.workspace_id,
            period_start=cached.period_start,
            period_end=cached.period_end,
            version=cached.version,
            summary=cached.summary,
            wins=cached.wins,
            blockers=cached.blockers,
            highlights=cached.highlights,
            metrics=cached.metrics,
            generated_at=cached.generated_at,
        )

    digest = generator.generate(
        auth.workspace_id, payload.period_start, payload.period_end
    )
    saved = digest_repo.save(
        auth.workspace_id,
        payload.period_start,
        payload.period_end,
        digest,
    )
    session.commit()

    return WeeklyDigestResponse(
        workspace_id=saved.workspace_id,
        period_start=saved.period_start,
        period_end=saved.period_end,
        version=saved.version,
        summary=saved.summary,
        wins=saved.wins,
        blockers=saved.blockers,
        highlights=saved.highlights,
        metrics=saved.metrics,
        generated_at=saved.generated_at,
    )
