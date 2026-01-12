"""Repository for automation recommendations."""

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import AutomationRecommendation

logger = logging.getLogger(__name__)


class RecommendationRepository(BaseRepository[AutomationRecommendation]):
    """Repository for managing automation recommendations.

    Provides CRUD operations and query methods for AI-detected
    automation opportunities (slash commands, MCP servers, etc.).
    """

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session: Database session
        """
        super().__init__(AutomationRecommendation, session)

    def get_by_conversation(
        self,
        conversation_id: UUID,
        status: Optional[str] = None,
        recommendation_type: Optional[str] = None,
    ) -> list[AutomationRecommendation]:
        """Get recommendations for a conversation.

        Args:
            conversation_id: Conversation ID
            status: Filter by status (pending, accepted, dismissed, implemented)
            recommendation_type: Filter by type (slash_command, mcp_server, etc.)

        Returns:
            List of recommendations ordered by confidence (descending)
        """
        stmt = (
            select(AutomationRecommendation)
            .where(AutomationRecommendation.conversation_id == conversation_id)
            .order_by(AutomationRecommendation.confidence.desc())
        )

        if status:
            stmt = stmt.where(AutomationRecommendation.status == status)

        if recommendation_type:
            stmt = stmt.where(
                AutomationRecommendation.recommendation_type == recommendation_type
            )

        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def create_recommendation(
        self,
        conversation_id: UUID,
        recommendation_type: str,
        title: str,
        description: str,
        confidence: float,
        evidence: dict[str, Any],
        suggested_implementation: Optional[dict[str, Any]] = None,
        priority: int = 2,
    ) -> AutomationRecommendation:
        """Create a new recommendation.

        Args:
            conversation_id: Conversation this recommendation belongs to
            recommendation_type: Type of recommendation (slash_command, etc.)
            title: Short title for the recommendation
            description: Detailed description
            confidence: Confidence score (0.0 to 1.0)
            evidence: Supporting evidence (quotes, message indices)
            suggested_implementation: Optional implementation details
            priority: Priority level (0=critical, 4=low)

        Returns:
            Created recommendation
        """
        recommendation = AutomationRecommendation(
            conversation_id=conversation_id,
            recommendation_type=recommendation_type,
            title=title,
            description=description,
            confidence=confidence,
            priority=priority,
            evidence=evidence,
            suggested_implementation=suggested_implementation,
            status="pending",
        )

        self.session.add(recommendation)
        self.session.flush()
        self.session.refresh(recommendation)

        logger.info(
            f"Created recommendation for conversation {conversation_id}: "
            f"{title} ({recommendation_type}, confidence={confidence:.2f})"
        )

        return recommendation

    def bulk_create(
        self,
        conversation_id: UUID,
        recommendations: list[dict[str, Any]],
    ) -> list[AutomationRecommendation]:
        """Create multiple recommendations for a conversation.

        Args:
            conversation_id: Conversation ID
            recommendations: List of recommendation dictionaries

        Returns:
            List of created recommendations
        """
        created = []
        for rec in recommendations:
            created.append(
                self.create_recommendation(
                    conversation_id=conversation_id,
                    recommendation_type=rec.get("recommendation_type", "slash_command"),
                    title=rec["title"],
                    description=rec["description"],
                    confidence=rec["confidence"],
                    evidence=rec.get("evidence", {}),
                    suggested_implementation=rec.get("suggested_implementation"),
                    priority=rec.get("priority", 2),
                )
            )

        logger.info(
            f"Created {len(created)} recommendations for conversation {conversation_id}"
        )

        return created

    def update_status(
        self,
        recommendation_id: UUID,
        status: str,
        user_feedback: Optional[str] = None,
    ) -> Optional[AutomationRecommendation]:
        """Update recommendation status and feedback.

        Args:
            recommendation_id: Recommendation ID
            status: New status (pending, accepted, dismissed, implemented)
            user_feedback: Optional user feedback

        Returns:
            Updated recommendation or None if not found
        """
        recommendation = self.get(recommendation_id)
        if not recommendation:
            return None

        recommendation.status = status
        if user_feedback is not None:
            recommendation.user_feedback = user_feedback

        self.session.flush()
        self.session.refresh(recommendation)

        logger.info(f"Updated recommendation {recommendation_id} status to {status}")

        return recommendation

    def delete_for_conversation(self, conversation_id: UUID) -> int:
        """Delete all recommendations for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of recommendations deleted
        """
        stmt = select(AutomationRecommendation).where(
            AutomationRecommendation.conversation_id == conversation_id
        )
        result = self.session.execute(stmt)
        recommendations = result.scalars().all()

        count = len(recommendations)
        for rec in recommendations:
            self.session.delete(rec)

        self.session.flush()

        if count > 0:
            logger.info(
                f"Deleted {count} recommendations for conversation {conversation_id}"
            )

        return count

    def get_summary_stats(self) -> dict[str, Any]:
        """Get aggregate statistics for recommendations.

        Returns:
            Dictionary with summary statistics
        """
        # Count by status
        status_counts = {}
        for status in ["pending", "accepted", "dismissed", "implemented"]:
            stmt = select(func.count()).where(AutomationRecommendation.status == status)
            count = self.session.execute(stmt).scalar() or 0
            status_counts[status] = count

        # Count by type
        type_counts = {}
        stmt = select(
            AutomationRecommendation.recommendation_type,
            func.count().label("count"),
        ).group_by(AutomationRecommendation.recommendation_type)
        result = self.session.execute(stmt)
        for row in result:
            type_counts[row[0]] = row[1]

        # Average confidence
        avg_stmt = select(func.avg(AutomationRecommendation.confidence))
        avg_confidence = self.session.execute(avg_stmt).scalar() or 0.0

        # Total count
        total = self.count()

        return {
            "total": total,
            "by_status": status_counts,
            "by_type": type_counts,
            "average_confidence": round(avg_confidence, 3),
        }

    def get_high_confidence(
        self,
        min_confidence: float = 0.7,
        limit: int = 10,
    ) -> list[AutomationRecommendation]:
        """Get high-confidence pending recommendations.

        Args:
            min_confidence: Minimum confidence threshold
            limit: Maximum results to return

        Returns:
            List of high-confidence recommendations
        """
        stmt = (
            select(AutomationRecommendation)
            .where(AutomationRecommendation.status == "pending")
            .where(AutomationRecommendation.confidence >= min_confidence)
            .order_by(AutomationRecommendation.confidence.desc())
            .limit(limit)
        )

        result = self.session.execute(stmt)
        return list(result.scalars().all())
