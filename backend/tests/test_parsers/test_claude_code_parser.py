"""
Tests for Claude Code conversation log parser.
"""

from pathlib import Path

import pytest

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.base import ParseFormatError
from catsyphon.parsers.claude_code import ClaudeCodeParser

# Get the fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestClaudeCodeParserDetection:
    """Tests for format detection (can_parse method)."""

    def test_can_parse_valid_minimal_log(self):
        """Test detection of valid minimal Claude Code log."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        assert parser.can_parse(log_file) is True

    def test_can_parse_valid_full_log(self):
        """Test detection of valid full Claude Code log."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        assert parser.can_parse(log_file) is True

    def test_cannot_parse_text_file(self):
        """Test rejection of plain text file."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "not_a_log.txt"

        assert parser.can_parse(log_file) is False

    def test_cannot_parse_nonexistent_file(self):
        """Test handling of nonexistent file."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "does_not_exist.jsonl"

        assert parser.can_parse(log_file) is False

    def test_cannot_parse_directory(self):
        """Test rejection of directory path."""
        parser = ClaudeCodeParser()

        assert parser.can_parse(FIXTURES_DIR) is False


class TestClaudeCodeParserParsing:
    """Tests for parsing functionality."""

    def test_parse_minimal_conversation(self):
        """Test parsing minimal conversation (just warmup)."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        assert isinstance(result, ParsedConversation)
        assert result.agent_type == "claude-code"
        assert result.agent_version == "2.0.17"
        assert result.session_id == "test-session-001"
        assert result.git_branch == "main"
        assert result.working_directory == "/Users/test/project"
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"

    def test_parse_full_conversation(self):
        """Test parsing full conversation with tool calls."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        assert isinstance(result, ParsedConversation)
        assert result.agent_type == "claude-code"
        assert result.session_id == "test-session-002"
        # 6 messages: warmup (user+assistant), user request, assistant tool call,
        # tool result (user), final assistant response
        assert len(result.messages) == 6

    def test_parse_extracts_timestamps(self):
        """Test that timestamps are correctly extracted."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        assert result.start_time is not None
        assert result.end_time is not None
        assert result.end_time >= result.start_time

    def test_parse_malformed_logs_gracefully(self):
        """Test that parser handles malformed logs gracefully."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "malformed_conversation.jsonl"

        # Should parse what it can, not fail completely
        result = parser.parse(log_file)

        assert isinstance(result, ParsedConversation)
        # Should have parsed the valid message
        assert len(result.messages) >= 1

    def test_parse_nonexistent_file_raises_error(self):
        """Test that parsing nonexistent file raises error."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "does_not_exist.jsonl"

        with pytest.raises(ParseFormatError):
            parser.parse(log_file)

    def test_parse_invalid_format_raises_error(self):
        """Test that parsing invalid format raises error."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "not_a_log.txt"

        with pytest.raises(ParseFormatError):
            parser.parse(log_file)


class TestToolCallExtraction:
    """Tests for tool call extraction."""

    def test_extract_tool_calls_from_full_conversation(self):
        """Test extraction of tool calls from conversation."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        # Find the assistant message with tool calls
        tool_messages = [msg for msg in result.messages if msg.tool_calls]

        assert len(tool_messages) > 0

        # Check the Read tool call
        tool_call = tool_messages[0].tool_calls[0]
        assert tool_call.tool_name == "Read"
        assert tool_call.parameters["file_path"] == "README.md"
        assert tool_call.result is not None
        assert "Test Project" in tool_call.result
        assert tool_call.success is True

    def test_tool_call_has_parameters(self):
        """Test that tool calls include parameters."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        tool_messages = [msg for msg in result.messages if msg.tool_calls]
        tool_call = tool_messages[0].tool_calls[0]

        assert isinstance(tool_call.parameters, dict)
        assert "file_path" in tool_call.parameters

    def test_tool_call_matched_with_result(self):
        """Test that tool calls are matched with their results."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        tool_messages = [msg for msg in result.messages if msg.tool_calls]
        tool_call = tool_messages[0].tool_calls[0]

        # Result should be populated
        assert tool_call.result is not None
        assert len(tool_call.result) > 0


class TestMessageExtraction:
    """Tests for message extraction and content parsing."""

    def test_extract_user_message_content(self):
        """Test extraction of user message content."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        user_msg = result.messages[0]
        assert user_msg.role == "user"
        assert user_msg.content == "Warmup"

    def test_extract_assistant_message_content(self):
        """Test extraction of assistant message content."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        assistant_msg = result.messages[1]
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == "Warmup complete"

    def test_extract_model_info(self):
        """Test extraction of model information."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        assistant_msg = result.messages[1]
        assert assistant_msg.model == "claude-sonnet-4-5-20250929"

    def test_extract_token_usage(self):
        """Test extraction of token usage statistics."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        result = parser.parse(log_file)

        assistant_msg = result.messages[1]
        assert assistant_msg.token_usage is not None
        assert assistant_msg.token_usage["input_tokens"] == 10
        assert assistant_msg.token_usage["output_tokens"] == 5

    def test_messages_ordered_by_timestamp(self):
        """Test that messages are ordered chronologically."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        timestamps = [msg.timestamp for msg in result.messages]
        assert timestamps == sorted(timestamps)


