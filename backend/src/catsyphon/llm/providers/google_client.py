"""Google Gemini adapter implementing the provider-agnostic LLM protocol."""

from __future__ import annotations

from typing import Any

from catsyphon.llm.pricing import estimate_cost_usd
from catsyphon.llm.types import LLMResponse, LLMUsage


class GoogleAnalyticsClient:
    """Google implementation for analytics generation workloads."""

    provider = "google"

    def __init__(self, api_key: str):
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package is required for LLM_PROVIDER=google. "
                "Install with: uv add google-genai"
            ) from exc

        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        config = self._genai.types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            system_instruction=system_prompt,
        )
        response = self._client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
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
        config = self._genai.types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt,
        )
        response = self._client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
        )
        return self._normalize_response(model=model, response=response)

    def health_check(self, *, model: str) -> None:
        response = self._client.models.generate_content(
            model=model,
            contents="health-check",
            config=self._genai.types.GenerateContentConfig(max_output_tokens=1),
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Google health check returned no text")

    def _normalize_response(self, *, model: str, response: Any) -> LLMResponse:
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or 0
        )
        resolved_model = str(getattr(response, "model_version", None) or model)

        finish_reason = "unknown"
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "unknown"))

        return LLMResponse(
            content=str(getattr(response, "text", "") or ""),
            provider="google",
            model=resolved_model,
            finish_reason=finish_reason,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=estimate_cost_usd(
                    "google",
                    resolved_model,
                    prompt_tokens,
                    completion_tokens,
                ),
            ),
            raw_response=response,
        )

