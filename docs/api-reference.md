# CatSyphon Parser API Reference

**Version:** 1.0.0

This document provides technical reference for CatSyphon's parser API, protocols, and data models.

---

## Table of Contents

1. [Parser Protocols](#parser-protocols)
2. [Data Models](#data-models)
3. [Parser Metadata](#parser-metadata)
4. [Incremental Parsing](#incremental-parsing)
5. [Plugin System](#plugin-system)
6. [Exceptions](#exceptions)
7. [OTEL Ingestion API](#otel-ingestion-api)

---

## Parser Protocols

### ConversationParser

**Required interface for all parser plugins.**

```python
from typing import Protocol
from pathlib import Path
from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.metadata import ParserMetadata

class ConversationParser(Protocol):
    """Base protocol for conversation log parsers."""

    @property
    def metadata(self) -> ParserMetadata:
        """
        Get parser metadata.

        Returns:
            ParserMetadata: Parser name, version, capabilities, etc.

        Note:
            Required as of v0.2.0 for plugin system integration.
        """
        ...

    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given log file.

        Args:
            file_path: Path to the log file to check

        Returns:
            bool: True if this parser can parse the file, False otherwise

        Note:
            Should be fast (<10ms) and non-destructive. Only read enough
            to determine format compatibility.
        """
        ...

    def parse(self, file_path: Path) -> ParsedConversation:
        """
        Parse a conversation log file into structured format.

        Args:
            file_path: Path to the log file to parse

        Returns:
            ParsedConversation: Structured conversation data

        Raises:
            ParseFormatError: If the file format is invalid
            ParseDataError: If required data is missing or malformed
            ParserError: For other parsing errors
            FileNotFoundError: If the file doesn't exist

        Note:
            Should be resilient and extract as much data as possible,
            using default values and warnings rather than failing.
        """
        ...
```

### IncrementalParser

**Optional protocol for parsers supporting incremental parsing (10x-106x faster).**

```python
from typing import Protocol
from pathlib import Path
from catsyphon.parsers.incremental import IncrementalParseResult

class IncrementalParser(Protocol):
    """Protocol for parsers that support incremental parsing."""

    def supports_incremental(self, file_path: Path) -> bool:
        """
        Check if incremental parsing is supported for this file.

        Args:
            file_path: Path to the log file

        Returns:
            bool: True if incremental parsing supported, False otherwise

        Note:
            Allows parsers to opt-out on a per-file basis (e.g., for
            corrupted files or formats that require full reparse).
        """
        ...

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """
        Parse only new content appended since last_offset.

        Args:
            file_path: Path to the log file
            last_offset: Byte offset where parsing last stopped
            last_line: Line number where parsing last stopped

        Returns:
            IncrementalParseResult: Only new messages and updated state

        Raises:
            ValueError: If offset is invalid or file format incompatible
        """
        ...
```

---

## Data Models

### ParsedConversation

**Top-level conversation object returned by parsers.**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class ParsedConversation:
    """Structured conversation data extracted from logs."""

    # Messages
    messages: List[ParsedMessage]
    """All messages in the conversation."""

    total_messages: int
    """Total count of messages."""

    user_message_count: int = 0
    """Count of user messages."""

    assistant_message_count: int = 0
    """Count of assistant messages."""

    # Tool calls
    tool_calls: List[ParsedToolCall] = field(default_factory=list)
    """All tool calls made during conversation."""

    # Timing
    start_time: Optional[datetime] = None
    """Timestamp of first message."""

    end_time: Optional[datetime] = None
    """Timestamp of last message."""

    duration_seconds: Optional[float] = None
    """Total conversation duration in seconds."""

    # Files
    files_touched: List[str] = field(default_factory=list)
    """List of file paths read, edited, or written."""

    # Metadata
    model_name: Optional[str] = None
    """AI model used (e.g., 'claude-sonnet-4')."""

    total_input_tokens: int = 0
    """Total input tokens consumed."""

    total_output_tokens: int = 0
    """Total output tokens generated."""

    total_cost_usd: float = 0.0
    """Total estimated cost in USD."""

    # Raw data (optional)
    raw_metadata: dict = field(default_factory=dict)
    """Additional format-specific metadata."""
```

### ParsedMessage

**Individual message in a conversation.**

```python
@dataclass
class ParsedMessage:
    """A single message in a conversation."""

    role: str
    """Message role: 'user', 'assistant', 'system'."""

    content: str
    """Message text content."""

    timestamp: Optional[datetime]
    """When the message was created."""

    message_index: int
    """Sequential index in conversation (0-based)."""

    # Optional fields
    model: Optional[str] = None
    """Model that generated this message (for assistant messages)."""

    input_tokens: Optional[int] = None
    """Input tokens for this message."""

    output_tokens: Optional[int] = None
    """Output tokens for this message."""

    cost_usd: Optional[float] = None
    """Estimated cost for this message."""

    parent_message_id: Optional[str] = None
    """ID of parent message (for branching conversations)."""

    # Tool calls
    tool_calls: List[ParsedToolCall] = field(default_factory=list)
    """Tool calls made in this message."""

    # Raw data
    raw_data: dict = field(default_factory=dict)
    """Original message data (format-specific)."""
```

### ParsedToolCall

**Tool/function call made by the assistant.**

```python
@dataclass
class ParsedToolCall:
    """A tool/function call made by the assistant."""

    name: str
    """Tool name (e.g., 'Read', 'Write', 'Bash')."""

    timestamp: Optional[datetime] = None
    """When the tool was called."""

    # Parameters
    parameters: dict = field(default_factory=dict)
    """Tool input parameters."""

    # Results
    result: Optional[str] = None
    """Tool output/result."""

    error: Optional[str] = None
    """Error message if tool failed."""

    # Matching
    tool_call_id: Optional[str] = None
    """Unique ID for matching calls with results."""

    # Metadata
    duration_ms: Optional[float] = None
    """Tool execution duration in milliseconds."""

    raw_data: dict = field(default_factory=dict)
    """Original tool call data."""
```

---

## Parser Metadata

### ParserMetadata

**Metadata describing a parser's capabilities.**

```python
from dataclasses import dataclass, field
from typing import List, Set
from catsyphon.parsers.metadata import ParserCapability

@dataclass
class ParserMetadata:
    """Metadata about a parser implementation."""

    name: str
    """Unique parser identifier (lowercase-with-hyphens)."""

    version: str
    """Semantic version (e.g., '1.0.0')."""

    supported_formats: List[str]
    """File extensions (e.g., ['.jsonl', '.json'])."""

    capabilities: Set[ParserCapability] = field(default_factory=set)
    """Parser capabilities (BATCH, INCREMENTAL, STREAMING)."""

    priority: int = 50
    """Selection priority (0-100, higher = preferred)."""

    description: str = ""
    """Human-readable description."""

    # Methods
    def supports_format(self, extension: str) -> bool:
        """Check if parser supports a file extension."""
        ...

    def has_capability(self, capability: ParserCapability) -> bool:
        """Check if parser has a specific capability."""
        ...
```

### ParserCapability

**Enum of parser capability flags.**

```python
from enum import Enum

class ParserCapability(str, Enum):
    """Parser capability flags."""

    INCREMENTAL = "incremental_parsing"
    """Supports incremental parsing of appended content."""

    BATCH = "batch_processing"
    """Supports full file parsing."""

    STREAMING = "streaming"
    """Supports streaming/real-time parsing."""
```

---

## Incremental Parsing

### IncrementalParseResult

**Result from incremental parsing operation.**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class IncrementalParseResult:
    """Result from incremental parsing."""

    new_messages: List[ParsedMessage]
    """Only the messages parsed in this incremental update."""

    last_processed_offset: int
    """Byte offset where parsing stopped."""

    last_processed_line: int
    """Line number where parsing stopped."""

    file_size_bytes: int
    """Current file size in bytes."""

    partial_hash: str
    """SHA-256 hash of content up to last_processed_offset."""

    last_message_timestamp: Optional[datetime] = None
    """Timestamp of last message parsed (for validation)."""
```

### ChangeType

**Type of file change detected.**

```python
from enum import Enum

class ChangeType(str, Enum):
    """Type of file change detected."""

    APPEND = "append"
    """New content added to end (incremental parse)."""

    TRUNCATE = "truncate"
    """File size decreased (full reparse required)."""

    REWRITE = "rewrite"
    """Mid-file content changed (full reparse required)."""

    UNCHANGED = "unchanged"
    """No changes detected."""
```

### Utility Functions

```python
def detect_file_change_type(
    file_path: Path,
    last_offset: int,
    last_file_size: int,
    last_partial_hash: Optional[str],
) -> ChangeType:
    """
    Detect what type of change occurred to a file.

    Args:
        file_path: Path to file to check
        last_offset: Byte offset where parsing last stopped
        last_file_size: File size at last parse
        last_partial_hash: SHA-256 hash of content up to last_offset

    Returns:
        ChangeType indicating the type of change

    Examples:
        >>> detect_file_change_type(Path("log.jsonl"), 1000, 1000, "abc123")
        ChangeType.UNCHANGED

        >>> detect_file_change_type(Path("log.jsonl"), 1000, 1000, "abc123")
        ChangeType.APPEND  # If file grew to 1500 bytes
    """
    ...

def calculate_partial_hash(file_path: Path, offset: int) -> str:
    """
    Calculate SHA-256 hash of file content up to offset.

    Args:
        file_path: Path to file
        offset: Byte offset to read up to

    Returns:
        str: Hex-encoded SHA-256 hash

    Raises:
        ValueError: If offset is negative or exceeds file size

    Examples:
        >>> calculate_partial_hash(Path("log.jsonl"), 1000)
        'a7b2c3d4e5f6...'
    """
    ...
```

---

## Plugin System

### PluginMetadata

**Plugin manifest metadata (from catsyphon.json).**

```python
from pydantic import BaseModel, Field

class PluginMetadata(BaseModel):
    """Metadata from plugin manifest file."""

    name: str = Field(
        ...,
        pattern=r"^[a-z0-9-]+$",
        description="Unique plugin name (lowercase-with-hyphens)",
    )

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version (X.Y.Z)",
    )

    description: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Human-readable description",
    )

    parser_class: str = Field(
        ...,
        description="Fully qualified class name (module.Class)",
    )

    supported_formats: List[str] = Field(
        ...,
        min_length=1,
        description="File extensions (e.g., ['.json', '.jsonl'])",
    )

    # Optional fields
    author: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None
    requires_python: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
```

### PluginLoader

**Plugin discovery and loading.**

```python
from typing import List, Optional
from pathlib import Path
from catsyphon.parsers.base import ConversationParser
from catsyphon.plugins.manifest import PluginManifest

class PluginLoader:
    """Discovers and loads parser plugins."""

    # Entry point group for CatSyphon parsers
    ENTRY_POINT_GROUP = "catsyphon.parsers"

    # Default plugin directories
    DEFAULT_PLUGIN_DIRS = [
        Path.home() / ".catsyphon" / "plugins",
        Path(".catsyphon") / "parsers",
    ]

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        enable_entry_points: bool = True,
        enable_directories: bool = True,
    ) -> None:
        """
        Initialize plugin loader.

        Args:
            plugin_dirs: Additional directories to scan
            enable_entry_points: Enable entry point discovery
            enable_directories: Enable directory scanning
        """
        ...

    def discover_plugins(self) -> List[PluginManifest]:
        """
        Discover all available plugins.

        Returns:
            List[PluginManifest]: Discovered plugin manifests

        Note:
            Results are cached. Call again to refresh.
        """
        ...

    def load_plugin(self, name: str) -> ConversationParser:
        """
        Load a specific plugin by name.

        Args:
            name: Plugin name to load

        Returns:
            ConversationParser: Loaded parser instance

        Raises:
            PluginLoadError: If plugin not found or fails to load

        Note:
            Results are cached. Multiple calls return same instance.
        """
        ...

    def load_all_plugins(self) -> List[ConversationParser]:
        """
        Load all discovered plugins.

        Returns:
            List[ConversationParser]: Loaded parser instances

        Note:
            Plugins that fail to load are logged but not included.
        """
        ...

    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """Get manifest for a specific plugin."""
        ...

    def list_plugins(self) -> List[str]:
        """Get names of all discovered plugins."""
        ...

    @property
    def plugin_count(self) -> int:
        """Get count of discovered plugins."""
        ...
```

---

## Exceptions

### Base Exceptions

```python
class ParserError(Exception):
    """Base exception for all parser errors."""
    pass

class ParseFormatError(ParserError):
    """Raised when the log format is invalid or unrecognized."""
    pass

class ParseDataError(ParserError):
    """Raised when required data is missing or malformed."""
    pass
```

### Plugin Exceptions

```python
class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""
    pass
```

### Usage Examples

```python
from catsyphon.parsers.base import ParseFormatError, ParseDataError

def parse(self, file_path: Path) -> ParsedConversation:
    if not file_path.exists():
        raise FileNotFoundError(f"Log file not found: {file_path}")

    if not self.can_parse(file_path):
        raise ParseFormatError(
            f"File {file_path} is not in expected format"
        )

    messages = self._parse_messages(file_path)

    if not messages:
        raise ParseDataError("No messages found in log file")

    return ParsedConversation(messages=messages, ...)
```

---

## OTEL Ingestion API

CatSyphon exposes a minimal OTLP HTTP ingest endpoint for OpenTelemetry logs.
This is opt-in and gated by configuration.

### POST /v1/logs

Ingest OTLP log records for a workspace.

**Headers**
- `Content-Type`: `application/x-protobuf` (preferred) or `application/json`
- `X-Workspace-Id`: workspace UUID (required)
- `X-Catsyphon-Otel-Token`: optional shared secret (if configured)
- `Authorization`: optional `Bearer <token>` (alternate to X-Catsyphon-Otel-Token)

**Request Body**
- OTLP `ExportLogsServiceRequest` payload (protobuf or JSON).

**Responses**
- `200 OK`: events accepted
- `204 No Content`: request parsed but contained no log records
- `400 Bad Request`: invalid payload
- `401 Unauthorized`: token invalid
- `403 Forbidden`: OTEL ingest disabled
- `413 Payload Too Large`: exceeds max payload size

### GET /otel/stats

Basic OTEL ingestion stats for a workspace.

**Headers**
- `X-Workspace-Id`: workspace UUID (required)

**Response**
```json
{
  "total_events": 1200,
  "last_event_at": "2026-01-28T04:12:33.123Z"
}
```

## Version History

### v1.0.0 (2025-01-16)
- Initial API reference
- ConversationParser and IncrementalParser protocols
- ParsedConversation, ParsedMessage, ParsedToolCall models
- ParserMetadata and capabilities system
- Plugin system (PluginLoader, PluginMetadata)
- Incremental parsing utilities

---

## See Also

- [Parser Plugin SDK](./plugin-sdk.md) - Complete guide to creating parsers
- [Parser Quick Start](./parser-quickstart.md) - 15-minute tutorial
- [Implementation Plan](./implementation-plan.md) - Technical architecture
