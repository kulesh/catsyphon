"""Tests for LLM-based conversation tagger."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.tagging.llm_tagger import LLMTagger
from catsyphon.tagging.providers import LLMResponse


@pytest.fixture
def mock_provider() -> Mock:
    """Create a mock LLM provider."""
    provider = Mock()
    provider.provider_name = "openai"
    provider.model_name = "gpt-4o-mini"
    provider.calculate_cost.return_value = 0.001
    return provider


@pytest.fixture
def llm_tagger(mock_provider: Mock) -> LLMTagger:
    """Create an LLM tagger instance with mocked provider."""
    return LLMTagger(provider=mock_provider, max_tokens=500)


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
                content="Can you help me implement a new authentication feature?",
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
            ),
            ParsedMessage(
                role="assistant",
                content="I'll help you implement OAuth authentication. Let me start by reading your current auth setup.",
                timestamp=datetime(2025, 1, 1, 10, 1, 0),
            ),
            ParsedMessage(
                role="user",
                content="Great, the implementation looks good!",
                timestamp=datetime(2025, 1, 1, 10, 25, 0),
            ),
        ],
    )


class TestLLMTagger:
    """Tests for LLMTagger class."""

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_initialization_with_api_key(self, mock_openai_class: Mock):
        """Test tagger initialization with legacy API key parameter."""
        mock_openai_class.return_value = Mock()
        tagger = LLMTagger(api_key="test_key", model="gpt-4o-mini", max_tokens=500)
        assert tagger.provider.model_name == "gpt-4o-mini"
        assert tagger.max_tokens == 500

    def test_initialization_with_provider(self, mock_provider: Mock):
        """Test tagger initialization with provider instance."""
        tagger = LLMTagger(provider=mock_provider, max_tokens=600)
        assert tagger.provider is mock_provider
        assert tagger.max_tokens == 600

    def test_initialization_requires_provider_or_api_key(self):
        """Test that initialization fails without provider or api_key."""
        with pytest.raises(ValueError, match="Either provider or api_key must be provided"):
            LLMTagger()

    def test_tag_conversation_success(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test successful tagging with mocked provider."""
        # Mock provider response
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "feature_add",
                "outcome": "success",
                "sentiment": "positive",
                "sentiment_score": 0.8,
                "features": ["authentication", "OAuth"],
                "problems": []
            }""",
            prompt_tokens=150,
            completion_tokens=50,
            total_tokens=200,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1234.5,
        )

        # Tag conversation
        tags, metrics = llm_tagger.tag_conversation(sample_conversation)

        # Verify tag results
        assert tags.intent == "feature_add"
        assert tags.outcome == "success"
        assert tags.sentiment == "positive"
        assert tags.sentiment_score == 0.8

        # Verify metrics
        assert metrics["llm_prompt_tokens"] == 150
        assert metrics["llm_completion_tokens"] == 50
        assert metrics["llm_total_tokens"] == 200
        assert metrics["llm_model"] == "gpt-4o-mini"
        assert metrics["llm_provider"] == "openai"
        assert metrics["llm_finish_reason"] == "stop"
        assert metrics["llm_cache_hit"] is False
        assert "llm_tagging_ms" in metrics
        assert "llm_cost_usd" in metrics
        assert "authentication" in tags.features
        assert "OAuth" in tags.features
        assert tags.problems == []

        # Verify provider was called correctly
        mock_provider.complete.assert_called_once()
        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["json_schema"] is not None

    def test_tag_conversation_with_invalid_intent(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid intent value."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "invalid_intent",
                "outcome": "success",
                "sentiment": "positive",
                "sentiment_score": 0.5,
                "features": [],
                "problems": []
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "other" for invalid intent
        assert tags.intent == "other"

    def test_tag_conversation_with_invalid_outcome(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid outcome value."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "bug_fix",
                "outcome": "invalid_outcome",
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "features": [],
                "problems": []
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "unknown" for invalid outcome
        assert tags.outcome == "unknown"

    def test_tag_conversation_with_invalid_sentiment(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid sentiment value."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "learning",
                "outcome": "success",
                "sentiment": "invalid_sentiment",
                "sentiment_score": 0.0,
                "features": [],
                "problems": []
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "neutral" for invalid sentiment
        assert tags.sentiment == "neutral"

    def test_sentiment_score_clamping(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that sentiment score is clamped to -1.0 to 1.0 range."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "debugging",
                "outcome": "partial",
                "sentiment": "negative",
                "sentiment_score": -5.0,
                "features": [],
                "problems": []
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Score should be clamped to -1.0
        assert tags.sentiment_score == -1.0

    def test_features_list_truncation(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that features list is truncated to max 5 items."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "feature_add",
                "outcome": "success",
                "sentiment": "positive",
                "sentiment_score": 0.7,
                "features": ["feat1", "feat2", "feat3", "feat4", "feat5", "feat6", "feat7"],
                "problems": []
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Features should be truncated to 5
        assert len(tags.features) == 5

    def test_problems_list_truncation(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that problems list is truncated to max 5 items."""
        mock_provider.complete.return_value = LLMResponse(
            content="""{
                "intent": "bug_fix",
                "outcome": "partial",
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "features": [],
                "problems": ["prob1", "prob2", "prob3", "prob4", "prob5", "prob6"]
            }""",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Problems should be truncated to 5
        assert len(tags.problems) == 5

    def test_tag_conversation_api_error(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when provider fails."""
        mock_provider.complete.side_effect = Exception("API Error")

        # Should return fallback tags instead of crashing
        tags, metrics = llm_tagger.tag_conversation(sample_conversation)

        assert tags.intent == "other"
        assert tags.outcome == "unknown"
        assert tags.sentiment == "neutral"
        assert tags.sentiment_score == 0.0
        assert metrics["llm_error"] == "API Error"

    def test_tag_conversation_empty_response(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when provider returns empty response."""
        mock_provider.complete.return_value = LLMResponse(
            content="",
            prompt_tokens=100,
            completion_tokens=0,
            total_tokens=100,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=500.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should return fallback tags
        assert tags.intent == "other"
        assert tags.outcome == "unknown"
        assert tags.sentiment == "neutral"

    def test_tag_conversation_invalid_json(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when provider returns invalid JSON."""
        mock_provider.complete.return_value = LLMResponse(
            content="invalid json {{{",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1000.0,
        )

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should return fallback tags
        assert tags.intent == "other"
        assert tags.outcome == "unknown"

    def test_build_prompt(
        self, llm_tagger: LLMTagger, sample_conversation: ParsedConversation
    ):
        """Test prompt building."""
        prompt = llm_tagger._build_prompt(sample_conversation)

        # Verify prompt contains key information
        assert "claude-code" in prompt
        assert "3" in prompt  # 3 messages
        assert "30.0" in prompt  # 30 minutes duration
        assert "Can you help me implement" in prompt  # First message
        assert "Great, the implementation" in prompt  # Last message

    def test_build_prompt_with_long_messages(self, llm_tagger: LLMTagger):
        """Test that long messages are truncated in prompt."""
        long_content = "A" * 500  # 500 characters
        conversation = ParsedConversation(
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=datetime(2025, 1, 1, 10, 0, 0),
            end_time=datetime(2025, 1, 1, 10, 1, 0),
            messages=[
                ParsedMessage(
                    role="user",
                    content=long_content,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                ),
            ],
        )

        prompt = llm_tagger._build_prompt(conversation)

        # Prompt should not contain full 500 characters (truncated to 200)
        assert long_content not in prompt
        assert "A" * 200 in prompt

    def test_build_prompt_without_end_time(self, llm_tagger: LLMTagger):
        """Test prompt building when end_time is None."""
        conversation = ParsedConversation(
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=datetime(2025, 1, 1, 10, 0, 0),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Quick question",
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                ),
            ],
        )

        prompt = llm_tagger._build_prompt(conversation)

        # Should handle None end_time gracefully (duration = 0)
        assert "0.0" in prompt

    def test_all_valid_intents(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that all valid intent values are accepted."""
        valid_intents = [
            "feature_add",
            "bug_fix",
            "refactor",
            "learning",
            "debugging",
            "other",
        ]

        for intent in valid_intents:
            mock_provider.complete.return_value = LLMResponse(
                content=f"""{{
                    "intent": "{intent}",
                    "outcome": "success",
                    "sentiment": "neutral",
                    "sentiment_score": 0.0,
                    "features": [],
                    "problems": []
                }}""",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                finish_reason="stop",
                model="gpt-4o-mini",
                duration_ms=1000.0,
            )

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.intent == intent

    def test_all_valid_outcomes(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that all valid outcome values are accepted."""
        valid_outcomes = ["success", "partial", "failed", "abandoned", "unknown"]

        for outcome in valid_outcomes:
            mock_provider.complete.return_value = LLMResponse(
                content=f"""{{
                    "intent": "other",
                    "outcome": "{outcome}",
                    "sentiment": "neutral",
                    "sentiment_score": 0.0,
                    "features": [],
                    "problems": []
                }}""",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                finish_reason="stop",
                model="gpt-4o-mini",
                duration_ms=1000.0,
            )

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.outcome == outcome

    def test_all_valid_sentiments(
        self,
        llm_tagger: LLMTagger,
        mock_provider: Mock,
        sample_conversation: ParsedConversation,
    ):
        """Test that all valid sentiment values are accepted."""
        valid_sentiments = ["positive", "neutral", "negative", "frustrated"]

        for sentiment in valid_sentiments:
            mock_provider.complete.return_value = LLMResponse(
                content=f"""{{
                    "intent": "other",
                    "outcome": "unknown",
                    "sentiment": "{sentiment}",
                    "sentiment_score": 0.0,
                    "features": [],
                    "problems": []
                }}""",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                finish_reason="stop",
                model="gpt-4o-mini",
                duration_ms=1000.0,
            )

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.sentiment == sentiment
