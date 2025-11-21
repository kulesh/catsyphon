"""Token counting and budget allocation for canonicalization."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import tiktoken for accurate OpenAI token counting
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning(
        "tiktoken not available - falling back to character-based estimation. "
        "Install with: pip install tiktoken"
    )


class TokenCounter:
    """Count tokens for different models with fallback estimation."""

    # Fallback: approximate chars-per-token ratios
    CHARS_PER_TOKEN = {
        "gpt-4o-mini": 4.0,
        "gpt-4o": 4.0,
        "gpt-4": 4.0,
        "claude-sonnet": 4.5,
        "default": 4.0,
    }

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize token counter for specific model.

        Args:
            model: Model name (e.g., "gpt-4o-mini", "gpt-4o")
        """
        self.model = model
        self.encoding: Optional[object] = None

        if TIKTOKEN_AVAILABLE:
            try:
                # Get encoding for model
                if "gpt-4o" in model:
                    self.encoding = tiktoken.encoding_for_model("gpt-4o")
                elif "gpt-4" in model:
                    self.encoding = tiktoken.encoding_for_model("gpt-4")
                else:
                    # Default to cl100k_base (used by GPT-4 family)
                    self.encoding = tiktoken.get_encoding("cl100k_base")

                logger.debug(f"Using tiktoken encoding for {model}")
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {e}")
                self.encoding = None

    def count(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens (exact with tiktoken, estimated otherwise)
        """
        if not text:
            return 0

        if self.encoding is not None:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"tiktoken encoding failed: {e}, falling back to estimation")

        # Fallback: character-based estimation
        chars_per_token = self.CHARS_PER_TOKEN.get(self.model, self.CHARS_PER_TOKEN["default"])
        return int(len(text) / chars_per_token)

    def truncate_to_budget(self, text: str, token_budget: int) -> tuple[str, int]:
        """Truncate text to fit within token budget.

        Args:
            text: Text to truncate
            token_budget: Maximum tokens allowed

        Returns:
            Tuple of (truncated_text, actual_token_count)
        """
        current_tokens = self.count(text)

        if current_tokens <= token_budget:
            return text, current_tokens

        # Binary search for truncation point
        if self.encoding is not None:
            try:
                # Encode and truncate at token level
                tokens = self.encoding.encode(text)
                truncated_tokens = tokens[:token_budget]
                truncated_text = self.encoding.decode(truncated_tokens)
                return truncated_text, len(truncated_tokens)
            except Exception as e:
                logger.warning(f"Token-level truncation failed: {e}")

        # Fallback: character-based truncation
        chars_per_token = self.CHARS_PER_TOKEN.get(self.model, self.CHARS_PER_TOKEN["default"])
        max_chars = int(token_budget * chars_per_token)
        truncated_text = text[:max_chars]
        return truncated_text, self.count(truncated_text)


class BudgetAllocator:
    """Allocate token budget across conversation components."""

    def __init__(self, total_budget: int):
        """Initialize budget allocator.

        Args:
            total_budget: Total token budget available
        """
        self.total_budget = total_budget
        self.allocations: dict[str, int] = {}
        self.spent: dict[str, int] = {}

    def allocate(self, component: str, percentage: float) -> int:
        """Allocate budget percentage to component.

        Args:
            component: Component name (e.g., "metadata", "main_messages", "children")
            percentage: Percentage of total budget (0.0 to 1.0)

        Returns:
            Allocated token count for component
        """
        if not 0.0 <= percentage <= 1.0:
            raise ValueError(f"Percentage must be 0.0-1.0, got {percentage}")

        allocation = int(self.total_budget * percentage)
        self.allocations[component] = allocation
        self.spent[component] = 0
        return allocation

    def spend(self, component: str, tokens: int) -> None:
        """Record tokens spent on component.

        Args:
            component: Component name
            tokens: Tokens spent
        """
        if component not in self.spent:
            self.spent[component] = 0
        self.spent[component] += tokens

    def remaining(self, component: str) -> int:
        """Get remaining budget for component.

        Args:
            component: Component name

        Returns:
            Remaining tokens in budget
        """
        allocated = self.allocations.get(component, 0)
        spent = self.spent.get(component, 0)
        return max(0, allocated - spent)

    def total_remaining(self) -> int:
        """Get total remaining budget across all components."""
        total_allocated = sum(self.allocations.values())
        total_spent = sum(self.spent.values())
        return max(0, total_allocated - total_spent)

    def summary(self) -> dict[str, dict[str, int]]:
        """Get budget allocation summary.

        Returns:
            Dictionary with allocation, spent, and remaining for each component
        """
        return {
            component: {
                "allocated": self.allocations.get(component, 0),
                "spent": self.spent.get(component, 0),
                "remaining": self.remaining(component),
            }
            for component in set(list(self.allocations.keys()) + list(self.spent.keys()))
        }
