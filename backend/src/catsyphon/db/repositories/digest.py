"""Repository for weekly digests."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import WeeklyDigest


class DigestRepository(BaseRepository[WeeklyDigest]):
    """Repository for managing weekly digests."""

    def __init__(self, session: Session):
        super().__init__(WeeklyDigest, session)

    def get_latest(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[WeeklyDigest]:
        stmt = (
            select(WeeklyDigest)
            .where(
                WeeklyDigest.workspace_id == workspace_id,
                WeeklyDigest.period_start == period_start,
                WeeklyDigest.period_end == period_end,
            )
            .order_by(WeeklyDigest.generated_at.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def save(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
        digest: dict[str, Any],
    ) -> WeeklyDigest:
        self.invalidate(workspace_id, period_start, period_end)
        db_digest = WeeklyDigest(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            version=1,
            summary=digest.get("summary", ""),
            wins=digest.get("wins", []),
            blockers=digest.get("blockers", []),
            highlights=digest.get("highlights", []),
            metrics=digest.get("metrics", {}),
            generated_at=datetime.now().astimezone(),
        )
        self.session.add(db_digest)
        self.session.flush()
        self.session.refresh(db_digest)
        return db_digest

    def invalidate(
        self, workspace_id: UUID, period_start: datetime, period_end: datetime
    ) -> int:
        stmt = delete(WeeklyDigest).where(
            WeeklyDigest.workspace_id == workspace_id,
            WeeklyDigest.period_start == period_start,
            WeeklyDigest.period_end == period_end,
        )
        result = self.session.execute(stmt)
        return result.rowcount or 0
