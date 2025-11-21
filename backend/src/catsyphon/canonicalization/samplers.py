"""Message sampling strategies for canonicalization."""

import logging
from dataclasses import dataclass
from typing import Any

from catsyphon.canonicalization.models import CanonicalConfig
from catsyphon.canonicalization.tokens import TokenCounter
from catsyphon.models.db import Epoch, Message

logger = logging.getLogger(__name__)


@dataclass
class SampledMessage:
    """Message with priority score for sampling."""

    message: Message
    priority: int  # Higher = more important
    reason: str  # Why this message was prioritized
    estimated_tokens: int


class SemanticSampler:
    """Sample messages based on semantic importance.

    Prioritizes:
    1. First and last messages (context)
    2. Messages with errors (failures/blockers)
    3. Messages with tool calls (actions taken)
    4. Messages with thinking content (reasoning)
    5. Epoch boundary messages (transitions)
    """

    # Priority levels
    PRIORITY_FIRST_LAST = 1000
    PRIORITY_ERROR = 900
    PRIORITY_TOOL_CALL = 800
    PRIORITY_THINKING = 700
    PRIORITY_EPOCH_BOUNDARY = 600
    PRIORITY_CODE_CHANGE = 500
    PRIORITY_NORMAL = 100

    def __init__(self, config: CanonicalConfig, token_counter: TokenCounter):
        """Initialize sampler.

        Args:
            config: Canonicalization configuration
            token_counter: Token counter for estimating message sizes
        """
        self.config = config
        self.token_counter = token_counter

    def sample(
        self,
        messages: list[Message],
        epochs: list[Epoch],
        token_budget: int,
    ) -> list[SampledMessage]:
        """Sample messages within token budget.

        Args:
            messages: All messages in conversation
            epochs: All epochs in conversation
            token_budget: Maximum tokens to use

        Returns:
            List of sampled messages with priority info
        """
        if not messages:
            return []

        # Assign priorities to all messages
        prioritized = self._prioritize_messages(messages, epochs)

        # Sort by priority (descending) and sequence (ascending for ties)
        prioritized.sort(key=lambda sm: (-sm.priority, sm.message.sequence))

        # Fit messages into budget
        sampled: list[SampledMessage] = []
        total_tokens = 0

        for sm in prioritized:
            if total_tokens + sm.estimated_tokens <= token_budget:
                sampled.append(sm)
                total_tokens += sm.estimated_tokens
            elif len(sampled) < 2:  # Always include at least 2 messages
                sampled.append(sm)
                total_tokens += sm.estimated_tokens

        # Re-sort by sequence for chronological order
        sampled.sort(key=lambda sm: sm.message.sequence)

        logger.info(
            f"Sampled {len(sampled)}/{len(messages)} messages "
            f"({total_tokens}/{token_budget} tokens)"
        )

        return sampled

    def _prioritize_messages(
        self, messages: list[Message], epochs: list[Epoch]
    ) -> list[SampledMessage]:
        """Assign priority scores to all messages."""
        prioritized: list[SampledMessage] = []
        epoch_boundaries = self._get_epoch_boundaries(messages, epochs)

        for i, msg in enumerate(messages):
            priority = self.PRIORITY_NORMAL
            reasons: list[str] = []

            # First/last messages (always include)
            if i == 0:
                priority = max(priority, self.PRIORITY_FIRST_LAST)
                reasons.append("first")
            elif i == len(messages) - 1:
                priority = max(priority, self.PRIORITY_FIRST_LAST)
                reasons.append("last")

            # Messages in configurable first/last N
            elif i < self.config.always_include_first_n:
                priority = max(priority, self.PRIORITY_FIRST_LAST - 100)
                reasons.append(f"first-{self.config.always_include_first_n}")
            elif i >= len(messages) - self.config.always_include_last_n:
                priority = max(priority, self.PRIORITY_FIRST_LAST - 100)
                reasons.append(f"last-{self.config.always_include_last_n}")

            # Error detection
            if self._has_error(msg):
                priority = max(priority, self.PRIORITY_ERROR)
                reasons.append("error")

            # Tool calls
            if msg.tool_calls:
                priority = max(priority, self.PRIORITY_TOOL_CALL)
                reasons.append(f"tools:{len(msg.tool_calls)}")

            # Thinking content
            if msg.thinking_content and self.config.include_thinking:
                priority = max(priority, self.PRIORITY_THINKING)
                reasons.append("thinking")

            # Code changes
            if msg.code_changes:
                priority = max(priority, self.PRIORITY_CODE_CHANGE)
                reasons.append(f"code:{len(msg.code_changes)}")

            # Epoch boundaries
            if msg.id in epoch_boundaries:
                priority = max(priority, self.PRIORITY_EPOCH_BOUNDARY)
                reasons.append("epoch-boundary")

            # Estimate token count
            estimated_tokens = self._estimate_message_tokens(msg)

            prioritized.append(
                SampledMessage(
                    message=msg,
                    priority=priority,
                    reason=", ".join(reasons) if reasons else "normal",
                    estimated_tokens=estimated_tokens,
                )
            )

        return prioritized

    def _get_epoch_boundaries(
        self, messages: list[Message], epochs: list[Epoch]
    ) -> set[Any]:
        """Get message IDs that are epoch boundaries."""
        boundaries = set()

        # Group messages by epoch
        epoch_messages: dict[Any, list[Message]] = {}
        for msg in messages:
            if msg.epoch_id not in epoch_messages:
                epoch_messages[msg.epoch_id] = []
            epoch_messages[msg.epoch_id].append(msg)

        # Find first and last message of each epoch
        for epoch_id, msgs in epoch_messages.items():
            if msgs:
                sorted_msgs = sorted(msgs, key=lambda m: m.sequence)
                boundaries.add(sorted_msgs[0].id)  # First
                if len(sorted_msgs) > 1:
                    boundaries.add(sorted_msgs[-1].id)  # Last

        return boundaries

    def _has_error(self, message: Message) -> bool:
        """Check if message contains error indicators."""
        content_lower = (message.content or "").lower()

        # Error keywords
        error_patterns = [
            "error",
            "exception",
            "failed",
            "failure",
            "traceback",
            "warning",
            "⚠️",
            "❌",
            "[error]",
            "[warning]",
        ]

        return any(pattern in content_lower for pattern in error_patterns)

    def _estimate_message_tokens(self, message: Message) -> int:
        """Estimate token count for a message."""
        tokens = 0

        # Role + timestamp structure
        tokens += 10

        # Content
        content = message.content or ""
        if len(content) > self.config.max_message_chars:
            content = content[: self.config.max_message_chars] + "..."
        tokens += self.token_counter.count(content)

        # Thinking content (if included)
        if message.thinking_content and self.config.include_thinking:
            thinking = message.thinking_content
            if len(thinking) > self.config.max_thinking_chars:
                thinking = thinking[: self.config.max_thinking_chars] + "..."
            tokens += self.token_counter.count(thinking)

        # Tool calls (if included)
        if message.tool_calls and self.config.include_tool_details:
            tokens += len(message.tool_calls) * 50  # Estimate per tool call

        # Code changes (if included)
        if message.code_changes and self.config.include_code_changes:
            tokens += len(message.code_changes) * 30  # Estimate per code change

        return tokens


