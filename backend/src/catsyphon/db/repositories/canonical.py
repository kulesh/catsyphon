"""Repository for conversation canonical representations."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from catsyphon.canonicalization import (
    CanonicalConversation,
    Canonicalizer,
    CanonicalType,
)
from catsyphon.canonicalization.version import CANONICAL_VERSION
from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import ConversationCanonical

logger = logging.getLogger(__name__)


def _build_postgres_upsert_stmt(data: dict):
    """Build PostgreSQL upsert statement for canonical cache rows.

    Uses physical column names from `conversation_canonical` to avoid ORM
    attribute alias mismatches (e.g. `canonical_metadata` -> `metadata`).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    table = ConversationCanonical.__table__
    insert_values = {
        "conversation_id": data["conversation_id"],
        "version": data["version"],
        "canonical_type": data["canonical_type"],
        "narrative": data["narrative"],
        "token_count": data["token_count"],
        "metadata": data["canonical_metadata"],
        "config": data["config"],
        "source_message_count": data["source_message_count"],
        "source_token_estimate": data["source_token_estimate"],
        "generated_at": data["generated_at"],
    }

    return (
        pg_insert(table)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=[
                table.c.conversation_id,
                table.c.version,
                table.c.canonical_type,
            ],
            set_={
                table.c.narrative: insert_values["narrative"],
                table.c.token_count: insert_values["token_count"],
                table.c.metadata: insert_values["metadata"],
                table.c.config: insert_values["config"],
                table.c.source_message_count: insert_values["source_message_count"],
                table.c.source_token_estimate: insert_values["source_token_estimate"],
                table.c.generated_at: insert_values["generated_at"],
            },
        )
        .returning(table.c.id)
    )


