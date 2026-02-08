# Incremental Parsing

## Overview

Incremental parsing is an optimization that dramatically improves performance when processing log files that are actively being appended to, such as during live Claude Code sessions or watch daemon monitoring.

**Key Benefits:**
- **10x to 106x faster** parsing depending on file size and append size
- **45x to 465x less memory** usage
- **Automatic detection** of file changes (APPEND, TRUNCATE, REWRITE, UNCHANGED)
- **Graceful degradation** to full reparse if incremental parsing fails
- **Zero configuration** - works automatically across all ingestion paths

## Performance Benchmarks

### Speed Improvements (vs full reparse)

| Scenario | Full Parse | Incremental Parse | Speedup |
|----------|-----------|------------------|---------|
| Small append (1 to 100) | 1.64 ms | 0.17 ms | **9.9x** |
| Medium log (10 to 1000) | 12.65 ms | 0.35 ms | **36.6x** |
| Large log (1 to 5000) | 61.76 ms | 0.58 ms | **106.0x** |
| Multiple appends (5 × 10) | 16.64 ms | 1.19 ms | **14.0x** |

### Memory Reduction

| File Size | Full Parse Peak | Incremental Parse Peak | Reduction |
|-----------|----------------|----------------------|-----------|
| 1,000 messages (~130 KB) | 1481.3 KB | 33.0 KB | **45x** |
| 50,000 messages (~7.3 MB) | 72.51 MB | 159.76 KB | **465x** |

**Note**: Memory reduction scales with file size. For 100MB+ files, reductions of 1000x+ are expected.

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  RawLogRepository     │
            │  .get_by_file_path()  │
            └───────────┬───────────┘
                        │
          ┌─────────────▼──────────────┐
          │   Existing RawLog found?    │
          └─────────────┬───────────────┘
                        │
            ┌───────────┴────────────┐
            │                        │
         Yes│                        │No
            │                        │
            ▼                        ▼
    ┌───────────────┐     ┌──────────────────┐
    │ Change Type   │     │ Full Parse       │
    │ Detection     │     │ (parse)          │
    └───────┬───────┘     └─────────┬────────┘
            │                       │
            ▼                       │
    ┌───────────────┐               │
    │ UNCHANGED?    │               │
    └───────┬───────┘               │
            │                       │
      ┌─────┴─────┐                 │
      │           │                 │
   Yes│        No │                 │
      │           │                 │
      ▼           ▼                 │
  ┌──────┐  ┌──────────┐            │
  │ Skip │  │ APPEND?  │            │
  └──────┘  └────┬─────┘            │
                 │                  │
          ┌──────┴───────┐          │
          │              │          │
       Yes│           No │          │
          │              │          │
          ▼              ▼          │
  ┌───────────────┐  ┌──────────┐  │
  │ Incremental   │  │ Full     │  │
  │ Parse         │  │ Reparse  │  │
  │ (parse_incr)  │  │ (parse)  │  │
  └───────────────┘  └──────────┘  │
          │              │          │
          └──────────────┴──────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Update RawLog State  │
          │ - offset             │
          │ - line number        │
          │ - hash               │
          │ - file size          │
          └──────────────────────┘
