"""
Acceptance test: Incremental re-ingestion of appended log file.

Given a previously parsed log file
When the file is appended to with new messages
Then incremental parsing produces only the new messages
And the total message count matches full parse + incremental delta
"""

import json
from pathlib import Path

import pytest

from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.parsers.incremental import (
    ChangeType,
    calculate_partial_hash,
    detect_file_change_type,
)


def _make_message(
    session_id: str,
    uuid: str,
    parent_uuid: str,
    role: str,
    content: str,
    timestamp: str,
    msg_type: str | None = None,
) -> str:
    """Build a single JSONL line in Claude Code format."""
    effective_type = msg_type or role
    msg: dict = {
        "sessionId": session_id,
        "version": "2.0.0",
        "cwd": "/Users/test/project",
        "gitBranch": "main",
        "timestamp": timestamp,
        "type": effective_type,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "message": {"role": role, "content": content},
    }
    if role == "assistant":
        msg["message"]["model"] = "claude-sonnet-4"
    return json.dumps(msg)


# Reusable message lines ------------------------------------------------

SESSION = "incr-session-001"

INITIAL_LINES = [
    _make_message(
        SESSION,
        "m1",
        "00000000-0000-0000-0000-000000000000",
        "user",
        "Hello",
        "2025-06-01T10:00:00.000Z",
    ),
    _make_message(
        SESSION,
        "m2",
        "m1",
        "assistant",
        "Hi there!",
        "2025-06-01T10:00:01.000Z",
    ),
]

APPENDED_LINES = [
    _make_message(
        SESSION,
        "m3",
        "m2",
        "user",
        "What is Python?",
        "2025-06-01T10:00:02.000Z",
    ),
    _make_message(
        SESSION,
        "m4",
        "m3",
        "assistant",
        "A programming language.",
        "2025-06-01T10:00:03.000Z",
    ),
]


