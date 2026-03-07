"""Anthropic adapter implementing the provider-agnostic LLM protocol."""

from __future__ import annotations

from typing import Any

from catsyphon.llm.pricing import estimate_cost_usd
from catsyphon.llm.types import LLMResponse, LLMUsage


class AnthropicAnalyticsClient:
    """Anthropic implementation for analytics generation workloads."""

    provider = "anthropic"

    def __init__(self, api_key: str):
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for LLM_PROVIDER=anthropic. "
                "Install with: uv add anthropic"
            ) from exc

        self._client = Anthropic(api_key=api_key)

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._normalize_response(model=model, response=response)

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._normalize_response(model=model, response=response)

    def health_check(self, *, model: str) -> None:
        response = self._client.messages.create(
            model=model,
            messages=[{"role": "user", "content": "health-check"}],
            max_tokens=1,
        )
        if not response.content:
            raise RuntimeError("Anthropic health check returned no content")

    def _normalize_response(self, *, model: str, response: Any) -> LLMResponse:
        blocks = getattr(response, "content", None) or []
        text_parts: list[str] = []
        for block in blocks:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", "") or "")
        content = "".join(text_parts).strip()

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = prompt_tokens + completion_tokens
        resolved_model = str(getattr(response, "model", None) or model)

        return LLMResponse(
            content=content,
            provider="anthropic",
            model=resolved_model,
            finish_reason=str(getattr(response, "stop_reason", "unknown") or "unknown"),
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=estimate_cost_usd(
                    "anthropic",
                    resolved_model,
                    prompt_tokens,
                    completion_tokens,
                ),
            ),
            raw_response=response,
        )

