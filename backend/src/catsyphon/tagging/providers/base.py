"""Base protocol and types for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standardized response from LLM providers.

    Attributes:
        content: The generated text content (should be valid JSON for tagging)
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
        finish_reason: Why generation stopped (stop, length, error, etc.)
        model: The actual model used (may differ from requested)
        duration_ms: Time taken for the API call in milliseconds
        raw_response: Provider-specific raw response for debugging
    """

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    model: str
    duration_ms: float
    raw_response: Any = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Implementations must handle:
    - API client initialization
    - Structured JSON output (using provider-specific mechanisms)
    - Token counting and cost calculation
    - Error handling with appropriate exceptions
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'openai', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier being used."""
        ...

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            system_prompt: System message setting the context
            user_prompt: User message with the actual request
            max_tokens: Maximum tokens in the response
            temperature: Sampling temperature (0.0-1.0)
            json_schema: Optional JSON schema for structured output

        Returns:
            LLMResponse with the completion and metadata

        Raises:
            Exception: Provider-specific errors should be caught and re-raised
                with meaningful context
        """
        ...

    @abstractmethod
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate the cost in USD for the given token usage.

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        ...
