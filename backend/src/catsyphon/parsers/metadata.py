"""
Parser metadata definitions for the plugin system.

This module defines the metadata structure that parsers use to declare
their capabilities, supported formats, and other plugin information.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set


class ParserCapability(str, Enum):
    """
    Parser capability flags.

    These flags indicate what features a parser supports beyond basic parsing.
    """

    INCREMENTAL = "incremental_parsing"
    """Parser supports incremental parsing (parse only new content)."""

    BATCH = "batch_processing"
    """Parser can efficiently process multiple files in batch."""

    STREAMING = "streaming"
    """Parser can process large files in streaming mode (low memory)."""


@dataclass
class ParserMetadata:
    """
    Metadata about a parser implementation.

    This class defines information that parsers provide about their
    capabilities, version, and supported formats.

    Attributes:
        name: Parser identifier (e.g., 'claude-code', 'cursor', 'copilot')
        version: Parser version using semantic versioning (e.g., '1.0.0')
        supported_formats: File extensions supported (e.g., ['.jsonl', '.db'])
        capabilities: Set of ParserCapability flags indicating features
        priority: Selection priority (0-100, higher = preferred). Used when
                  multiple parsers can handle the same format.
        description: Optional human-readable description

    Example:
        >>> metadata = ParserMetadata(
        ...     name="cursor",
        ...     version="1.0.0",
        ...     supported_formats=[".db", ".sqlite"],
        ...     capabilities={ParserCapability.BATCH},
        ...     priority=75,
        ... )
    """

    name: str
    version: str
    supported_formats: List[str]
    capabilities: Set[ParserCapability] = field(default_factory=set)
    priority: int = 50
    description: str = ""

    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        if not self.name:
            raise ValueError("Parser name cannot be empty")

        if not self.version:
            raise ValueError("Parser version cannot be empty")

        if not self.supported_formats:
            raise ValueError("Parser must support at least one format")

        if not 0 <= self.priority <= 100:
            raise ValueError("Priority must be between 0 and 100")

        # Normalize file extensions to lowercase
        self.supported_formats = [fmt.lower() for fmt in self.supported_formats]

    def supports_format(self, extension: str) -> bool:
        """
        Check if parser supports a given file extension.

        Args:
            extension: File extension to check (e.g., '.jsonl' or 'jsonl')

        Returns:
            True if format is supported, False otherwise
        """
        # Normalize extension
        if not extension.startswith('.'):
            extension = f'.{extension}'

        return extension.lower() in self.supported_formats

    def has_capability(self, capability: ParserCapability) -> bool:
        """
        Check if parser has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if parser has the capability, False otherwise
        """
        return capability in self.capabilities
