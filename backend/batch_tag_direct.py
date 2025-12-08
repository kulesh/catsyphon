#!/usr/bin/env python3
"""
Direct batch tagging script - bypasses API to avoid timeout issues.
Directly queries database and calls tagging pipeline.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import text

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.tagging import TaggingPipeline


def get_untagged_conversations(session):
    """Get all conversation IDs that need tagging."""
    result = session.execute(
        text(
            """
            SELECT id, message_count
            FROM conversations
            WHERE tags::text = '{}'
            AND message_count >= 2
            ORDER BY created_at DESC
        """
        )
    )
    return [(row[0], row[1]) for row in result]


def get_conversation_messages(session, conv_id):
    """Get all messages for a conversation."""
    result = session.execute(
        text(
            """
            SELECT role, content, timestamp, thinking_content
            FROM messages
            WHERE conversation_id = :conv_id
            ORDER BY sequence ASC
        """
        ),
        {"conv_id": str(conv_id)},
    )
    return list(result)


def get_conversation_details(session, conv_id):
    """Get conversation metadata."""
    result = session.execute(
        text(
            """
            SELECT agent_type, agent_version, start_time, end_time, metadata
            FROM conversations
            WHERE id = :conv_id
        """
        ),
        {"conv_id": str(conv_id)},
    )
    return result.fetchone()


def update_conversation_tags(session, conv_id, tags):
    """Update conversation with tags."""
    import json

    tags_json = json.dumps(tags)
    session.execute(
        text(
            """
            UPDATE conversations
            SET tags = cast(:tags as jsonb)
            WHERE id = cast(:conv_id as uuid)
        """
        ),
        {"conv_id": str(conv_id), "tags": tags_json},
    )
    session.commit()


def main():
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in environment")
        sys.exit(1)

    print("Initializing tagging pipeline...")
    pipeline = TaggingPipeline(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        cache_dir=Path(settings.tagging_cache_dir),
        cache_ttl_days=settings.tagging_cache_ttl_days,
        enable_cache=settings.tagging_enable_cache,
    )

    with db_session() as session:
        untagged = get_untagged_conversations(session)
        total = len(untagged)
        print(f"Found {total} untagged conversations with 2+ messages\n")

        if total == 0:
            print("No conversations to tag.")
            return

        successful = 0
        failed = 0

        for i, (conv_id, msg_count) in enumerate(untagged, 1):
            print(
                f"[{i}/{total}] Tagging {conv_id} ({msg_count} msgs)... ",
                end="",
                flush=True,
            )

            try:
                start_time = time.time()

                # Get conversation details
                conv_details = get_conversation_details(session, conv_id)
                if not conv_details:
                    print("SKIP (not found)")
                    continue

                # Get messages
                messages = get_conversation_messages(session, conv_id)
                if len(messages) < 2:
                    print("SKIP (too few messages)")
                    continue

                # Build ParsedConversation
                parsed_messages = [
                    ParsedMessage(
                        role=msg[0],
                        content=msg[1] or "",
                        timestamp=msg[2],
                        thinking_content=msg[3],
                    )
                    for msg in messages
                ]

                metadata = conv_details[4] if conv_details[4] else {}
                parsed = ParsedConversation(
                    agent_type=conv_details[0],
                    agent_version=conv_details[1],
                    start_time=conv_details[2],
                    end_time=conv_details[3],
                    messages=parsed_messages,
                    session_id=metadata.get("session_id"),
                    git_branch=metadata.get("git_branch"),
                    working_directory=metadata.get("working_directory"),
                    metadata=metadata,
                )

                # Run tagging
                tags, llm_metrics = pipeline.tag_conversation(parsed)

                # Update database
                update_conversation_tags(session, conv_id, tags)

                elapsed = time.time() - start_time
                intent = tags.get("intent")
                sentiment = tags.get("sentiment")
                print(f"OK ({elapsed:.1f}s) intent={intent}, sentiment={sentiment}")
                successful += 1

            except Exception as e:
                print(f"FAILED: {e}")
                failed += 1
                continue

        print("\n=== Summary ===")
        print(f"Total: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
