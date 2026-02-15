# ADR-009: Incremental-from-Zero (Eliminate Full Parse Path)

**Status:** Proposed
**Date:** 2026-02-15

## Context

CatSyphon maintains two distinct code paths for parsing conversation logs:

1. **Full parse** — `BaseParser.parse()` reads an entire file, returns a fully-materialized `ParsedConversation` containing every message, tool call, code change, and metadata field. Used for first-time file ingestion.

2. **Incremental parse** — `BaseParser.parse_incremental()` reads from a byte offset, returns an `IncrementalParseResult` containing only newly-appended messages. Used by the watch daemon for subsequent file updates.

The full parse path materializes data four times before it reaches PostgreSQL:

```
raw JSONL → list[dict] → list[ParsedMessage] → list[dict] (for bulk insert) → ORM objects
```

Each stage's output lives in memory while the next stage builds its copy. Peak memory reaches 4-6x the file size. For a 90MB Codex session log, this means 360-540MB per parse. Under Docker's 3GB memory limit, even a single concurrent full-parse of a large file can trigger OOM kills — and the watch daemon's initial directory scan tries to process many such files.

ADR-003 solved the _subsequent_ parse problem brilliantly: incremental parsing peaks at ~3x the _append size_, not the file size. But the architecture still falls back to the expensive full-parse path for every file it encounters for the first time, which is exactly when the initial scan processes hundreds of files.

The two code paths also create maintenance burden. Bug fixes, new metadata extraction, and parser improvements must be implemented twice — once in `parse()` and once in `parse_incremental()`. The Codex parser's `_load_records()` accumulates all records in a list; the Claude Code parser's `_parse_all_lines()` does the same. Neither streams.

## Decision

Eliminate the full-parse code path. Treat first-time file ingestion as incremental parsing from offset zero.

### Core Idea

An incremental parse with `offset=0` and no prior state _is_ a full parse — it just produces the result in bounded chunks instead of materializing the entire file. The existing incremental infrastructure (offset tracking, change detection, `RawLog` state) handles the rest.

### Design

**1. Split metadata extraction from message parsing.**

Currently, `parse()` does two things in one pass: (a) extract conversation-level metadata from the first few messages (session ID, agent type, start time, project hints), and (b) parse all messages. These concerns separate naturally:

```python
class BaseParser:
    def parse_metadata(self, file_path: Path) -> ConversationMetadata:
        """Read the first N messages to extract session metadata.
        Lightweight — reads <=10 messages, does not parse the full file."""

    def parse_messages(
        self, file_path: Path, offset: int = 0, limit: int = 500
    ) -> MessageChunk:
        """Parse up to `limit` messages starting from byte `offset`.
        Returns messages + new offset for the next chunk."""
```

`ConversationMetadata` carries everything needed to create the conversation record: session ID, agent type, start/end time, and parser metadata. `MessageChunk` carries a bounded list of `ParsedMessage` objects plus the byte offset where reading stopped.

**2. Chunked ingestion loop.**

The ingestion pipeline processes first-time files as:

```
metadata = parser.parse_metadata(file_path)
conversation = create_conversation(metadata)
offset = 0
while True:
    chunk = parser.parse_messages(file_path, offset, limit=500)
    insert_messages(conversation, chunk.messages)
    session.flush()
    session.expire_all()  # Free ORM objects from identity map
    offset = chunk.next_offset
    if chunk.is_last:
        break
update_raw_log_state(file_path, offset)
```

Peak memory = `limit × message_size` regardless of file size. For 500 messages averaging 2KB each, that's ~3MB peak — constant whether the file has 500 or 50,000 messages.

**3. Incremental append becomes the same loop with a non-zero starting offset.**

The watch daemon's incremental path uses the identical `parse_messages()` call, just starting from the stored offset. There is no separate `parse_incremental()` method. The only difference is where `offset` starts and whether the conversation record already exists.

```
# Watch daemon detects APPEND
metadata = load_existing_conversation(raw_log)
offset = raw_log.last_processed_offset
while True:
    chunk = parser.parse_messages(file_path, offset, limit=500)
    insert_messages(metadata.conversation, chunk.messages)
    session.flush()
    session.expire_all()
    offset = chunk.next_offset
    if chunk.is_last:
        break
update_raw_log_state(file_path, offset)
```

Same loop. Same chunk size. Same memory profile.

**4. `parse()` becomes a convenience wrapper.**

For callers that genuinely need a fully-materialized `ParsedConversation` (tests, one-off scripts, debugging), `parse()` remains but is implemented as:

