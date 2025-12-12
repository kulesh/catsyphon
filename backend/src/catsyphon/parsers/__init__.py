"""
Conversation log parsers for various coding agent types.

This package provides parsers for different agent log formats, along with
a registry for automatic format detection.
"""

from catsyphon.parsers.base import (
    ConversationParser,
    EmptyFileError,
    ParseDataError,
    ParseFormatError,
    ParserError,
)
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.parsers.codex import CodexParser
from catsyphon.parsers.registry import ParserRegistry, get_default_registry
from catsyphon.parsers.types import ParseResult

__all__ = [
    "ConversationParser",
    "ParserError",
    "ParseFormatError",
    "ParseDataError",
    "EmptyFileError",
    "ClaudeCodeParser",
    "CodexParser",
    "ParserRegistry",
    "get_default_registry",
    "ParseResult",
]
