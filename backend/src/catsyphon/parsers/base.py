"""
Base parser protocol and exception classes for conversation log parsers.

This module defines the interface that all conversation log parsers must implement,
as well as common exception types for parser errors.
"""

from pathlib import Path
from typing import Protocol

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.metadata import ParserMetadata


class ParserError(Exception):
    """Base exception for all parser errors."""

    pass


class ParseFormatError(ParserError):
    """Raised when the log format is invalid or unrecognized."""

    pass


class ParseDataError(ParserError):
    """Raised when required data is missing or malformed."""

    pass


class ConversationParser(Protocol):
    """
    Protocol for conversation log parsers.

    All parser implementations must provide these methods to integrate
    with the parser registry and ingestion pipeline.

    BREAKING CHANGE: As of v0.2.0, parsers must provide a `metadata` property.
    """

    @property
    def metadata(self) -> ParserMetadata:
        """
        Get parser metadata.

        Returns:
            ParserMetadata object with parser name, version, capabilities, etc.

        Note:
            This property is required as of v0.2.0. It provides information
            used by the plugin system for parser discovery and selection.
        """
        ...

    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given log file.

        Args:
            file_path: Path to the log file to check

        Returns:
            True if this parser can parse the file, False otherwise

        Note:
            This method should be fast and non-destructive. It should only
            read enough of the file to determine format compatibility.
        """
        ...

    def parse(self, file_path: Path) -> ParsedConversation:
        """
        Parse a conversation log file into structured format.

        Args:
            file_path: Path to the log file to parse

        Returns:
            ParsedConversation object with extracted data

        Raises:
            ParseFormatError: If the file format is invalid
            ParseDataError: If required data is missing or malformed
            ParserError: For other parsing errors

        Note:
            The parser should be resilient and extract as much data as possible,
            even if some parts of the log are malformed. Use default values
            and log warnings rather than failing completely.
        """
        ...
