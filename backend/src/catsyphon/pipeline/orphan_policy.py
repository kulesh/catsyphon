"""Policy for marking orphaned agent conversations as permanently unresolvable.

An orphaned agent conversation is one whose parent_session_id references a
parent conversation that does not (yet) exist in the database.  A background
linking loop retries periodically.  This module defines the policy that
determines when retrying is futile and the orphan should be marked permanent.

Policy (hybrid):
  An orphan is permanent when BOTH conditions hold:
    1. _linking_attempts >= MAX_LINKING_ATTEMPTS  (default 10)
    2. _first_orphaned_at   older than MAX_ORPHAN_AGE_HOURS (default 24)

The hybrid avoids false positives during slow bulk imports (attempt-only would
fire too early) and stalled daemons (time-only would fire on restart).
"""

from __future__ import annotations

from datetime import datetime, timezone

# ── Policy constants ────────────────────────────────────────────────────────
MAX_LINKING_ATTEMPTS: int = 10
MAX_ORPHAN_AGE_HOURS: int = 24

# ── JSONB keys stored in agent_metadata / extra_data ────────────────────────
KEY_LINKING_ATTEMPTS = "_linking_attempts"
KEY_FIRST_ORPHANED_AT = "_first_orphaned_at"


def record_failed_attempt(metadata: dict) -> dict:
    """Return a *new* dict with an incremented attempt counter.

    On the first call, ``_first_orphaned_at`` is stamped with the current UTC
    time.  Callers must assign the return value back to the ORM attribute so
    SQLAlchemy detects the JSONB mutation.
    """
    updated = {**metadata}
    updated[KEY_LINKING_ATTEMPTS] = updated.get(KEY_LINKING_ATTEMPTS, 0) + 1
    if KEY_FIRST_ORPHANED_AT not in updated:
        updated[KEY_FIRST_ORPHANED_AT] = datetime.now(timezone.utc).isoformat()
    return updated


def should_mark_permanent(
    metadata: dict,
    *,
    max_attempts: int = MAX_LINKING_ATTEMPTS,
    max_age_hours: int = MAX_ORPHAN_AGE_HOURS,
) -> bool:
    """Return True when the orphan should be marked permanently unresolvable."""
    attempts = metadata.get(KEY_LINKING_ATTEMPTS, 0)
    if attempts < max_attempts:
        return False

    first_orphaned_raw = metadata.get(KEY_FIRST_ORPHANED_AT)
    if not first_orphaned_raw:
        return False

    try:
        first_orphaned = datetime.fromisoformat(first_orphaned_raw)
        if first_orphaned.tzinfo is None:
            first_orphaned = first_orphaned.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False

    age_hours = (datetime.now(timezone.utc) - first_orphaned).total_seconds() / 3600
    return age_hours >= max_age_hours
