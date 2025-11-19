#!/usr/bin/env python3
"""
Backfill conversation.success field from tags.outcome field.

This script updates existing conversations to set the success boolean field
based on the outcome tag value:
- outcome="success" → success=True
- outcome="failed" → success=False
- outcome="partial" → success=False (partial success counts as failure for metrics)
- outcome="unknown" or "abandoned" → success=None (no outcome)
"""

from catsyphon.db.connection import db_session
from catsyphon.models.db import Conversation
from sqlalchemy import select, update


def main():
    """Backfill success field from tags.outcome."""
    with db_session() as db:
        # Get all conversations
        conversations = db.execute(select(Conversation)).scalars().all()

        print(f"Found {len(conversations)} conversations")

        updated_success = 0
        updated_failed = 0
        updated_null = 0
        no_change = 0

        for conv in conversations:
            if not conv.tags or "outcome" not in conv.tags:
                continue

            outcome = conv.tags["outcome"]
            new_success_value = None

            if outcome == "success":
                new_success_value = True
            elif outcome in ("failed", "partial"):
                new_success_value = False
            elif outcome in ("unknown", "abandoned"):
                new_success_value = None

            # Only update if value changed
            if new_success_value != conv.success:
                conv.success = new_success_value
                if new_success_value is True:
                    updated_success += 1
                elif new_success_value is False:
                    updated_failed += 1
                else:
                    updated_null += 1
            else:
                no_change += 1

        # Commit changes
        db.commit()

        print(f"\nResults:")
        print(f"  Updated to success=True: {updated_success}")
        print(f"  Updated to success=False: {updated_failed}")
        print(f"  Updated to success=None: {updated_null}")
        print(f"  No change needed: {no_change}")
        print(f"  Total updated: {updated_success + updated_failed + updated_null}")


if __name__ == "__main__":
    main()
