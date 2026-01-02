"""Repository for conversation recaps caching."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import ConversationRecap


class RecapRepository(BaseRepository[ConversationRecap]):
    """Repository for managing cached conversation recaps."""

    def __init__(self, session: Session):
        super().__init__(ConversationRecap, session)

    def get_latest(self, conversation_id: UUID) -> Optional[ConversationRecap]:
        stmt = (
            select(ConversationRecap)
            .where(ConversationRecap.conversation_id == conversation_id)
            .order_by(ConversationRecap.generated_at.desc())
            .limit(1)
        )
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def save(
        self,
        conversation_id: UUID,
        recap: dict[str, Any],
        canonical_version: int,
    ) -> ConversationRecap:
        self.invalidate(conversation_id)
        db_recap = ConversationRecap(
            conversation_id=conversation_id,
            version=1,
            summary=recap.get("summary", "") or "",
            key_files=recap.get("key_files") or [],
            blockers=recap.get("blockers") or [],
            next_steps=recap.get("next_steps") or [],
            metadata=recap.get("metadata") or {},
            canonical_version=canonical_version,
            generated_at=datetime.now().astimezone(),
        )
        self.session.add(db_recap)
        self.session.flush()
        self.session.refresh(db_recap)
        return db_recap

    def invalidate(self, conversation_id: UUID) -> int:
        stmt = delete(ConversationRecap).where(
            ConversationRecap.conversation_id == conversation_id
        )
        result = self.session.execute(stmt)
        return result.rowcount or 0
