"""Tests for session gap detection."""

from datetime import UTC, datetime, timedelta

from catsyphon.utils.gap_detection import detect_session_gaps


def _ts(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 1, day, hour, 0, 0, tzinfo=UTC)


def test_no_gaps_in_regular_sessions() -> None:
    timestamps = [_ts(d) for d in range(1, 11)]
    gaps = detect_session_gaps(timestamps)
    assert gaps == []


def test_detects_large_gap() -> None:
    timestamps = [_ts(d) for d in range(1, 11)]
    timestamps.append(_ts(25))
    gaps = detect_session_gaps(timestamps)
    assert len(gaps) == 1
    assert gaps[0].start == _ts(10)
    assert gaps[0].end == _ts(25)
    assert gaps[0].duration == timedelta(days=15)


def test_too_few_timestamps() -> None:
    assert detect_session_gaps([]) == []
    assert detect_session_gaps([_ts(1)]) == []
    assert detect_session_gaps([_ts(1), _ts(10)]) == []


def test_multiple_gaps() -> None:
    timestamps = [
        _ts(1), _ts(2), _ts(3), _ts(4), _ts(5),
        _ts(15),
        _ts(16), _ts(17), _ts(18),
        _ts(30),
    ]
    gaps = detect_session_gaps(timestamps)
    assert len(gaps) == 2
    assert gaps[0].start == _ts(5)
    assert gaps[0].end == _ts(15)
    assert gaps[1].start == _ts(18)
    assert gaps[1].end == _ts(30)


def test_custom_min_gap_days() -> None:
    timestamps = [_ts(d) for d in range(1, 11)]
    timestamps.append(_ts(15))
    gaps_default = detect_session_gaps(timestamps, min_gap_days=3.0)
    gaps_strict = detect_session_gaps(timestamps, min_gap_days=1.0)
    assert len(gaps_default) == 1
    assert len(gaps_strict) == 1


def test_unsorted_input() -> None:
    timestamps = [_ts(25), _ts(1), _ts(5), _ts(2), _ts(3), _ts(4)]
    gaps = detect_session_gaps(timestamps)
    assert len(gaps) == 1
    assert gaps[0].start == _ts(5)
    assert gaps[0].end == _ts(25)


def test_returns_median_interval() -> None:
    timestamps = [_ts(d) for d in range(1, 11)]
    timestamps.append(_ts(25))
    gaps = detect_session_gaps(timestamps)
    assert len(gaps) == 1
    assert gaps[0].median_interval == timedelta(days=1)
