"""
Parser registry for auto-detecting and routing conversation log formats.

The registry maintains a collection of parser implementations and provides
automatic format detection to route log files to the appropriate parser.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.base import ConversationParser, EmptyFileError, ParseFormatError
from catsyphon.parsers.incremental import IncrementalParser
from catsyphon.parsers.metadata import ParserMetadata
from catsyphon.parsers.types import ParseResult, ProbeResult

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

    def _sorted_parsers(self, file_path: Path) -> list[ConversationParser]:
        """
        Order parsers using metadata priority and format support.

        Parsers that don't declare metadata fall back to priority 50.
        Parsers that list supported formats but don't include this file
        extension are deprioritized.
        """

        def score(parser: ConversationParser) -> tuple[int, int]:
            priority = 50
            format_penalty = 0
            metadata: Optional[ParserMetadata] = getattr(parser, "metadata", None)
            if metadata:
                priority = metadata.priority
                if metadata.supported_formats and not metadata.supports_format(
                    file_path.suffix
                ):
                    # Penalize but still allow can_parse() to reject definitively
                    format_penalty = -100
            return (priority + format_penalty, 0)

        return sorted(self._parsers, key=lambda p: score(p), reverse=True)

    def parse_with_metadata(self, file_path: Path) -> ParseResult:
        """
        Parse a conversation log file with automatic format detection and metadata.

        Args:
            file_path: Path to the log file to parse

        Returns:
            ParseResult containing ParsedConversation and parser metadata

        Raises:
            ParseFormatError: If no parser can handle the file format
            ParseDataError: If the file is malformed
            FileNotFoundError: If the file doesn't exist

        Example:
            >>> registry = ParserRegistry()
            >>> registry.register(ClaudeCodeParser())
            >>> result = registry.parse_with_metadata(Path("log.jsonl"))
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")

        # Check for empty files early - these are often abandoned sessions
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise EmptyFileError(f"Log file is empty (0 bytes): {file_path}")

        attempts: list[str] = []
        parse_errors: list[str] = []

        # Try each registered parser
        for parser in self._sorted_parsers(file_path):
            parser_name = type(parser).__name__
            logger.debug(f"Trying parser: {parser_name}")

            # Probe
            try:
                probe_fn = getattr(parser, "probe", None)
                if callable(probe_fn):
                    probe: ProbeResult = probe_fn(file_path)
                    can_parse = probe.can_parse
                    reasons = probe.reasons
                    confidence = probe.confidence
                else:
                    can_parse = parser.can_parse(file_path)
                    reasons = ["can_parse returned True"] if can_parse else []
                    confidence = 0.5
            except Exception as probe_error:
                probe_msg = f"{parser_name} probe failed: {probe_error}"
                attempts.append(probe_msg)
                logger.debug(probe_msg)
                continue

            if not can_parse:
                attempts.append(f"{parser_name} skipped (probe negative)")
                continue

            # Parse
            try:
                parse_start = time.time() * 1000
                parsed = parser.parse(file_path)
                parse_duration_ms = (time.time() * 1000) - parse_start
            except Exception as parse_error:
                error_msg = f"{parser_name} parse failed: {parse_error}"
                parse_errors.append(error_msg)
                logger.debug(error_msg, exc_info=True)
                continue

            parser_meta: Optional[ParserMetadata] = getattr(parser, "metadata", None)
            parser_meta_name = parser_meta.name if parser_meta else parser_name.lower()
            parser_meta_version = parser_meta.version if parser_meta else None

            # Attach parser metadata to parsed output for downstream observability
            if parser_meta is not None:
                existing_meta = getattr(parsed, "metadata", {}) or {}
                existing_meta["parser"] = {
                    "name": parser_meta.name,
                    "version": parser_meta.version,
                    "confidence": confidence,
                    "reasons": reasons,
                }
                parsed.metadata = existing_meta

            metrics = {"parse_duration_ms": parse_duration_ms}

            # Retrieve collected issues from parser if available
            collected_issues = []
            if hasattr(parser, "get_collected_issues"):
                collected_issues = parser.get_collected_issues()

            result = ParseResult(
                conversation=parsed,
                parser_name=parser_meta_name,
                parser_version=parser_meta_version,
                parse_method="full",
                change_type=None,
                metrics=metrics,
                warnings=[],  # Legacy field
                issues=collected_issues,
            )

            return result

        # No parser could handle this file
        attempted = (
            "; ".join(attempts + parse_errors)
            if (attempts or parse_errors)
            else "no parsers registered"
        )
        raise ParseFormatError(
            f"No parser could handle file format: {file_path}. Attempts: {attempted}"
        )

    def parse(self, file_path: Path) -> ParsedConversation:
        """
        Backwards-compatible parse that returns ParsedConversation only.

        Use parse_with_metadata() for richer observability.
        """
        return self.parse_with_metadata(file_path).conversation

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

        for parser in self._sorted_parsers(file_path):
            try:
                probe_fn = getattr(parser, "probe", None)
                if callable(probe_fn):
                    probe: ProbeResult = probe_fn(file_path)
                    if probe.can_parse:
                        return parser
                    continue

                if parser.can_parse(file_path):
                    return parser
            except Exception as e:
                logger.debug(f"Parser {type(parser).__name__} check failed: {e}")
                continue

        return None

    def find_incremental_parser(self, file_path: Path) -> Optional[IncrementalParser]:
        """
        Find a parser that supports incremental parsing for the given file.

        Args:
            file_path: Path to the log file

        Returns:
            The first parser that supports incremental parsing for this file,
            or None if no match found

        Note:
            This method checks both:
            1. If the parser can handle the file format (can_parse)
            2. If the parser implements IncrementalParser protocol
            3. If the parser supports incremental mode for this specific file

        Example:
            >>> registry = get_default_registry()
            >>> parser = registry.find_incremental_parser(Path("log.jsonl"))
            >>> if parser:
            ...     result = parser.parse_incremental(path, offset, line)
        """
        if not file_path.exists():
            return None

        for parser in self._parsers:
            try:
                # Check if parser can handle this file format
                probe_fn = getattr(parser, "probe", None)
                if callable(probe_fn):
                    probe: ProbeResult = probe_fn(file_path)
                    if not probe.can_parse:
                        continue
                else:
                    if not parser.can_parse(file_path):
                        continue

                # Check if parser implements IncrementalParser protocol
                if not isinstance(parser, IncrementalParser):
                    continue

                # Check if parser supports incremental parsing for this specific file
                if hasattr(parser, "supports_incremental"):
                    if not parser.supports_incremental(file_path):
                        continue

                # Found a matching incremental parser
                return parser

            except Exception as e:
                logger.debug(
                    f"Parser {type(parser).__name__} incremental check failed: {e}"
                )
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
        from catsyphon.parsers.codex import CodexParser

        _default_registry.register(ClaudeCodeParser())
        _default_registry.register(CodexParser())

        logger.debug("Initialized default parser registry")

        # Load optional external parsers from configuration
        try:
            from importlib import import_module

            from catsyphon.config import settings

            modules = []
            if getattr(settings, "parser_modules", None):
                # Accept comma- or space-separated env values
                if isinstance(settings.parser_modules, str):
                    modules = [
                        m.strip()
                        for m in settings.parser_modules.split(",")
                        if m.strip()
                    ]
                else:
                    modules = list(settings.parser_modules)

            for module_path in modules:
                try:
                    module = import_module(module_path)
                    factory = getattr(module, "get_parser", None)
                    parser = (
                        factory()
                        if callable(factory)
                        else getattr(module, "PARSER", None)
                    )
                    if parser:
                        _default_registry.register(parser)
                        logger.info(f"Loaded external parser from {module_path}")
                    else:
                        logger.warning(
                            f"Module {module_path} did not provide get_parser()/PARSER"
                        )
                except Exception as import_error:
                    logger.warning(
                        f"Failed to load parser module {module_path}: {import_error}"
                    )
        except Exception as e:
            logger.debug(f"Parser plugin load skipped due to error: {e}")

    return _default_registry