class EpochSampler:
    """Sample messages based on epoch boundaries.

    Alternative sampling strategy that respects conversation structure.
    Includes full first and last epochs, summarizes middle epochs.
    """

    def __init__(self, config: CanonicalConfig, token_counter: TokenCounter):
        """Initialize epoch sampler.

        Args:
            config: Canonicalization configuration
            token_counter: Token counter for estimating sizes
        """
        self.config = config
        self.token_counter = token_counter

    def sample(
        self,
        messages: list[Message],
        epochs: list[Epoch],
        token_budget: int,
    ) -> list[SampledMessage]:
        """Sample messages by epoch.

        Args:
            messages: All messages in conversation
            epochs: All epochs in conversation
            token_budget: Maximum tokens to use

        Returns:
            List of sampled messages
        """
        if not messages or not epochs:
            return []

        # Group messages by epoch
        epoch_messages: dict[Any, list[Message]] = {}
        for msg in messages:
            if msg.epoch_id not in epoch_messages:
                epoch_messages[msg.epoch_id] = []
            epoch_messages[msg.epoch_id].append(msg)

        # Sort epochs by sequence
        sorted_epochs = sorted(epochs, key=lambda e: e.sequence)

        sampled: list[SampledMessage] = []
        total_tokens = 0

        # Always include first epoch fully
        if sorted_epochs:
            first_epoch_msgs = epoch_messages.get(sorted_epochs[0].id, [])
            for msg in sorted(first_epoch_msgs, key=lambda m: m.sequence):
                sm = SampledMessage(
                    message=msg,
                    priority=1000,
                    reason="first-epoch",
                    estimated_tokens=self._estimate_message_tokens(msg),
                )
                sampled.append(sm)
                total_tokens += sm.estimated_tokens

        # Always include last epoch fully
        if len(sorted_epochs) > 1:
            last_epoch_msgs = epoch_messages.get(sorted_epochs[-1].id, [])
            for msg in sorted(last_epoch_msgs, key=lambda m: m.sequence):
                sm = SampledMessage(
                    message=msg,
                    priority=1000,
                    reason="last-epoch",
                    estimated_tokens=self._estimate_message_tokens(msg),
                )
                sampled.append(sm)
                total_tokens += sm.estimated_tokens

        # Sample middle epochs if budget allows
        remaining_budget = token_budget - total_tokens
        middle_epochs = sorted_epochs[1:-1] if len(sorted_epochs) > 2 else []

        for epoch in middle_epochs:
            epoch_msgs = epoch_messages.get(epoch.id, [])
            if not epoch_msgs:
                continue

            # Include only key messages from middle epochs
            sorted_msgs = sorted(epoch_msgs, key=lambda m: m.sequence)
            for msg in sorted_msgs:
                if self._is_key_message(msg):
                    sm = SampledMessage(
                        message=msg,
                        priority=500,
                        reason="middle-epoch-key",
                        estimated_tokens=self._estimate_message_tokens(msg),
                    )

                    if total_tokens + sm.estimated_tokens <= token_budget:
                        sampled.append(sm)
                        total_tokens += sm.estimated_tokens

        # Re-sort by sequence
        sampled.sort(key=lambda sm: sm.message.sequence)

        logger.info(
            f"Epoch sampler: {len(sampled)}/{len(messages)} messages "
            f"({total_tokens}/{token_budget} tokens)"
        )

        return sampled

    def _is_key_message(self, message: Message) -> bool:
        """Check if message is key (error, tool call, thinking)."""
        if message.tool_calls:
            return True
        if message.thinking_content and self.config.include_thinking:
            return True
        if message.code_changes:
            return True

        content_lower = (message.content or "").lower()
        error_patterns = ["error", "exception", "failed", "failure"]
        return any(pattern in content_lower for pattern in error_patterns)

    def _estimate_message_tokens(self, message: Message) -> int:
        """Estimate token count for a message."""
        # Reuse SemanticSampler's estimation logic
        sampler = SemanticSampler(self.config, self.token_counter)
        return sampler._estimate_message_tokens(message)


