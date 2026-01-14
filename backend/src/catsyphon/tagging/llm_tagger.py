"""LLM-based conversation tagger using pluggable providers."""

import json
import logging
from typing import Any, Optional

from catsyphon.models.parsed import ConversationTags, ParsedConversation
from catsyphon.tagging.llm_logger import llm_logger
from catsyphon.tagging.providers import LLMProvider, create_provider

logger = logging.getLogger(__name__)


# Taxonomy for consistent tagging
INTENT_VALUES = ["feature_add", "bug_fix", "refactor", "learning", "debugging", "other"]
OUTCOME_VALUES = ["success", "partial", "failed", "abandoned", "unknown"]
SENTIMENT_VALUES = ["positive", "neutral", "negative", "frustrated"]


TAGGING_PROMPT = """Analyze this coding agent conversation and extract metadata in JSON format.

# Conversation Summary
- Agent: {agent_type}
- Messages: {message_count}
- Duration: {duration_minutes} minutes
- Status: {status}

# Sample Messages (first 3 and last 3):
{sample_messages}

# Extract the following metadata:

1. **intent** - What was the user trying to accomplish?
   Options: {intent_options}

2. **outcome** - What was the result?
   Options: {outcome_options}

3. **sentiment** - Overall emotional tone of the interaction
   Options: {sentiment_options}

4. **sentiment_score** - Numeric sentiment (-1.0 to 1.0)
   -1.0 = very negative, 0.0 = neutral, 1.0 = very positive

5. **features** - List of features or capabilities discussed (max 5)

6. **problems** - List of problems or blockers encountered (max 5)

7. **reasoning** - Brief explanation (2-3 sentences) of why you assigned these tags,
   highlighting key evidence from the conversation that informed your analysis.

Return ONLY valid JSON in this exact format:
{{
  "intent": "one of the intent options",
  "outcome": "one of the outcome options",
  "sentiment": "one of the sentiment options",
  "sentiment_score": 0.0,
  "features": ["feature1", "feature2"],
  "problems": ["problem1", "problem2"],
  "reasoning": "Brief explanation of tag assignments..."
}}"""


CANONICAL_TAGGING_PROMPT = """Analyze this coding agent conversation narrative and extract metadata in JSON format.

# Conversation Narrative
{narrative}

# Extract the following metadata:

1. **intent** - What was the user trying to accomplish?
   Options: {intent_options}

2. **outcome** - What was the result?
   Options: {outcome_options}

3. **sentiment** - Overall emotional tone of the interaction
   Options: {sentiment_options}

4. **sentiment_score** - Numeric sentiment (-1.0 to 1.0)
   -1.0 = very negative, 0.0 = neutral, 1.0 = very positive

5. **features** - List of features or capabilities discussed (max 5)

6. **problems** - List of problems or blockers encountered (max 5)

7. **reasoning** - Brief explanation (2-3 sentences) of why you assigned these tags,
   highlighting key evidence from the conversation that informed your analysis.

Return ONLY valid JSON in this exact format:
{{
  "intent": "one of the intent options",
  "outcome": "one of the outcome options",
  "sentiment": "one of the sentiment options",
  "sentiment_score": 0.0,
  "features": ["feature1", "feature2"],
  "problems": ["problem1", "problem2"],
  "reasoning": "Brief explanation of tag assignments..."
}}"""


# JSON Schema for structured output (used by providers that support it)
TAGGING_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": INTENT_VALUES,
            "description": "What the user was trying to accomplish",
        },
        "outcome": {
            "type": "string",
            "enum": OUTCOME_VALUES,
            "description": "The result of the conversation",
        },
        "sentiment": {
            "type": "string",
            "enum": SENTIMENT_VALUES,
            "description": "Overall emotional tone",
        },
        "sentiment_score": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "Numeric sentiment score",
        },
        "features": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
            "description": "Features or capabilities discussed",
        },
        "problems": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
            "description": "Problems or blockers encountered",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of tag assignments",
        },
    },
    "required": ["intent", "outcome", "sentiment", "sentiment_score"],
    "additionalProperties": False,
}