```

### Step-by-Step Flow

1. **File arrives for ingestion** (via watch daemon, CLI, or API)

2. **Check for existing RawLog entry**
   - Query `RawLogRepository.get_by_file_path()`
   - If not found → **Full parse** (first time seeing this file)
   - If found → **Change detection**

3. **Change detection** (`detect_file_change_type()`)
   - Compare current file size with `last_file_size`
   - If smaller → **TRUNCATE** (file was truncated or recreated)
   - If same size:
     - Calculate partial hash of existing content
     - Compare with stored `partial_hash`
     - If match → **UNCHANGED** (skip processing)
     - If different → **REWRITE** (content changed)
   - If larger:
     - Calculate partial hash of existing content
     - Compare with stored `partial_hash`
     - If match → **APPEND** (new content added)
     - If different → **REWRITE** (content modified)

4. **Routing based on change type**
   - **UNCHANGED**: Skip processing entirely
   - **APPEND**: Call `parse_incremental()` with saved state
   - **TRUNCATE** or **REWRITE**: Full reparse with `parse()`

5. **Incremental parsing** (`parse_incremental()`)
   - Open file and seek to `last_processed_offset`
   - Read only new content from that point
   - Parse new JSON lines
   - Merge tool calls with results (same as full parse)
   - Sort messages chronologically
   - Return only new messages

6. **Update state**
   - Save new `last_processed_offset`
   - Save new `last_processed_line`
   - Calculate and save new `partial_hash`
   - Update `file_size_bytes`

### State Tracking

State is stored in the `raw_logs` table:

```sql
CREATE TABLE raw_logs (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    file_path TEXT UNIQUE NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    last_processed_offset BIGINT NOT NULL DEFAULT 0,
    last_processed_line INTEGER NOT NULL DEFAULT 0,
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    partial_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**Key Fields:**
- `file_path`: Unique identifier for the log file
- `file_hash`: SHA-256 hash of entire file content (for deduplication)
- `last_processed_offset`: Byte offset where parsing stopped
- `last_processed_line`: Line number where parsing stopped
- `file_size_bytes`: File size at last parse
- `partial_hash`: SHA-256 hash of content from offset 0 to `last_processed_offset`

## Implementation Details

### Key Files

- **`backend/src/catsyphon/parsers/incremental.py`**
  - `calculate_partial_hash()` - Hash content from offset to current position
  - `detect_file_change_type()` - Determine APPEND, TRUNCATE, REWRITE, or UNCHANGED
  - `ChangeType` enum - Change type constants
  - `IncrementalParseResult` - Return type for incremental parses

- **`backend/src/catsyphon/parsers/claude_code.py`**
  - `parse_incremental()` - Parse only new content from a given offset
  - Streaming file read with seek()
  - Message sorting and tool call merging

- **`backend/src/catsyphon/pipeline/ingestion.py`**
  - `ingest_conversation()` - Main ingestion entry point
  - `append_to_conversation()` - Append new messages to existing conversation
  - Smart routing logic based on change detection

- **`backend/src/catsyphon/watch.py`**
  - Watch daemon integration
  - Error handling and retry logic
  - Stats tracking for incremental parses

### Change Detection Algorithm

```python
def detect_file_change_type(
    file_path: Path,
    last_processed_offset: int,
    last_file_size: int,
    stored_partial_hash: str,
) -> ChangeType:
    """Detect how a file has changed since last parse."""
    current_size = file_path.stat().st_size

    # File truncated or recreated
    if current_size < last_file_size:
        return ChangeType.TRUNCATE

    # File size unchanged - check if content modified
    if current_size == last_file_size:
        current_hash = calculate_partial_hash(file_path, 0, current_size)
        if current_hash == stored_partial_hash:
            return ChangeType.UNCHANGED
        else:
            return ChangeType.REWRITE

    # File grew - check if content was appended or rewritten
    current_hash = calculate_partial_hash(file_path, 0, last_processed_offset)
    if current_hash == stored_partial_hash:
        return ChangeType.APPEND
    else:
        return ChangeType.REWRITE
```

**Why partial hash?**
- Full file hashing would defeat the performance benefit of incremental parsing
- Partial hash (existing content only) is fast and sufficient for change detection
- SHA-256 provides strong guarantee against accidental collisions

### Incremental Parsing Algorithm

```python
def parse_incremental(
    self, file_path: Path, start_offset: int, start_line: int
) -> IncrementalParseResult:
    """Parse only new content from a given offset."""

    # Open file and seek to last processed position
    with file_path.open("r", encoding="utf-8") as f:
        f.seek(start_offset)

        # Read and parse only new lines
        new_messages = []
        for line_num, line in enumerate(f, start=start_line + 1):
            try:
                data = json.loads(line)
                message = self._convert_to_parsed_message(data, line_num)
                if message:
                    new_messages.append(message)
            except json.JSONDecodeError:
                logger.warning(f"Skipping invalid JSON at line {line_num}")
                continue

        # Record final position
        final_offset = f.tell()
        final_line = start_line + len(new_messages)

    # Merge tool calls with results (same as full parse)
    self._merge_tool_calls_with_results(new_messages)

    # Sort messages by timestamp
    new_messages.sort(key=lambda m: m.timestamp or datetime.min)

    # Calculate new partial hash
    partial_hash = calculate_partial_hash(file_path, 0, final_offset)

    return IncrementalParseResult(
        new_messages=new_messages,
        last_processed_offset=final_offset,
        last_processed_line=final_line,
        file_size_bytes=file_path.stat().st_size,
        partial_hash=partial_hash,
        last_message_timestamp=new_messages[-1].timestamp if new_messages else None,
    )
```

## Error Handling

### Graceful Degradation

Incremental parsing includes multiple fallback mechanisms:

1. **Change detection errors** → Fall back to full reparse
   ```python
   try:
       change_type = detect_file_change_type(...)
   except Exception as e:
       logger.warning(f"Change detection failed: {e}, falling back to full reparse")
       # Proceed with full reparse
   ```

2. **Incremental parsing errors** → Fall back to full reparse
   ```python
   try:
       result = parser.parse_incremental(...)
   except Exception as e:
       logger.warning(f"Incremental parse failed: {e}, falling back to full reparse")
       result = parser.parse(file_path)
   ```

3. **Invalid state** → Reset and full reparse
   - If `last_processed_offset` exceeds file size → Full reparse
   - If file path changed → New RawLog entry, full parse

### Retry Queue

The watch daemon includes a retry queue for files that fail processing:

- Failed files are added to retry queue with exponential backoff
- Maximum 3 retry attempts with 5s, 10s, 20s delays
- After max retries, file is marked as failed and skipped

## Usage

### Automatic Usage

Incremental parsing is **automatically used** in all ingestion paths:

```bash
# Watch daemon automatically uses incremental parsing
uv run catsyphon watch /path/to/logs --project "my-project"

# CLI ingest automatically uses incremental parsing for existing files
uv run catsyphon ingest /path/to/logs --project "my-project"
```

### Programmatic Usage

```python
from pathlib import Path
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.db.repositories.raw_log import RawLogRepository
from catsyphon.parsers.incremental import detect_file_change_type, ChangeType

parser = ClaudeCodeParser()
repo = RawLogRepository(session)

# Check if file was previously parsed
existing_log = repo.get_by_file_path(str(file_path))

if existing_log:
    # Detect changes
    change_type = detect_file_change_type(
        file_path,
        existing_log.last_processed_offset,
        existing_log.file_size_bytes,
        existing_log.partial_hash,
    )

    if change_type == ChangeType.UNCHANGED:
        # Skip processing
        return
    elif change_type == ChangeType.APPEND:
        # Incremental parse
        result = parser.parse_incremental(
            file_path,
            existing_log.last_processed_offset,
            existing_log.last_processed_line,
        )
        # Append result.new_messages to conversation
    else:
        # Full reparse required
        result = parser.parse(file_path)
else:
    # First time seeing this file
    result = parser.parse(file_path)
```

## Testing

### Unit Tests

- **`tests/test_parsers/test_incremental.py`** - Change detection and hashing
- **`tests/test_parsers/test_claude_code_incremental.py`** - Incremental parsing logic
- **`tests/test_watch/test_file_watcher.py`** - Watch daemon integration

### Performance Benchmarks

- **`tests/test_performance.py`** - Comprehensive benchmarks

Run benchmarks:
```bash
cd backend

# Run all benchmarks (fast tests only)
uv run pytest tests/test_performance.py -v -s -m "benchmark and not slow"

# Run including slow benchmark (50k messages)
uv run pytest tests/test_performance.py -v -s -m benchmark
```

## Debugging

### Logging

Enable debug logging to see change detection in action:

```bash
# Set log level to DEBUG
export LOG_LEVEL=DEBUG

# Watch with verbose mode (includes SQL queries)
uv run catsyphon watch /path/to/logs --verbose
```

Debug log output:
```
DEBUG - Change detection: APPEND for conversation.jsonl
DEBUG - Incremental parse: 10 new messages (offset 1234 → 5678)
DEBUG - Updated RawLog state: offset=5678, line=100, hash=abc123...
```

### Stats Tracking

The watch daemon tracks incremental parsing stats:

```python
class WatcherStats:
    files_processed: int      # Files successfully parsed
    files_skipped: int        # Files skipped (UNCHANGED)
    files_failed: int         # Files that failed parsing
    last_activity: datetime   # Last file processed
```

## Future Enhancements

Potential improvements for future phases:

1. **Multi-file incremental parsing** - Detect related files and parse together
2. **Incremental tagging** - Only tag new messages instead of full conversation
3. **Streaming API** - Real-time message streaming as file is appended
4. **Compression** - Store compressed partial content for even faster hash calculation
5. **Parallel incremental parsing** - Process multiple appends concurrently
6. **Database-level optimization** - Use PostgreSQL COPY for bulk message insertion

## References

- [Implementation Plan](../archive/implementation-plan.md) - Phase 2 implementation details
- [Database Schema](../backend/db/migrations/) - Alembic migrations for state tracking
- [Parser Plugin System](../backend/src/catsyphon/parsers/) - Parser architecture
- [Performance Benchmarks](../backend/tests/test_performance.py) - Benchmark tests