class ChronologicalSampler:
    """Include all messages chronologically with unlimited token budget.

    This sampler produces a complete chronological log of EVERYTHING in a
    conversation - all messages, all tool calls, all thinking content, without
    any filtering or budget constraints.

    Use cases:
    - Large context models (Claude 3.5 with 200K context, GPT-4 Turbo)
    - Full conversation exports for archival/debugging
    - Analysis tools requiring complete context
    - Manual review and comprehensive logging

    Note: May produce very large outputs (50K-200K+ tokens for complex sessions).
    """

    def __init__(self, config: CanonicalConfig, token_counter: TokenCounter):
        """Initialize chronological sampler.

        Args:
            config: Canonicalization configuration
            token_counter: Token counter for tracking (budget not enforced)
        """
        self.config = config
        self.token_counter = token_counter

    def sample(
        self,
        messages: list[Message],
        epochs: list[Epoch],
        token_budget: int,
    ) -> list[SampledMessage]:
        """Include all messages chronologically.

        Args:
            messages: All messages in conversation
            epochs: All epochs in conversation (not used)
            token_budget: Token budget (not enforced, used for logging only)

        Returns:
            List of all messages as SampledMessage objects, chronologically sorted
        """
        if not messages:
            return []

        # Sort messages by sequence (should already be sorted, but ensure it)
        sorted_messages = sorted(messages, key=lambda m: m.sequence)

        sampled: list[SampledMessage] = []
        total_tokens = 0

        for msg in sorted_messages:
            estimated_tokens = self._estimate_message_tokens(msg)

            sampled.append(
                SampledMessage(
                    message=msg,
                    priority=1000,  # All messages equal priority
                    reason="chronological",
                    estimated_tokens=estimated_tokens,
                )
            )
            total_tokens += estimated_tokens

        # Log statistics (no budget enforcement)
        logger.info(
            f"Chronological sampler: included all {len(sampled)} messages "
            f"({total_tokens} tokens, budget was {token_budget})"
        )

        return sampled

    def _estimate_message_tokens(self, message: Message) -> int:
        """Estimate token count for a message."""
        # Reuse SemanticSampler's estimation logic
        sampler = SemanticSampler(self.config, self.token_counter)
        return sampler._estimate_message_tokens(message)
