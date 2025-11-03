"""
Tests for parser registry.
"""

from pathlib import Path

import pytest

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.base import ParseFormatError
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.parsers.registry import ParserRegistry, get_default_registry

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
