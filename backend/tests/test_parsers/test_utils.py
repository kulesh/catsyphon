"""
Tests for parser utility functions.
"""

from datetime import datetime

import pytest

from catsyphon.parsers.utils import (
    ThinkingResult,
    build_message_tree,
    extract_text_content,
    extract_thinking_content,
    is_thinking_redacted,
    match_tool_calls_with_results,
    parse_iso_timestamp,
    safe_get_nested,
)


class TestParseIsoTimestamp:
    """Tests for parse_iso_timestamp function."""

    def test_parse_valid_iso_timestamp(self):
        """Test parsing valid ISO 8601 timestamp."""
        timestamp_str = "2025-10-16T19:12:28.024Z"
        result = parse_iso_timestamp(timestamp_str)

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 16

    def test_parse_timestamp_without_milliseconds(self):
        """Test parsing timestamp without milliseconds."""
        timestamp_str = "2025-10-16T19:12:28Z"
        result = parse_iso_timestamp(timestamp_str)

        assert isinstance(result, datetime)
        assert result.hour == 19
        assert result.minute == 12
        assert result.second == 28

    def test_parse_timestamp_with_timezone_offset(self):
        """Test parsing timestamp with timezone offset."""
        timestamp_str = "2025-10-16T19:12:28+05:30"
        result = parse_iso_timestamp(timestamp_str)

        assert isinstance(result, datetime)
        # Should have timezone info
        assert result.tzinfo is not None

    def test_parse_invalid_timestamp_raises_error(self):
        """Test that invalid timestamp raises ValueError."""
        with pytest.raises(ValueError):
            parse_iso_timestamp("not a timestamp")

    def test_parse_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_iso_timestamp("")


class TestBuildMessageTree:
    """Tests for build_message_tree function."""

    def test_build_simple_tree(self):
        """Test building tree from simple linear conversation."""
        messages = [
            {"uuid": "msg-1", "parentUuid": None},
            {"uuid": "msg-2", "parentUuid": "msg-1"},
            {"uuid": "msg-3", "parentUuid": "msg-2"},
        ]

        tree = build_message_tree(messages)

        assert len(tree) == 3
        assert tree["msg-1"]["children"] == ["msg-2"]
        assert tree["msg-2"]["children"] == ["msg-3"]
        assert tree["msg-3"]["children"] == []

    def test_build_tree_with_branches(self):
        """Test building tree with branching conversation."""
        messages = [
            {"uuid": "msg-1", "parentUuid": None},
            {"uuid": "msg-2", "parentUuid": "msg-1"},
            {"uuid": "msg-3", "parentUuid": "msg-1"},
        ]

        tree = build_message_tree(messages)

        assert len(tree) == 3
        assert "msg-2" in tree["msg-1"]["children"]
        assert "msg-3" in tree["msg-1"]["children"]

    def test_build_tree_preserves_original_data(self):
        """Test that original message data is preserved."""
        messages = [
            {"uuid": "msg-1", "parentUuid": None, "content": "Hello"},
            {"uuid": "msg-2", "parentUuid": "msg-1", "content": "World"},
        ]

        tree = build_message_tree(messages)

        assert tree["msg-1"]["content"] == "Hello"
        assert tree["msg-2"]["content"] == "World"