class CanonicalRepository(BaseRepository[ConversationCanonical]):
    """Repository for managing canonical conversation representations.

    Provides cache-first pattern with window-based regeneration:
    1. Check for cached canonical form
    2. If exists and fresh, return it
    3. If stale or missing, generate new one
    4. Cache and return
    """

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session: Database session
        """
        super().__init__(ConversationCanonical, session)

    def get_or_generate(
        self,
        conversation: any,  # Conversation model
        canonical_type: CanonicalType,
        canonicalizer: Optional[Canonicalizer] = None,
        regeneration_threshold_tokens: int = 2000,
        children: Optional[list[any]] = None,
    ) -> CanonicalConversation:
        """Get cached canonical or generate fresh one.

        Args:
            conversation: Conversation database model
            canonical_type: Type of canonical representation
            canonicalizer: Optional custom canonicalizer (creates default if None)
            regeneration_threshold_tokens: Token growth threshold for regeneration
            children: Optional child conversations

        Returns:
            CanonicalConversation representation
        """
        # Check cache
        cached = self.get_cached(
            conversation_id=conversation.id,
            canonical_type=canonical_type.value,
        )

        # Determine if regeneration needed
        if cached and not self.should_regenerate(
            conversation=conversation,
            cached=cached,
            threshold_tokens=regeneration_threshold_tokens,
        ):
            logger.info(
                f"Using cached canonical for conversation {conversation.id} "
                f"(type={canonical_type.value})"
            )
            return self._to_canonical_conversation(cached)

        # Generate fresh canonical
        logger.info(
            f"Generating fresh canonical for conversation {conversation.id} "
            f"(type={canonical_type.value}, "
            f"cached={'stale' if cached else 'missing'})"
        )

        if canonicalizer is None:
            canonicalizer = Canonicalizer(canonical_type=canonical_type)

        canonical = canonicalizer.canonicalize(
            conversation=conversation,
            children=children,
        )

        # Save to database
        self.save_canonical(
            conversation_id=conversation.id,
            canonical_type=canonical_type.value,
            canonical=canonical,
        )

        return canonical

    def get_cached(
        self,
        conversation_id: UUID,
        canonical_type: str,
    ) -> Optional[ConversationCanonical]:
        """Get cached canonical representation.

        Args:
            conversation_id: Conversation ID
            canonical_type: Type of canonical (e.g., "tagging", "insights")

        Returns:
            Cached canonical or None
        """
        stmt = (
            select(ConversationCanonical)
            .where(ConversationCanonical.conversation_id == conversation_id)
            .where(ConversationCanonical.canonical_type == canonical_type)
            .order_by(ConversationCanonical.generated_at.desc())
            .limit(1)
        )

        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def should_regenerate(
        self,
        conversation: any,
        cached: ConversationCanonical,
        threshold_tokens: int = 2000,
    ) -> bool:
        """Determine if cached canonical should be regenerated.

        Regeneration triggers:
        1. Algorithm version mismatch
        2. Token growth exceeds threshold (window-based)

        Args:
            conversation: Current conversation state
            cached: Cached canonical representation
            threshold_tokens: Regenerate if source grew by this many tokens

        Returns:
            True if regeneration needed
        """
        # Check version mismatch
        if cached.version != CANONICAL_VERSION:
            logger.info(
                f"Regeneration needed: version mismatch "
                f"(cached={cached.version}, current={CANONICAL_VERSION})"
            )
            return True

        # Check message count growth (simple heuristic)
        current_message_count = conversation.message_count
        cached_message_count = cached.source_message_count

        if current_message_count != cached_message_count:
            # Estimate token growth
            message_growth = current_message_count - cached_message_count
            estimated_tokens_per_message = (
                cached.source_token_estimate / cached_message_count
                if cached_message_count > 0
                else 100
            )
            estimated_growth = message_growth * estimated_tokens_per_message

            if estimated_growth > threshold_tokens:
                logger.info(
                    f"Regeneration needed: token growth threshold exceeded "
                    f"(messages: {cached_message_count} → {current_message_count}, "
                    f"estimated growth: ~{int(estimated_growth)} tokens, "
                    f"threshold: {threshold_tokens})"
                )
                return True

        # No regeneration needed
        logger.debug(
            f"Cached canonical still fresh "
            f"(messages: {current_message_count}, "
            f"version: {cached.version})"
        )
        return False

    def save_canonical(
        self,
        conversation_id: UUID,
        canonical_type: str,
        canonical: CanonicalConversation,
    ) -> ConversationCanonical:
        """Save canonical representation to database.

        Uses upsert pattern: deletes existing entry (if any) before inserting.

        Args:
            conversation_id: Conversation ID
            canonical_type: Type of canonical
            canonical: Canonical conversation to save

        Returns:
            Saved database model
        """
        # Estimate source tokens (for window-based regeneration)
        # Simple estimate: message_count * avg_tokens_per_message
        estimated_source_tokens = canonical.message_count * 100  # Conservative estimate

        data = {
            "conversation_id": conversation_id,
            "version": canonical.canonical_version,
            "canonical_type": canonical_type,
            "narrative": canonical.narrative,
            "token_count": canonical.token_count,
            "canonical_metadata": {
                "tools_used": canonical.tools_used,
                "files_touched": canonical.files_touched,
                "has_errors": canonical.has_errors,
                "code_changes_summary": canonical.code_changes_summary,
            },
            "config": canonical.config.to_dict() if canonical.config else {},
            "source_message_count": canonical.message_count,
            "source_token_estimate": estimated_source_tokens,
            "generated_at": canonical.generated_at or datetime.now(),
        }

        # Prefer PostgreSQL upsert to avoid race conditions across workers.
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            stmt = _build_postgres_upsert_stmt(data)
            canonical_id = self.session.execute(stmt).scalar_one()
            db_canonical = self.session.get(ConversationCanonical, canonical_id)
            if db_canonical is None:
                raise RuntimeError("Upserted canonical row could not be loaded")
        else:
            # SQLite fallback: use a savepoint and handle unique conflicts.
            savepoint = self.session.begin_nested()
            try:
                # Delete existing entry if present (upsert pattern)
                self.invalidate(
                    conversation_id=conversation_id,
                    canonical_type=canonical_type,
                )
                db_canonical = ConversationCanonical(**data)
                self.session.add(db_canonical)
                self.session.flush()
                savepoint.commit()
            except IntegrityError:
                savepoint.rollback()
                db_canonical = self.get_cached(conversation_id, canonical_type)
                if db_canonical is None:
                    raise
            else:
                self.session.refresh(db_canonical)

        logger.info(
            f"Saved canonical for conversation {conversation_id} "
            f"(type={canonical_type}, tokens={canonical.token_count})"
        )

        return db_canonical

    def invalidate(
        self,
        conversation_id: Optional[UUID] = None,
        canonical_type: Optional[str] = None,
    ) -> int:
        """Invalidate (delete) cached canonical representations.

        Args:
            conversation_id: Optional conversation to invalidate (None = all)
            canonical_type: Optional type to invalidate (None = all types)

        Returns:
            Number of records deleted
        """
        stmt = select(ConversationCanonical)

        if conversation_id:
            stmt = stmt.where(ConversationCanonical.conversation_id == conversation_id)
        if canonical_type:
            stmt = stmt.where(ConversationCanonical.canonical_type == canonical_type)

        result = self.session.execute(stmt)
        canonicals = result.scalars().all()

        for canonical in canonicals:
            self.session.delete(canonical)

        self.session.flush()

        count = len(canonicals)
        logger.info(
            f"Invalidated {count} canonical representations "
            f"(conversation_id={conversation_id}, type={canonical_type})"
        )

        return count

    def _to_canonical_conversation(
        self, db_canonical: ConversationCanonical
    ) -> CanonicalConversation:
        """Convert database model to CanonicalConversation.

        Args:
            db_canonical: Database model

        Returns:
            CanonicalConversation instance
        """
        metadata = db_canonical.canonical_metadata or {}

        return CanonicalConversation(
            session_id=str(db_canonical.conversation_id),
            conversation_id=str(db_canonical.conversation_id),
            agent_type="",  # Not stored in canonical cache
            agent_version=None,
            conversation_type="",  # Not stored in canonical cache
            start_time=datetime.now(),  # Not stored in canonical cache
            end_time=None,
            duration_seconds=None,
            message_count=db_canonical.source_message_count,
            epoch_count=0,  # Not stored in canonical cache
            files_count=len(metadata.get("files_touched", [])),
            tool_calls_count=0,  # Not stored in canonical cache
            narrative=db_canonical.narrative,
            token_count=db_canonical.token_count,
            tools_used=metadata.get("tools_used", []),
            files_touched=metadata.get("files_touched", []),
            has_errors=metadata.get("has_errors", False),
            code_changes_summary=metadata.get("code_changes_summary", {}),
            canonical_version=db_canonical.version,
            generated_at=db_canonical.generated_at,
        )
