"""Session gap detection.

Identifies suspicious gaps in ingested session timelines that may
indicate deleted log files (e.g. Claude Code's cleanupPeriodDays).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence


@dataclass
class SessionGap:
    """A gap between sessions that exceeds the expected interval."""

    start: datetime
    end: datetime
    duration: timedelta
    median_interval: timedelta


def detect_session_gaps(
    timestamps: Sequence[datetime],
    min_gap_days: float = 3.0,
    multiplier: float = 5.0,
) -> list[SessionGap]:
    """Find suspicious gaps in a series of session timestamps.

    A gap is suspicious when it exceeds both ``min_gap_days`` and
    ``multiplier`` times the median interval between sessions.

    Args:
        timestamps: Session start times (need not be sorted).
        min_gap_days: Minimum absolute gap size to flag.
        multiplier: A gap must also be this many times the median interval.

    Returns:
        List of detected gaps, sorted chronologically.
    """
    if len(timestamps) < 3:
        return []

    sorted_ts = sorted(timestamps)
    intervals = [
        (sorted_ts[i + 1] - sorted_ts[i])
        for i in range(len(sorted_ts) - 1)
    ]

    sorted_intervals = sorted(intervals)
    mid = len(sorted_intervals) // 2
    if len(sorted_intervals) % 2 == 0:
        median = (sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2
    else:
        median = sorted_intervals[mid]

    min_gap = timedelta(days=min_gap_days)
    threshold = max(min_gap, median * multiplier)

    gaps: list[SessionGap] = []
    for i, interval in enumerate(intervals):
        if interval >= threshold:
            gaps.append(SessionGap(
                start=sorted_ts[i],
                end=sorted_ts[i + 1],
                duration=interval,
                median_interval=median,
            ))

    return gaps
