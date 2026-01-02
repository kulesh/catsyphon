"""Timestamp normalization tests for collector session updates."""

from datetime import datetime, timedelta, timezone

from catsyphon.db.repositories.collector_session import (
    CollectorSessionRepository,
    _to_naive_utc,
)


def test_to_naive_utc_converts_timezone_aware():
    aware = datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    naive = _to_naive_utc(aware)

    assert naive.tzinfo is None
    assert naive == datetime(2026, 1, 2, 8, 0, 0)


def test_update_last_activity_handles_mixed_timezones(db_session, sample_conversation):
    repo = CollectorSessionRepository(db_session)

    sample_conversation.end_time = datetime(
        2026, 1, 2, 8, 0, 0, tzinfo=timezone.utc
    )
    event_timestamp = datetime(
        2026, 1, 2, 10, 0, 0, tzinfo=timezone(timedelta(hours=2))
    )

    repo.update_last_activity(sample_conversation, event_timestamp)

    assert sample_conversation.end_time.tzinfo is None
    assert sample_conversation.end_time == datetime(2026, 1, 2, 8, 0, 0)
