"""OpenTelemetry event repository."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import OtelEvent


class OtelEventRepository(BaseRepository[OtelEvent]):
    """Repository for OtelEvent model."""

    def __init__(self, session: Session):
        super().__init__(OtelEvent, session)

    def bulk_create(self, events: List[dict]) -> List[OtelEvent]:
        """Bulk create OTEL events for efficiency."""
        instances = [OtelEvent(**event) for event in events]
        self.session.bulk_save_objects(instances, return_defaults=True)
        self.session.flush()
        return instances

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """Count OTEL events for a workspace."""
        return (
            self.session.query(func.count(OtelEvent.id))
            .filter(OtelEvent.workspace_id == workspace_id)
            .scalar()
            or 0
        )

    def last_event_time(self, workspace_id: uuid.UUID) -> Optional[datetime]:
        """Get most recent OTEL event timestamp for a workspace."""
        return (
            self.session.query(func.max(OtelEvent.event_timestamp))
            .filter(OtelEvent.workspace_id == workspace_id)
            .scalar()
        )
