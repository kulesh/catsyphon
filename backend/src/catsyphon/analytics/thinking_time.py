"""
Thinking-time aggregation helpers.

Approximate "thinking time" as the latency between a user message and the first
assistant message that follows it. We also capture whether the assistant
message contained thinking_content or tool_calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from catsyphon.models.db import Message


@dataclass
class ThinkingPair:
    """A single user→assistant pair with derived metadata."""

    latency_seconds: float
    has_thinking: bool
    has_tool_call: bool


@dataclass
class ThinkingTimeAggregate:
    """Aggregate stats over many user→assistant pairs."""

    pair_count: int
    median_latency_seconds: Optional[float]
    p95_latency_seconds: Optional[float]
    max_latency_seconds: Optional[float]
    pct_with_thinking: Optional[float]
    pct_with_tool_calls: Optional[float]


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Compute a percentile from a pre-sorted list (0-100 inclusive)."""
    if not sorted_values:
        raise ValueError("Cannot compute percentile of empty list")
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def pair_user_assistant(messages: Iterable[Message]) -> List[ThinkingPair]:
    """
    Pair each user message with the first following assistant message.

    Args:
        messages: Iterable of Message objects (order does not matter; will be sorted).

    Returns:
        List of ThinkingPair instances.
    """
    # Sort by timestamp to ensure correct ordering
    sorted_msgs = sorted(messages, key=lambda m: m.timestamp)
    pairs: List[ThinkingPair] = []
    last_user: Optional[Message] = None

    for msg in sorted_msgs:
        if msg.role == "user":
            last_user = msg
        elif msg.role == "assistant" and last_user is not None:
            latency = (msg.timestamp - last_user.timestamp).total_seconds()
            has_thinking = bool(getattr(msg, "thinking_content", None))
            tool_calls = getattr(msg, "tool_calls", None) or []
            pairs.append(
                ThinkingPair(
                    latency_seconds=latency,
                    has_thinking=has_thinking,
                    has_tool_call=bool(tool_calls),
                )
            )
            # Only pair the first assistant after the user
            last_user = None

    return pairs


def aggregate_thinking_time(
    pairs: List[ThinkingPair],
    max_latency_seconds: Optional[float] = None,
) -> ThinkingTimeAggregate:
    """
    Aggregate thinking-time metrics from user→assistant pairs.

    Args:
        pairs: List of ThinkingPair objects.
        max_latency_seconds: Optional cap to reduce outlier skew.

    Returns:
        ThinkingTimeAggregate with latency distribution and flag percentages.
    """
    if not pairs:
        return ThinkingTimeAggregate(
            pair_count=0,
            median_latency_seconds=None,
            p95_latency_seconds=None,
            max_latency_seconds=None,
            pct_with_thinking=None,
            pct_with_tool_calls=None,
        )

    latencies = sorted(
        (
            min(p.latency_seconds, max_latency_seconds)
            if max_latency_seconds is not None
            else p.latency_seconds
        )
        for p in pairs
    )
    thinking_count = sum(1 for p in pairs if p.has_thinking)
    tool_count = sum(1 for p in pairs if p.has_tool_call)
    pair_count = len(pairs)

    median = _percentile(latencies, 50)
    p95 = latencies[-1] if pair_count <= 2 else _percentile(latencies, 95)
    max_latency = latencies[-1]

    pct_thinking = thinking_count / pair_count if pair_count else None
    pct_tool = tool_count / pair_count if pair_count else None

    return ThinkingTimeAggregate(
        pair_count=pair_count,
        median_latency_seconds=median,
        p95_latency_seconds=p95,
        max_latency_seconds=max_latency,
        pct_with_thinking=pct_thinking,
        pct_with_tool_calls=pct_tool,
    )
