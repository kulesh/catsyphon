"""Provider-agnostic protocol for LLM analytics clients."""

from __future__ import annotations

from typing import Protocol

from .types import LLMResponse


class LLMClient(Protocol):
    """Protocol implemented by all LLM provider adapters."""

    provider: str

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate structured JSON output."""

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate free-form text output."""

    def health_check(self, *, model: str) -> None:
        """Validate API key and model accessibility."""

