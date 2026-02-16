"""
Incremental parsing infrastructure.

Provides two protocol layers:

1. **ChunkedParser** (ADR-009) — the primary interface. Two methods:
   - ``parse_metadata()`` reads the first few lines for session-level metadata.
   - ``parse_messages(offset, limit)`` returns a bounded ``MessageChunk``.
   First-time ingestion is chunked from offset=0; subsequent appends
   resume from the stored offset. Peak memory is ~3 MB per chunk regardless
   of file size.

2. **IncrementalParser** (legacy, ADR-003) — deprecated but retained until
   all callers migrate. Will be removed after Step 6 of the ADR-009 plan.

Utility helpers (``detect_file_change_type``, ``calculate_partial_hash``)
are shared by both layers.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Protocol, runtime_checkable

from catsyphon.models.parsed import ConversationMetadata, ParsedMessage


class ChangeType(str, Enum):
    """Type of file change detected."""

    APPEND = "append"  # New content added to end (incremental parse)
    TRUNCATE = "truncate"  # File size decreased (full reparse required)
    REWRITE = "rewrite"  # Mid-file content changed (full reparse required)
    UNCHANGED = "unchanged"  # No changes detected


@dataclass
class IncrementalParseResult:
    """Result from incremental parsing operation.

    .. deprecated:: ADR-009
        Use ``MessageChunk`` from ``ChunkedParser.parse_messages()`` instead.

    Contains only the NEW messages parsed since last offset, along with
    updated state tracking information.
    """

    new_messages: List[ParsedMessage]
    """Only the messages parsed in this incremental update."""

    last_processed_offset: int
    """Byte offset in file where parsing stopped."""

    last_processed_line: int
    """Line number where parsing stopped (for debugging)."""

    file_size_bytes: int
    """Current file size in bytes."""

    partial_hash: str
    """SHA-256 hash of content up to last_processed_offset."""

    last_message_timestamp: Optional[datetime] = None
    """Timestamp of the last message parsed (for validation)."""


@runtime_checkable
class IncrementalParser(Protocol):
    """
    Protocol for parsers that support incremental parsing.

    Parsers implementing this protocol can parse only new content
    appended to files, rather than reparsing the entire file.

    Note:
        This is a separate protocol from ConversationParser. Parsers can
        implement both protocols to support both full and incremental modes.
    """

    def supports_incremental(self, file_path: Path) -> bool:
        """
        Check if incremental parsing is supported for this specific file.

        Args:
            file_path: Path to the log file

        Returns:
            True if incremental parsing is supported for this file, False otherwise

        Note:
            Some file formats may not support incremental parsing (e.g., binary
            formats that require full reparse, or corrupted files). This method
            allows parsers to opt-out on a per-file basis.

            Default implementation should return True if the parser generally
            supports incremental parsing.
        """
        ...

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """
        Parse only new content appended since last_offset.

        Args:
            file_path: Path to the log file
            last_offset: Byte offset where parsing last stopped
            last_line: Line number where parsing last stopped

        Returns:
            IncrementalParseResult with only new messages and updated state

        Raises:
            ValueError: If file format is invalid or offset is out of bounds
        """
        ...


# ---------------------------------------------------------------------------
# ADR-009: Chunked parsing protocol
# ---------------------------------------------------------------------------


@dataclass
class MessageChunk:
    """A bounded batch of parsed messages with cursor state.

    Returned by ``ChunkedParser.parse_messages()``. The ``next_offset``
    and ``next_line`` fields form the cursor for the subsequent call;
    ``is_last`` is True when EOF has been reached.

    ``summaries`` and ``compaction_events`` live here because they appear
    inline in the JSONL stream and are encountered during chunk parsing.
    The ingestion loop accumulates them across chunks.
    """

    messages: list[ParsedMessage]
    next_offset: int
    next_line: int
    is_last: bool
    partial_hash: str
    file_size: int
    summaries: list[dict] = field(default_factory=list)
    compaction_events: list[dict] = field(default_factory=list)


@runtime_checkable
class ChunkedParser(Protocol):
    """Protocol for parsers that support chunked (bounded-memory) parsing.

    Implementors provide two methods:
    - ``parse_metadata`` — lightweight, reads first N lines.
    - ``parse_messages`` — returns a bounded ``MessageChunk``.

    First-time ingestion calls ``parse_messages(offset=0)`` in a loop.
    Subsequent appends resume from the stored offset. Same loop, same
    memory profile.
    """

    def parse_metadata(self, file_path: Path) -> ConversationMetadata:
        """Extract session-level metadata from the first few lines.

        Must be cheap — reads ≤10 JSONL lines. Never materializes the
        full file.
        """
        ...

    def parse_messages(
        self,
        file_path: Path,
        offset: int = 0,
        limit: int = 500,
    ) -> MessageChunk:
        """Parse up to *limit* messages starting from byte *offset*.

        Returns a ``MessageChunk`` whose ``next_offset`` is the cursor
        for the next call and whose ``is_last`` flag signals EOF.
        """
        ...


def detect_file_change_type(
    file_path: Path,
    last_offset: int,
    last_file_size: int,
    last_partial_hash: Optional[str],
) -> ChangeType:
    """
    Detect what type of change occurred to a file.

    This function determines whether a file was appended to, truncated,
    rewritten, or unchanged since the last parse.

    Args:
        file_path: Path to the file to check
        last_offset: Byte offset where parsing last stopped
        last_file_size: File size at last parse
        last_partial_hash: SHA-256 hash of content up to last_offset

    Returns:
        ChangeType indicating the type of change detected

    Examples:
        >>> detect_file_change_type(Path("log.jsonl"), 1000, 1000, "abc123")
        ChangeType.UNCHANGED

        >>> detect_file_change_type(Path("log.jsonl"), 1000, 1000, "abc123")
        ChangeType.APPEND  # If file grew to 1500 bytes

        >>> detect_file_change_type(Path("log.jsonl"), 1000, 2000, "abc123")
        ChangeType.TRUNCATE  # If file shrunk to 500 bytes

        >>> detect_file_change_type(Path("log.jsonl"), 1000, 2000, "abc123")
        ChangeType.REWRITE  # If mid-file content changed
    """
    if not file_path.exists():
        # File deleted - treat as truncate for reparse
        return ChangeType.TRUNCATE

    current_size = file_path.stat().st_size

    # Quick check: file size unchanged
    if current_size == last_file_size:
        # If we have a partial hash, verify content hasn't changed
        if last_partial_hash:
            current_partial_hash = calculate_partial_hash(
                file_path, min(last_offset, current_size)
            )
            if current_partial_hash != last_partial_hash:
                return ChangeType.REWRITE
        return ChangeType.UNCHANGED

    # File shrunk - truncation detected
    if current_size < last_file_size:
        return ChangeType.TRUNCATE

    # File grew - check if it's a clean append or mid-file rewrite
    if current_size > last_file_size:
        # Verify content up to last_offset hasn't changed
        if last_partial_hash:
            current_partial_hash = calculate_partial_hash(file_path, last_offset)
            if current_partial_hash != last_partial_hash:
                # Mid-file content changed - full reparse required
                return ChangeType.REWRITE

        # File grew and old content intact - clean append
        return ChangeType.APPEND

    # Fallback (shouldn't reach here)
    return ChangeType.UNCHANGED


def calculate_partial_hash(file_path: Path, offset: int) -> str:
    """
    Calculate SHA-256 hash of file content up to specified offset.

    This is used to detect if mid-file content has been modified between
    parses. If the partial hash changes, a full reparse is required.

    Args:
        file_path: Path to the file
        offset: Byte offset to read up to

    Returns:
        Hex-encoded SHA-256 hash of content from start to offset

    Raises:
        ValueError: If offset is negative or exceeds file size

    Examples:
        >>> calculate_partial_hash(Path("log.jsonl"), 1000)
        'a7b2c3d4e5f6...'
    """
    if offset < 0:
        raise ValueError(f"Offset must be non-negative, got {offset}")

    file_size = file_path.stat().st_size
    if offset > file_size:
        raise ValueError(
            f"Offset {offset} exceeds file size {file_size} for {file_path}"
        )

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks to handle large files efficiently
        bytes_read = 0
        chunk_size = 8192

        while bytes_read < offset:
            # Read up to chunk_size, but not past offset
            remaining = offset - bytes_read
            chunk = f.read(min(chunk_size, remaining))

            if not chunk:
                break  # EOF reached

            sha256.update(chunk)
            bytes_read += len(chunk)

    return sha256.hexdigest()


def calculate_content_partial_hash(content: str, offset: int) -> str:
    """
    Calculate SHA-256 hash of string content up to specified byte offset.

    Similar to calculate_partial_hash but operates on in-memory content
    rather than reading from a file. Useful for testing.

    Args:
        content: String content to hash
        offset: Byte offset to hash up to

    Returns:
        Hex-encoded SHA-256 hash of content from start to offset

    Raises:
        ValueError: If offset is negative or exceeds content length
    """
    content_bytes = content.encode("utf-8")

    if offset < 0:
        raise ValueError(f"Offset must be non-negative, got {offset}")

    if offset > len(content_bytes):
        raise ValueError(f"Offset {offset} exceeds content length {len(content_bytes)}")

    return hashlib.sha256(content_bytes[:offset]).hexdigest()
