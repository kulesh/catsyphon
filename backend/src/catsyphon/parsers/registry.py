"""
Parser registry for auto-detecting and routing conversation log formats.

The registry maintains a collection of parser implementations and provides
automatic format detection to route log files to the appropriate parser.
"""

import logging
from pathlib import Path
from typing import Optional

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.base import ConversationParser, ParseFormatError

logger = logging.getLogger(__name__)


class ParserRegistry:
    """
    Registry for conversation log parsers with auto-detection.

    The registry maintains a list of parser implementations and provides
    automatic format detection. When parsing a file, it tries each parser's
    can_parse() method and uses the first match.

    Example:
        >>> from catsyphon.parsers.claude_code import ClaudeCodeParser
        >>> registry = ParserRegistry()
        >>> registry.register(ClaudeCodeParser())
        >>> conversation = registry.parse(Path("conversation.jsonl"))
    """

    def __init__(self) -> None:
        """Initialize an empty parser registry."""
        self._parsers: list[ConversationParser] = []

    def register(self, parser: ConversationParser) -> None:
        """
        Register a parser implementation.

        Args:
            parser: Parser instance implementing the ConversationParser protocol

        Note:
            Parsers are tried in registration order. Register more specific
            parsers before generic ones to ensure correct detection.
        """
        self._parsers.append(parser)
        logger.debug(f"Registered parser: {type(parser).__name__}")

    def parse(self, file_path: Path) -> ParsedConversation:
        """
        Parse a conversation log file with automatic format detection.

        Args:
            file_path: Path to the log file to parse

        Returns:
            ParsedConversation object from the appropriate parser

        Raises:
            ParseFormatError: If no parser can handle the file format
            ParseDataError: If the file is malformed
            FileNotFoundError: If the file doesn't exist

        Example:
            >>> registry = ParserRegistry()
            >>> registry.register(ClaudeCodeParser())
            >>> conversation = registry.parse(Path("log.jsonl"))
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")

        # Try each registered parser
        for parser in self._parsers:
            parser_name = type(parser).__name__
            logger.debug(f"Trying parser: {parser_name}")

            try:
                if parser.can_parse(file_path):
                    logger.info(f"Parsing {file_path} with {parser_name}")
                    return parser.parse(file_path)
            except Exception as e:
                logger.debug(f"Parser {parser_name} failed: {e}")
                continue

        # No parser could handle this file
        raise ParseFormatError(
            f"No parser could handle file format: {file_path}. "
            f"Tried {len(self._parsers)} parser(s)."
        )

    def find_parser(self, file_path: Path) -> Optional[ConversationParser]:
        """
        Find a parser that can handle the given file.

        Args:
            file_path: Path to the log file

        Returns:
            The first parser that can handle the file, or None if no match

        Note:
            This method doesn't actually parse the file, just finds a compatible
            parser. Useful for validation or testing.
        """
        if not file_path.exists():
            return None

        for parser in self._parsers:
            try:
                if parser.can_parse(file_path):
                    return parser
            except Exception as e:
                logger.debug(f"Parser {type(parser).__name__} check failed: {e}")
                continue

        return None

    @property
    def registered_parsers(self) -> list[str]:
        """
        Get names of all registered parsers.

        Returns:
            List of parser class names
        """
        return [type(parser).__name__ for parser in self._parsers]


# Global registry instance (singleton pattern)
_default_registry: Optional[ParserRegistry] = None


def get_default_registry() -> ParserRegistry:
    """
    Get the default global parser registry.

    The registry is lazy-initialized on first access and includes
    all built-in parsers.

    Returns:
        Global ParserRegistry instance

    Note:
        This is a singleton. Multiple calls return the same instance.
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = ParserRegistry()

        # Register built-in parsers
        from catsyphon.parsers.claude_code import ClaudeCodeParser

        _default_registry.register(ClaudeCodeParser())

        logger.debug("Initialized default parser registry")

    return _default_registry