class TestIncrementalReingest:
    """
    Scenario: A watch daemon detects new lines appended to a log file
    and triggers an incremental parse instead of a full reparse.
    """

    @pytest.fixture
    def parser(self) -> ClaudeCodeParser:
        return ClaudeCodeParser()

    @pytest.fixture
    def log_file(self, tmp_path: Path) -> Path:
        """Write the initial two messages and return the file path."""
        path = tmp_path / "session.jsonl"
        path.write_text("\n".join(INITIAL_LINES) + "\n", encoding="utf-8")
        return path

    # -- Step 1: Full parse establishes baseline -------------------------

    def test_full_parse_baseline(self, parser: ClaudeCodeParser, log_file: Path):
        """
        Given a fresh log file with 2 messages
        When fully parsed
        Then 2 messages are returned.
        """
        parsed = parser.parse(log_file)

        assert len(parsed.messages) == 2
        assert parsed.session_id == SESSION

    # -- Step 2: Detect append change type --------------------------------

    def test_detect_append_after_growth(self, log_file: Path):
        """
        Given a file whose size and partial hash are recorded
        When new lines are appended
        Then detect_file_change_type reports APPEND.
        """
        original_size = log_file.stat().st_size
        original_hash = calculate_partial_hash(log_file, original_size)

        # Append new messages
        with log_file.open("a", encoding="utf-8") as f:
            for line in APPENDED_LINES:
                f.write(line + "\n")

        change = detect_file_change_type(
            log_file,
            last_offset=original_size,
            last_file_size=original_size,
            last_partial_hash=original_hash,
        )
        assert change == ChangeType.APPEND

    def test_unchanged_detected_when_no_append(self, log_file: Path):
        """
        Given a file whose size and hash are recorded
        When nothing changes
        Then detect_file_change_type reports UNCHANGED.
        """
        size = log_file.stat().st_size
        partial_hash = calculate_partial_hash(log_file, size)

        change = detect_file_change_type(
            log_file,
            last_offset=size,
            last_file_size=size,
            last_partial_hash=partial_hash,
        )
        assert change == ChangeType.UNCHANGED

    # -- Step 3: Incremental parse returns only new messages ---------------

    def test_incremental_parse_returns_only_new_messages(
        self, parser: ClaudeCodeParser, log_file: Path
    ):
        """
        Given a file with 2 messages already parsed (offset recorded)
        When 2 more messages are appended
        Then parse_incremental returns exactly 2 new messages.
        """
        original_size = log_file.stat().st_size
        original_line_count = 2

        # Append
        with log_file.open("a", encoding="utf-8") as f:
            for line in APPENDED_LINES:
                f.write(line + "\n")

        result = parser.parse_incremental(
            log_file, last_offset=original_size, last_line=original_line_count
        )

        assert len(result.new_messages) == 2
        assert result.new_messages[0].content == "What is Python?"
        assert result.new_messages[1].content == "A programming language."

    def test_incremental_state_tracking_updated(
        self, parser: ClaudeCodeParser, log_file: Path
    ):
        """
        Given an incremental parse
        Then the result carries updated offset, line count, and hash.
        """
        original_size = log_file.stat().st_size

        with log_file.open("a", encoding="utf-8") as f:
            for line in APPENDED_LINES:
                f.write(line + "\n")

        result = parser.parse_incremental(
            log_file, last_offset=original_size, last_line=2
        )

        assert result.last_processed_offset > original_size
        assert result.last_processed_line == 4  # 2 original + 2 new
        assert result.file_size_bytes == log_file.stat().st_size
        assert len(result.partial_hash) == 64

    # -- Step 4: Total = full + incremental delta -------------------------

    def test_total_equals_full_plus_incremental(
        self, parser: ClaudeCodeParser, log_file: Path
    ):
        """
        Given:
          full parse of original file -> N messages
          append new lines
          incremental parse -> M new messages
        Then:
          full reparse of entire file -> N + M messages
        """
        # Full parse of original
        full_original = parser.parse(log_file)
        original_count = len(full_original.messages)
        original_size = log_file.stat().st_size

        # Append
        with log_file.open("a", encoding="utf-8") as f:
            for line in APPENDED_LINES:
                f.write(line + "\n")

        # Incremental parse
        incremental = parser.parse_incremental(
            log_file, last_offset=original_size, last_line=original_count
        )
        incremental_count = len(incremental.new_messages)

        # Full reparse of entire file
        full_reparse = parser.parse(log_file)
        total_count = len(full_reparse.messages)

        assert total_count == original_count + incremental_count

    # -- Step 5: Multiple sequential appends accumulate correctly ----------

    def test_multiple_sequential_appends(
        self, parser: ClaudeCodeParser, log_file: Path
    ):
        """
        Given a series of appends
        Then each incremental parse returns only the newest batch
        And cumulative total matches a final full reparse.
        """
        offset = log_file.stat().st_size
        line_count = 2
        cumulative_incremental = 0

        # First append: 2 messages
        with log_file.open("a", encoding="utf-8") as f:
            for line in APPENDED_LINES:
                f.write(line + "\n")

        result1 = parser.parse_incremental(log_file, offset, line_count)
        cumulative_incremental += len(result1.new_messages)
        offset = result1.last_processed_offset
        line_count = result1.last_processed_line

        # Second append: 1 more message
        extra_line = _make_message(
            SESSION,
            "m5",
            "m4",
            "user",
            "Thanks!",
            "2025-06-01T10:00:04.000Z",
        )
        with log_file.open("a", encoding="utf-8") as f:
            f.write(extra_line + "\n")

        result2 = parser.parse_incremental(log_file, offset, line_count)
        cumulative_incremental += len(result2.new_messages)

        # Full reparse for ground truth
        full = parser.parse(log_file)

        assert len(full.messages) == 2 + cumulative_incremental
        assert result2.new_messages[0].content == "Thanks!"
