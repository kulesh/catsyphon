"""Tests for LLM provider implementations."""

from unittest.mock import Mock, patch

import pytest

from catsyphon.tagging.providers import (
    LLMProvider,
    LLMResponse,
    create_provider,
    get_available_providers,
)
from catsyphon.tagging.providers.anthropic_provider import (
    ANTHROPIC_PRICING,
    STRUCTURED_OUTPUT_MODELS,
    AnthropicProvider,
)
from catsyphon.tagging.providers.openai_provider import OPENAI_PRICING, OpenAIProvider


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_response(self):
        """Test creating an LLMResponse."""
        response = LLMResponse(
            content='{"intent": "feature_add"}',
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            finish_reason="stop",
            model="gpt-4o-mini",
            duration_ms=1234.5,
        )

        assert response.content == '{"intent": "feature_add"}'
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 50
        assert response.total_tokens == 150
        assert response.finish_reason == "stop"
        assert response.model == "gpt-4o-mini"
        assert response.duration_ms == 1234.5
        assert response.raw_response is None

    def test_response_with_raw_response(self):
        """Test creating LLMResponse with raw response object."""
        mock_raw = Mock()
        response = LLMResponse(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="stop",
            model="test-model",
            duration_ms=100.0,
            raw_response=mock_raw,
        )

        assert response.raw_response is mock_raw


class TestProviderFactory:
    """Tests for provider factory function."""

    def test_get_available_providers(self):
        """Test listing available providers."""
        providers = get_available_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert len(providers) == 2

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_create_openai_provider(self, mock_openai_class: Mock):
        """Test creating OpenAI provider."""
        mock_openai_class.return_value = Mock()

        provider = create_provider(
            provider_type="openai",
            api_key="sk-test-key",
            model="gpt-4o-mini",
        )

        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-4o-mini"

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_create_anthropic_provider(self, mock_anthropic_class: Mock):
        """Test creating Anthropic provider."""
        mock_anthropic_class.return_value = Mock()

        provider = create_provider(
            provider_type="anthropic",
            api_key="sk-ant-test-key",
            model="claude-sonnet-4-5-20250514",
        )

        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"
        assert provider.model_name == "claude-sonnet-4-5-20250514"

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_create_provider_default_model(self, mock_openai_class: Mock):
        """Test provider creation with default model."""
        mock_openai_class.return_value = Mock()

        provider = create_provider(
            provider_type="openai",
            api_key="sk-test-key",
        )

        assert provider.model_name == "gpt-4o-mini"

    def test_create_provider_invalid_type(self):
        """Test error on invalid provider type."""
        with pytest.raises(ValueError, match="Unknown provider type"):
            create_provider(
                provider_type="invalid",  # type: ignore
                api_key="test-key",
            )

    def test_create_provider_missing_api_key(self):
        """Test error when API key is missing."""
        with pytest.raises(ValueError, match="API key is required"):
            create_provider(
                provider_type="openai",
                api_key="",
            )


