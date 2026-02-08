# Parser Plugin Quickstart

**⏱️ Time to first parser: 15 minutes**

This guide gets you from zero to a working CatSyphon parser plugin as quickly as possible.

---

## Prerequisites

- Python 3.11+
- CatSyphon installed: `pip install catsyphon`
- A sample log file from your target AI assistant

---

## Step 1: Analyze Your Log Format (5 min)

Open a sample log file and identify:

1. **File extension**: `.json`, `.jsonl`, `.log`, `.db`?
2. **Structure**: Line-based (JSONL) or single blob (JSON)?
3. **Key fields**: Where are `role`, `content`, `timestamp`?
4. **Unique markers**: Any text/fields unique to this format?

**Example Gemini Log:**
```jsonl
{"timestamp": "2025-01-16T10:00:00Z", "role": "user", "content": "Hello"}
{"timestamp": "2025-01-16T10:00:05Z", "role": "model", "content": "Hi there!"}
```

✅ Extension: `.jsonl`
✅ Structure: Line-based
✅ Fields: `timestamp`, `role`, `content`
✅ Unique marker: `"role": "model"` (not "assistant")

---

## Step 2: Create Parser File (5 min)

Copy this template to `gemini_parser.py`:

```python
"""Parser for Google Gemini conversation logs."""
import json
from pathlib import Path
from datetime import datetime
from catsyphon.parsers.base import ConversationParser
from catsyphon.parsers.metadata import ParserMetadata, ParserCapability
from catsyphon.models.parsed import ParsedConversation, ParsedMessage

class GeminiParser(ConversationParser):
    """Parser for Gemini Code Assist logs."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="gemini-code-assist",
            version="1.0.0",
            supported_formats=[".jsonl"],
            capabilities={ParserCapability.BATCH},
            priority=50,
            description="Parser for Google Gemini Code Assist logs",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path: Path) -> bool:
        """Quick check if this is a Gemini log."""
        # 1. Check extension
        if file_path.suffix.lower() != ".jsonl":
            return False

        # 2. Check file exists
        if not file_path.exists() or file_path.is_dir():
            return False

        # 3. Check first line for unique marker
        try:
            with open(file_path) as f:
                first_line = f.readline()
                data = json.loads(first_line)

                # Gemini uses "model" not "assistant"
                return "role" in data and (
                    data.get("role") == "model" or
                    "gemini" in first_line.lower()
                )
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse the entire log file."""
        messages = []

        with open(file_path) as f:
            for line_num, line in enumerate(f, start=1):
                # Skip empty lines
                if not line.strip():
                    continue

                try:
                    # Parse JSON
                    data = json.loads(line)

                    # Convert Gemini "model" → "assistant"
                    role = data.get("role", "unknown")
                    if role == "model":
                        role = "assistant"

                    # Create message
                    message = ParsedMessage(
                        role=role,
                        content=data.get("content", ""),
                        timestamp=self._parse_timestamp(data.get("timestamp")),
                        message_index=line_num,
                    )
                    messages.append(message)

                except json.JSONDecodeError:
                    # Skip invalid lines (resilient parsing)
                    continue

        return ParsedConversation(
            messages=messages,
            total_messages=len(messages),
            user_message_count=sum(1 for m in messages if m.role == "user"),
            assistant_message_count=sum(1 for m in messages if m.role == "assistant"),
            start_time=messages[0].timestamp if messages else None,
            end_time=messages[-1].timestamp if messages else None,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse ISO 8601 timestamp."""
        if not ts_str:
            return None

        try:
            # Handle "Z" timezone
            ts_str = ts_str.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str)
        except ValueError:
            return None
```

**Customization Points:**
- Line 14: Change `name` to match your AI assistant
- Line 16: Change `supported_formats` to your file extensions
- Line 40-44: Change unique marker detection logic
- Line 63-65: Adjust role mapping if needed

---

## Step 3: Create Manifest (2 min)

Create `catsyphon.json`:

```json
{
  "name": "gemini-code-assist-parser",
  "version": "1.0.0",
  "description": "Parser for Google Gemini Code Assist conversation logs",
  "parser_class": "gemini_parser.GeminiParser",
  "supported_formats": [".jsonl"],
  "author": "Your Name",
  "license": "MIT"
}
```

**Customization:**
- Line 2: Unique plugin name (lowercase-with-hyphens)
- Line 4: Parser description
- Line 5: Module and class name (must match your Python file)

---

## Step 4: Install Plugin (1 min)

```bash
# Create plugin directory
mkdir -p ~/.catsyphon/plugins/gemini-parser

# Copy files
cp gemini_parser.py ~/.catsyphon/plugins/gemini-parser/
cp catsyphon.json ~/.catsyphon/plugins/gemini-parser/

# Done! CatSyphon will auto-discover it
```

---

## Step 5: Test It (2 min)

```bash
# Try parsing a log file
catsyphon ingest /path/to/gemini/log.jsonl --project "Test"

# Check if it worked
catsyphon db-status

# View in web UI
catsyphon serve
# Open http://localhost:8000
```

