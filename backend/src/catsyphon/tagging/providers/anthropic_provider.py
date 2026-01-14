"""Anthropic LLM provider implementation."""

import logging
import time
from typing import Any

from anthropic import Anthropic

from catsyphon.tagging.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (as of late 2024/2025)
ANTHROPIC_PRICING = {
    # Claude 4.5 family (structured outputs supported)
    "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-1-20250410": {"input": 15.00, "output": 75.00},
    # Claude 3.5 family (use tool_use for structured output)
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    # Default fallback
    "default": {"input": 3.00, "output": 15.00},
}

# Models that support native structured outputs (beta feature)
STRUCTURED_OUTPUT_MODELS = {
    "claude-sonnet-4-5-20250514",
    "claude-sonnet-4-5",
    "claude-opus-4-1-20250410",
    "claude-opus-4-1",
    # Haiku 4.5 expected soon
}

# Beta header for structured outputs
STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"


class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider using the Anthropic Python SDK.

    Supports two methods for structured JSON output:
    1. Native structured outputs (beta) for Claude 4.5+ models
    2. Prompt-based JSON extraction for older models
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250514",
    ):
        """Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-sonnet-4-5-20250514)
        """
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=api_key)
        self._model = model
        self._supports_structured = self._check_structured_support(model)
        logger.info(
            f"Initialized Anthropic provider with model: {model} "
            f"(structured outputs: {self._supports_structured})"
        )

    def _check_structured_support(self, model: str) -> bool:
        """Check if model supports native structured outputs.

        Args:
            model: Model identifier

        Returns:
            True if model supports structured outputs beta
        """
        # Check exact match or prefix match for versioned models
        if model in STRUCTURED_OUTPUT_MODELS:
            return True

        # Check if it's a versioned variant of a supported model
        for supported in STRUCTURED_OUTPUT_MODELS:
            if model.startswith(supported.rsplit("-", 1)[0]):
                return True

        return False

    @property
    def provider_name(self) -> str:
        """Return 'anthropic' as the provider identifier."""
        return "anthropic"

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
        """Generate a completion using Anthropic's API.

        Uses native structured outputs for Claude 4.5+ models, or
        enhanced prompt instructions for older models.

        Args:
            system_prompt: System message setting the context
            user_prompt: User message with the request
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            json_schema: Optional JSON schema for structured output

        Returns:
            LLMResponse with completion and metadata

        Raises:
            Exception: Anthropic API errors
        """
        start_time = time.time()

        # Build base request
        request_params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        # Use structured outputs if supported and schema provided
        if json_schema is not None and self._supports_structured:
            return self._complete_with_structured_output(
                request_params, json_schema, start_time
            )
        elif json_schema is not None:
            # Fall back to prompt-based JSON for older models
            return self._complete_with_prompt_json(
                request_params, json_schema, start_time
            )
        else:
            # No schema, just make a regular completion
            return self._complete_regular(request_params, start_time)

    def _complete_with_structured_output(
        self,
        request_params: dict[str, Any],
        json_schema: dict[str, Any],
        start_time: float,
    ) -> LLMResponse:
        """Complete using native structured outputs (beta).

        Args:
            request_params: Base request parameters
            json_schema: JSON schema for output format
            start_time: Request start time for duration calculation

        Returns:
            LLMResponse with structured output
        """
        # Add structured output format
        request_params["betas"] = [STRUCTURED_OUTPUTS_BETA]
        request_params["output_format"] = {
            "type": "json_schema",
            "json_schema": json_schema,
        }

        # Use beta endpoint
        response = self.client.beta.messages.create(**request_params)
        duration_ms = (time.time() - start_time) * 1000

        return self._build_response(response, duration_ms)

    def _complete_with_prompt_json(
        self,
        request_params: dict[str, Any],
        json_schema: dict[str, Any],
        start_time: float,
    ) -> LLMResponse:
        """Complete using prompt-based JSON instructions.

        For models that don't support native structured outputs,
        we enhance the system prompt with strict JSON instructions.

        Args:
            request_params: Base request parameters
            json_schema: JSON schema (used for documentation in prompt)
            start_time: Request start time

        Returns:
            LLMResponse with JSON content
        """
        # Enhance system prompt with JSON instructions
        json_instruction = (
            "\n\nIMPORTANT: You must respond with valid JSON only. "
            "No markdown code blocks, no explanations, no additional text. "
            "Return ONLY the raw JSON object."
        )
        request_params["system"] = request_params["system"] + json_instruction

        # Make regular API call
        response = self.client.messages.create(**request_params)
        duration_ms = (time.time() - start_time) * 1000

        return self._build_response(response, duration_ms)

    def _complete_regular(
        self,
        request_params: dict[str, Any],
        start_time: float,
    ) -> LLMResponse:
        """Complete without JSON formatting requirements.

        Args:
            request_params: Request parameters
            start_time: Request start time

        Returns:
            LLMResponse with completion
        """
        response = self.client.messages.create(**request_params)
        duration_ms = (time.time() - start_time) * 1000

        return self._build_response(response, duration_ms)

    def _build_response(self, response: Any, duration_ms: float) -> LLMResponse:
        """Build LLMResponse from Anthropic API response.

        Args:
            response: Anthropic API response
            duration_ms: Request duration in milliseconds

        Returns:
            Standardized LLMResponse
        """
        # Extract text content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # Extract usage metrics
        usage = response.usage
        prompt_tokens = usage.input_tokens if usage else 0
        completion_tokens = usage.output_tokens if usage else 0
        total_tokens = prompt_tokens + completion_tokens

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=response.stop_reason or "unknown",
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
        # Try exact model match first
        pricing = ANTHROPIC_PRICING.get(self._model)

        # Fall back to prefix matching for versioned models
        if pricing is None:
            for model_key, model_pricing in ANTHROPIC_PRICING.items():
                if model_key != "default" and self._model.startswith(
                    model_key.rsplit("-", 1)[0]
                ):
                    pricing = model_pricing
                    break

        # Use default if no match found
        if pricing is None:
            pricing = ANTHROPIC_PRICING["default"]

        # Convert from per-million to per-token
        input_cost = prompt_tokens * (pricing["input"] / 1_000_000)
        output_cost = completion_tokens * (pricing["output"] / 1_000_000)

        return input_cost + output_cost