class TestOpenAIProvider:
    """Tests for OpenAI provider implementation."""

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_initialization(self, mock_openai_class: Mock):
        """Test provider initialization."""
        mock_openai_class.return_value = Mock()

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-4o-mini"
        mock_openai_class.assert_called_once_with(api_key="sk-test")

    def test_initialization_no_api_key(self):
        """Test error when API key is missing."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenAIProvider(api_key="", model="gpt-4o-mini")

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_complete_with_json_schema(self, mock_openai_class: Mock):
        """Test completion with JSON schema."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"result": "test"}'), finish_reason="stop")
        ]
        mock_response.usage = Mock(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        mock_response.model = "gpt-4o-mini"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        response = provider.complete(
            system_prompt="System",
            user_prompt="User",
            json_schema={"type": "object"},
        )

        assert response.content == '{"result": "test"}'
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 50

        # Verify JSON mode was enabled
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_complete_without_json_schema(self, mock_openai_class: Mock):
        """Test completion without JSON schema."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Plain text"), finish_reason="stop")
        ]
        mock_response.usage = Mock(
            prompt_tokens=50, completion_tokens=25, total_tokens=75
        )
        mock_response.model = "gpt-4o-mini"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        response = provider.complete(
            system_prompt="System",
            user_prompt="User",
        )

        assert response.content == "Plain text"

        # Verify JSON mode was NOT enabled
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "response_format" not in call_kwargs

    def test_calculate_cost_gpt4o_mini(self):
        """Test cost calculation for gpt-4o-mini."""
        with patch("catsyphon.tagging.providers.openai_provider.OpenAI"):
            provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        cost = provider.calculate_cost(prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(cost - 0.15) < 0.001

        cost = provider.calculate_cost(prompt_tokens=0, completion_tokens=1_000_000)
        assert abs(cost - 0.60) < 0.001

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation falls back to default for unknown models."""
        with patch("catsyphon.tagging.providers.openai_provider.OpenAI"):
            provider = OpenAIProvider(api_key="sk-test", model="unknown-model")

        # Should use default pricing
        cost = provider.calculate_cost(prompt_tokens=1_000_000, completion_tokens=0)
        assert cost == OPENAI_PRICING["default"]["input"]


class TestAnthropicProvider:
    """Tests for Anthropic provider implementation."""

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_initialization(self, mock_anthropic_class: Mock):
        """Test provider initialization."""
        mock_anthropic_class.return_value = Mock()

        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
        )

        assert provider.provider_name == "anthropic"
        assert provider.model_name == "claude-sonnet-4-5-20250514"
        mock_anthropic_class.assert_called_once_with(api_key="sk-ant-test")

    def test_initialization_no_api_key(self):
        """Test error when API key is missing."""
        with pytest.raises(ValueError, match="API key is required"):
            AnthropicProvider(api_key="", model="claude-sonnet-4-5-20250514")

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_structured_output_support_detection(self, mock_anthropic_class: Mock):
        """Test detection of structured output support."""
        mock_anthropic_class.return_value = Mock()

        # Claude 4.5 models should support structured outputs
        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
        )
        assert provider._supports_structured is True

        # Claude 3.5 models should NOT support structured outputs
        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-3-5-haiku-20241022"
        )
        assert provider._supports_structured is False

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_complete_with_structured_output(self, mock_anthropic_class: Mock):
        """Test completion with structured output for Claude 4.5."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='{"result": "test"}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_response.stop_reason = "end_turn"
        mock_response.model = "claude-sonnet-4-5-20250514"
        mock_client.beta.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
        )
        response = provider.complete(
            system_prompt="System",
            user_prompt="User",
            json_schema={"type": "object"},
        )

        assert response.content == '{"result": "test"}'
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 50

        # Verify structured output was used
        call_kwargs = mock_client.beta.messages.create.call_args[1]
        assert "betas" in call_kwargs
        assert "structured-outputs-2025-11-13" in call_kwargs["betas"]
        assert "output_format" in call_kwargs

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_complete_with_prompt_json_fallback(self, mock_anthropic_class: Mock):
        """Test completion falls back to prompt-based JSON for older models."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='{"result": "test"}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_response.stop_reason = "end_turn"
        mock_response.model = "claude-3-5-haiku-20241022"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-3-5-haiku-20241022"
        )
        response = provider.complete(
            system_prompt="System",
            user_prompt="User",
            json_schema={"type": "object"},
        )

        assert response.content == '{"result": "test"}'

        # Verify regular messages endpoint was used (not beta)
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]

        # System prompt should have JSON instruction appended
        assert "valid JSON only" in call_kwargs["system"]

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_complete_without_json_schema(self, mock_anthropic_class: Mock):
        """Test completion without JSON schema."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="Plain text response")]
        mock_response.usage = Mock(input_tokens=50, output_tokens=25)
        mock_response.stop_reason = "end_turn"
        mock_response.model = "claude-sonnet-4-5-20250514"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
        )
        response = provider.complete(
            system_prompt="System",
            user_prompt="User",
        )

        assert response.content == "Plain text response"

        # Verify regular endpoint was used
        mock_client.messages.create.assert_called_once()

    def test_calculate_cost_haiku(self):
        """Test cost calculation for Claude 3.5 Haiku."""
        with patch("catsyphon.tagging.providers.anthropic_provider.Anthropic"):
            provider = AnthropicProvider(
                api_key="sk-ant-test", model="claude-3-5-haiku-20241022"
            )

        # Haiku: $0.80/1M input, $4.00/1M output
        cost = provider.calculate_cost(prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(cost - 0.80) < 0.001

        cost = provider.calculate_cost(prompt_tokens=0, completion_tokens=1_000_000)
        assert abs(cost - 4.00) < 0.001

    def test_calculate_cost_sonnet(self):
        """Test cost calculation for Claude Sonnet 4.5."""
        with patch("catsyphon.tagging.providers.anthropic_provider.Anthropic"):
            provider = AnthropicProvider(
                api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
            )

        # Sonnet 4.5: $3.00/1M input, $15.00/1M output
        cost = provider.calculate_cost(prompt_tokens=1_000_000, completion_tokens=0)
        assert abs(cost - 3.00) < 0.001

        cost = provider.calculate_cost(prompt_tokens=0, completion_tokens=1_000_000)
        assert abs(cost - 15.00) < 0.001

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation falls back to default for unknown models."""
        with patch("catsyphon.tagging.providers.anthropic_provider.Anthropic"):
            provider = AnthropicProvider(
                api_key="sk-ant-test", model="unknown-claude-model"
            )

        # Should use default pricing
        cost = provider.calculate_cost(prompt_tokens=1_000_000, completion_tokens=0)
        assert cost == ANTHROPIC_PRICING["default"]["input"]


class TestProviderInterface:
    """Tests to verify providers implement the interface correctly."""

    @patch("catsyphon.tagging.providers.openai_provider.OpenAI")
    def test_openai_implements_interface(self, mock_openai_class: Mock):
        """Test that OpenAI provider implements LLMProvider interface."""
        mock_openai_class.return_value = Mock()
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

        # Check all required properties/methods exist
        assert hasattr(provider, "provider_name")
        assert hasattr(provider, "model_name")
        assert hasattr(provider, "complete")
        assert hasattr(provider, "calculate_cost")

        # Verify property types
        assert isinstance(provider.provider_name, str)
        assert isinstance(provider.model_name, str)

    @patch("catsyphon.tagging.providers.anthropic_provider.Anthropic")
    def test_anthropic_implements_interface(self, mock_anthropic_class: Mock):
        """Test that Anthropic provider implements LLMProvider interface."""
        mock_anthropic_class.return_value = Mock()
        provider = AnthropicProvider(
            api_key="sk-ant-test", model="claude-sonnet-4-5-20250514"
        )

        # Check all required properties/methods exist
        assert hasattr(provider, "provider_name")
        assert hasattr(provider, "model_name")
        assert hasattr(provider, "complete")
        assert hasattr(provider, "calculate_cost")

        # Verify property types
        assert isinstance(provider.provider_name, str)
        assert isinstance(provider.model_name, str)
