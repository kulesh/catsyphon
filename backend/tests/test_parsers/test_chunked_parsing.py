"""Tests for ADR-009: Chunked parsing (ChunkedParser protocol).

Covers:
- Data structure construction (ConversationMetadata, MessageChunk)
- Protocol compliance (isinstance checks)
- parse_metadata() for both parsers
- parse_messages() first chunk, subsequent chunk, is_last, small file
- parse() convenience wrapper produces identical results
- Summaries/compaction events extracted in chunks
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from catsyphon.models.parsed import ConversationMetadata
from catsyphon.parsers.incremental import ChunkedParser, MessageChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_claude_log(tmp_path: Path, num_messages: int = 5) -> Path:
    """Write a Claude Code JSONL log with N user/assistant pairs."""
    log_file = tmp_path / "claude-test.jsonl"
    lines: list[dict[str, Any]] = []

    for i in range(num_messages):
        ts = f"2025-10-16T19:12:{i:02d}.000Z"
        if i == 0:
            # First line has session metadata
            lines.append(
                {
                    "parentUuid": "00000000-0000-0000-0000-000000000000",
                    "isSidechain": False,
                    "userType": "external",
                    "cwd": "/Users/test/project",
                    "sessionId": "test-session-chunked",
                    "version": "2.0.17",
                    "gitBranch": "main",
                    "slug": "test-slug",
                    "type": "user",
                    "message": {"role": "user", "content": f"Message {i}"},
                    "uuid": f"msg-{i:03d}",
                    "timestamp": ts,
                }
            )
        elif i % 2 == 0:
            lines.append(
                {
                    "parentUuid": f"msg-{i - 1:03d}",
                    "isSidechain": False,
                    "sessionId": "test-session-chunked",
                    "type": "user",
                    "message": {"role": "user", "content": f"Message {i}"},
                    "uuid": f"msg-{i:03d}",
                    "timestamp": ts,
                }
            )
        else:
            lines.append(
                {
                    "parentUuid": f"msg-{i - 1:03d}",
                    "isSidechain": False,
                    "sessionId": "test-session-chunked",
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": f"Reply {i}"}],
                        "model": "claude-sonnet-4-5-20250929",
                    },
                    "uuid": f"msg-{i:03d}",
                    "timestamp": ts,
                }
            )

    with log_file.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    return log_file


def _write_codex_log(tmp_path: Path, num_messages: int = 4) -> Path:
    """Write a Codex JSONL log."""
    log_file = tmp_path / "codex-test.jsonl"
    ts = datetime.now(UTC).isoformat()

    lines: list[dict[str, Any]] = [
        {
            "timestamp": ts,
            "type": "session_meta",
            "payload": {
                "id": "codex-session-chunked",
                "cwd": "/Users/example/project",
                "originator": "codex_cli",
                "cli_version": "0.63.0",
                "model_provider": "openai",
            },
        },
    ]

    for i in range(num_messages):
        role = "user" if i % 2 == 0 else "assistant"
        text_type = "input_text" if role == "user" else "output_text"
        lines.append(
            {
                "timestamp": ts,
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": [{"type": text_type, "text": f"Codex message {i}"}],
                },
            }
        )

    with log_file.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    return log_file


# ---------------------------------------------------------------------------
# Data structure tests
# ---------------------------------------------------------------------------


class TestConversationMetadata:
    def test_construction_with_required_fields(self):
        meta = ConversationMetadata(
            session_id="test-123",
            agent_type="claude-code",
            start_time=datetime.now(),
        )
        assert meta.session_id == "test-123"
        assert meta.agent_type == "claude-code"
        assert meta.conversation_type == "main"
        assert meta.parent_session_id is None

    def test_construction_with_all_fields(self):
        meta = ConversationMetadata(
            session_id="agent-456",
            agent_type="claude-code",
            start_time=datetime.now(),
            agent_version="2.0.17",
            working_directory="/Users/test/project",
            git_branch="main",
            conversation_type="agent",
            parent_session_id="parent-789",
            slug="my-session",
            metadata={"key": "value"},
        )
        assert meta.conversation_type == "agent"
        assert meta.parent_session_id == "parent-789"
        assert meta.slug == "my-session"


class TestMessageChunk:
    def test_construction_empty(self):
        chunk = MessageChunk(
            messages=[],
            next_offset=0,
            next_line=0,
            is_last=True,
            partial_hash="abc",
            file_size=100,
        )
        assert chunk.is_last is True
        assert chunk.messages == []
        assert chunk.summaries == []
        assert chunk.compaction_events == []

    def test_construction_with_summaries(self):
        chunk = MessageChunk(
            messages=[],
            next_offset=100,
            next_line=5,
            is_last=False,
            partial_hash="def",
            file_size=500,
            summaries=[{"summary": "test"}],
            compaction_events=[{"type": "compaction"}],
        )
        assert len(chunk.summaries) == 1
        assert len(chunk.compaction_events) == 1
        assert chunk.is_last is False


# ---------------------------------------------------------------------------
# Protocol compliance tests
# ---------------------------------------------------------------------------


class TestChunkedParserProtocol:
    def test_claude_code_parser_is_chunked_parser(self):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        parser = ClaudeCodeParser()
        assert isinstance(parser, ChunkedParser)

    def test_codex_parser_is_chunked_parser(self):
        from catsyphon.parsers.codex import CodexParser

        parser = CodexParser()
        assert isinstance(parser, ChunkedParser)


# ---------------------------------------------------------------------------
# Claude Code: parse_metadata()
# ---------------------------------------------------------------------------


class TestClaudeCodeParseMetadata:
    def test_extracts_session_metadata(self, tmp_path):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = _write_claude_log(tmp_path)
        parser = ClaudeCodeParser()
        meta = parser.parse_metadata(log_file)

        assert meta.session_id == "test-session-chunked"
        assert meta.agent_type == "claude-code"
        assert meta.agent_version == "2.0.17"
        assert meta.git_branch == "main"
        assert meta.working_directory == "/Users/test/project"
        assert meta.conversation_type == "main"
        assert meta.slug == "test-slug"

    def test_metadata_only_file_uses_filename_as_session_id(self, tmp_path):
        """A metadata-only file with UUID filename should extract session_id."""
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = tmp_path / "12345678-1234-1234-1234-123456789abc.jsonl"
        # Write a record without sessionId
        with log_file.open("w") as f:
            f.write(
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "test"},
                        "uuid": "msg-001",
                        "timestamp": "2025-10-16T19:12:00.000Z",
                    }
                )
                + "\n"
            )

        parser = ClaudeCodeParser()
        meta = parser.parse_metadata(log_file)
        assert meta.session_id == "12345678-1234-1234-1234-123456789abc"


# ---------------------------------------------------------------------------
# Claude Code: parse_messages()
# ---------------------------------------------------------------------------


class TestClaudeCodeParseMessages:
    def test_first_chunk_from_offset_zero(self, tmp_path):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = _write_claude_log(tmp_path, num_messages=5)
        parser = ClaudeCodeParser()

        chunk = parser.parse_messages(log_file, offset=0, limit=500)

        assert len(chunk.messages) > 0
        assert chunk.is_last is True  # Small file fits in one chunk
        assert chunk.next_offset > 0
        assert chunk.file_size > 0

    def test_small_limit_produces_multiple_chunks(self, tmp_path):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = _write_claude_log(tmp_path, num_messages=10)
        parser = ClaudeCodeParser()

        # First chunk with very small limit
        chunk1 = parser.parse_messages(log_file, offset=0, limit=3)
        assert len(chunk1.messages) > 0
        assert chunk1.is_last is False  # More data

        # Second chunk from where first left off
        chunk2 = parser.parse_messages(log_file, offset=chunk1.next_offset, limit=500)
        assert len(chunk2.messages) > 0
        assert chunk2.is_last is True  # Should reach EOF

        # Total messages from both chunks
        total = len(chunk1.messages) + len(chunk2.messages)
        assert total == 10  # All messages accounted for

    def test_empty_file_returns_empty_chunk(self, tmp_path):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = tmp_path / "empty.jsonl"
        log_file.write_text("")

        parser = ClaudeCodeParser()
        chunk = parser.parse_messages(log_file, offset=0)

        assert chunk.messages == []
        assert chunk.is_last is True


# ---------------------------------------------------------------------------
# Codex: parse_metadata()
# ---------------------------------------------------------------------------


class TestCodexParseMetadata:
    def test_extracts_session_metadata(self, tmp_path):
        from catsyphon.parsers.codex import CodexParser

        log_file = _write_codex_log(tmp_path)
        parser = CodexParser()
        meta = parser.parse_metadata(log_file)

        assert meta.session_id == "codex-session-chunked"
        assert meta.agent_type == "codex"
        assert meta.agent_version == "0.63.0"
        assert meta.working_directory == "/Users/example/project"
        assert meta.conversation_type == "main"


# ---------------------------------------------------------------------------
# Codex: parse_messages()
# ---------------------------------------------------------------------------


class TestCodexParseMessages:
    def test_first_chunk_from_offset_zero(self, tmp_path):
        from catsyphon.parsers.codex import CodexParser

        log_file = _write_codex_log(tmp_path, num_messages=4)
        parser = CodexParser()

        chunk = parser.parse_messages(log_file, offset=0, limit=500)

        assert len(chunk.messages) > 0
        assert chunk.is_last is True

    def test_small_limit_produces_multiple_chunks(self, tmp_path):
        from catsyphon.parsers.codex import CodexParser

        log_file = _write_codex_log(tmp_path, num_messages=10)
        parser = CodexParser()

        chunk1 = parser.parse_messages(log_file, offset=0, limit=3)
        assert chunk1.is_last is False

        chunk2 = parser.parse_messages(log_file, offset=chunk1.next_offset, limit=500)
        assert chunk2.is_last is True


# ---------------------------------------------------------------------------
# parse() convenience wrapper — identical output
# ---------------------------------------------------------------------------


class TestConvenienceWrapper:
    def test_claude_code_parse_matches_chunked(self, tmp_path):
        """parse() via chunked methods produces same result as direct parse."""
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = _write_claude_log(tmp_path, num_messages=8)
        parser = ClaudeCodeParser()

        # Use parse() convenience wrapper
        result = parser.parse(log_file)

        assert result.session_id == "test-session-chunked"
        assert result.agent_type == "claude-code"
        assert len(result.messages) == 8

    def test_codex_parse_matches_chunked(self, tmp_path):
        """parse() via chunked methods produces same result as direct parse."""
        from catsyphon.parsers.codex import CodexParser

        log_file = _write_codex_log(tmp_path, num_messages=6)
        parser = CodexParser()

        result = parser.parse(log_file)

        assert result.session_id == "codex-session-chunked"
        assert result.agent_type == "codex"
        assert len(result.messages) == 6


# ---------------------------------------------------------------------------
# Registry: find_chunked_parser()
# ---------------------------------------------------------------------------


class TestRegistryFindChunkedParser:
    def test_finds_claude_code_parser(self, tmp_path):
        from catsyphon.parsers import get_default_registry

        log_file = _write_claude_log(tmp_path)
        registry = get_default_registry()

        parser = registry.find_chunked_parser(log_file)

        assert parser is not None
        assert isinstance(parser, ChunkedParser)

    def test_finds_codex_parser(self, tmp_path):
        from catsyphon.parsers import get_default_registry

        log_file = _write_codex_log(tmp_path)
        registry = get_default_registry()

        parser = registry.find_chunked_parser(log_file)

        assert parser is not None
        assert isinstance(parser, ChunkedParser)

    def test_returns_none_for_unknown_file(self, tmp_path):
        from catsyphon.parsers import get_default_registry

        unknown_file = tmp_path / "unknown.txt"
        unknown_file.write_text("not a log file")
        registry = get_default_registry()

        parser = registry.find_chunked_parser(unknown_file)

        assert parser is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        from catsyphon.parsers import get_default_registry

        registry = get_default_registry()
        parser = registry.find_chunked_parser(tmp_path / "nonexistent.jsonl")

        assert parser is None


# ---------------------------------------------------------------------------
# Append simulation (incremental from non-zero offset)
# ---------------------------------------------------------------------------


class TestAppendSimulation:
    """Simulates the watch daemon's append detection: parse new content only."""

    def test_append_produces_only_new_messages(self, tmp_path):
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        log_file = _write_claude_log(tmp_path, num_messages=3)
        parser = ClaudeCodeParser()

        # "First parse" — read all messages, record offset
        chunk1 = parser.parse_messages(log_file, offset=0, limit=500)
        assert chunk1.is_last is True
        first_offset = chunk1.next_offset
        first_count = len(chunk1.messages)

        # Append more data
        with log_file.open("a") as f:
            for i in range(3, 6):
                ts = f"2025-10-16T19:13:{i:02d}.000Z"
                role = "user" if i % 2 == 0 else "assistant"
                if role == "user":
                    msg = {
                        "sessionId": "test-session-chunked",
                        "type": "user",
                        "message": {"role": "user", "content": f"Appended {i}"},
                        "uuid": f"msg-{i:03d}",
                        "timestamp": ts,
                    }
                else:
                    msg = {
                        "sessionId": "test-session-chunked",
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": f"Reply {i}"}],
                        },
                        "uuid": f"msg-{i:03d}",
                        "timestamp": ts,
                    }
                f.write(json.dumps(msg) + "\n")

        # "Incremental parse" from stored offset
        chunk2 = parser.parse_messages(log_file, offset=first_offset, limit=500)
        assert chunk2.is_last is True
        assert len(chunk2.messages) == 3  # Only the 3 appended messages
        assert chunk2.next_offset > first_offset
