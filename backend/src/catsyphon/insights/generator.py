"""Insights generator using canonical representations and LLM analysis."""

import json
import logging
import time
from typing import Any, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from catsyphon.canonicalization import CanonicalType, Canonicalizer
from catsyphon.db.repositories.canonical import CanonicalRepository

logger = logging.getLogger(__name__)


INSIGHTS_PROMPT = """Analyze this coding agent conversation and extract comprehensive insights.

# Conversation Narrative
{narrative}

# Extract the following insights in JSON format:

1. **workflow_patterns** - List of observable workflow patterns or anti-patterns (max 5)
   Examples: "iterative-refinement", "exploratory-search", "direct-implementation", "error-driven-development"

2. **productivity_indicators** - Signals of high or low productivity (max 5)
   Examples: "high-tool-diversity", "frequent-context-switches", "steady-progress", "repeated-failures"

3. **collaboration_quality** - How well human and agent worked together (score 1-10)

4. **key_moments** - Critical turning points in the conversation (max 3)
   Format: {{"timestamp": "relative", "event": "description", "impact": "positive|negative|neutral"}}

5. **learning_opportunities** - Areas where the developer could improve (max 3)

6. **agent_effectiveness** - How effectively the agent helped (score 1-10)

7. **scope_clarity** - How well-defined the goal was (score 1-10)

8. **technical_debt_indicators** - Signs of technical debt being created or addressed (max 3)

9. **testing_behavior** - Observations about testing practices
   Examples: "no-tests-written", "test-first-approach", "tests-added-after", "tests-fixed"

10. **summary** - 2-3 sentence summary of the conversation and its outcome

Return ONLY valid JSON in this exact format:
{{
  "workflow_patterns": ["pattern1", "pattern2"],
  "productivity_indicators": ["indicator1", "indicator2"],
  "collaboration_quality": 8,
  "key_moments": [
    {{"timestamp": "early", "event": "description", "impact": "positive"}},
    {{"timestamp": "mid", "event": "description", "impact": "negative"}}
  ],
  "learning_opportunities": ["opportunity1", "opportunity2"],
  "agent_effectiveness": 8,
  "scope_clarity": 7,
  "technical_debt_indicators": ["debt1"],
  "testing_behavior": "tests-added-after",
  "summary": "Brief summary of the conversation..."
}}"""


class InsightsGenerator:
    """Generator that uses canonical representations to extract deep insights.

    This generator leverages:
    - Canonical narratives (intelligently sampled conversation context)
    - LLM analysis (for qualitative insights)
    - Metadata extraction (for quantitative metrics)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1000,
    ):
        """Initialize the insights generator.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o-mini)
            max_tokens: Maximum tokens for response (default: 1000)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate_insights(
        self,
        conversation,
        session: Session,
        children: Optional[list] = None,
    ) -> dict[str, Any]:
        """Generate comprehensive insights for a conversation.

        This method:
        1. Gets or generates canonical representation (cached)
        2. Sends canonical narrative to LLM for analysis
        3. Extracts quantitative metrics from canonical metadata
        4. Combines qualitative and quantitative insights

        Args:
            conversation: Database Conversation object
            session: SQLAlchemy session for canonical caching
            children: Optional child conversations

        Returns:
            Dictionary of insights
        """
        try:
            # Get canonical representation (uses cache-first pattern)
            canonical_repo = CanonicalRepository(session)
            canonicalizer = Canonicalizer(canonical_type=CanonicalType.INSIGHTS)

            canonical = canonical_repo.get_or_generate(
                conversation=conversation,
                canonical_type="insights",
                canonicalizer=canonicalizer,
                regeneration_threshold_tokens=2000,
                children=children or [],
            )

            logger.info(
                f"Generating insights for conversation {conversation.id} "
                f"using canonical ({canonical.token_count} tokens)"
            )

            # Extract qualitative insights using LLM
            llm_insights = self._extract_llm_insights(canonical.narrative)

            # Extract quantitative metrics from canonical metadata
            quantitative_insights = self._extract_quantitative_insights(
                canonical, conversation
            )

            # Combine insights
            combined_insights = {
                **llm_insights,
                **quantitative_insights,
                "canonical_version": canonical.canonical_version,
                "analysis_timestamp": time.time(),
            }

            logger.info(
                f"Insights generated successfully for conversation {conversation.id}"
            )

            return combined_insights

        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            return self._fallback_insights()

    def _extract_llm_insights(self, narrative: str) -> dict[str, Any]:
        """Extract qualitative insights using LLM analysis.

        Args:
            narrative: Canonical narrative text

        Returns:
            Dictionary of LLM-extracted insights
        """
        try:
            prompt = INSIGHTS_PROMPT.format(narrative=narrative)

            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing developer-AI collaboration patterns. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(f"LLM insights extraction took {duration_ms:.0f}ms")

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from OpenAI")
                return {}

            insights = json.loads(content)
            return insights

        except Exception as e:
            logger.error(f"LLM insights extraction failed: {e}")
            return {}

    def _extract_quantitative_insights(
        self, canonical, conversation
    ) -> dict[str, Any]:
        """Extract quantitative metrics from canonical metadata.

        Args:
            canonical: CanonicalConversation object
            conversation: Database Conversation object

        Returns:
            Dictionary of quantitative insights
        """
        metadata = canonical.canonical_metadata or {}

        return {
            "quantitative_metrics": {
                "message_count": canonical.message_count,
                "epoch_count": canonical.epoch_count,
                "files_touched_count": canonical.files_count,
                "tool_calls_count": canonical.tool_calls_count,
                "token_count": canonical.token_count,
                "has_errors": canonical.has_errors,
                "tools_used": canonical.tools_used or [],
                "child_conversations_count": len(canonical.children) if canonical.children else 0,
                "duration_seconds": conversation.duration_seconds if hasattr(conversation, 'duration_seconds') else None,
            }
        }

    def _fallback_insights(self) -> dict[str, Any]:
        """Return fallback insights when generation fails.

        Returns:
            Minimal insights dictionary
        """
        return {
            "workflow_patterns": [],
            "productivity_indicators": [],
            "collaboration_quality": 5,
            "key_moments": [],
            "learning_opportunities": [],
            "agent_effectiveness": 5,
            "scope_clarity": 5,
            "technical_debt_indicators": [],
            "testing_behavior": "unknown",
            "summary": "Insights generation failed. Please try again.",
            "quantitative_metrics": {},
        }