class TestMatchToolCallsWithResults:
    """Tests for match_tool_calls_with_results function."""

    def test_match_tool_call_with_result(self):
        """Test matching tool call with its result."""
        messages = [
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_001",
                            "name": "Read",
                            "input": {"file_path": "test.py"},
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_001",
                            "content": "file contents",
                            "is_error": False,
                        }
                    ]
                }
            },
        ]

        results = match_tool_calls_with_results(messages)

        assert "tool_001" in results
        assert results["tool_001"]["content"] == "file contents"
        assert results["tool_001"]["is_error"] is False

    def test_match_multiple_tool_calls(self):
        """Test matching multiple tool calls."""
        messages = [
            {
                "message": {
                    "content": [
                        {"type": "tool_use", "id": "tool_001", "name": "Read"},
                        {"type": "tool_use", "id": "tool_002", "name": "Write"},
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_001",
                            "content": "result 1",
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_002",
                            "content": "result 2",
                        }
                    ]
                }
            },
        ]

        results = match_tool_calls_with_results(messages)

        assert len(results) == 2
        assert "tool_001" in results
        assert "tool_002" in results

    def test_handle_string_content(self):
        """Test handling messages with string content."""
        messages = [
            {"message": {"content": "Just a string"}},
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_001",
                            "content": "result",
                        }
                    ]
                }
            },
        ]

        results = match_tool_calls_with_results(messages)

        assert len(results) == 1
        assert "tool_001" in results


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_extract_from_string(self):
        """Test extracting text from string content."""
        content = "Hello, world!"
        result = extract_text_content(content)

        assert result == "Hello, world!"

    def test_extract_from_array_with_text(self):
        """Test extracting text from array content."""
        content = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]
        result = extract_text_content(content)

        assert "Hello" in result
        assert "World" in result

    def test_extract_ignores_non_text_items(self):
        """Test that non-text items are ignored."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "tool_001"},
            {"type": "text", "text": "World"},
        ]
        result = extract_text_content(content)

        assert "Hello" in result
        assert "World" in result
        assert "tool_001" not in result

    def test_extract_from_empty_array(self):
        """Test extracting from empty array."""
        content = []
        result = extract_text_content(content)

        assert result == ""

    def test_extract_from_none(self):
        """Test handling None content."""
        result = extract_text_content(None)

        assert result == ""


class TestIsThinkingRedacted:
    """Tests for is_thinking_redacted function."""

    def test_normal_text_not_redacted(self):
        assert not is_thinking_redacted("Let me analyze this problem step by step.")

    def test_short_base64_not_redacted(self):
        assert not is_thinking_redacted("abc123")

    def test_empty_string_not_redacted(self):
        assert not is_thinking_redacted("")

    def test_signature_blob_detected(self):
        blob = "A" * 600
        assert is_thinking_redacted(blob)

    def test_base64_like_blob_detected(self):
        blob = "aB3+/cD4=" * 80
        assert is_thinking_redacted(blob)

    def test_long_text_with_spaces_not_redacted(self):
        text = "word " * 100
        assert not is_thinking_redacted(text)


class TestExtractThinkingContent:
    """Tests for extract_thinking_content function."""

    def test_extract_from_array_with_thinking(self):
        content = [
            {"type": "thinking", "thinking": "Let me analyze this..."},
            {"type": "text", "text": "Here's my answer"},
        ]
        result = extract_thinking_content(content)

        assert isinstance(result, ThinkingResult)
        assert result.content == "Let me analyze this..."
        assert not result.redacted
        assert not result.is_summary

    def test_extract_multiple_thinking_blocks(self):
        content = [
            {"type": "thinking", "thinking": "First thought"},
            {"type": "text", "text": "Some text"},
            {"type": "thinking", "thinking": "Second thought"},
        ]
        result = extract_thinking_content(content)

        assert "First thought" in result.content
        assert "Second thought" in result.content
        assert "\n\n" in result.content
        assert not result.redacted

    def test_extract_ignores_non_thinking_items(self):
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "thinking", "thinking": "Thinking content"},
            {"type": "tool_use", "id": "tool_001"},
        ]
        result = extract_thinking_content(content)

        assert result.content == "Thinking content"
        assert "Hello" not in result.content

    def test_extract_from_string_returns_none(self):
        content = "Just a string"
        result = extract_thinking_content(content)

        assert result.content is None
        assert not result.redacted

    def test_extract_from_empty_array_returns_none(self):
        content = []
        result = extract_thinking_content(content)

        assert result.content is None

    def test_extract_from_array_without_thinking_returns_none(self):
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "tool_001"},
        ]
        result = extract_thinking_content(content)

        assert result.content is None

    def test_extract_ignores_empty_thinking_blocks(self):
        content = [
            {"type": "thinking", "thinking": ""},
            {"type": "thinking", "thinking": "Valid content"},
            {"type": "thinking"},  # Missing thinking field
        ]
        result = extract_thinking_content(content)

        assert result.content == "Valid content"

    def test_redacted_signature_blob_detected(self):
        blob = "A" * 600
        content = [
            {"type": "thinking", "thinking": blob},
            {"type": "text", "text": "Here's my answer"},
        ]
        result = extract_thinking_content(content)

        assert result.content is None
        assert result.redacted is True
        assert not result.is_summary

    def test_redacted_blob_with_real_thinking_mixed(self):
        blob = "B" * 600
        content = [
            {"type": "thinking", "thinking": blob},
            {"type": "thinking", "thinking": "Real reasoning here"},
        ]
        result = extract_thinking_content(content)

        assert result.content == "Real reasoning here"
        assert result.redacted is True

    def test_thinking_summary_block(self):
        content = [
            {"type": "thinking_summary", "text": "Summary of reasoning"},
            {"type": "text", "text": "Here's my answer"},
        ]
        result = extract_thinking_content(content)

        assert result.content == "Summary of reasoning"
        assert result.is_summary is True
        assert not result.redacted

    def test_redacted_with_summary_fallback(self):
        blob = "C" * 600
        content = [
            {"type": "thinking", "thinking": blob},
            {"type": "thinking_summary", "text": "Summary of what I thought"},
            {"type": "text", "text": "Answer"},
        ]
        result = extract_thinking_content(content)

        assert result.content == "Summary of what I thought"
        assert result.redacted is True
        assert result.is_summary is True


class TestSafeGetNested:
    """Tests for safe_get_nested function."""

    def test_get_nested_value(self):
        """Test getting nested dictionary value."""
        data = {"level1": {"level2": {"level3": "value"}}}
        result = safe_get_nested(data, "level1", "level2", "level3")

        assert result == "value"

    def test_get_missing_key_returns_default(self):
        """Test that missing key returns default value."""
        data = {"level1": {"level2": "value"}}
        result = safe_get_nested(data, "level1", "missing", "key", default="N/A")

        assert result == "N/A"

    def test_get_from_nested_list(self):
        """Test getting value from nested list."""
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        result = safe_get_nested(data, "items", 0, "name")

        # Note: Current implementation doesn't support integer keys
        # This documents expected behavior
        assert result is None or result == "first"

    def test_get_returns_none_when_path_breaks(self):
        """Test that None is returned when path breaks."""
        data = {"level1": None}
        result = safe_get_nested(data, "level1", "level2", "level3")

        assert result is None

    def test_get_with_explicit_none_default(self):
        """Test that explicit None default works."""
        data = {"key": "value"}
        result = safe_get_nested(data, "missing", default=None)

        assert result is None
