"""Tests for tagging pipeline."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.tagging.pipeline import TaggingPipeline


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "tag_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
@patch("catsyphon.tagging.pipeline.LLMTagger")
def tagging_pipeline(
    mock_llm_tagger_class: Mock, temp_cache_dir: Path
) -> TaggingPipeline:
    """Create a tagging pipeline instance with mocked LLM tagger."""
    # Mock LLM tagger to avoid OpenAI client initialization
    mock_llm_tagger_class.return_value = Mock()

    return TaggingPipeline(
        openai_api_key="test_api_key",
        openai_model="gpt-4o-mini",
        cache_dir=temp_cache_dir,
        cache_ttl_days=30,
        enable_cache=True,
    )


@pytest.fixture
def sample_conversation() -> ParsedConversation:
    """Create a sample parsed conversation."""
    return ParsedConversation(
        agent_type="claude-code",
        agent_version="1.0.0",
        start_time=datetime(2025, 1, 1, 10, 0, 0),
        end_time=datetime(2025, 1, 1, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Help me fix this error in the code",
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
            ),
            ParsedMessage(
                role="assistant",
                content="I'll help debug this. Let me read file app.py to check the error.",
                timestamp=datetime(2025, 1, 1, 10, 1, 0),
            ),
            ParsedMessage(
                role="assistant",
                content="Found the issue - there's a TypeError exception in the function.",
                timestamp=datetime(2025, 1, 1, 10, 2, 0),
            ),
        ],
    )


class TestTaggingPipeline:
    """Tests for TaggingPipeline class."""

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    def test_initialization_with_cache(
        self, mock_llm_tagger_class: Mock, temp_cache_dir: Path
    ):
        """Test pipeline initialization with cache enabled."""
        mock_llm_tagger_class.return_value = Mock()

        pipeline = TaggingPipeline(
            openai_api_key="test_key",
            openai_model="gpt-4o-mini",
            cache_dir=temp_cache_dir,
            enable_cache=True,
        )

        assert pipeline.enable_cache is True
        assert pipeline.cache is not None
        assert pipeline.rule_tagger is not None
        assert pipeline.llm_tagger is not None

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    def test_initialization_without_cache(
        self, mock_llm_tagger_class: Mock, temp_cache_dir: Path
    ):
        """Test pipeline initialization with cache disabled."""
        mock_llm_tagger_class.return_value = Mock()

        pipeline = TaggingPipeline(
            openai_api_key="test_key",
            openai_model="gpt-4o-mini",
            cache_dir=temp_cache_dir,
            enable_cache=False,
        )

        assert pipeline.enable_cache is False

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_tag_conversation_merges_results(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
        sample_conversation: ParsedConversation,
    ):
        """Test that pipeline merges rule-based and LLM results."""
        # Mock rule tagger results
        from catsyphon.models.parsed import ConversationTags

        rule_tags = ConversationTags(
            has_errors=True,
            tools_used=["read", "bash"],
            iterations=2,
            patterns=["debugging", "testing"],
        )

        # Mock LLM tagger results
        llm_tags = ConversationTags(
            intent="bug_fix",
            outcome="success",
            sentiment="positive",
            sentiment_score=0.7,
            features=["error handling", "debugging"],
            problems=["TypeError exception"],
        )

        # Setup mocks
        mock_rule_tagger = Mock()
        mock_rule_tagger.tag_conversation.return_value = rule_tags
        tagging_pipeline.rule_tagger = mock_rule_tagger

        mock_llm_tagger = Mock()
        mock_llm_tagger.tag_conversation.return_value = llm_tags
        tagging_pipeline.llm_tagger = mock_llm_tagger

        # Tag conversation
        result = tagging_pipeline.tag_conversation(sample_conversation)

        # Verify merged results
        assert result["intent"] == "bug_fix"  # From LLM
        assert result["outcome"] == "success"  # From LLM
        assert result["sentiment"] == "positive"  # From LLM
        assert result["sentiment_score"] == 0.7  # From LLM
        assert result["has_errors"] is True  # From rule tagger
        assert result["tools_used"] == ["read", "bash"]  # From rule tagger
        assert result["iterations"] == 2  # From rule tagger
        assert result["patterns"] == ["debugging", "testing"]  # From rule tagger
        assert result["features"] == ["error handling", "debugging"]  # From LLM
        assert result["problems"] == ["TypeError exception"]  # From LLM

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_tag_conversation_uses_cache(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
        sample_conversation: ParsedConversation,
    ):
        """Test that pipeline uses cache for repeated requests."""
        from catsyphon.models.parsed import ConversationTags

        # Mock taggers
        rule_tags = ConversationTags(has_errors=False, tools_used=["read"])
        llm_tags = ConversationTags(
            intent="feature_add",
            outcome="success",
            sentiment="positive",
            sentiment_score=0.8,
        )

        mock_rule_tagger = Mock()
        mock_rule_tagger.tag_conversation.return_value = rule_tags
        tagging_pipeline.rule_tagger = mock_rule_tagger

        mock_llm_tagger = Mock()
        mock_llm_tagger.tag_conversation.return_value = llm_tags
        tagging_pipeline.llm_tagger = mock_llm_tagger

        # First call - should hit taggers
        result1 = tagging_pipeline.tag_conversation(sample_conversation)
        assert mock_rule_tagger.tag_conversation.call_count == 1
        assert mock_llm_tagger.tag_conversation.call_count == 1

        # Second call - should hit cache
        result2 = tagging_pipeline.tag_conversation(sample_conversation)
        assert mock_rule_tagger.tag_conversation.call_count == 1  # Not called again
        assert mock_llm_tagger.tag_conversation.call_count == 1  # Not called again

        # Results should be the same
        assert result1["intent"] == result2["intent"]
        assert result1["outcome"] == result2["outcome"]

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_tag_conversation_without_cache(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
    ):
        """Test that pipeline skips cache when disabled."""
        from catsyphon.models.parsed import ConversationTags

        # Create pipeline with cache disabled
        pipeline = TaggingPipeline(
            openai_api_key="test_key",
            openai_model="gpt-4o-mini",
            cache_dir=temp_cache_dir,
            enable_cache=False,
        )

        # Mock taggers
        rule_tags = ConversationTags(has_errors=False)
        llm_tags = ConversationTags(
            intent="feature_add", outcome="success", sentiment="positive"
        )

        mock_rule_tagger = Mock()
        mock_rule_tagger.tag_conversation.return_value = rule_tags
        pipeline.rule_tagger = mock_rule_tagger

        mock_llm_tagger = Mock()
        mock_llm_tagger.tag_conversation.return_value = llm_tags
        pipeline.llm_tagger = mock_llm_tagger

        # First call
        pipeline.tag_conversation(sample_conversation)
        assert mock_rule_tagger.tag_conversation.call_count == 1
        assert mock_llm_tagger.tag_conversation.call_count == 1

        # Second call - taggers should be called again (no cache)
        pipeline.tag_conversation(sample_conversation)
        assert mock_rule_tagger.tag_conversation.call_count == 2
        assert mock_llm_tagger.tag_conversation.call_count == 2

    def test_cache_stats(self, tagging_pipeline: TaggingPipeline):
        """Test that cache stats are accessible."""
        stats = tagging_pipeline.cache_stats()

        assert isinstance(stats, dict)
        assert "total" in stats
        assert "valid" in stats
        assert "expired" in stats

    def test_clear_cache(self, tagging_pipeline: TaggingPipeline):
        """Test that cache can be cleared."""
        removed = tagging_pipeline.clear_cache()
        assert isinstance(removed, int)
        assert removed >= 0

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_merge_tags_priority(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
    ):
        """Test that rule-based tags take precedence for deterministic fields."""
        from catsyphon.models.parsed import ConversationTags

        rule_tags = ConversationTags(
            has_errors=True,
            tools_used=["bash", "git"],
            iterations=3,
            patterns=["pattern1"],
        )

        llm_tags = ConversationTags(
            intent="refactor",
            outcome="partial",
            sentiment="neutral",
            sentiment_score=0.0,
            features=["feature1"],
            problems=["problem1"],
        )

        merged = tagging_pipeline._merge_tags(rule_tags, llm_tags)

        # Rule-based fields
        assert merged.has_errors == rule_tags.has_errors
        assert merged.tools_used == rule_tags.tools_used
        assert merged.iterations == rule_tags.iterations
        assert merged.patterns == rule_tags.patterns

        # LLM fields
        assert merged.intent == llm_tags.intent
        assert merged.outcome == llm_tags.outcome
        assert merged.sentiment == llm_tags.sentiment
        assert merged.sentiment_score == llm_tags.sentiment_score
        assert merged.features == llm_tags.features
        assert merged.problems == llm_tags.problems

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_merge_tags_with_none_values(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
    ):
        """Test merging when some fields are None."""
        from catsyphon.models.parsed import ConversationTags

        rule_tags = ConversationTags(
            has_errors=False,
            tools_used=[],
            iterations=1,
            patterns=[],
        )

        llm_tags = ConversationTags(
            intent=None,
            outcome=None,
            sentiment=None,
            sentiment_score=None,
            features=[],
            problems=[],
        )

        merged = tagging_pipeline._merge_tags(rule_tags, llm_tags)

        # Should handle None values gracefully
        assert merged.intent is None
        assert merged.outcome is None
        assert merged.sentiment is None
        assert merged.has_errors is False
        assert merged.iterations == 1

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_tag_conversation_returns_dict(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
        sample_conversation: ParsedConversation,
    ):
        """Test that tag_conversation returns a dictionary."""
        from catsyphon.models.parsed import ConversationTags

        rule_tags = ConversationTags(has_errors=False)
        llm_tags = ConversationTags(
            intent="learning", outcome="success", sentiment="positive"
        )

        mock_rule_tagger = Mock()
        mock_rule_tagger.tag_conversation.return_value = rule_tags
        tagging_pipeline.rule_tagger = mock_rule_tagger

        mock_llm_tagger = Mock()
        mock_llm_tagger.tag_conversation.return_value = llm_tags
        tagging_pipeline.llm_tagger = mock_llm_tagger

        result = tagging_pipeline.tag_conversation(sample_conversation)

        # Should return a dict
        assert isinstance(result, dict)
        assert "intent" in result
        assert "outcome" in result
        assert "sentiment" in result
        assert "has_errors" in result

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_default_cache_directory(
        self, mock_rule_tagger_class: Mock, mock_llm_tagger_class: Mock
    ):
        """Test that default cache directory is used when not specified."""
        pipeline = TaggingPipeline(
            openai_api_key="test_key",
            openai_model="gpt-4o-mini",
            cache_dir=None,  # Should use default
        )

        # Should create default cache directory
        assert pipeline.cache.cache_dir == Path(".catsyphon_cache/tags")

    @patch("catsyphon.tagging.pipeline.LLMTagger")
    @patch("catsyphon.tagging.pipeline.RuleTagger")
    def test_cache_stores_results_after_tagging(
        self,
        mock_rule_tagger_class: Mock,
        mock_llm_tagger_class: Mock,
        tagging_pipeline: TaggingPipeline,
        sample_conversation: ParsedConversation,
    ):
        """Test that results are stored in cache after tagging."""
        from catsyphon.models.parsed import ConversationTags

        rule_tags = ConversationTags(has_errors=True)
        llm_tags = ConversationTags(
            intent="debugging", outcome="success", sentiment="positive"
        )

        mock_rule_tagger = Mock()
        mock_rule_tagger.tag_conversation.return_value = rule_tags
        tagging_pipeline.rule_tagger = mock_rule_tagger

        mock_llm_tagger = Mock()
        mock_llm_tagger.tag_conversation.return_value = llm_tags
        tagging_pipeline.llm_tagger = mock_llm_tagger

        # Cache should be empty
        stats_before = tagging_pipeline.cache_stats()
        assert stats_before["total"] == 0

        # Tag conversation
        tagging_pipeline.tag_conversation(sample_conversation)

        # Cache should have 1 entry
        stats_after = tagging_pipeline.cache_stats()
        assert stats_after["total"] == 1
