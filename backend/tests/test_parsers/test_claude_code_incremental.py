"""
Tests for ClaudeCodeParser incremental parsing.

Tests the parse_incremental() method of ClaudeCodeParser to ensure it
correctly parses only new messages appended to log files.
"""

from datetime import datetime
from pathlib import Path

import pytest

from catsyphon.parsers.base import ParseFormatError
from catsyphon.parsers.claude_code import ClaudeCodeParser


class TestClaudeCodeParserIncremental:
    """Tests for ClaudeCodeParser.parse_incremental() method."""

    @pytest.fixture
    def parser(self):
        """Create a ClaudeCodeParser instance."""
        return ClaudeCodeParser()

    @pytest.fixture
    def sample_log_base(self):
        """Base log content (first 2 messages)."""
        return (
            '{"sessionId":"test-123","version":"2.0.0","cwd":"/tmp","gitBranch":"main",'
            '"timestamp":"2025-01-13T10:00:00.000Z","type":"user","message":{"role":"user",'
            '"content":"Hello"}}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":"Hi there!","model":"claude-sonnet-4"}}\n'
        )

    @pytest.fixture
    def sample_log_appended(self):
        """Appended log content (1 more message)."""
        return (
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:02.000Z","type":"user",'
            '"message":{"role":"user","content":"How are you?"}}\n'
        )

    def test_parse_incremental_with_new_messages(
        self,
        parser: ClaudeCodeParser,
        tmp_path: Path,
        sample_log_base: str,
        sample_log_appended: str,
    ):
        """Test parsing incremental updates with new messages."""
        log_file = tmp_path / "test.jsonl"

        # Write initial content
        log_file.write_text(sample_log_base, encoding="utf-8")
        initial_size = log_file.stat().st_size

        # Append more content
        log_file.write_text(sample_log_base + sample_log_appended, encoding="utf-8")

        # Parse incremental (only new message)
        result = parser.parse_incremental(log_file, initial_size, 2)

        # Should only have 1 new message (the appended one)
        assert len(result.new_messages) == 1
        assert result.new_messages[0].role == "user"
        assert result.new_messages[0].content == "How are you?"

        # State tracking should be updated
        assert result.last_processed_offset > initial_size
        assert result.last_processed_line == 3  # Started at line 2, added 1 line
        assert result.file_size_bytes == log_file.stat().st_size
        assert len(result.partial_hash) == 64

    def test_parse_incremental_no_new_messages(
        self, parser: ClaudeCodeParser, tmp_path: Path, sample_log_base: str
    ):
        """Test parsing when no new messages were added."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")

        file_size = log_file.stat().st_size

        # Parse incremental from end (no new content)
        result = parser.parse_incremental(log_file, file_size, 2)

        # Should have no new messages
        assert len(result.new_messages) == 0
        assert result.last_processed_offset == file_size
        assert result.last_processed_line == 2  # Unchanged
        assert result.last_message_timestamp is None

    def test_parse_incremental_from_start(
        self, parser: ClaudeCodeParser, tmp_path: Path, sample_log_base: str
    ):
        """Test parsing from offset 0 (essentially full parse)."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")

        # Parse from beginning
        result = parser.parse_incremental(log_file, 0, 0)

        # Should parse all messages
        assert len(result.new_messages) == 2
        assert result.new_messages[0].role == "user"
        assert result.new_messages[1].role == "assistant"
        assert result.last_processed_line == 2

    def test_parse_incremental_with_tool_calls(
        self, parser: ClaudeCodeParser, tmp_path: Path
    ):
        """Test parsing incremental updates that include tool calls."""
        initial_content = (
            '{"sessionId":"test-123","version":"2.0.0","timestamp":"2025-01-13T10:00:00.000Z",'
            '"type":"user","message":{"role":"user","content":"List files"}}\n'
        )

        appended_content = (
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":[{"type":"tool_use","id":"tool_1",'
            '"name":"Bash","input":{"command":"ls"}}],"model":"claude-sonnet-4"}}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:02.000Z","type":"user",'
            '"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tool_1",'
            '"content":"file1.txt\\nfile2.txt"}]}}\n'
        )

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(initial_content, encoding="utf-8")
        initial_size = log_file.stat().st_size

        # Append tool call messages
        log_file.write_text(initial_content + appended_content, encoding="utf-8")

        # Parse incremental
        result = parser.parse_incremental(log_file, initial_size, 1)

        # Should have 2 new messages (assistant with tool call, user with result)
        assert len(result.new_messages) == 2
        assert result.new_messages[0].role == "assistant"
        assert len(result.new_messages[0].tool_calls) == 1
        assert result.new_messages[0].tool_calls[0].tool_name == "Bash"
        assert result.new_messages[0].tool_calls[0].result == "file1.txt\nfile2.txt"

    def test_parse_incremental_multiple_appends(
        self, parser: ClaudeCodeParser, tmp_path: Path
    ):
        """Test multiple sequential incremental parses."""
        log_file = tmp_path / "test.jsonl"

        # Message 1
        msg1 = (
            '{"sessionId":"test-123","version":"2.0.0","timestamp":"2025-01-13T10:00:00.000Z",'
            '"type":"user","message":{"role":"user","content":"First"}}\n'
        )
        log_file.write_text(msg1, encoding="utf-8")
        size1 = log_file.stat().st_size

        # Append Message 2
        msg2 = (
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":"Second","model":"claude-sonnet-4"}}\n'
        )
        log_file.write_text(msg1 + msg2, encoding="utf-8")

        # First incremental parse (msg1 -> msg2)
        result1 = parser.parse_incremental(log_file, size1, 1)
        assert len(result1.new_messages) == 1
        assert result1.new_messages[0].content == "Second"
        size2 = result1.last_processed_offset

        # Append Message 3
        msg3 = (
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:02.000Z","type":"user",'
            '"message":{"role":"user","content":"Third"}}\n'
        )
        log_file.write_text(msg1 + msg2 + msg3, encoding="utf-8")

        # Second incremental parse (msg2 -> msg3)
        result2 = parser.parse_incremental(log_file, size2, 2)
        assert len(result2.new_messages) == 1
        assert result2.new_messages[0].content == "Third"

    def test_parse_incremental_skips_invalid_lines(
        self, parser: ClaudeCodeParser, tmp_path: Path
    ):
        """Test that invalid JSON lines are skipped gracefully."""
        initial = (
            '{"sessionId":"test-123","version":"2.0.0","timestamp":"2025-01-13T10:00:00.000Z",'
            '"type":"user","message":{"role":"user","content":"Valid"}}\n'
        )

        appended = (
            '{"invalid json\n'  # Invalid JSON line
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":"Valid","model":"claude-sonnet-4"}}\n'
        )

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(initial, encoding="utf-8")
        initial_size = log_file.stat().st_size

        log_file.write_text(initial + appended, encoding="utf-8")

        # Parse incremental (should skip invalid line)
        result = parser.parse_incremental(log_file, initial_size, 1)

        # Should only have 1 valid message (invalid line skipped)
        assert len(result.new_messages) == 1
        assert result.new_messages[0].content == "Valid"

    def test_parse_incremental_tracks_timestamp(
        self,
        parser: ClaudeCodeParser,
        tmp_path: Path,
        sample_log_base: str,
        sample_log_appended: str,
    ):
        """Test that last_message_timestamp is tracked correctly."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")
        initial_size = log_file.stat().st_size

        log_file.write_text(sample_log_base + sample_log_appended, encoding="utf-8")

        result = parser.parse_incremental(log_file, initial_size, 2)

        # Should track timestamp of last message
        assert result.last_message_timestamp is not None
        assert isinstance(result.last_message_timestamp, datetime)

    def test_parse_incremental_file_not_found(
        self, parser: ClaudeCodeParser, tmp_path: Path
    ):
        """Test that missing file raises appropriate error."""
        missing_file = tmp_path / "missing.jsonl"

        with pytest.raises(ParseFormatError, match="does not exist"):
            parser.parse_incremental(missing_file, 0, 0)

    def test_parse_incremental_negative_offset(
        self, parser: ClaudeCodeParser, tmp_path: Path, sample_log_base: str
    ):
        """Test that negative offset raises ValueError."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")

        with pytest.raises(ValueError, match="non-negative"):
            parser.parse_incremental(log_file, -10, 0)

    def test_parse_incremental_offset_exceeds_file(
        self, parser: ClaudeCodeParser, tmp_path: Path, sample_log_base: str
    ):
        """Test that offset beyond file size raises ValueError."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")

        with pytest.raises(ValueError, match="exceeds file size"):
            parser.parse_incremental(log_file, 10000, 0)

    def test_parse_incremental_partial_hash_calculation(
        self, parser: ClaudeCodeParser, tmp_path: Path, sample_log_base: str
    ):
        """Test that partial hash is correctly calculated."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text(sample_log_base, encoding="utf-8")

        result = parser.parse_incremental(log_file, 0, 0)

        # Hash should be 64 character hex string (SHA-256)
        assert len(result.partial_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.partial_hash)

    def test_parse_incremental_preserves_message_order(
        self, parser: ClaudeCodeParser, tmp_path: Path
    ):
        """Test that messages are returned in chronological order."""
        # Messages with out-of-order timestamps in file
        content = (
            '{"sessionId":"test-123","version":"2.0.0","timestamp":"2025-01-13T10:00:02.000Z",'
            '"type":"user","message":{"role":"user","content":"Second"}}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:00.000Z","type":"user",'
            '"message":{"role":"user","content":"First"}}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z","type":"user",'
            '"message":{"role":"user","content":"Middle"}}\n'
        )

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(content, encoding="utf-8")

        result = parser.parse_incremental(log_file, 0, 0)

        # Should be sorted by timestamp
        assert result.new_messages[0].content == "First"
        assert result.new_messages[1].content == "Middle"
        assert result.new_messages[2].content == "Second"

    def test_parse_incremental_filters_non_conversational_messages(
        self,
        parser: ClaudeCodeParser,
        tmp_path: Path,
    ):
        """Test that incremental parse filters out non-conversational messages.

        This test ensures that file snapshots, summaries, and other non-conversational
        message types are filtered out during incremental parsing, matching the behavior
        of the full parse path.

        Regression test for: Parser allows null role causing database constraint violation
        """
        # Content with mix of conversational and non-conversational messages
        content = (
            '{"sessionId":"test-123","version":"2.0.0","cwd":"/tmp","gitBranch":"main",'
            '"timestamp":"2025-01-13T10:00:00.000Z","type":"user","message":{"role":"user",'
            '"content":"Hello"}}\n'
            # File snapshot (should be filtered)
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z",'
            '"type":"file_snapshot","file":"test.py","content":"print(1)"}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:02.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":"Hi there!","model":"claude-sonnet-4"}}\n'
            # Summary (should be filtered)
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:03.000Z",'
            '"type":"summary","content":"Conversation summary"}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:04.000Z","type":"user",'
            '"message":{"role":"user","content":"How are you?"}}\n'
            # Metadata (should be filtered)
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:05.000Z",'
            '"type":"metadata","key":"value"}\n'
        )

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(content, encoding="utf-8")

        result = parser.parse_incremental(log_file, 0, 0)

        # Should only include the 3 conversational messages
        assert len(result.new_messages) == 3
        assert result.new_messages[0].role == "user"
        assert result.new_messages[0].content == "Hello"
        assert result.new_messages[1].role == "assistant"
        assert result.new_messages[1].content == "Hi there!"
        assert result.new_messages[2].role == "user"
        assert result.new_messages[2].content == "How are you?"

    def test_parse_incremental_filters_messages_without_role(
        self,
        parser: ClaudeCodeParser,
        tmp_path: Path,
    ):
        """Test that messages without a role field are filtered out.

        This ensures we don't attempt to create database records with null roles,
        which would violate the NOT NULL constraint.
        """
        # Content with messages that don't have the role field
        content = (
            '{"sessionId":"test-123","version":"2.0.0","cwd":"/tmp","gitBranch":"main",'
            '"timestamp":"2025-01-13T10:00:00.000Z","type":"user","message":{"role":"user",'
            '"content":"Valid message"}}\n'
            # Message without role (should be filtered)
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:01.000Z",'
            '"type":"some_event","message":{"content":"No role field"}}\n'
            '{"sessionId":"test-123","timestamp":"2025-01-13T10:00:02.000Z","type":"assistant",'
            '"message":{"role":"assistant","content":"Another valid message","model":"claude-sonnet-4"}}\n'
        )

        log_file = tmp_path / "test.jsonl"
        log_file.write_text(content, encoding="utf-8")

        result = parser.parse_incremental(log_file, 0, 0)

        # Should only include the 2 valid conversational messages
        assert len(result.new_messages) == 2
        assert all(msg.role in ("user", "assistant") for msg in result.new_messages)
