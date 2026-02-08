# ADR-003: Incremental Parsing

**Status:** Accepted
**Date:** 2025-11-01

## Context

Conversation log files grow continuously during live coding sessions. A single Claude Code session can produce a log file that grows from kilobytes to megabytes over hours. The watch daemon detects changes every 2 seconds. Full reparsing on every change is prohibitively expensive for large files -- both in CPU time and memory allocation.

## Decision

Offset-based incremental parsing. Each `RawLog` entry stores parsing state:

- `last_processed_offset`: byte position where the previous parse ended
- `file_size_bytes`: file size at last parse
- `partial_hash`: hash of the first N bytes for identity verification

On subsequent ingestion, the system classifies the change:

| Change Type | Detection | Action |
|---|---|---|
| **UNCHANGED** | Same size + same partial hash | Skip entirely |
| **APPEND** | Larger size + same partial hash prefix | Parse from `last_processed_offset` only |
| **TRUNCATE** | Smaller size | Full reparse |
| **REWRITE** | Same/larger size + different partial hash | Full reparse |

Incremental parsing reads only the new bytes, parses only new messages, and appends them to the existing conversation record.

## Alternatives Considered

**File diffing** (compute diff between stored and current content). Requires storing full previous content or maintaining a shadow copy. Memory-intensive and slower than offset-based seeking for append-only files.

**inotify-based line tracking.** OS-level file change notifications. Platform-dependent (inotify on Linux, FSEvents on macOS), and doesn't provide semantic understanding of what changed -- just that something did. Still need parsing logic on top.

**Database-level dedup** (parse everything, deduplicate messages at insert). Simpler parsing but pushes O(n) comparison work into the database on every cycle. Wasteful when 99% of content is unchanged.

## Consequences

- 10x to 106x faster than full reparse depending on file size and append volume.
- 45x to 465x reduction in memory usage for large files.
- Requires state tracking in the `raw_logs` table (`last_processed_offset`, `file_size_bytes`, `partial_hash`).
- Graceful degradation: any failure in incremental path triggers automatic fallback to full reparse with a logged warning.
- Append detection assumes log files are append-only during normal operation. Log rotation or manual editing triggers REWRITE, which is handled correctly but at full-parse cost.
