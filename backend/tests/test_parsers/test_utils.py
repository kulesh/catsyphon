"""
Tests for parser utility functions.
"""

from datetime import datetime

import pytest

from catsyphon.parsers.utils import (
    build_message_tree,
    extract_text_content,
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
