"""Tests for LLM-based conversation tagger."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.tagging.llm_tagger import LLMTagger


@pytest.fixture
@patch("catsyphon.tagging.llm_tagger.OpenAI")
def llm_tagger(mock_openai_class: Mock) -> LLMTagger:
    """Create an LLM tagger instance with mocked OpenAI client."""
    # Mock the OpenAI client
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    tagger = LLMTagger(api_key="test_api_key", model="gpt-4o-mini")
    tagger.client = mock_client
    return tagger


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

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_initialization(self, mock_openai_class: Mock):
        """Test tagger initialization."""
        mock_openai_class.return_value = Mock()
        tagger = LLMTagger(api_key="test_key", model="gpt-4o-mini", max_tokens=500)
        assert tagger.model == "gpt-4o-mini"
        assert tagger.max_tokens == 500

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_success(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test successful tagging with OpenAI."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=150, completion_tokens=50, total_tokens=200
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "feature_add",
                        "outcome": "success",
                        "sentiment": "positive",
                        "sentiment_score": 0.8,
                        "features": ["authentication", "OAuth"],
                        "problems": []
                    }"""
                ),
                finish_reason="stop",
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

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
        assert metrics["llm_finish_reason"] == "stop"
        assert metrics["llm_cache_hit"] is False
        assert "llm_tagging_ms" in metrics
        assert "llm_cost_usd" in metrics
        assert "authentication" in tags.features
        assert "OAuth" in tags.features
        assert tags.problems == []

        # Verify API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["max_tokens"] == 500
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_with_invalid_intent(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid intent value."""
        # Mock OpenAI response with invalid intent
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "invalid_intent",
                        "outcome": "success",
                        "sentiment": "positive",
                        "sentiment_score": 0.5,
                        "features": [],
                        "problems": []
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "other" for invalid intent
        assert tags.intent == "other"

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_with_invalid_outcome(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid outcome value."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "bug_fix",
                        "outcome": "invalid_outcome",
                        "sentiment": "neutral",
                        "sentiment_score": 0.0,
                        "features": [],
                        "problems": []
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "unknown" for invalid outcome
        assert tags.outcome == "unknown"

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_with_invalid_sentiment(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test tagging with invalid sentiment value."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "learning",
                        "outcome": "success",
                        "sentiment": "invalid_sentiment",
                        "sentiment_score": 0.0,
                        "features": [],
                        "problems": []
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should default to "neutral" for invalid sentiment
        assert tags.sentiment == "neutral"

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_sentiment_score_clamping(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test that sentiment score is clamped to -1.0 to 1.0 range."""
        # Mock response with out-of-range sentiment score
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "debugging",
                        "outcome": "partial",
                        "sentiment": "negative",
                        "sentiment_score": -5.0,
                        "features": [],
                        "problems": []
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Score should be clamped to -1.0
        assert tags.sentiment_score == -1.0

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_features_list_truncation(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test that features list is truncated to max 5 items."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "feature_add",
                        "outcome": "success",
                        "sentiment": "positive",
                        "sentiment_score": 0.7,
                        "features": ["feat1", "feat2", "feat3", "feat4", "feat5", "feat6", "feat7"],
                        "problems": []
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Features should be truncated to 5
        assert len(tags.features) == 5

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_problems_list_truncation(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test that problems list is truncated to max 5 items."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [
            Mock(
                message=Mock(
                    content="""{
                        "intent": "bug_fix",
                        "outcome": "partial",
                        "sentiment": "neutral",
                        "sentiment_score": 0.0,
                        "features": [],
                        "problems": ["prob1", "prob2", "prob3", "prob4", "prob5", "prob6"]
                    }"""
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Problems should be truncated to 5
        assert len(tags.problems) == 5

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_api_error(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when OpenAI API fails."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        llm_tagger.client = mock_client

        # Should return fallback tags instead of crashing
        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        assert tags.intent == "other"
        assert tags.outcome == "unknown"
        assert tags.sentiment == "neutral"
        assert tags.sentiment_score == 0.0

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_empty_response(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when OpenAI returns empty response."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [Mock(message=Mock(content=None))]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

        tags, _ = llm_tagger.tag_conversation(sample_conversation)

        # Should return fallback tags
        assert tags.intent == "other"
        assert tags.outcome == "unknown"
        assert tags.sentiment == "neutral"

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_tag_conversation_invalid_json(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test fallback behavior when OpenAI returns invalid JSON."""
        mock_response = Mock()
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.choices = [Mock(message=Mock(content="invalid json {{{"))]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        llm_tagger.client = mock_client

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

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_all_valid_intents(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
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
            mock_response = Mock()
            mock_response.model = "gpt-4o-mini"
            mock_response.usage = Mock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )
            mock_response.choices = [
                Mock(
                    message=Mock(
                        content=f"""{{
                            "intent": "{intent}",
                            "outcome": "success",
                            "sentiment": "neutral",
                            "sentiment_score": 0.0,
                            "features": [],
                            "problems": []
                        }}"""
                    )
                )
            ]

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            llm_tagger.client = mock_client

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.intent == intent

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_all_valid_outcomes(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test that all valid outcome values are accepted."""
        valid_outcomes = ["success", "partial", "failed", "abandoned", "unknown"]

        for outcome in valid_outcomes:
            mock_response = Mock()
            mock_response.model = "gpt-4o-mini"
            mock_response.usage = Mock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )
            mock_response.choices = [
                Mock(
                    message=Mock(
                        content=f"""{{
                            "intent": "other",
                            "outcome": "{outcome}",
                            "sentiment": "neutral",
                            "sentiment_score": 0.0,
                            "features": [],
                            "problems": []
                        }}"""
                    )
                )
            ]

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            llm_tagger.client = mock_client

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.outcome == outcome

    @patch("catsyphon.tagging.llm_tagger.OpenAI")
    def test_all_valid_sentiments(
        self,
        mock_openai_class: Mock,
        llm_tagger: LLMTagger,
        sample_conversation: ParsedConversation,
    ):
        """Test that all valid sentiment values are accepted."""
        valid_sentiments = ["positive", "neutral", "negative", "frustrated"]

        for sentiment in valid_sentiments:
            mock_response = Mock()
            mock_response.model = "gpt-4o-mini"
            mock_response.usage = Mock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )
            mock_response.choices = [
                Mock(
                    message=Mock(
                        content=f"""{{
                            "intent": "other",
                            "outcome": "unknown",
                            "sentiment": "{sentiment}",
                            "sentiment_score": 0.0,
                            "features": [],
                            "problems": []
                        }}"""
                    )
                )
            ]

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            llm_tagger.client = mock_client

            tags, _ = llm_tagger.tag_conversation(sample_conversation)
            assert tags.sentiment == sentiment