**Troubleshooting:**

If ingestion fails:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
catsyphon ingest /path/to/log.jsonl --project "Test"

# Check what parsers were discovered
python3 -c "
from catsyphon.plugins.loader import PluginLoader
loader = PluginLoader()
loader.discover_plugins()
print('Discovered parsers:', loader.list_plugins())
"
```

---

## Next Steps

### Add Incremental Parsing (10x-106x faster)

For line-based formats (JSONL, logs), add incremental support:

```python
from catsyphon.parsers.incremental import IncrementalParser, IncrementalParseResult, calculate_partial_hash

class GeminiParser(ConversationParser, IncrementalParser):
    # ... existing code ...

    def supports_incremental(self, file_path: Path) -> bool:
        """Gemini JSONL supports incremental parsing."""
        return self.can_parse(file_path)

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """Parse only new lines since last_offset."""
        new_messages = []
        current_offset = last_offset
        current_line = last_line

        # Open file and seek to last position
        with open(file_path, "rb") as f:
            f.seek(last_offset)

            # Read only new lines
            for line in f:
                current_line += 1
                line_str = line.decode("utf-8")

                if line_str.strip():
                    try:
                        data = json.loads(line_str)
                        role = data.get("role", "unknown")
                        if role == "model":
                            role = "assistant"

                        message = ParsedMessage(
                            role=role,
                            content=data.get("content", ""),
                            timestamp=self._parse_timestamp(data.get("timestamp")),
                            message_index=current_line,
                        )
                        new_messages.append(message)
                    except json.JSONDecodeError:
                        pass

                current_offset += len(line)

        # Return incremental result
        return IncrementalParseResult(
            new_messages=new_messages,
            last_processed_offset=current_offset,
            last_processed_line=current_line,
            file_size_bytes=file_path.stat().st_size,
            partial_hash=calculate_partial_hash(file_path, current_offset),
        )
```

Update capabilities:
```python
capabilities={ParserCapability.BATCH, ParserCapability.INCREMENTAL},
```

### Distribute as Package

Create `pyproject.toml`:

```toml
[project]
name = "catsyphon-gemini-parser"
version = "1.0.0"
description = "CatSyphon parser for Google Gemini Code Assist"
requires-python = ">=3.11"
dependencies = ["catsyphon>=0.2.0"]

[project.entry-points."catsyphon.parsers"]
gemini = "gemini_parser:get_metadata"
```

Add to `gemini_parser.py`:
```python
from catsyphon.plugins.manifest import PluginMetadata

def get_metadata() -> PluginMetadata:
    """Entry point for plugin discovery."""
    return PluginMetadata(
        name="gemini-code-assist",
        version="1.0.0",
        description="Parser for Google Gemini Code Assist logs",
        parser_class="gemini_parser.GeminiParser",
        supported_formats=[".jsonl"],
    )
```

Install:
```bash
pip install -e .  # Development
pip install .     # Production
```

---

## Full Documentation

- **Complete SDK Guide:** [Plugin SDK](./plugin-sdk.md)
- **API Reference:** [API Reference](../reference/api-reference.md)
- **Examples:** [examples/parsers/](../examples/parsers/)

---

## Template for Other AI Assistants

### OpenAI Codex

Change in `can_parse()`:
```python
return "model" in data and ("code-" in data["model"] or "codex" in data["model"])
```

### Cursor IDE

For SQLite databases:
```python
import sqlite3

def can_parse(self, file_path: Path) -> bool:
    if file_path.suffix.lower() not in [".db", ".sqlite"]:
        return False

    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        return "conversations" in tables and "messages" in tables
    except Exception:
        return False
```

### GitHub Copilot

For JSON blob format:
```python
def can_parse(self, file_path: Path) -> bool:
    if file_path.suffix.lower() != ".json":
        return False

    try:
        with open(file_path) as f:
            data = json.load(f)
            return (
                "telemetry" in data or
                "copilot" in data.get("source", "").lower()
            )
    except Exception:
        return False
```

---

## Common Issues

**Q: Parser not discovered?**
```bash
# Check manifest is valid JSON
python3 -c "import json; print(json.load(open('catsyphon.json')))"

# Check directory structure
ls -la ~/.catsyphon/plugins/your-parser/
```

**Q: `can_parse()` always returns False?**
```python
# Add debug prints
def can_parse(self, file_path: Path) -> bool:
    print(f"Checking: {file_path}")
    print(f"Suffix: {file_path.suffix}")
    # ... rest of logic
```

**Q: Messages not extracted correctly?**
```python
# Add debug in parse()
def parse(self, file_path: Path) -> ParsedConversation:
    messages = []
    for line in f:
        data = json.loads(line)
        print(f"Line data: {data}")  # Debug
        # ... rest of logic
```

---

**🎉 You're done! You now have a working CatSyphon parser plugin.**

Share it with the community: https://github.com/anthropics/catsyphon-parsers
