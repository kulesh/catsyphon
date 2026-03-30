"""Provider-aware token pricing helpers."""

from __future__ import annotations

from typing import Final

from .types import LLMProvider

# USD price per 1M tokens. Conservative defaults when unknown.
_OPENAI_PRICING_PER_1M: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}

_ANTHROPIC_PRICING_PER_1M: Final[dict[str, tuple[float, float]]] = {
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-7-sonnet-latest": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "claude-opus-4-5-20251101": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}

_GOOGLE_PRICING_PER_1M: Final[dict[str, tuple[float, float]]] = {
    "gemini-1.5-flash": (0.35, 1.05),
    "gemini-1.5-pro": (3.50, 10.50),
}


_ALL_PRICING: Final[dict[str, dict[str, tuple[float, float]]]] = {
    "openai": _OPENAI_PRICING_PER_1M,
    "anthropic": _ANTHROPIC_PRICING_PER_1M,
    "google": _GOOGLE_PRICING_PER_1M,
}


def estimate_cost_from_model(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Estimate cost auto-detecting provider from model name prefix."""
    if model.startswith("claude"):
        provider: LLMProvider = "anthropic"
    elif model.startswith("gpt"):
        provider = "openai"
    elif model.startswith("gemini"):
        provider = "google"
    else:
        return None
    return estimate_cost_usd(provider, model, input_tokens, output_tokens)


def estimate_cost_usd(
    provider: LLMProvider,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    """Estimate request cost in USD from token usage and model pricing."""

    if provider == "openai":
        price = _OPENAI_PRICING_PER_1M.get(model)
    elif provider == "anthropic":
        price = _ANTHROPIC_PRICING_PER_1M.get(model)
    elif provider == "google":
        price = _GOOGLE_PRICING_PER_1M.get(model)
    else:
        price = None

    if price is None:
        return None

    input_per_million, output_per_million = price
    return (prompt_tokens / 1_000_000 * input_per_million) + (
        completion_tokens / 1_000_000 * output_per_million
    )

