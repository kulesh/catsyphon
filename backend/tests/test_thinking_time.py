from datetime import datetime, timedelta, timezone

from catsyphon.analytics.thinking_time import (
    aggregate_thinking_time,
    pair_user_assistant,
)


class DummyMessage:
    def __init__(
        self,
        role: str,
        ts: datetime,
        thinking_content=None,
        tool_calls=None,
    ):
        self.role = role
        self.timestamp = ts
        self.thinking_content = thinking_content
        self.tool_calls = tool_calls or []


def test_pairs_first_assistant_only():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    msgs = [
        DummyMessage("user", base),
        DummyMessage(
            "assistant", base + timedelta(seconds=3), thinking_content="thought"
        ),
        DummyMessage(
            "assistant", base + timedelta(seconds=5)
        ),  # should be ignored for pairing
    ]
    pairs = pair_user_assistant(msgs)
    assert len(pairs) == 1
    assert pairs[0].latency_seconds == 3
    assert pairs[0].has_thinking is True
    assert pairs[0].has_tool_call is False


def test_pairs_with_tool_calls():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    msgs = [
        DummyMessage("user", base),
        DummyMessage(
            "assistant", base + timedelta(seconds=7), tool_calls=[{"type": "tool_use"}]
        ),
    ]
    pairs = pair_user_assistant(msgs)
    assert len(pairs) == 1
    assert pairs[0].latency_seconds == 7
    assert pairs[0].has_tool_call is True
    assert pairs[0].has_thinking is False


def test_aggregate_percentiles_and_flags():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    msgs = [
        DummyMessage("user", base),
        DummyMessage("assistant", base + timedelta(seconds=4), thinking_content="x"),
        DummyMessage("user", base + timedelta(seconds=10)),
        DummyMessage(
            "assistant", base + timedelta(seconds=18), tool_calls=[{"type": "tool_use"}]
        ),
    ]
    pairs = pair_user_assistant(msgs)
    agg = aggregate_thinking_time(pairs)

    assert agg.pair_count == 2
    # latencies are [4, 8]
    assert agg.median_latency_seconds == 6.0  # midpoint between 4 and 8
    assert agg.p95_latency_seconds >= 8.0  # upper end for two-point set
    assert agg.max_latency_seconds == 8.0
    assert agg.pct_with_thinking == 0.5
    assert agg.pct_with_tool_calls == 0.5
