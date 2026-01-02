"""MCP server opportunity detection using rule-based pre-filtering and LLM analysis."""

import json
import logging
import re
import time
from typing import Any, Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from catsyphon.advisor.models import (
    MCP_CATEGORIES,
    MCPDetectionResult,
    MCPRecommendation,
)
from catsyphon.advisor.prompts import MCP_DETECTION_PROMPT, MCP_SYSTEM_PROMPT
from catsyphon.canonicalization import Canonicalizer, CanonicalType
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.db.repositories.recommendation import RecommendationRepository

logger = logging.getLogger(__name__)


class MCPDetector:
    """Detects MCP server opportunities in conversations.

    This detector uses a two-phase approach:
    1. Rule-based pre-filtering: Scan narrative for category signals
    2. LLM analysis: Evaluate detected categories for actual need

    This approach is more cost-effective than pure LLM analysis while
    still leveraging LLM judgment for context-aware recommendations.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 2000,
        min_confidence: float = 0.4,
    ):
        """Initialize the detector.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o-mini)
            max_tokens: Maximum tokens for response (default: 2000)
            min_confidence: Minimum confidence threshold (default: 0.4)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.min_confidence = min_confidence

    async def detect(
        self,
        conversation: Any,
        session: Session,
        children: Optional[list[Any]] = None,
        save_to_db: bool = True,
    ) -> MCPDetectionResult:
        """Detect MCP server opportunities in a conversation.

        Args:
            conversation: Database Conversation object
            session: SQLAlchemy session
            children: Optional child conversations
            save_to_db: Whether to save recommendations to database

        Returns:
            MCPDetectionResult with recommendations
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
                f"Running MCP detection for conversation {conversation.id} "
                f"({canonical.token_count} tokens)"
            )

            # Phase 1: Rule-based pre-filtering
            detected_categories = self._detect_categories(canonical.narrative)

            if not detected_categories:
                logger.info(
                    f"No MCP categories detected for conversation {conversation.id}"
                )
                return MCPDetectionResult(
                    recommendations=[],
                    conversation_id=str(conversation.id),
                    tokens_analyzed=canonical.token_count,
                    detection_model=self.model,
                    categories_detected=[],
                )

            logger.info(
                f"Pre-detected {len(detected_categories)} MCP categories: "
                f"{list(detected_categories.keys())}"
            )

            # Phase 2: LLM analysis
            recommendations = self._detect_with_llm(
                canonical.narrative, detected_categories
            )

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

            result = MCPDetectionResult(
                recommendations=recommendations,
                conversation_id=str(conversation.id),
                tokens_analyzed=canonical.token_count,
                detection_model=self.model,
                categories_detected=list(detected_categories.keys()),
            )

            logger.info(
                f"Detected {len(recommendations)} MCP opportunities "
                f"for conversation {conversation.id}"
            )

            return result

        except Exception as e:
            logger.error(f"MCP detection failed: {e}")
            return MCPDetectionResult(
                recommendations=[],
                conversation_id=str(conversation.id) if conversation else None,
                tokens_analyzed=0,
                detection_model=self.model,
                categories_detected=[],
            )

    def detect_sync(
        self,
        conversation: Any,
        session: Session,
        children: Optional[list[Any]] = None,
        save_to_db: bool = True,
    ) -> MCPDetectionResult:
        """Synchronous version of detect for non-async contexts.

        Args:
            conversation: Database Conversation object
            session: SQLAlchemy session
            children: Optional child conversations
            save_to_db: Whether to save recommendations to database

        Returns:
            MCPDetectionResult with recommendations
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

    def _detect_categories(self, narrative: str) -> dict[str, dict[str, Any]]:
        """Detect MCP categories using rule-based signal matching.

        Args:
            narrative: Canonical narrative text

        Returns:
            Dictionary mapping category names to match details
        """
        detected: dict[str, dict[str, Any]] = {}

        for category, config in MCP_CATEGORIES.items():
            matches = []
            for signal in config["signals"]:
                if re.search(signal, narrative, re.IGNORECASE):
                    matches.append(signal)

            if matches:
                detected[category] = {
                    "matched_signals": matches,
                    "match_count": len(matches),
                    "mcps": config["mcps"],
                    "use_cases": config["use_cases"],
                }

        return detected

    def _detect_with_llm(
        self, narrative: str, detected_categories: dict[str, dict[str, Any]]
    ) -> list[MCPRecommendation]:
        """Run LLM detection on the narrative.

        Args:
            narrative: Canonical narrative text
            detected_categories: Pre-detected categories from rule-based scan

        Returns:
            List of detected recommendations
        """
        try:
            # Format detected categories for the prompt
            categories_text = self._format_detected_categories(detected_categories)

            prompt = MCP_DETECTION_PROMPT.format(
                narrative=narrative, detected_categories=categories_text
            )

            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MCP_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(f"LLM MCP detection took {duration_ms:.0f}ms")

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
                    rec = MCPRecommendation(
                        category=rec_data.get("category", ""),
                        suggested_mcps=rec_data.get("suggested_mcps", []),
                        use_cases=rec_data.get("use_cases", []),
                        title=rec_data.get("title", ""),
                        description=rec_data.get("description", ""),
                        confidence=rec_data.get("confidence", 0.0),
                        friction_score=rec_data.get("friction_score", 0.0),
                        priority=self._score_to_priority(
                            rec_data.get("confidence", 0.0),
                            rec_data.get("friction_score", 0.0),
                        ),
                        evidence=rec_data.get("evidence", {}),
                    )
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse MCP recommendation: {e}")
                    continue

            # Sort by combined score (friction * confidence), highest first
            recommendations.sort(
                key=lambda r: r.friction_score * r.confidence, reverse=True
            )

            return recommendations[:5]  # Max 5 recommendations

        except Exception as e:
            logger.error(f"LLM MCP detection failed: {e}")
            return []

    def _format_detected_categories(
        self, detected_categories: dict[str, dict[str, Any]]
    ) -> str:
        """Format detected categories for the LLM prompt.

        Args:
            detected_categories: Pre-detected categories

        Returns:
            Formatted string for prompt
        """
        lines = []
        for category, details in detected_categories.items():
            signals = details["matched_signals"][:5]  # Limit for prompt size
            mcps = details["mcps"]
            lines.append(
                f"- **{category}**: {len(details['matched_signals'])} signal matches "
                f"(e.g., {', '.join(signals[:3])}). "
                f"Suggested MCPs: {', '.join(mcps)}"
            )

        return "\n".join(lines) if lines else "None detected"

    def _score_to_priority(self, confidence: float, friction_score: float) -> int:
        """Convert confidence and friction scores to priority level.

        Higher combined score = lower priority number (more important).

        Args:
            confidence: Confidence score (0.0 to 1.0)
            friction_score: Friction score (0.0 to 1.0)

        Returns:
            Priority level (0=critical, 4=low)
        """
        combined = (confidence + friction_score) / 2

        if combined >= 0.85:
            return 0  # Critical
        elif combined >= 0.7:
            return 1  # High
        elif combined >= 0.5:
            return 2  # Medium
        elif combined >= 0.3:
            return 3  # Low
        else:
            return 4  # Very low

    def _save_recommendations(
        self,
        session: Session,
        conversation_id: UUID,
        recommendations: list[MCPRecommendation],
    ) -> None:
        """Save recommendations to the database.

        Args:
            session: SQLAlchemy session
            conversation_id: Conversation ID
            recommendations: List of recommendations to save
        """
        repo = RecommendationRepository(session)

        # Delete existing MCP recommendations for this conversation first
        existing = repo.get_by_conversation(
            conversation_id, recommendation_type="mcp_server"
        )
        for existing_rec in existing:
            session.delete(existing_rec)
        session.flush()

        # Convert to database format and save
        db_recommendations: list[dict[str, Any]] = []
        for mcp_rec in recommendations:
            db_recommendations.append(
                {
                    "recommendation_type": "mcp_server",
                    "title": mcp_rec.title,
                    "description": mcp_rec.description,
                    "confidence": mcp_rec.confidence,
                    "priority": mcp_rec.priority,
                    "evidence": mcp_rec.evidence,
                    "suggested_implementation": {
                        "category": mcp_rec.category,
                        "suggested_mcps": mcp_rec.suggested_mcps,
                        "use_cases": mcp_rec.use_cases,
                        "friction_score": mcp_rec.friction_score,
                    },
                }
            )

        repo.bulk_create(conversation_id, db_recommendations)

        logger.info(
            f"Saved {len(recommendations)} MCP recommendations "
            f"for conversation {conversation_id}"
        )
