"""
Batch writer with configurable flush intervals.

Provides a lower-level API for batching events with time-based
and count-based flush triggers.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from catsyphon_sdk.models import Event, EventType

if TYPE_CHECKING:
    from catsyphon_sdk.client import AsyncCollectorClient, CollectorClient

logger = logging.getLogger(__name__)


class BatchWriter:
    """
    Synchronous batch writer with automatic flush.

    Flushes events when:
    - Batch size is reached
    - Flush interval expires
    - Explicitly called
    - Context manager exits

    Usage:
        with client.batch_writer("session-123") as writer:
            writer.add(event1)
            writer.add(event2)
            # Auto-flushes on batch size or interval
        # Auto-flushes on exit
    """

    def __init__(
        self,
        client: "CollectorClient",
        session_id: str,
        batch_size: int = 20,
        flush_interval: float = 5.0,
        auto_start: bool = True,
    ):
        """
        Initialize the batch writer.

        Args:
            client: CollectorClient instance
            session_id: Session identifier
            batch_size: Maximum events before flush
            flush_interval: Maximum seconds between flushes
            auto_start: Whether to start the flush timer automatically
        """
        self.client = client
        self.session_id = session_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._events: list[Event] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._timer: Optional[threading.Timer] = None
        self._closed = False
        self._sequence = 0

        if auto_start:
            self._start_timer()

    def __enter__(self) -> "BatchWriter":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _start_timer(self) -> None:
        """Start the periodic flush timer."""
        if self._closed:
            return

        self._timer = threading.Timer(self.flush_interval, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        """Called by timer to flush if needed."""
        if self._closed:
            return

        with self._lock:
            if self._events and time.time() - self._last_flush >= self.flush_interval:
                self._flush_locked()

        self._start_timer()

    def _flush_locked(self) -> None:
        """Flush events (must be called with lock held)."""
        if not self._events:
            return

        try:
            response = self.client.send_events(self.session_id, self._events)
            logger.debug(
                f"Flushed {len(self._events)} events, accepted={response.accepted}"
            )
        except Exception as e:
            logger.error(f"Failed to flush events: {e}")
            raise
        finally:
            self._events.clear()
            self._last_flush = time.time()

    def add(self, event: Event) -> None:
        """
        Add an event to the batch.

        Args:
            event: Event to add
        """
        with self._lock:
            self._events.append(event)

            if len(self._events) >= self.batch_size:
                self._flush_locked()

    def add_raw(
        self,
        event_type: EventType,
        data: dict[str, Any],
        emitted_at: Optional[datetime] = None,
    ) -> None:
        """
        Add a raw event to the batch.

        Args:
            event_type: Type of event
            data: Event data
            emitted_at: When the event occurred
        """
        with self._lock:
            self._sequence += 1
            now = datetime.now(timezone.utc)

            event = Event(
                sequence=self._sequence,
                type=event_type,
                emitted_at=emitted_at or now,
                observed_at=now,
                data=data,
            )
            self._events.append(event)

            if len(self._events) >= self.batch_size:
                self._flush_locked()

    def flush(self) -> None:
        """Manually flush all pending events."""
        with self._lock:
            self._flush_locked()

    def close(self) -> None:
        """Close the batch writer and flush remaining events."""
        self._closed = True

        if self._timer:
            self._timer.cancel()
            self._timer = None

        with self._lock:
            if self._events:
                self._flush_locked()

    @property
    def pending_count(self) -> int:
        """Get the number of pending events."""
        with self._lock:
            return len(self._events)


class AsyncBatchWriter:
    """
    Asynchronous batch writer with automatic flush.

    Usage:
        async with client.batch_writer("session-123") as writer:
            await writer.add(event1)
            await writer.add(event2)
        # Auto-flushes on exit
    """

    def __init__(
        self,
        client: "AsyncCollectorClient",
        session_id: str,
        batch_size: int = 20,
        flush_interval: float = 5.0,
        auto_start: bool = True,
    ):
        """Initialize the async batch writer."""
        self.client = client
        self.session_id = session_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._events: list[Event] = []
        self._lock = asyncio.Lock()
        self._last_flush = time.time()
        self._flush_task: Optional[asyncio.Task[None]] = None
        self._closed = False
        self._sequence = 0

        if auto_start:
            self._start_flush_task()

    async def __aenter__(self) -> "AsyncBatchWriter":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _start_flush_task(self) -> None:
        """Start the periodic flush task."""
        if self._closed:
            return

        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        """Periodically flush events."""
        while not self._closed:
            await asyncio.sleep(self.flush_interval)

            if self._closed:
                break

            async with self._lock:
                if self._events and time.time() - self._last_flush >= self.flush_interval:
                    await self._flush_locked()

    async def _flush_locked(self) -> None:
        """Flush events (must be called with lock held)."""
        if not self._events:
            return

        try:
            response = await self.client.send_events(self.session_id, self._events)
            logger.debug(
                f"Flushed {len(self._events)} events, accepted={response.accepted}"
            )
        except Exception as e:
            logger.error(f"Failed to flush events: {e}")
            raise
        finally:
            self._events.clear()
            self._last_flush = time.time()

    async def add(self, event: Event) -> None:
        """Add an event to the batch."""
        async with self._lock:
            self._events.append(event)

            if len(self._events) >= self.batch_size:
                await self._flush_locked()

    async def add_raw(
        self,
        event_type: EventType,
        data: dict[str, Any],
        emitted_at: Optional[datetime] = None,
    ) -> None:
        """Add a raw event to the batch."""
        async with self._lock:
            self._sequence += 1
            now = datetime.now(timezone.utc)

            event = Event(
                sequence=self._sequence,
                type=event_type,
                emitted_at=emitted_at or now,
                observed_at=now,
                data=data,
            )
            self._events.append(event)

            if len(self._events) >= self.batch_size:
                await self._flush_locked()

    async def flush(self) -> None:
        """Manually flush all pending events."""
        async with self._lock:
            await self._flush_locked()

    async def close(self) -> None:
        """Close the batch writer and flush remaining events."""
        self._closed = True

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        async with self._lock:
            if self._events:
                await self._flush_locked()

    @property
    def pending_count(self) -> int:
        """Get the number of pending events."""
        return len(self._events)
