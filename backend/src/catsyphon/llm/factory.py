"""Factory for provider-agnostic analytics LLM clients."""

from __future__ import annotations

from catsyphon.config import Settings
from catsyphon.llm.protocol import LLMClient
from catsyphon.llm.providers.anthropic_client import AnthropicAnalyticsClient
from catsyphon.llm.providers.google_client import GoogleAnalyticsClient
from catsyphon.llm.providers.openai_client import OpenAIAnalyticsClient


def create_llm_client(settings: Settings) -> LLMClient:
    """Build an analytics client for the currently configured provider."""

    provider = settings.active_llm_provider
    api_key = settings.get_llm_api_key(provider)
    if not api_key:
        raise RuntimeError(
            f"LLM provider '{provider}' is not configured. "
            f"Set {settings.required_llm_api_key_env(provider)}."
        )

    return create_llm_client_for(provider=provider, api_key=api_key)


def create_llm_client_for(*, provider: str, api_key: str) -> LLMClient:
    """Build an analytics client from an explicit provider+key pair."""
    if provider == "openai":
        return OpenAIAnalyticsClient(api_key=api_key)
    if provider == "anthropic":
        return AnthropicAnalyticsClient(api_key=api_key)
    if provider == "google":
        return GoogleAnalyticsClient(api_key=api_key)

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")
