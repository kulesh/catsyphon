"""OpenAI LLM provider implementation."""

import logging
import time
from typing import Any

from openai import OpenAI

from catsyphon.tagging.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (as of late 2024)
OPENAI_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # Default fallback for unknown models
    "default": {"input": 0.15, "output": 0.60},
}


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using the OpenAI Python SDK.

    Supports JSON mode via response_format parameter for structured outputs.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
    ):
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4o-mini)
        """
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=api_key)
        self._model = model
        logger.info(f"Initialized OpenAI provider with model: {model}")

    @property
    def provider_name(self) -> str:
        """Return 'openai' as the provider identifier."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the model identifier."""
        return self._model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate a completion using OpenAI's API.

        Args:
            system_prompt: System message setting the context
            user_prompt: User message with the request
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            json_schema: Optional JSON schema (uses JSON mode if provided)

        Returns:
            LLMResponse with completion and metadata

        Raises:
            Exception: OpenAI API errors
        """
        start_time = time.time()

        # Build request parameters
        request_params: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Enable JSON mode if schema is provided
        # OpenAI's JSON mode ensures valid JSON output
        if json_schema is not None:
            request_params["response_format"] = {"type": "json_object"}

        # Make API call
        response = self.client.chat.completions.create(**request_params)
        duration_ms = (time.time() - start_time) * 1000

        # Extract content
        content = response.choices[0].message.content or ""

        # Extract usage metrics
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=response.choices[0].finish_reason or "unknown",
            model=response.model,
            duration_ms=duration_ms,
            raw_response=response,
        )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on token usage.

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = OPENAI_PRICING.get(self._model, OPENAI_PRICING["default"])

        # Convert from per-million to per-token
        input_cost = prompt_tokens * (pricing["input"] / 1_000_000)
        output_cost = completion_tokens * (pricing["output"] / 1_000_000)

        return input_cost + output_cost
