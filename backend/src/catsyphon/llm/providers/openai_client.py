"""OpenAI adapter implementing the provider-agnostic LLM protocol."""

from __future__ import annotations

from typing import Any

from catsyphon.llm.pricing import estimate_cost_usd
from catsyphon.llm.types import LLMResponse, LLMUsage


class OpenAIAnalyticsClient:
    """OpenAI implementation for analytics generation workloads."""

    provider = "openai"

    def __init__(self, api_key: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
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
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._normalize_response(model=model, response=response)

    def health_check(self, *, model: str) -> None:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "health-check"}],
            max_tokens=1,
        )
        if not response.choices:
            raise RuntimeError("OpenAI health check returned no choices")

    def _normalize_response(self, *, model: str, response: Any) -> LLMResponse:
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens
        finish_reason = response.choices[0].finish_reason if response.choices else ""
        content = response.choices[0].message.content if response.choices else ""
        resolved_model = response.model or model

        return LLMResponse(
            content=content or "",
            provider="openai",
            model=resolved_model,
            finish_reason=finish_reason or "unknown",
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=estimate_cost_usd(
                    "openai",
                    resolved_model,
                    prompt_tokens,
                    completion_tokens,
                ),
            ),
            raw_response=response,
        )