class TestCodeChangeDetection:
    """Tests for code change detection from tool calls."""

    def test_code_changes_empty_without_edit_write(self):
        """Test that conversations without Edit/Write have no code changes."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        # This conversation only has Read tool, no edits
        assert len(result.code_changes) == 0

    def test_files_touched_includes_read_files(self):
        """Test that files_touched includes files from Read tool."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "full_conversation.jsonl"

        result = parser.parse(log_file)

        # Note: Current implementation only tracks Edit/Write changes
        # This test documents expected behavior for Read tool
        # May need to update if we want to track reads separately
        assert isinstance(result.files_touched, list)


class TestUtilityMethods:
    """Tests for internal utility methods."""

    def test_parse_all_lines_skips_invalid_json(self):
        """Test that invalid JSON lines are skipped."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "malformed_conversation.jsonl"

        messages = parser._parse_all_lines(log_file)

        # Should have parsed the 2 valid lines, skipped the invalid one
        assert len(messages) == 2

    def test_parse_all_lines_handles_empty_lines(self):
        """Test that empty lines are skipped."""
        parser = ClaudeCodeParser()
        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        messages = parser._parse_all_lines(log_file)

        # Should have exactly 2 messages
        assert len(messages) == 2


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_parse_empty_file_raises_error(self, tmp_path):
        """Test parsing empty file raises appropriate error."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")

        parser = ClaudeCodeParser()

        with pytest.raises(ParseFormatError):
            parser.parse(empty_file)

    def test_convert_to_parsed_message_handles_missing_timestamp(self):
        """Test that missing timestamp is handled gracefully."""
        parser = ClaudeCodeParser()

        msg_data = {
            "message": {"role": "user", "content": "Test"},
            "uuid": "test-uuid",
            # Missing timestamp
        }

        result = parser._convert_to_parsed_message(msg_data, {})

        # Should return None for missing timestamp
        assert result is None

    def test_extract_tool_call_handles_missing_fields(self):
        """Test tool call extraction with missing fields."""
        parser = ClaudeCodeParser()

        # Missing tool_use_id
        tool_use_item = {"name": "Read"}

        result = parser._extract_tool_call(tool_use_item, {})

        assert result is None

    def test_detect_code_changes_with_write_tool(self):
        """Test code change detection for Write tool."""
        from catsyphon.models.parsed import ToolCall

        parser = ClaudeCodeParser()

        tool_calls = [
            ToolCall(
                tool_name="Write",
                parameters={"file_path": "test.py", "content": "print('hello')"},
                result="File written",
                success=True,
            )
        ]

        changes = parser._detect_code_changes(tool_calls)

        assert len(changes) == 1
        assert changes[0].file_path == "test.py"
        assert changes[0].change_type == "create"

    def test_detect_code_changes_with_edit_tool(self):
        """Test code change detection for Edit tool."""
        from catsyphon.models.parsed import ToolCall

        parser = ClaudeCodeParser()

        tool_calls = [
            ToolCall(
                tool_name="Edit",
                parameters={
                    "file_path": "test.py",
                    "old_string": "old",
                    "new_string": "new",
                },
                result="File edited",
                success=True,
            )
        ]

        changes = parser._detect_code_changes(tool_calls)

        assert len(changes) == 1
        assert changes[0].file_path == "test.py"
        assert changes[0].change_type == "edit"
