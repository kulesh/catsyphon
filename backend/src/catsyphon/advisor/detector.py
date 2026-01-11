"""Slash command detection using LLM analysis."""

import json
import logging
import time
from typing import Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from catsyphon.advisor.models import DetectionResult, SlashCommandRecommendation
from catsyphon.advisor.prompts import SLASH_COMMAND_DETECTION_PROMPT, SYSTEM_PROMPT
from catsyphon.canonicalization import Canonicalizer, CanonicalType
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.db.repositories.recommendation import RecommendationRepository

logger = logging.getLogger(__name__)


class SlashCommandDetector:
    """Detects slash command opportunities in conversations using LLM analysis.

    This detector:
    1. Gets canonical representation of the conversation
    2. Sends it to an LLM for pattern analysis
    3. Parses and validates the recommendations
    4. Stores recommendations in the database
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1500,
        min_confidence: float = 0.4,
    ):
        """Initialize the detector.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o-mini)
            max_tokens: Maximum tokens for response (default: 1500)
            min_confidence: Minimum confidence threshold (default: 0.4)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.min_confidence = min_confidence

    async def detect(
        self,
        conversation,
        session: Session,
        children: Optional[list] = None,
        save_to_db: bool = True,
    ) -> DetectionResult:
        """Detect slash command opportunities in a conversation.

        Args:
            conversation: Database Conversation object
            session: SQLAlchemy session
            children: Optional child conversations
            save_to_db: Whether to save recommendations to database

        Returns:
            DetectionResult with recommendations
        """
        try:
            # Get canonical representation
            canonical_repo = CanonicalRepository(session)
            canonicalizer = Canonicalizer(canonical_type=CanonicalType.INSIGHTS)

            canonical = canonical_repo.get_or_generate(
                conversation=conversation,
                canonical_type=CanonicalType.INSIGHTS,
                canonicalizer=canonicalizer,
                regeneration_threshold_tokens=2000,
                children=children or [],
            )

            logger.info(
                f"Running slash command detection for conversation {conversation.id} "
                f"({canonical.token_count} tokens)"
            )

            # Run LLM detection
            recommendations = self._detect_with_llm(canonical.narrative)

            # Filter by minimum confidence
            recommendations = [
                r for r in recommendations if r.confidence >= self.min_confidence
            ]

            # Save to database if requested
            if save_to_db and recommendations:
                self._save_recommendations(
                    session=session,
                    conversation_id=conversation.id,
                    recommendations=recommendations,
                )

            result = DetectionResult(
                recommendations=recommendations,
                conversation_id=str(conversation.id),
                tokens_analyzed=canonical.token_count,
                detection_model=self.model,
            )

            logger.info(
                f"Detected {len(recommendations)} slash command opportunities "
                f"for conversation {conversation.id}"
            )

            return result

        except Exception as e:
            logger.error(f"Slash command detection failed: {e}")
            return DetectionResult(
                recommendations=[],
                conversation_id=str(conversation.id) if conversation else None,
                tokens_analyzed=0,
                detection_model=self.model,
            )

    def detect_sync(
        self,
        conversation,
        session: Session,
        children: Optional[list] = None,
        save_to_db: bool = True,
    ) -> DetectionResult:
        """Synchronous version of detect for non-async contexts.

        Args:
            conversation: Database Conversation object
            session: SQLAlchemy session
            children: Optional child conversations
            save_to_db: Whether to save recommendations to database

        Returns:
            DetectionResult with recommendations
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.detect(conversation, session, children, save_to_db)
        )

    def _detect_with_llm(self, narrative: str) -> list[SlashCommandRecommendation]:
        """Run LLM detection on the narrative.

        Args:
            narrative: Canonical narrative text

        Returns:
            List of detected recommendations
        """
        try:
            prompt = SLASH_COMMAND_DETECTION_PROMPT.format(narrative=narrative)

            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(f"LLM slash command detection took {duration_ms:.0f}ms")

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from OpenAI")
                return []

            data = json.loads(content)
            recommendations_data = data.get("recommendations", [])

            # Parse into Pydantic models
            recommendations = []
            for rec_data in recommendations_data:
                try:
                    rec = SlashCommandRecommendation(
                        command_name=rec_data.get("command_name", ""),
                        title=rec_data.get("title", ""),
                        description=rec_data.get("description", ""),
                        trigger_phrases=rec_data.get("trigger_phrases", []),
                        template=rec_data.get("template"),
                        confidence=rec_data.get("confidence", 0.0),
                        priority=self._confidence_to_priority(
                            rec_data.get("confidence", 0.0)
                        ),
                        evidence=rec_data.get("evidence", {}),
                    )
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse recommendation: {e}")
                    continue

            # Sort by confidence (highest first)
            recommendations.sort(key=lambda r: r.confidence, reverse=True)

            return recommendations[:5]  # Max 5 recommendations

        except Exception as e:
            logger.error(f"LLM detection failed: {e}")
            return []

    def _confidence_to_priority(self, confidence: float) -> int:
        """Convert confidence score to priority level.

        Higher confidence = lower priority number (more important).

        Args:
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            Priority level (0=critical, 4=low)
        """
        if confidence >= 0.9:
            return 0  # Critical
        elif confidence >= 0.8:
            return 1  # High
        elif confidence >= 0.6:
            return 2  # Medium
        elif confidence >= 0.4:
            return 3  # Low
        else:
            return 4  # Very low

    def _save_recommendations(
        self,
        session: Session,
        conversation_id: UUID,
        recommendations: list[SlashCommandRecommendation],
    ) -> None:
        """Save recommendations to the database.

        Args:
            session: SQLAlchemy session
            conversation_id: Conversation ID
            recommendations: List of recommendations to save
        """
        repo = RecommendationRepository(session)

        # Delete existing recommendations for this conversation first
        repo.delete_for_conversation(conversation_id)

        # Convert to database format and save
        db_recommendations = []
        for rec in recommendations:
            db_recommendations.append(
                {
                    "recommendation_type": "slash_command",
                    "title": rec.title,
                    "description": rec.description,
                    "confidence": rec.confidence,
                    "priority": rec.priority,
                    "evidence": rec.evidence,
                    "suggested_implementation": {
                        "command_name": rec.command_name,
                        "trigger_phrases": rec.trigger_phrases,
                        "template": rec.template,
                    },
                }
            )

        repo.bulk_create(conversation_id, db_recommendations)

        logger.info(
            "Saved %s recommendations for conversation %s",
            len(recommendations),
            conversation_id,
        )
