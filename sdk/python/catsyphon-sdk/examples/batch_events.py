#!/usr/bin/env python3
"""
Example: Batch Event Writing with CatSyphon SDK

This example demonstrates the BatchWriter for high-throughput event logging
with automatic batching and time-based flushing.

Useful for:
- Processing existing log files
- High-frequency event streams
- Custom event types
"""

import os
import time
import uuid
from datetime import datetime, timezone

from catsyphon_sdk import (
    BatchWriter,
    CollectorClient,
    Event,
    EventType,
    MessageData,
    SessionStartData,
)


def batch_import_example():
    """Import events in batches with automatic flushing."""

    SERVER_URL = os.environ.get("CATSYPHON_URL", "http://localhost:8000")
    WORKSPACE_ID = os.environ.get("CATSYPHON_WORKSPACE_ID", "")

    client = CollectorClient.from_stored(SERVER_URL, WORKSPACE_ID)
    if client is None:
        print("No stored credentials. Please register first.")
        return

    session_id = f"batch-{uuid.uuid4().hex[:8]}"
    print(f"Starting batch import: {session_id}")

    # BatchWriter automatically flushes:
    # - Every 10 events (batch_size)
    # - Every 5 seconds (flush_interval)
    # - On context exit
    with BatchWriter(
        client,
        session_id,
        batch_size=10,
        flush_interval=5.0,
    ) as writer:
        # Add session start
        writer.add_raw(
            event_type=EventType.SESSION_START,
            data={
                "agent_type": "batch-importer",
                "agent_version": "1.0.0",
            },
        )

        # Simulate importing many events
        for i in range(25):
            writer.add_raw(
                event_type=EventType.MESSAGE,
                data={
                    "author_role": "human" if i % 2 == 0 else "assistant",
                    "message_type": "prompt" if i % 2 == 0 else "response",
                    "content": f"Message {i + 1}",
                },
            )

            # Show progress
            if (i + 1) % 10 == 0:
                print(f"  Added {i + 1} events, pending: {writer.pending_count}")

        # Add session end
        writer.add_raw(
            event_type=EventType.SESSION_END,
            data={
                "outcome": "success",
                "total_messages": 25,
            },
        )

    print(f"Batch import completed: {session_id}")


def time_based_flush_example():
    """Demonstrate time-based flushing for real-time streaming."""

    SERVER_URL = os.environ.get("CATSYPHON_URL", "http://localhost:8000")
    WORKSPACE_ID = os.environ.get("CATSYPHON_WORKSPACE_ID", "")

    client = CollectorClient.from_stored(SERVER_URL, WORKSPACE_ID)
    if client is None:
        print("No stored credentials. Please register first.")
        return

    session_id = f"stream-{uuid.uuid4().hex[:8]}"
    print(f"Starting stream: {session_id}")
    print("(Events will auto-flush every 2 seconds)")

    with BatchWriter(
        client,
        session_id,
        batch_size=100,  # High batch size
        flush_interval=2.0,  # But flush every 2 seconds
    ) as writer:
        writer.add_raw(
            event_type=EventType.SESSION_START,
            data={"agent_type": "streamer"},
        )

        # Simulate slow event stream
        for i in range(5):
            writer.add_raw(
                event_type=EventType.MESSAGE,
                data={
                    "author_role": "assistant",
                    "message_type": "response",
                    "content": f"Streaming message {i + 1}",
                },
            )
            print(f"  Event {i + 1} added, pending: {writer.pending_count}")
            time.sleep(1)  # 1 second between events

        writer.add_raw(
            event_type=EventType.SESSION_END,
            data={"outcome": "success"},
        )

    print(f"Stream completed: {session_id}")


def custom_event_types():
    """Example with typed Event objects for more control."""

    SERVER_URL = os.environ.get("CATSYPHON_URL", "http://localhost:8000")
    WORKSPACE_ID = os.environ.get("CATSYPHON_WORKSPACE_ID", "")

    client = CollectorClient.from_stored(SERVER_URL, WORKSPACE_ID)
    if client is None:
        print("No stored credentials. Please register first.")
        return

    session_id = f"typed-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    sequence = 0

    def next_seq() -> int:
        nonlocal sequence
        sequence += 1
        return sequence

    with BatchWriter(client, session_id, auto_start=False) as writer:
        # Create typed events
        events = [
            Event(
                sequence=next_seq(),
                type=EventType.SESSION_START,
                emitted_at=now,
                observed_at=now,
                data=SessionStartData(
                    agent_type="typed-example",
                    working_directory="/tmp",
                ).model_dump(exclude_none=True),
            ),
            Event(
                sequence=next_seq(),
                type=EventType.MESSAGE,
                emitted_at=now,
                observed_at=now,
                data=MessageData(
                    author_role="human",
                    message_type="prompt",
                    content="Hello with types!",
                ).model_dump(),
            ),
            Event(
                sequence=next_seq(),
                type=EventType.MESSAGE,
                emitted_at=now,
                observed_at=now,
                data=MessageData(
                    author_role="assistant",
                    message_type="response",
                    content="Types are great for validation!",
                    model="example-v1",
                    token_usage={"input": 5, "output": 10},
                ).model_dump(exclude_none=True),
            ),
        ]

        for event in events:
            writer.add(event)

        writer.flush()

    print(f"Typed events sent: {session_id}")


if __name__ == "__main__":
    print("=== CatSyphon SDK Batch Examples ===\n")

    print("--- Batch Import Example ---")
    batch_import_example()

    print("\n--- Time-Based Flush Example ---")
    time_based_flush_example()

    print("\n--- Typed Events Example ---")
    custom_event_types()
