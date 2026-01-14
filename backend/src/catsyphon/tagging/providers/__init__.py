"""LLM Provider implementations for conversation tagging.

This module provides a pluggable provider system for LLM-based tagging.
Currently supported providers:
- OpenAI (gpt-4o-mini, gpt-4o, etc.)
- Anthropic (claude-sonnet-4-5, claude-3-5-haiku, etc.)

Usage:
    from catsyphon.tagging.providers import create_provider

    provider = create_provider(
        provider_type="openai",
        api_key="sk-xxx",
        model="gpt-4o-mini",
    )

    response = provider.complete(
        system_prompt="You are an expert...",
        user_prompt="Analyze this...",
        json_schema={"type": "object", ...},
    )
"""

import logging
from typing import Literal

from catsyphon.tagging.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Type alias for provider names
ProviderType = Literal["openai", "anthropic"]


def create_provider(
    provider_type: ProviderType,
    api_key: str,
    model: str | None = None,
) -> LLMProvider:
    """Factory function to create LLM providers.

    Args:
        provider_type: The provider to use ("openai" or "anthropic")
        api_key: API key for the provider
        model: Optional model override (uses provider default if not specified)

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider_type is unknown or api_key is missing
    """
    if not api_key:
        raise ValueError(f"API key is required for {provider_type} provider")

    if provider_type == "openai":
        from catsyphon.tagging.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o-mini",
        )

    elif provider_type == "anthropic":
        from catsyphon.tagging.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-sonnet-4-5-20250514",
        )

    else:
        raise ValueError(
            f"Unknown provider type: {provider_type}. "
            f"Supported providers: openai, anthropic"
        )


def get_available_providers() -> list[str]:
    """Get list of available provider types.

    Returns:
        List of provider type strings
    """
    return ["openai", "anthropic"]


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ProviderType",
    "create_provider",
    "get_available_providers",
]
