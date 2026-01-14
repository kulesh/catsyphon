"""Tagging pipeline that combines rule-based and LLM taggers with caching."""

import logging
from pathlib import Path
from typing import Any, Literal, Optional

from sqlalchemy.orm import Session

from catsyphon.canonicalization import Canonicalizer, CanonicalType
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.models.parsed import ConversationTags, ParsedConversation

from .cache import TagCache
from .llm_tagger import LLMTagger
from .providers import LLMProvider, create_provider
from .rule_tagger import RuleTagger

logger = logging.getLogger(__name__)


class TaggingPipeline:
    """Pipeline that orchestrates tagging with caching and multiple taggers.

    The pipeline follows this flow:
    1. Check cache for existing tags
    2. If cache miss:
       a. Run rule-based tagger (fast, deterministic)
       b. Run LLM tagger (slow, intelligent)
       c. Merge results (rule-based takes precedence)
       d. Store in cache
    3. Return merged tags

    Supports multiple LLM providers (OpenAI, Anthropic) through the provider factory.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        # Legacy parameters for backward compatibility
        openai_api_key: str | None = None,
        openai_model: str = "gpt-4o-mini",
        # New provider parameters
        provider_type: Literal["openai", "anthropic"] = "openai",
        api_key: str | None = None,
        model: str | None = None,
        # Cache settings
        cache_dir: Optional[Path] = None,
        cache_ttl_days: int = 30,
        enable_cache: bool = True,
    ):
        """Initialize the tagging pipeline.

        Args:
            provider: Pre-configured LLMProvider instance (preferred)
            openai_api_key: OpenAI API key (legacy, use api_key instead)
            openai_model: OpenAI model (legacy, use model instead)
            provider_type: Provider to use ("openai" or "anthropic")
            api_key: API key for the selected provider
            model: Model to use (provider-specific default if not specified)
            cache_dir: Directory for cache (default: .catsyphon_cache/tags)
            cache_ttl_days: Cache time-to-live in days (default: 30)
            enable_cache: Whether to use caching (default: True)
        """
        self.rule_tagger = RuleTagger()

        # Initialize LLM provider
        if provider is not None:
            llm_provider = provider
        elif api_key:
            llm_provider = create_provider(
                provider_type=provider_type,
                api_key=api_key,
                model=model,
            )
        elif openai_api_key:
            # Legacy: use openai_api_key parameter
            llm_provider = create_provider(
                provider_type="openai",
                api_key=openai_api_key,
                model=openai_model,
            )
        else:
            raise ValueError(
                "Either provider, api_key, or openai_api_key must be provided"
            )

        self.llm_tagger = LLMTagger(provider=llm_provider)

        # Setup cache
        if cache_dir is None:
            cache_dir = Path(".catsyphon_cache/tags")
        self.cache = TagCache(cache_dir=cache_dir, ttl_days=cache_ttl_days)
        self.enable_cache = enable_cache

        logger.info(
            f"TaggingPipeline initialized "
            f"(provider: {llm_provider.provider_name}, "
            f"model: {llm_provider.model_name}, cache: {enable_cache})"
        )

    def tag_conversation(
        self, parsed: ParsedConversation
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Tag a conversation with combined rule-based and LLM tags.

        DEPRECATED: Use tag_from_canonical_async for better performance and accuracy.
        This method is kept for backward compatibility.

        Args:
            parsed: The parsed conversation to tag

        Returns:
            Tuple of (tags_dict, llm_metrics_dict)
            - tags_dict: Dictionary of tags suitable for database storage
            - llm_metrics_dict: LLM metrics (tokens, cost, duration, model)
        """
        logger.warning(
            "Using deprecated tag_conversation method. "
            "Consider migrating to tag_from_canonical_async for better performance."
        )

        # Check cache first
        if self.enable_cache:
            cached_tags = self.cache.get(parsed)
            if cached_tags:
                logger.info("Using cached tags")
                # Cache hit - no LLM API call made
                cache_metrics = {
                    "llm_tagging_ms": 0,
                    "llm_prompt_tokens": 0,
                    "llm_completion_tokens": 0,
                    "llm_total_tokens": 0,
                    "llm_cost_usd": 0.0,
                    "llm_model": "cached",
                    "llm_finish_reason": "cached",
                    "llm_cache_hit": True,
                }
                return cached_tags.to_dict(), cache_metrics

        # Run taggers
        logger.info("Running taggers (cache miss)")
        rule_tags = self.rule_tagger.tag_conversation(parsed)
        llm_tags, llm_metrics = self.llm_tagger.tag_conversation(parsed)

        # Merge tags (rule-based takes precedence for deterministic fields)
        merged_tags = self._merge_tags(rule_tags, llm_tags)

        # Store in cache
        if self.enable_cache:
            self.cache.set(parsed, merged_tags)

        return merged_tags.to_dict(), llm_metrics

    def tag_from_canonical(
        self,
        conversation,
        session: Session,
        children: Optional[list] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Tag a conversation using canonical representation.

        This is the preferred method as it:
        - Uses intelligently sampled content (not just first/last messages)
        - Leverages pre-extracted metadata (errors, tools, patterns)
        - Caches canonical representations to avoid recomputation
        - Provides better context to LLM with hierarchical narrative

        Args:
            conversation: Database Conversation object (must have .id attribute)
            session: SQLAlchemy session for canonical caching
            children: Optional list of child conversations to include

        Returns:
            Tuple of (tags_dict, llm_metrics_dict)
            - tags_dict: Dictionary of tags suitable for database storage
            - llm_metrics_dict: LLM metrics (tokens, cost, duration, model)
        """
        # Check cache first (using conversation ID as key)
        # Note: We could enhance cache to use canonical hash, but for now
        # we rely on the canonical repository's caching
        if self.enable_cache and hasattr(conversation, "id"):
            # Try to get from tag cache using conversation ID
            # This requires adapting the cache to support ID-based lookup
            # For now, we'll skip tag cache and rely on canonical cache
            pass

        # Get or generate canonical representation
        canonical_repo = CanonicalRepository(session)
        canonicalizer = Canonicalizer(canonical_type=CanonicalType.TAGGING)

        canonical = canonical_repo.get_or_generate(
            conversation=conversation,
            canonical_type=CanonicalType.TAGGING,
            canonicalizer=canonicalizer,
            regeneration_threshold_tokens=2000,
            children=children,
        )

        logger.info(
            f"Using canonical representation: "
            f"{canonical.token_count} tokens, version {canonical.canonical_version}"
        )

        # Build metadata dict from canonical fields
        metadata = {
            "tools_used": canonical.tools_used,
            "files_touched": canonical.files_touched,
            "has_errors": canonical.has_errors,
        }

        # Run taggers with canonical data
        rule_tags = self.rule_tagger.tag_from_canonical(canonical)
        llm_tags, llm_metrics = self.llm_tagger.tag_from_canonical(
            narrative=canonical.narrative,
            metadata=metadata,
        )

        # Merge tags (rule-based takes precedence for deterministic fields)
        merged_tags = self._merge_tags(rule_tags, llm_tags)

        # Note: Tag cache could be updated here if needed
        # For now, canonical caching provides the primary benefit

        return merged_tags.to_dict(), llm_metrics

    def _merge_tags(
        self, rule_tags: ConversationTags, llm_tags: ConversationTags
    ) -> ConversationTags:
        """Merge rule-based and LLM tags.

        Rule-based tags take precedence for deterministic fields:
        - has_errors
        - tools_used
        - iterations
        - patterns

        LLM tags are used for subjective analysis:
        - intent
        - outcome
        - sentiment
        - sentiment_score
        - features
        - problems

        Args:
            rule_tags: Tags from rule-based tagger
            llm_tags: Tags from LLM tagger

        Returns:
            Merged ConversationTags
        """
        return ConversationTags(
            # LLM tags (subjective analysis)
            intent=llm_tags.intent,
            outcome=llm_tags.outcome,
            sentiment=llm_tags.sentiment,
            sentiment_score=llm_tags.sentiment_score,
            # Rule-based tags (deterministic)
            has_errors=rule_tags.has_errors,
            tools_used=rule_tags.tools_used,
            iterations=rule_tags.iterations,
            patterns=rule_tags.patterns,
            # Merge lists (prefer LLM for features/problems, add rule patterns)
            features=llm_tags.features,
            problems=llm_tags.problems,
            # Empty entities dict (can be extended later)
            entities={},
        )

    def clear_cache(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of entries removed
        """
        return self.cache.clear_expired()

    def cache_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return self.cache.stats()
