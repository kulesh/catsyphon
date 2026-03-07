"""Shared types for provider-agnostic LLM analytics clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LLMProvider = Literal["openai", "anthropic", "google", "unknown"]


@dataclass(frozen=True)
class LLMUsage:
    """Normalized usage metrics from an LLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response payload from an LLM provider."""

    content: str
    provider: LLMProvider
    model: str
    finish_reason: str
    usage: LLMUsage
    raw_response: Any | None = None

