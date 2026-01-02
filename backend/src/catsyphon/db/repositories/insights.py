"""Repository for conversation insights caching."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import ConversationInsights

logger = logging.getLogger(__name__)

# TTL configuration based on project activity
TTL_DAYS_ACTIVE_PROJECT = 7  # Projects with recent activity
TTL_DAYS_INACTIVE_PROJECT = 30  # Projects with no recent activity
ACTIVE_PROJECT_THRESHOLD_DAYS = 7  # Project is "active" if activity within this window


class InsightsRepository(BaseRepository[ConversationInsights]):
    """Repository for managing cached conversation insights.

    Provides cache-first pattern with TTL-based expiration:
    1. Check for cached insights
    2. If exists and not expired, return it
    3. If expired or missing, return None (caller should regenerate)
    4. TTL is based on project activity level
    """

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session: Database session
        """
        super().__init__(ConversationInsights, session)

    def get_cached(
        self,
        conversation_id: UUID,
        check_ttl: bool = True,
    ) -> Optional[ConversationInsights]:
        """Get cached insights for a conversation.

        Args:
            conversation_id: Conversation ID
            check_ttl: If True, returns None for expired cache entries

        Returns:
            Cached insights or None if not found/expired
        """
        stmt = (
            select(ConversationInsights)
            .where(ConversationInsights.conversation_id == conversation_id)
            .order_by(ConversationInsights.generated_at.desc())
            .limit(1)
        )

        result = self.session.execute(stmt)
        cached = result.scalar_one_or_none()

        if cached is None:
            logger.debug(f"No cached insights for conversation {conversation_id}")
            return None

        # Check TTL if enabled
        if check_ttl and cached.expires_at is not None:
            now = datetime.now(cached.expires_at.tzinfo)
            if now > cached.expires_at:
                logger.info(
                    f"Cached insights expired for conversation {conversation_id} "
                    f"(expired_at={cached.expires_at})"
                )
                return None

        logger.info(
            f"Using cached insights for conversation {conversation_id} "
            f"(generated_at={cached.generated_at})"
        )
        return cached

    def get_cached_batch(
        self,
        conversation_ids: list[UUID],
        check_ttl: bool = True,
    ) -> dict[UUID, ConversationInsights]:
        """Get cached insights for multiple conversations in a single query.

        Args:
            conversation_ids: List of conversation IDs
            check_ttl: If True, excludes expired cache entries

        Returns:
            Dictionary mapping conversation_id to cached insights
        """
        if not conversation_ids:
            return {}

        # Build query for all conversations at once
        stmt = select(ConversationInsights).where(
            ConversationInsights.conversation_id.in_(conversation_ids)
        )

        # Filter out expired entries if TTL check is enabled
        if check_ttl:
            now = datetime.now().astimezone()
            stmt = stmt.where(
                (ConversationInsights.expires_at.is_(None))
                | (ConversationInsights.expires_at >= now)
            )

        result = self.session.execute(stmt)
        insights_list = result.scalars().all()

        # Build lookup dict (use most recent per conversation)
        # Since we're not ordering, we'll handle duplicates by overwriting
        # (the DB should only have one entry per conversation_id after invalidate)
        cache_map: dict[UUID, ConversationInsights] = {}
        for insight in insights_list:
            existing = cache_map.get(insight.conversation_id)
            if existing is None or insight.generated_at > existing.generated_at:
                cache_map[insight.conversation_id] = insight

        logger.debug(
            f"Batch cache lookup: {len(cache_map)}/{len(conversation_ids)} hits"
        )
        return cache_map

    def save(
        self,
        conversation_id: UUID,
        insights: dict[str, Any],
        canonical_version: int,
        project_last_activity: Optional[datetime] = None,
    ) -> ConversationInsights:
        """Save insights to cache.

        Args:
            conversation_id: Conversation ID
            insights: Insights dictionary (from InsightsGenerator)
            canonical_version: Version of canonical used for generation
            project_last_activity: Optional project last activity timestamp for TTL

        Returns:
            Saved ConversationInsights model
        """
        # Calculate TTL based on project activity
        ttl_days = self._calculate_ttl_days(project_last_activity)
        expires_at = datetime.now().astimezone() + timedelta(days=ttl_days)

        # Delete any existing cached insights for this conversation
        self.invalidate(conversation_id=conversation_id)

        # Create new cache entry
        db_insights = ConversationInsights(
            conversation_id=conversation_id,
            version=1,
            workflow_patterns=insights.get("workflow_patterns", []),
            productivity_indicators=insights.get("productivity_indicators", []),
            collaboration_quality=insights.get("collaboration_quality", 5),
            key_moments=insights.get("key_moments", []),
            learning_opportunities=insights.get("learning_opportunities", []),
            agent_effectiveness=insights.get("agent_effectiveness", 5),
            scope_clarity=insights.get("scope_clarity", 5),
            technical_debt_indicators=insights.get("technical_debt_indicators", []),
            testing_behavior=insights.get("testing_behavior", "unknown"),
            summary=insights.get("summary", ""),
            quantitative_metrics=insights.get("quantitative_metrics", {}),
            canonical_version=canonical_version,
            generated_at=datetime.now().astimezone(),
            expires_at=expires_at,
        )

        self.session.add(db_insights)
        self.session.flush()
        self.session.refresh(db_insights)

        logger.info(
            f"Saved insights for conversation {conversation_id} "
            f"(ttl_days={ttl_days}, expires_at={expires_at})"
        )

        return db_insights

    def invalidate(
        self,
        conversation_id: Optional[UUID] = None,
    ) -> int:
        """Invalidate (delete) cached insights.

        Args:
            conversation_id: Conversation to invalidate (None = all)

        Returns:
            Number of records deleted
        """
        # ===== OPTIMIZED: Use bulk delete instead of load-then-delete =====
        stmt = delete(ConversationInsights)

        if conversation_id:
            stmt = stmt.where(ConversationInsights.conversation_id == conversation_id)

        result: CursorResult[Any] = self.session.execute(stmt)  # type: ignore[assignment]
        count: int = result.rowcount or 0

        self.session.flush()

        if count > 0:
            logger.info(
                f"Invalidated {count} cached insights "
                f"(conversation_id={conversation_id})"
            )

        return count

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of records deleted
        """
        # ===== OPTIMIZED: Use bulk delete instead of load-then-delete =====
        now = datetime.now().astimezone()
        stmt = delete(ConversationInsights).where(ConversationInsights.expires_at < now)

        result: CursorResult[Any] = self.session.execute(stmt)  # type: ignore[assignment]
        count: int = result.rowcount or 0

        self.session.flush()

        if count > 0:
            logger.info(f"Cleaned up {count} expired insights cache entries")

        return count

    def _calculate_ttl_days(
        self, project_last_activity: Optional[datetime] = None
    ) -> int:
        """Calculate TTL based on project activity.

        Active projects (activity within threshold) get shorter TTL
        because insights may become stale quickly as new sessions happen.

        Inactive projects get longer TTL since they're unlikely to change.

        Args:
            project_last_activity: Last activity timestamp for the project

        Returns:
            TTL in days
        """
        if project_last_activity is None:
            return TTL_DAYS_INACTIVE_PROJECT

        # Make both datetimes timezone-aware for comparison
        now = datetime.now().astimezone()
        if project_last_activity.tzinfo is None:
            project_last_activity = project_last_activity.replace(tzinfo=now.tzinfo)

        days_since_activity = (now - project_last_activity).days

        if days_since_activity <= ACTIVE_PROJECT_THRESHOLD_DAYS:
            return TTL_DAYS_ACTIVE_PROJECT
        else:
            return TTL_DAYS_INACTIVE_PROJECT

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        # ===== OPTIMIZED: Use func.count() instead of len(.all()) =====
        total = self.session.query(func.count(ConversationInsights.id)).scalar() or 0

        now = datetime.now().astimezone()
        expired = (
            self.session.query(func.count(ConversationInsights.id))
            .filter(ConversationInsights.expires_at < now)
            .scalar()
            or 0
        )

        valid = (
            self.session.query(func.count(ConversationInsights.id))
            .filter(
                (ConversationInsights.expires_at >= now)
                | (ConversationInsights.expires_at.is_(None))
            )
            .scalar()
            or 0
        )

        return {
            "total_cached": total,
            "valid_entries": valid,
            "expired_entries": expired,
        }