```python
def parse(self, file_path: Path) -> ParsedConversation:
    """Convenience: fully-materialize by consuming all chunks."""
    metadata = self.parse_metadata(file_path)
    messages = []
    offset = 0
    while True:
        chunk = self.parse_messages(file_path, offset)
        messages.extend(chunk.messages)
        offset = chunk.next_offset
        if chunk.is_last:
            break
    return ParsedConversation(metadata=metadata, messages=messages)
```

This is intentionally not used by the production ingestion pipeline.

### Data Structures

```python
@dataclass
class ConversationMetadata:
    """Extracted from the first few messages of a log file."""
    session_id: str
    agent_type: str
    start_time: datetime
    end_time: Optional[datetime]
    model: Optional[str]
    working_directory: Optional[str]
    parser_name: str
    parser_version: str

@dataclass
class MessageChunk:
    """A bounded batch of parsed messages with cursor state."""
    messages: list[ParsedMessage]
    next_offset: int          # Byte offset to resume from
    next_line: int            # Line number to resume from
    is_last: bool             # True if EOF reached
    partial_hash: str         # Hash of first N bytes (for change detection)
    file_size: int            # Current file size
```

### Migration Path

1. Add `parse_metadata()` and `parse_messages()` to `BaseParser` with default implementations that delegate to existing `parse()` (backwards-compatible).
2. Implement native chunked parsing in Claude Code parser first (largest user base, best-tested).
3. Implement native chunked parsing in Codex parser.
4. Update the ingestion pipeline's first-time path to use the chunked loop.
5. Remove the separate `parse_incremental()` method — `parse_messages(offset=stored_offset)` replaces it.
6. Deprecate and eventually remove `parse()` from the production ingestion path.

Each step produces a testable, deployable state. Steps 1-2 can ship independently.

## Alternatives Considered

**A. Chunked ingestion only (keep parser interface).** Parse the full file into `ParsedConversation` as before, but insert messages in chunks of 500 during ingestion, calling `session.flush()` between chunks. This caps ORM memory but not parser memory — the fully-materialized `ParsedConversation` still lives in memory throughout. Reduces peak from ~6x to ~3x file size. Simpler to implement but doesn't solve the fundamental problem: a 90MB Codex log still requires ~270MB just for the parsed representation.

**B. Two-pass parsing.** First pass extracts metadata (lightweight). Second pass streams messages. Similar to the chosen approach but keeps `parse()` and `parse_incremental()` as separate methods with a new `parse_metadata()` alongside. Three methods instead of two. The streaming second pass is essentially `parse_messages()` with `limit=∞`, so this is option C with more API surface and no unification benefit.

**C. Memory-mapped file I/O.** Use `mmap` to avoid reading the full file into memory. Python's `mmap` module maps a file into the process's virtual address space; the OS pages in only the regions accessed. For JSONL files this helps with the file I/O buffer (~1x file size saved) but doesn't address the four-stage materialization problem. Lines still need JSON parsing, and parsed objects still accumulate. `mmap` is a useful implementation detail _within_ the chunked parser (seek to offset via mmap instead of `file.seek()`), not an alternative architecture.

## Consequences

**Positive:**
- Constant memory usage regardless of file size. Peak memory proportional to chunk size, not input size.
- One code path for all ingestion: first-time, incremental append, and reparse after truncate/rewrite.
- Parser implementations become simpler — no need to maintain separate `parse()` and `parse_incremental()` methods with duplicated logic.
- The OOM crash loop fix (reducing scan workers to 1) can be reverted — concurrent chunked parsing of multiple files will stay within memory limits.

**Negative:**
- Breaking change to the `BaseParser` interface. All parser implementations (Claude Code, Codex, and any future parsers) must implement `parse_metadata()` and `parse_messages()`.
- Metadata extraction becomes a separate concern. Currently, metadata is discovered as a side effect of parsing all messages. The new `parse_metadata()` must handle this independently, which may mean reading the first few lines twice (once for metadata, once for the first chunk). Negligible cost for JSONL files.
- Transaction semantics change. Currently, all messages for a conversation are inserted in a single transaction. With chunked insertion, a crash mid-ingestion leaves a partially-ingested conversation. This is handled by the existing `RawLog` offset tracking — on restart, the pipeline resumes from the last committed offset, and duplicate message detection (by sequence number within a conversation) prevents double-insertion.
- Tests that assert on `ParsedConversation` as a single object need updating to work with chunks or use the convenience `parse()` wrapper.
