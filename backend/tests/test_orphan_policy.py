"""Tests for the permanent-orphan policy module."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from catsyphon.pipeline.orphan_policy import (
    KEY_FIRST_ORPHANED_AT,
    KEY_LINKING_ATTEMPTS,
    MAX_LINKING_ATTEMPTS,
    MAX_ORPHAN_AGE_HOURS,
    record_failed_attempt,
    should_mark_permanent,
)


class TestRecordFailedAttempt:
    def test_initializes_on_first_call(self):
        result = record_failed_attempt({})
        assert result[KEY_LINKING_ATTEMPTS] == 1
        assert KEY_FIRST_ORPHANED_AT in result

    def test_increments_counter(self):
        meta = {KEY_LINKING_ATTEMPTS: 5, KEY_FIRST_ORPHANED_AT: "2026-01-01T00:00:00+00:00"}
        result = record_failed_attempt(meta)
        assert result[KEY_LINKING_ATTEMPTS] == 6

    def test_preserves_first_orphaned_at(self):
        ts = "2026-01-01T00:00:00+00:00"
        meta = {KEY_LINKING_ATTEMPTS: 1, KEY_FIRST_ORPHANED_AT: ts}
        result = record_failed_attempt(meta)
        assert result[KEY_FIRST_ORPHANED_AT] == ts

    def test_preserves_other_keys(self):
        meta = {"parent_session_id": "abc-123", "some_flag": True}
        result = record_failed_attempt(meta)
        assert result["parent_session_id"] == "abc-123"
        assert result["some_flag"] is True

    def test_returns_new_dict(self):
        meta = {"existing": "data"}
        result = record_failed_attempt(meta)
        assert result is not meta


class TestShouldMarkPermanent:
    def _make_metadata(self, attempts: int, hours_ago: float) -> dict:
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            KEY_LINKING_ATTEMPTS: attempts,
            KEY_FIRST_ORPHANED_AT: ts.isoformat(),
        }

    def test_both_conditions_met(self):
        meta = self._make_metadata(MAX_LINKING_ATTEMPTS, MAX_ORPHAN_AGE_HOURS + 1)
        assert should_mark_permanent(meta) is True

    def test_attempts_only_not_sufficient(self):
        meta = self._make_metadata(MAX_LINKING_ATTEMPTS, 1)
        assert should_mark_permanent(meta) is False

    def test_time_only_not_sufficient(self):
        meta = self._make_metadata(1, MAX_ORPHAN_AGE_HOURS + 1)
        assert should_mark_permanent(meta) is False

    def test_neither_condition_met(self):
        meta = self._make_metadata(1, 1)
        assert should_mark_permanent(meta) is False

    def test_empty_metadata(self):
        assert should_mark_permanent({}) is False

    def test_missing_first_orphaned_at(self):
        meta = {KEY_LINKING_ATTEMPTS: 100}
        assert should_mark_permanent(meta) is False

    def test_malformed_timestamp(self):
        meta = {KEY_LINKING_ATTEMPTS: 100, KEY_FIRST_ORPHANED_AT: "not-a-date"}
        assert should_mark_permanent(meta) is False

    def test_custom_thresholds(self):
        meta = self._make_metadata(3, 2)
        assert should_mark_permanent(meta, max_attempts=3, max_age_hours=1) is True
        assert should_mark_permanent(meta, max_attempts=3, max_age_hours=3) is False
        assert should_mark_permanent(meta, max_attempts=4, max_age_hours=1) is False

    def test_naive_timestamp_treated_as_utc(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(tzinfo=None)
        meta = {
            KEY_LINKING_ATTEMPTS: MAX_LINKING_ATTEMPTS,
            KEY_FIRST_ORPHANED_AT: ts.isoformat(),
        }
        assert should_mark_permanent(meta) is True

    def test_exact_boundary_not_permanent(self):
        """At exactly the threshold, age_hours == max — should be permanent (>=)."""
        now = datetime.now(timezone.utc)
        ts = now - timedelta(hours=MAX_ORPHAN_AGE_HOURS)
        meta = {
            KEY_LINKING_ATTEMPTS: MAX_LINKING_ATTEMPTS,
            KEY_FIRST_ORPHANED_AT: ts.isoformat(),
        }
        # At exact boundary, >= means True
        assert should_mark_permanent(meta) is True
