# CatSyphon Parser Plugin SDK

**Version:** 1.0.0
**Last Updated:** 2025-01-16

This guide provides everything you need to create parser plugins for CatSyphon, enabling support for additional AI coding assistants like Google Gemini, OpenAI Codex, Cursor, GitHub Copilot, and more.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Plugin Architecture](#plugin-architecture)
4. [Creating a Parser](#creating-a-parser)
5. [Incremental Parsing](#incremental-parsing)
6. [Plugin Manifest](#plugin-manifest)
7. [Installation Methods](#installation-methods)
8. [Testing Your Parser](#testing-your-parser)
9. [Best Practices](#best-practices)
10. [Reference Examples](#reference-examples)

---

## Overview

### What are Parser Plugins?

Parser plugins extend CatSyphon to parse conversation logs from different AI coding assistants. Each plugin:

- Detects if it can parse a given log file (format detection)
- Extracts structured conversation data (messages, tool calls, metadata)
- Optionally supports incremental parsing for performance (10x-106x faster)

### Plugin Discovery

CatSyphon uses a **hybrid discovery system**:

1. **Entry Points** (recommended for distribution):
   - Python packages installed via pip
   - Declared in `pyproject.toml` entry points
   - Take precedence over directory plugins

2. **Directory Scanning** (recommended for development):
   - `~/.catsyphon/plugins/` (user plugins)
   - `.catsyphon/parsers/` (project-specific plugins)
   - Each subdirectory with `catsyphon.json` is a plugin

---

## Quick Start

### Minimal Parser (30 lines)

```python
# my_parser.py
from pathlib import Path
from catsyphon.parsers.base import ConversationParser
from catsyphon.parsers.metadata import ParserMetadata, ParserCapability
from catsyphon.models.parsed import ParsedConversation, ParsedMessage

class MyParser:
    """Parser for My AI Assistant logs."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="my-assistant",
            version="1.0.0",
            supported_formats=[".json", ".jsonl"],
            capabilities={ParserCapability.BATCH},
            priority=50,
            description="Parser for My AI Assistant conversation logs",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path: Path) -> bool:
        """Check if file is compatible."""
        if not file_path.suffix.lower() in [".json", ".jsonl"]:
            return False

        # Check first line for format markers
        with open(file_path) as f:
            first_line = f.readline()
            return "my_assistant_marker" in first_line

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse the log file."""
        messages = []

        # TODO: Parse your log format
        # Extract messages, tool calls, timestamps, etc.

        return ParsedConversation(
            messages=messages,
            total_messages=len(messages),
            # ... other fields
        )
```

### Manifest File (`catsyphon.json`)

```json
{
  "name": "my-assistant-parser",
  "version": "1.0.0",
  "description": "Parser for My AI Assistant conversation logs",
  "parser_class": "my_parser.MyParser",
  "supported_formats": [".json", ".jsonl"],
  "author": "Your Name",
  "homepage": "https://github.com/yourname/my-assistant-parser",
  "license": "MIT"
}
```

### Directory Installation

```bash
# Create plugin directory
mkdir -p ~/.catsyphon/plugins/my-assistant-parser

# Copy files
cp my_parser.py ~/.catsyphon/plugins/my-assistant-parser/
cp catsyphon.json ~/.catsyphon/plugins/my-assistant-parser/

# CatSyphon will auto-discover on next run
```

---

## Plugin Architecture

### Core Protocols

CatSyphon uses Python's Protocol classes (PEP 544) for type-safe, duck-typed interfaces:

```python
from typing import Protocol
from pathlib import Path
from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.metadata import ParserMetadata

class ConversationParser(Protocol):
    """Required interface for all parsers."""

    @property
    def metadata(self) -> ParserMetadata:
        """Parser metadata (name, version, capabilities)."""
        ...

    def can_parse(self, file_path: Path) -> bool:
        """Fast format detection (no parsing)."""
        ...

    def parse(self, file_path: Path) -> ParsedConversation:
        """Full parse into structured format."""
        ...
```

### Data Flow

```
Log File → can_parse() → parse() → ParsedConversation → Database
                ↓
        IncrementalParser? → parse_incremental() → IncrementalParseResult
```

---

## Creating a Parser

### Step 1: Understand Your Log Format

Before writing code, analyze your target log format:

**Example: Gemini Code Assist Logs**
```json
{
  "timestamp": "2025-01-16T10:30:00Z",
  "role": "user",
  "content": "Add a login form to the app"
}
{
  "timestamp": "2025-01-16T10:30:15Z",
  "role": "model",
  "content": "I'll create a login form...",
  "tools_used": ["write_file", "read_file"]
}
```

**Key Questions:**
- What file extension(s)? (`.json`, `.jsonl`, `.log`, `.db`)
- Line-based (JSONL) or single JSON blob?
- How are messages structured?
- How are tool calls represented?
- Are there unique format markers for detection?

### Step 2: Implement `can_parse()`

Fast detection without full parsing:

```python
def can_parse(self, file_path: Path) -> bool:
    """
    Quick format check. Should be fast (<10ms).

    Best Practices:
    - Check file extension first (fastest)
    - Read only first 1-10 lines (not entire file)
    - Look for unique format markers
    - Return False quickly if not compatible
    """
    # Extension check
    if file_path.suffix.lower() not in [".json", ".jsonl"]:
        return False

    # File must exist and be readable
    if not file_path.exists() or file_path.is_dir():
        return False

    # Check for format-specific markers
    try:
        with open(file_path, encoding="utf-8") as f:
            # Read first few lines
            for i, line in enumerate(f):
                if i >= 10:  # Don't read too much
                    break

                # Look for unique identifiers
                if "gemini_code_assist" in line.lower():
                    return True
                if '"model":"gemini-' in line:
                    return True

        return False

    except Exception:
        # If we can't read it, we can't parse it
        return False
```

### Step 3: Implement `parse()`

Full parsing into `ParsedConversation`:

```python
import json
from datetime import datetime
from catsyphon.models.parsed import (
    ParsedConversation,
    ParsedMessage,
    ParsedToolCall,
)

def parse(self, file_path: Path) -> ParsedConversation:
    """
    Parse entire log file.

    Returns:
        ParsedConversation with all messages, tool calls, metadata

    Raises:
        ParseFormatError: Invalid format
        ParseDataError: Missing required data
    """
    messages = []
    tool_calls = []

    with open(file_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue  # Skip empty lines

            try:
                data = json.loads(line)

                # Extract message
                message = self._parse_message(data, line_num)
                messages.append(message)

                # Extract tool calls if present
                if "tools_used" in data:
                    for tool_name in data["tools_used"]:
                        tool_call = ParsedToolCall(
                            name=tool_name,
                            timestamp=message.timestamp,
                            # ... other fields
                        )
                        tool_calls.append(tool_call)

            except json.JSONDecodeError as e:
                # Log warning but continue (resilient parsing)
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
                continue

    # Build conversation metadata
    return ParsedConversation(
        messages=messages,
        tool_calls=tool_calls,
        total_messages=len(messages),
        user_message_count=sum(1 for m in messages if m.role == "user"),
        assistant_message_count=sum(1 for m in messages if m.role == "assistant"),
        start_time=messages[0].timestamp if messages else None,
        end_time=messages[-1].timestamp if messages else None,
        # ... other fields
    )

def _parse_message(self, data: dict, line_num: int) -> ParsedMessage:
    """Helper to parse a single message."""
    return ParsedMessage(
        role=data.get("role", "unknown"),
        content=data.get("content", ""),
        timestamp=self._parse_timestamp(data.get("timestamp")),
        message_index=line_num,
        # ... other fields
    )

def _parse_timestamp(self, ts_string: str) -> datetime:
    """Parse ISO 8601 timestamp."""
    return datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
```

### Step 4: Add Metadata

Provide parser metadata for discovery:

```python
from catsyphon.parsers.metadata import ParserMetadata, ParserCapability

def __init__(self):
    self._metadata = ParserMetadata(
        name="gemini-code-assist",  # Unique identifier (lowercase-with-hyphens)
        version="1.0.0",  # Semantic version
        supported_formats=[".json", ".jsonl"],  # File extensions
        capabilities={ParserCapability.BATCH},  # Or INCREMENTAL, STREAMING
        priority=50,  # 0-100, higher = preferred (default: 50)
        description="Parser for Google Gemini Code Assist conversation logs",
    )

@property
def metadata(self):
    return self._metadata
```

---

## Incremental Parsing

### Why Incremental Parsing?

**Performance Benefits:**
- **10x-106x faster** for appended files
- **45x-465x less memory** usage
- **Essential for live monitoring** (watch daemon)

**When to Use:**
- Line-based formats (JSONL, log files)
- Append-only logs (new messages added to end)
- Large files (>1000 messages)

### Implementing `IncrementalParser`

```python
from catsyphon.parsers.incremental import (
    IncrementalParser,
    IncrementalParseResult,
    calculate_partial_hash,
)

class MyParser(IncrementalParser):
    """Parser with incremental support."""

    def supports_incremental(self, file_path: Path) -> bool:
        """
        Check if incremental parsing is supported for this file.

        Return False for:
        - Corrupted files
        - Non-append-only formats
        - Binary formats requiring full reparse
        """
        return self.can_parse(file_path)

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """
        Parse only NEW content since last_offset.

        Args:
            file_path: Log file path
            last_offset: Byte offset where we last stopped
            last_line: Line number where we last stopped

        Returns:
            IncrementalParseResult with only new messages
        """
        new_messages = []
        current_offset = last_offset
        current_line = last_line

        # Open file and seek to last position
        with open(file_path, "rb") as f:
            f.seek(last_offset)

            for line in f:
                current_line += 1
                line_str = line.decode("utf-8")

                if not line_str.strip():
                    current_offset += len(line)
                    continue

                try:
                    data = json.loads(line_str)
                    message = self._parse_message(data, current_line)
                    new_messages.append(message)

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON at line {current_line}")

                current_offset += len(line)

        # Calculate hash of content up to current position
        file_size = file_path.stat().st_size
        partial_hash = calculate_partial_hash(file_path, current_offset)

        return IncrementalParseResult(
            new_messages=new_messages,
            last_processed_offset=current_offset,
            last_processed_line=current_line,
            file_size_bytes=file_size,
            partial_hash=partial_hash,
            last_message_timestamp=new_messages[-1].timestamp if new_messages else None,
        )
```

### Capabilities Flag

Update your metadata to declare incremental support:

```python
self._metadata = ParserMetadata(
    # ... other fields
    capabilities={
        ParserCapability.BATCH,        # Full parsing
        ParserCapability.INCREMENTAL,  # Incremental parsing
    },
)
```

---

## Plugin Manifest

### Schema Reference

The `catsyphon.json` manifest uses Pydantic validation:

```json
{
  "name": "string (required)",
  "version": "string (required, semver: X.Y.Z)",
  "description": "string (required, 10-500 chars)",
  "parser_class": "string (required, module.Class format)",
  "supported_formats": ["array of strings (required, e.g., ['.json'])"],

  "author": "string (optional)",
  "homepage": "string (optional, URL)",
  "license": "string (optional, e.g., 'MIT')",
  "requires_python": "string (optional, e.g., '>=3.11')",
  "dependencies": ["array of strings (optional, e.g., ['requests>=2.28.0'])"]
}
```

### Field Validation

| Field | Type | Pattern | Example |
|-------|------|---------|---------|
| `name` | string | `^[a-z0-9-]+$` | `"gemini-parser"` |
| `version` | string | `^\d+\.\d+\.\d+$` | `"1.0.0"` |
| `description` | string | 10-500 chars | `"Parser for Gemini logs"` |
| `parser_class` | string | `module.Class` | `"gemini.parser.GeminiParser"` |
| `supported_formats` | array | Extensions | `[".json", ".jsonl"]` |

### Complete Example

```json
{
  "name": "gemini-code-assist-parser",
  "version": "1.0.0",
  "description": "Parser for Google Gemini Code Assist conversation logs in JSON/JSONL format",
  "parser_class": "gemini_parser.parser.GeminiParser",
  "supported_formats": [".json", ".jsonl"],

  "author": "Jane Developer",
  "homepage": "https://github.com/janedev/gemini-catsyphon-parser",
  "license": "MIT",
  "requires_python": ">=3.11",
  "dependencies": [
    "catsyphon>=0.2.0"
  ]
}
```

---

## Installation Methods

### Method 1: Directory Installation (Development)

**Best for:**
- Local development
- Testing
- Project-specific parsers

**Steps:**

1. Create plugin directory:
```bash
mkdir -p ~/.catsyphon/plugins/my-parser
```

2. Add your files:
```
~/.catsyphon/plugins/my-parser/
├── catsyphon.json          # Manifest
├── my_parser.py            # Parser implementation
└── __init__.py             # Optional
```

3. CatSyphon auto-discovers on next run:
```bash
catsyphon ingest /path/to/logs
# Your parser will be available
```

### Method 2: Entry Point Installation (Distribution)

**Best for:**
- Public distribution (PyPI)
- Team sharing (private package index)
- Production deployments

**Project Structure:**

```
my-catsyphon-parser/
├── pyproject.toml
├── README.md
├── src/
│   └── my_parser/
│       ├── __init__.py
│       ├── parser.py
│       └── metadata.py
└── tests/
    └── test_parser.py
```

**`pyproject.toml`:**

```toml
[project]
name = "my-catsyphon-parser"
version = "1.0.0"
description = "CatSyphon parser for My AI Assistant"
requires-python = ">=3.11"
dependencies = [
    "catsyphon>=0.2.0",
]

[project.entry-points."catsyphon.parsers"]
my-parser = "my_parser:get_metadata"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**`src/my_parser/__init__.py`:**

```python
from my_parser.parser import MyParser
from catsyphon.plugins.manifest import PluginMetadata

def get_metadata() -> PluginMetadata:
    """Entry point function for plugin discovery."""
    return PluginMetadata(
        name="my-assistant",
        version="1.0.0",
        description="Parser for My AI Assistant logs",
        parser_class="my_parser.parser.MyParser",
        supported_formats=[".json"],
    )

__all__ = ["MyParser", "get_metadata"]
```

**Install:**

```bash
# Development install
pip install -e .

# Production install
pip install my-catsyphon-parser

# From GitHub
pip install git+https://github.com/user/my-catsyphon-parser
```

### Method 3: Project-Specific Parsers

For custom parsers specific to a project:

```bash
# Create in project directory
mkdir -p .catsyphon/parsers/custom-parser

# Add files
cp my_parser.py .catsyphon/parsers/custom-parser/
cp catsyphon.json .catsyphon/parsers/custom-parser/

# Commit to version control
git add .catsyphon/parsers/
```

---

## Testing Your Parser

### Unit Tests

```python
# tests/test_my_parser.py
import pytest
from pathlib import Path
from my_parser import MyParser

@pytest.fixture
def parser():
    return MyParser()

@pytest.fixture
def sample_log(tmp_path):
    """Create a sample log file."""
    log_file = tmp_path / "test.jsonl"
    log_file.write_text("""
{"timestamp": "2025-01-16T10:00:00Z", "role": "user", "content": "Hello"}
{"timestamp": "2025-01-16T10:00:05Z", "role": "assistant", "content": "Hi!"}
    """.strip())
    return log_file

def test_can_parse_valid_log(parser, sample_log):
    """Test format detection."""
    assert parser.can_parse(sample_log) is True

def test_cannot_parse_text_file(parser, tmp_path):
    """Test rejection of wrong format."""
    text_file = tmp_path / "test.txt"
    text_file.write_text("Not a log file")
    assert parser.can_parse(text_file) is False

def test_parse_extracts_messages(parser, sample_log):
    """Test message extraction."""
    conversation = parser.parse(sample_log)

    assert conversation.total_messages == 2
    assert conversation.messages[0].role == "user"
    assert conversation.messages[0].content == "Hello"
    assert conversation.messages[1].role == "assistant"

def test_parse_handles_empty_file(parser, tmp_path):
    """Test resilience to empty files."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")

    with pytest.raises(Exception):  # Or your specific error
        parser.parse(empty_file)
```

### Integration Testing

Test with CatSyphon's plugin loader:

```python
from catsyphon.plugins.loader import PluginLoader

def test_plugin_discovery():
    """Test that plugin is discovered."""
    loader = PluginLoader()
    loader.discover_plugins()

    assert "my-assistant" in loader.list_plugins()

def test_plugin_loading():
    """Test that plugin loads correctly."""
    loader = PluginLoader()
    loader.discover_plugins()

    parser = loader.load_plugin("my-assistant")
    assert parser is not None
    assert hasattr(parser, "can_parse")
    assert hasattr(parser, "parse")
```

### Manual Testing

```bash
# 1. Install your parser
mkdir -p ~/.catsyphon/plugins/my-parser
cp * ~/.catsyphon/plugins/my-parser/

# 2. Test with real log file
catsyphon ingest /path/to/test/log --project "test"

# 3. Verify in database
catsyphon db-status

# 4. Check logs for errors
tail -f ~/.catsyphon/logs/catsyphon.log
```

---

## Best Practices

### Performance

1. **Fast `can_parse()`**:
   - Read only first 1-10 lines
   - Check file extension first
   - Return False early if not compatible
   - Target <10ms execution time

2. **Resilient `parse()`**:
   - Handle malformed JSON gracefully
   - Skip invalid lines, log warnings
   - Don't fail on missing optional fields
   - Use default values for missing data

3. **Memory Efficiency**:
   - Stream large files (don't load all into memory)
   - Use incremental parsing for >1000 messages
   - Release resources in try/finally blocks

### Error Handling

```python
from catsyphon.parsers.base import ParseFormatError, ParseDataError

def parse(self, file_path: Path):
    if not file_path.exists():
        raise FileNotFoundError(f"Log file not found: {file_path}")

    if not self.can_parse(file_path):
        raise ParseFormatError(
            f"File {file_path} is not in expected format"
        )

    messages = []

    try:
        # Parsing logic...
        pass
    except json.JSONDecodeError as e:
        raise ParseDataError(f"Invalid JSON in log: {e}")

    if not messages:
        raise ParseDataError("No messages found in log file")

    return ParsedConversation(messages=messages, ...)
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

def parse(self, file_path: Path):
    logger.info(f"Parsing {file_path.name}")

    for line_num, line in enumerate(f, start=1):
        try:
            # Parse line
            pass
        except Exception as e:
            logger.warning(f"Skipping line {line_num}: {e}")
            continue  # Resilient parsing

    logger.info(f"Extracted {len(messages)} messages")
```

### Type Safety

```python
from typing import Optional
from datetime import datetime

def _parse_timestamp(self, ts: Optional[str]) -> Optional[datetime]:
    """
    Parse timestamp with proper typing.

    Args:
        ts: ISO 8601 timestamp string or None

    Returns:
        Parsed datetime or None if invalid
    """
    if not ts:
        return None

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(f"Invalid timestamp: {ts}")
        return None
```

---

## Reference Examples

### Example 1: JSONL Parser (Line-Based)

```python
"""Parser for line-based JSON logs."""
import json
from pathlib import Path
from datetime import datetime
from catsyphon.parsers.base import ConversationParser
from catsyphon.parsers.metadata import ParserMetadata, ParserCapability
from catsyphon.parsers.incremental import IncrementalParser, IncrementalParseResult
from catsyphon.models.parsed import ParsedConversation, ParsedMessage

class JSONLParser(ConversationParser, IncrementalParser):
    """Example parser for JSONL format logs."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="example-jsonl",
            version="1.0.0",
            supported_formats=[".jsonl", ".ndjson"],
            capabilities={ParserCapability.BATCH, ParserCapability.INCREMENTAL},
            priority=50,
            description="Example parser for line-delimited JSON logs",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path: Path) -> bool:
        """Check if file is JSONL with our format."""
        if file_path.suffix.lower() not in [".jsonl", ".ndjson"]:
            return False

        if not file_path.exists() or file_path.is_dir():
            return False

        try:
            with open(file_path) as f:
                first_line = f.readline()
                if not first_line.strip():
                    return False

                data = json.loads(first_line)
                # Check for required fields
                return "role" in data and "content" in data

        except Exception:
            return False

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse entire JSONL file."""
        messages = []

        with open(file_path) as f:
            for line_num, line in enumerate(f, start=1):
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    message = ParsedMessage(
                        role=data.get("role", "unknown"),
                        content=data.get("content", ""),
                        timestamp=self._parse_ts(data.get("timestamp")),
                        message_index=line_num,
                    )
                    messages.append(message)

                except json.JSONDecodeError:
                    continue  # Skip invalid lines

        return ParsedConversation(
            messages=messages,
            total_messages=len(messages),
            start_time=messages[0].timestamp if messages else None,
            end_time=messages[-1].timestamp if messages else None,
        )

    def supports_incremental(self, file_path: Path) -> bool:
        """JSONL supports incremental parsing."""
        return self.can_parse(file_path)

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """Parse only new lines."""
        new_messages = []
        current_offset = last_offset
        current_line = last_line

        with open(file_path, "rb") as f:
            f.seek(last_offset)

            for line in f:
                current_line += 1
                line_str = line.decode("utf-8")

                if line_str.strip():
                    try:
                        data = json.loads(line_str)
                        message = ParsedMessage(
                            role=data.get("role", "unknown"),
                            content=data.get("content", ""),
                            timestamp=self._parse_ts(data.get("timestamp")),
                            message_index=current_line,
                        )
                        new_messages.append(message)
                    except json.JSONDecodeError:
                        pass

                current_offset += len(line)

        from catsyphon.parsers.incremental import calculate_partial_hash

        return IncrementalParseResult(
            new_messages=new_messages,
            last_processed_offset=current_offset,
            last_processed_line=current_line,
            file_size_bytes=file_path.stat().st_size,
            partial_hash=calculate_partial_hash(file_path, current_offset),
        )

    def _parse_ts(self, ts_str: str) -> datetime | None:
        """Parse ISO timestamp."""
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return None
```

### Example 2: Single JSON Blob Parser

```python
"""Parser for single JSON file (not line-based)."""
import json
from pathlib import Path
from catsyphon.parsers.base import ConversationParser
from catsyphon.parsers.metadata import ParserMetadata, ParserCapability
from catsyphon.models.parsed import ParsedConversation, ParsedMessage

class JSONBlobParser(ConversationParser):
    """Parser for single JSON object containing conversation."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="example-json-blob",
            version="1.0.0",
            supported_formats=[".json"],
            capabilities={ParserCapability.BATCH},  # No incremental support
            priority=50,
            description="Parser for single JSON blob conversation logs",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path: Path) -> bool:
        """Check if file is our JSON format."""
        if file_path.suffix.lower() != ".json":
            return False

        try:
            with open(file_path) as f:
                data = json.load(f)
                # Check structure
                return (
                    isinstance(data, dict) and
                    "conversation" in data and
                    "messages" in data["conversation"]
                )
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse JSON blob."""
        with open(file_path) as f:
            data = json.load(f)

        messages = []
        for idx, msg_data in enumerate(data["conversation"]["messages"]):
            message = ParsedMessage(
                role=msg_data.get("role"),
                content=msg_data.get("text", ""),
                timestamp=self._parse_ts(msg_data.get("timestamp")),
                message_index=idx,
            )
            messages.append(message)

        return ParsedConversation(
            messages=messages,
            total_messages=len(messages),
        )

    def _parse_ts(self, ts_str):
        # Same as previous example
        pass
```

---

## Common Scenarios

### Scenario 1: Google Gemini Code Assist

**Log Format:** JSONL with specific structure

```python
class GeminiParser(ConversationParser, IncrementalParser):
    """Parser for Google Gemini Code Assist logs."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="gemini-code-assist",
            version="1.0.0",
            supported_formats=[".jsonl"],
            capabilities={ParserCapability.BATCH, ParserCapability.INCREMENTAL},
            description="Parser for Google Gemini Code Assist conversation logs",
        )

    def can_parse(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".jsonl":
            return False

        try:
            with open(file_path) as f:
                first_line = f.readline()
                data = json.loads(first_line)
                # Look for Gemini-specific markers
                return (
                    "model" in data and
                    data.get("model", "").startswith("gemini-")
                )
        except Exception:
            return False

    # Implement parse(), parse_incremental()...
```

### Scenario 2: OpenAI Codex

**Log Format:** JSON blob or JSONL

```python
class CodexParser(ConversationParser):
    """Parser for OpenAI Codex logs."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="openai-codex",
            version="1.0.0",
            supported_formats=[".json", ".jsonl"],
            capabilities={ParserCapability.BATCH},
            description="Parser for OpenAI Codex conversation logs",
        )

    def can_parse(self, file_path: Path) -> bool:
        # Check for OpenAI-specific structure
        try:
            with open(file_path) as f:
                if file_path.suffix == ".json":
                    data = json.load(f)
                else:
                    data = json.loads(f.readline())

                return (
                    "model" in data and
                    ("code-" in data["model"] or "davinci-codex" in data["model"])
                )
        except Exception:
            return False

    # Implement parse()...
```

---

## Troubleshooting

### Plugin Not Discovered

1. **Check manifest syntax:**
```bash
python3 -c "import json; json.load(open('catsyphon.json'))"
```

2. **Verify directory structure:**
```bash
ls -la ~/.catsyphon/plugins/your-parser/
# Should contain: catsyphon.json, your_parser.py
```

3. **Enable debug logging:**
```bash
export LOG_LEVEL=DEBUG
catsyphon ingest /path/to/log
```

### Parser Not Loading

1. **Check Python syntax:**
```bash
python3 -c "from your_parser import YourParser; p = YourParser()"
```

2. **Verify class implements protocol:**
```bash
python3 -c "
from your_parser import YourParser
p = YourParser()
print(hasattr(p, 'can_parse'))
print(hasattr(p, 'parse'))
print(hasattr(p, 'metadata'))
"
```

3. **Check imports:**
```bash
python3 -c "from catsyphon.parsers.base import ConversationParser"
```

### `can_parse()` Returns False

Add debugging:

```python
def can_parse(self, file_path: Path) -> bool:
    print(f"Checking: {file_path}")
    print(f"Suffix: {file_path.suffix}")
    print(f"Exists: {file_path.exists()}")

    # ... rest of logic
```

---

## Support and Community

- **Documentation:** https://github.com/anthropics/catsyphon/docs
- **Issues:** https://github.com/anthropics/catsyphon/issues
- **Examples:** https://github.com/anthropics/catsyphon-parsers

---

## Changelog

### v1.0.0 (2025-01-16)
- Initial plugin SDK documentation
- Entry point and directory discovery
- Incremental parsing support
- Complete examples and best practices