class LLMTagger:
    """Tagger that uses LLM providers to extract conversation metadata.

    Supports multiple LLM providers (OpenAI, Anthropic) through the
    pluggable provider system.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        # Legacy parameters for backward compatibility
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        provider_type: str = "openai",
        max_tokens: int = 500,
    ):
        """Initialize the LLM tagger.

        Args:
            provider: Pre-configured LLMProvider instance (preferred)
            api_key: API key (legacy, creates OpenAI provider if no provider given)
            model: Model name (legacy, used when creating provider from api_key)
            provider_type: Provider type (legacy, "openai" or "anthropic")
            max_tokens: Maximum tokens for response
        """
        if provider is not None:
            self.provider = provider
        elif api_key:
            # Legacy initialization - create provider from api_key
            self.provider = create_provider(
                provider_type=provider_type,  # type: ignore
                api_key=api_key,
                model=model,
            )
        else:
            raise ValueError("Either provider or api_key must be provided")

        self.max_tokens = max_tokens

    def tag_conversation(
        self, parsed: ParsedConversation
    ) -> tuple[ConversationTags, dict[str, Any]]:
        """Tag a conversation using the LLM provider.

        Args:
            parsed: The parsed conversation to analyze

        Returns:
            Tuple of (ConversationTags, llm_metrics)
            - ConversationTags: LLM-extracted metadata
            - llm_metrics: Dict with duration_ms, tokens, cost, model, cache_hit
        """
        request_id = ""
        try:
            # Build prompt with conversation context
            prompt = self._build_prompt(parsed)

            # Log request (if LLM logging enabled)
            request_id = llm_logger.log_request(
                conversation=parsed,
                model=self.provider.model_name,
                prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=0.3,
            )

            # Call provider with JSON schema
            response = self.provider.complete(
                system_prompt=(
                    "You are an expert at analyzing coding agent conversations. "
                    "Return only valid JSON."
                ),
                user_prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=0.3,
                json_schema=TAGGING_JSON_SCHEMA,
            )

            # Log response (if LLM logging enabled)
            llm_logger.log_response(
                request_id=request_id,
                response=response.raw_response,
                duration_ms=response.duration_ms,
            )

            # Calculate cost
            cost_usd = self.provider.calculate_cost(
                response.prompt_tokens, response.completion_tokens
            )

            llm_metrics = {
                "llm_tagging_ms": response.duration_ms,
                "llm_prompt_tokens": response.prompt_tokens,
                "llm_completion_tokens": response.completion_tokens,
                "llm_total_tokens": response.total_tokens,
                "llm_cost_usd": cost_usd,
                "llm_model": response.model,
                "llm_provider": self.provider.provider_name,
                "llm_finish_reason": response.finish_reason,
                "llm_cache_hit": False,
            }

            # Parse response
            if not response.content:
                logger.warning(f"Empty response from {self.provider.provider_name}")
                return self._fallback_tags(), llm_metrics

            tags_dict = json.loads(response.content)
            return self._parse_tags(tags_dict), llm_metrics

        except Exception as e:
            logger.error(f"LLM tagging failed: {e}")
            # Log error (if LLM logging enabled)
            llm_logger.log_error(
                request_id=request_id,
                error=e,
                conversation=parsed,
            )
            # Return fallback tags with error metrics
            error_metrics = {
                "llm_tagging_ms": 0,
                "llm_prompt_tokens": 0,
                "llm_completion_tokens": 0,
                "llm_total_tokens": 0,
                "llm_cost_usd": 0.0,
                "llm_model": self.provider.model_name,
                "llm_provider": self.provider.provider_name,
                "llm_finish_reason": "error",
                "llm_cache_hit": False,
                "llm_error": str(e),
            }
            return self._fallback_tags(), error_metrics

    def tag_from_canonical(
        self,
        narrative: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[ConversationTags, dict[str, Any]]:
        """Tag a conversation using canonical narrative form.

        This is the preferred method as it uses intelligently sampled content
        from the canonical representation.

        Args:
            narrative: Canonical narrative (play format)
            metadata: Optional metadata from canonical (for context)

        Returns:
            Tuple of (ConversationTags, llm_metrics)
            - ConversationTags: LLM-extracted metadata
            - llm_metrics: Dict with duration_ms, tokens, cost, model, cache_hit
        """
        try:
            # Build prompt with canonical narrative
            prompt = self._build_canonical_prompt(narrative, metadata)

            # Call provider with JSON schema
            response = self.provider.complete(
                system_prompt=(
                    "You are an expert at analyzing coding agent conversations. "
                    "Return only valid JSON."
                ),
                user_prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=0.3,
                json_schema=TAGGING_JSON_SCHEMA,
            )

            logger.info(
                f"LLM tagging from canonical completed in {response.duration_ms:.0f}ms "
                f"(provider: {self.provider.provider_name})"
            )

            # Calculate cost
            cost_usd = self.provider.calculate_cost(
                response.prompt_tokens, response.completion_tokens
            )

            llm_metrics = {
                "llm_tagging_ms": response.duration_ms,
                "llm_prompt_tokens": response.prompt_tokens,
                "llm_completion_tokens": response.completion_tokens,
                "llm_total_tokens": response.total_tokens,
                "llm_cost_usd": cost_usd,
                "llm_model": response.model,
                "llm_provider": self.provider.provider_name,
                "llm_finish_reason": response.finish_reason,
                "llm_cache_hit": False,
            }

            # Parse response
            if not response.content:
                logger.warning(f"Empty response from {self.provider.provider_name}")
                return self._fallback_tags(), llm_metrics

            tags_dict = json.loads(response.content)
            return self._parse_tags(tags_dict), llm_metrics

        except Exception as e:
            logger.error(f"LLM tagging from canonical failed: {e}")
            error_metrics = {
                "llm_tagging_ms": 0,
                "llm_prompt_tokens": 0,
                "llm_completion_tokens": 0,
                "llm_total_tokens": 0,
                "llm_cost_usd": 0.0,
                "llm_model": self.provider.model_name,
                "llm_provider": self.provider.provider_name,
                "llm_finish_reason": "error",
                "llm_cache_hit": False,
                "llm_error": str(e),
            }
            return self._fallback_tags(), error_metrics

    def _build_canonical_prompt(
        self,
        narrative: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build tagging prompt from canonical narrative.

        Args:
            narrative: Canonical narrative text
            metadata: Optional metadata for context

        Returns:
            Formatted prompt for LLM
        """
        return CANONICAL_TAGGING_PROMPT.format(
            narrative=narrative,
            intent_options=", ".join(INTENT_VALUES),
            outcome_options=", ".join(OUTCOME_VALUES),
            sentiment_options=", ".join(SENTIMENT_VALUES),
        )

    def _build_prompt(self, parsed: ParsedConversation) -> str:
        """Build the tagging prompt from parsed conversation."""
        # Calculate duration
        if parsed.start_time and parsed.end_time:
            duration = (parsed.end_time - parsed.start_time).total_seconds() / 60
        else:
            duration = 0

        # Get sample messages (first 3 and last 3)
        messages = parsed.messages
        sample_count = min(3, len(messages))
        first_messages = messages[:sample_count]
        last_messages = messages[-sample_count:] if len(messages) > sample_count else []

        sample_text = "First messages:\n"
        for msg in first_messages:
            role = msg.role or "unknown"
            content = (msg.content or "")[:200]  # Truncate long messages
            sample_text += f"  [{role}]: {content}\n"

        if last_messages and last_messages != first_messages:
            sample_text += "\nLast messages:\n"
            for msg in last_messages:
                role = msg.role or "unknown"
                content = (msg.content or "")[:200]
                sample_text += f"  [{role}]: {content}\n"

        return TAGGING_PROMPT.format(
            agent_type=parsed.agent_type or "unknown",
            message_count=len(messages),
            duration_minutes=f"{duration:.1f}",
            status="completed",  # ParsedConversation doesn't have status field
            sample_messages=sample_text,
            intent_options=", ".join(INTENT_VALUES),
            outcome_options=", ".join(OUTCOME_VALUES),
            sentiment_options=", ".join(SENTIMENT_VALUES),
        )

    def _parse_tags(self, tags_dict: dict[str, Any]) -> ConversationTags:
        """Parse LLM response into ConversationTags.

        Validates values against taxonomy and provides sensible defaults.
        """
        # Validate and extract fields
        intent = tags_dict.get("intent", "other")
        if intent not in INTENT_VALUES:
            logger.warning(f"Invalid intent '{intent}', defaulting to 'other'")
            intent = "other"

        outcome = tags_dict.get("outcome", "unknown")
        if outcome not in OUTCOME_VALUES:
            logger.warning(f"Invalid outcome '{outcome}', defaulting to 'unknown'")
            outcome = "unknown"

        sentiment = tags_dict.get("sentiment", "neutral")
        if sentiment not in SENTIMENT_VALUES:
            logger.warning(f"Invalid sentiment '{sentiment}', defaulting to 'neutral'")
            sentiment = "neutral"

        # Clamp sentiment score to valid range
        sentiment_score = float(tags_dict.get("sentiment_score", 0.0))
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        # Extract lists (with max limits)
        features = tags_dict.get("features", [])[:5]
        problems = tags_dict.get("problems", [])[:5]

        # Extract reasoning
        reasoning = tags_dict.get("reasoning")

        return ConversationTags(
            intent=intent,
            outcome=outcome,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            features=features,
            problems=problems,
            reasoning=reasoning,
        )

    def _fallback_tags(self) -> ConversationTags:
        """Return fallback tags when LLM tagging fails."""
        return ConversationTags(
            intent="other",
            outcome="unknown",
            sentiment="neutral",
            sentiment_score=0.0,
        )
