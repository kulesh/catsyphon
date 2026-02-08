# ADR-005: Hash-Based Deduplication

**Status:** Accepted
**Date:** 2025-11-01

## Context

The same conversation log file can arrive through multiple ingestion paths: CLI import, web upload, and watch daemon monitoring overlapping directories. Without deduplication, identical conversations would be stored multiple times, inflating statistics and confusing users.

## Decision

SHA-256 content hash of the raw file bytes, computed before any parsing. The hash is stored in `raw_logs.content_hash` (indexed, unique constraint). Before processing, the pipeline checks for an existing record with the same hash:

- **Match found, no `--force` flag**: skip processing, return duplicate status.
- **Match found, `--force` flag**: delete existing records and re-ingest from scratch.
- **No match**: proceed with normal ingestion.

Hash computation happens at the deduplication stage, before the parser is invoked, so duplicate files never consume parsing resources.

## Alternatives Considered

**Path-based deduplication** (deduplicate by file path). Fragile across machines -- the same log file has different absolute paths on different developer workstations. Breaks entirely for uploaded files which have temporary paths.

**Session-ID-only deduplication** (deduplicate by the conversation's internal session identifier). Misses the case where the same session is re-ingested after the log file has been updated with new messages. Would incorrectly treat an updated file as a duplicate.

## Consequences

- Prevents duplicate conversations regardless of ingestion source or file location.
- SHA-256 of a typical log file (< 10MB) adds < 50ms overhead. Negligible compared to parsing and database operations.
- The `--force` flag provides an escape hatch for re-ingestion when the user knows the content has been reprocessed or corrected upstream.
- Content hash is computed on raw bytes, so any change to the file (even whitespace) produces a new hash. This is intentional -- any file modification should trigger re-evaluation.
- The `raw_logs.content_hash` index enables O(1) duplicate lookups regardless of table size.
