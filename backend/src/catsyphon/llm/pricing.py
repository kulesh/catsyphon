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
}

_GOOGLE_PRICING_PER_1M: Final[dict[str, tuple[float, float]]] = {
    "gemini-1.5-flash": (0.35, 1.05),
    "gemini-1.5-pro": (3.50, 10.50),
}


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

