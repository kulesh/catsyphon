"""
Tests for parser registry.
"""

from pathlib import Path

import pytest

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.base import ParseFormatError
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.parsers.incremental import IncrementalParser
from catsyphon.parsers.registry import ParserRegistry, get_default_registry
from catsyphon.parsers.types import ParseResult

# Get the fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParserRegistry:
    """Tests for ParserRegistry class."""

    def test_register_parser(self):
        """Test registering a parser."""
        registry = ParserRegistry()
        parser = ClaudeCodeParser()

        registry.register(parser)

        assert len(registry.registered_parsers) == 1
        assert "ClaudeCodeParser" in registry.registered_parsers

    def test_parse_with_registered_parser(self):
        """Test parsing with a registered parser."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        result = registry.parse(log_file)

        assert isinstance(result, ParsedConversation)
        assert result.agent_type == "claude-code"

    def test_parse_nonexistent_file_raises_error(self):
        """Test that parsing nonexistent file raises FileNotFoundError."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "does_not_exist.jsonl"

        with pytest.raises(FileNotFoundError):
            registry.parse(log_file)

    def test_parse_unsupported_format_raises_error(self):
        """Test that parsing unsupported format raises ParseFormatError."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "not_a_log.txt"

        with pytest.raises(ParseFormatError):
            registry.parse(log_file)

    def test_find_parser_for_valid_file(self):
        """Test finding parser for valid file."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        parser = registry.find_parser(log_file)

        assert parser is not None
        assert isinstance(parser, ClaudeCodeParser)

    def test_find_parser_returns_none_for_invalid_file(self):
        """Test that find_parser returns None for invalid file."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "not_a_log.txt"
        parser = registry.find_parser(log_file)

        assert parser is None

    def test_find_parser_returns_none_for_nonexistent_file(self):
        """Test that find_parser returns None for nonexistent file."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "does_not_exist.jsonl"
        parser = registry.find_parser(log_file)

        assert parser is None

    def test_empty_registry_raises_error(self):
        """Test that parsing with empty registry raises error."""
        registry = ParserRegistry()

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"

        with pytest.raises(ParseFormatError, match="No parser could handle"):
            registry.parse(log_file)

    def test_empty_file_raises_empty_file_error(self, tmp_path):
        """Test that parsing an empty file raises EmptyFileError.

        Empty files are common - they represent abandoned sessions that were
        created but never had any messages. These should be skipped gracefully
        rather than treated as parse failures.
        """
        from catsyphon.parsers import EmptyFileError

        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        # Create an empty .jsonl file
        empty_file = tmp_path / "empty_session.jsonl"
        empty_file.write_text("")

        with pytest.raises(EmptyFileError, match="Log file is empty"):
            registry.parse(empty_file)

    def test_parse_with_metadata_returns_parse_result(self):
        """Test parse_with_metadata returns ParseResult with parser info."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        result = registry.parse_with_metadata(log_file)

        assert isinstance(result, ParseResult)
        assert result.conversation.agent_type == "claude-code"
        assert result.parser_name == "claude-code"
        assert result.parse_method == "full"


class TestIncrementalParserFinding:
    """Tests for finding incremental parsers.

    REGRESSION TESTS: These tests prevent a critical bug where incremental
    parsing was never used due to missing @runtime_checkable decorator on
    IncrementalParser protocol (fixed in commit eba5cd5).
    """

    def test_find_incremental_parser_for_valid_file(self):
        """Test finding incremental parser for valid file.

        CRITICAL: This test verifies that isinstance(parser, IncrementalParser)
        works correctly, which requires @runtime_checkable decorator.
        """
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        parser = registry.find_incremental_parser(log_file)

        # Bug would cause this to be None due to TypeError in isinstance() check
        assert parser is not None, (
            "find_incremental_parser() returned None - check that "
            "IncrementalParser has @runtime_checkable decorator"
        )
        assert isinstance(parser, ClaudeCodeParser)
        assert hasattr(parser, "parse_incremental")

    def test_incremental_parser_implements_protocol(self):
        """Test that ClaudeCodeParser correctly implements IncrementalParser protocol.

        This verifies the @runtime_checkable decorator allows isinstance() checks.
        """
        parser = ClaudeCodeParser()

        # This would raise TypeError without @runtime_checkable
        assert isinstance(parser, IncrementalParser), (
            "ClaudeCodeParser should implement IncrementalParser protocol - "
            "check that IncrementalParser has @runtime_checkable decorator"
        )

    def test_find_incremental_parser_returns_none_for_invalid_file(self):
        """Test that find_incremental_parser returns None for invalid file."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "not_a_log.txt"
        parser = registry.find_incremental_parser(log_file)

        assert parser is None

    def test_find_incremental_parser_returns_none_for_nonexistent_file(self):
        """Test that find_incremental_parser returns None for nonexistent file."""
        registry = ParserRegistry()
        registry.register(ClaudeCodeParser())

        log_file = FIXTURES_DIR / "does_not_exist.jsonl"
        parser = registry.find_incremental_parser(log_file)

        assert parser is None

    def test_find_incremental_parser_with_empty_registry(self):
        """Test that find_incremental_parser returns None with empty registry."""
        registry = ParserRegistry()

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        parser = registry.find_incremental_parser(log_file)

        assert parser is None

    def test_default_registry_finds_incremental_parser(self):
        """Test that default registry can find incremental parsers.

        This is the integration test for the real-world usage in watch daemon.
        """
        registry = get_default_registry()

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        parser = registry.find_incremental_parser(log_file)

        assert parser is not None, (
            "Default registry should find incremental parser for .jsonl files"
        )
        assert hasattr(parser, "parse_incremental")
        assert hasattr(parser, "supports_incremental")


class TestDefaultRegistry:
    """Tests for default global registry."""

    def test_get_default_registry_returns_singleton(self):
        """Test that get_default_registry returns same instance."""
        registry1 = get_default_registry()
        registry2 = get_default_registry()

        assert registry1 is registry2

    def test_default_registry_has_claude_code_parser(self):
        """Test that default registry includes ClaudeCodeParser."""
        registry = get_default_registry()

        assert "ClaudeCodeParser" in registry.registered_parsers

    def test_default_registry_can_parse_claude_code_logs(self):
        """Test that default registry can parse Claude Code logs."""
        registry = get_default_registry()

        log_file = FIXTURES_DIR / "minimal_conversation.jsonl"
        result = registry.parse(log_file)

        assert isinstance(result, ParsedConversation)
        assert result.agent_type == "claude-code"
