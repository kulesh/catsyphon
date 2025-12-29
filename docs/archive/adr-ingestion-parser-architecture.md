# ADR: Unified Parser ↔ Ingestion Architecture

Status: Draft  
Date: 2025-11-XX  
Branch: feature/ingestion-parser-arch

## Context
- Parsers expose minimal contracts; ingestion often runs without parser name/version, change-type, or warnings.
- Deduplication and change detection logic is duplicated across watch, CLI, upload, and ingestion, causing inconsistent skip/fail semantics.
- Incremental flows are split (orchestrator, ingestion `append`, watch helper), making RawLog state fragile.
- Observability is partial: metrics are ad-hoc, stage timings are incomplete, and failures before job creation are invisible.
- Adding new parsers/plugins is error-prone: ordering is implicit, and capability negotiation is manual.

## Decision
Adopt a single ingestion state machine with a hardened parser contract. All entrypoints (CLI, upload, watch) go through the orchestrator, which performs detection, parsing, and dispatches to the ingestion pipeline with a consistent context. Parser results always carry metadata and metrics via `ParseResult`.

## Goals
- Simple: One orchestrator path for all sources; minimal branching in ingestion.
- Reliable: Deterministic dedup/change detection, clear failure semantics, idempotent RawLog updates.
- Extensible: Parsers declare capabilities; plugin loading is explicit; new parsers require no ingestion changes.
- Observable: Stage metrics, parser metadata, warnings, and change types are captured on every job.

## Non-goals
- Changing storage schema for ParsedConversation or RawLog.
- Adding new ingestion sources beyond CLI/upload/watch.
- Redesigning tagging; only pass-through metrics.

## State Machine (per file)
1. **Detect**: ensure file exists/readable; run lightweight `can_parse` probes (no data mutation).  
2. **Dedup**: hash-based duplicate check; optionally short-circuit skip.  
3. **Change Detect**: if already tracked, classify append/truncate/rewrite/unchanged; decide incremental vs full.  
4. **Parse**: execute selected parser (full or incremental). Parser returns `ParseResult` (or `IncrementalParseResult` + metadata) with metrics and warnings. Failures are surfaced, not swallowed.  
5. **Ingest**: call ingestion pipeline with `IngestContext` (job_id, parser info, change_type, source, file_path). RawLog state is updated atomically.  
6. **Post-process**: link orphaned agents (batch), tagging (optional), emit ingestion_job metrics.  
7. **Finalize**: mark job success/duplicate/skip/fail with metrics and warnings recorded.

## Parser Contract
- `ConversationParser.parse_with_metadata(Path) -> ParseResult`
  - Required: parser_name, parser_version, parse_method ("full"), change_type (None/enum), metrics dict, warnings list (strings), ParsedConversation.
- `IncrementalParser.parse_incremental(Path, last_offset, last_line) -> IncrementalParseResult`
  - Required metrics: parse_duration_ms, parse_method ("incremental"), change_type ("append"), parse_messages_count, last_processed_offset/line, file_size_bytes, partial_hash, last_message_timestamp.
- `can_parse(Path) -> ProbeResult` (confidence + reasons) to improve selection transparency.
- Parsers should never silently consume format errors; return warnings for partial issues and raise for hard failures.

## Metrics Schema (ingestion_jobs.metrics)
- Stage timings (ms): detect, deduplication_check, change_detection, parse, database_operations, tagging (if enabled), total_ms.
- Parser: parser_name, parser_version, parse_method, parse_change_type, parse_messages_count, parse_warning_count, parse_warnings[].
- Ingestion: messages_added, incremental (bool), source_type, file_hash (optional, for troubleshooting).
- Optional parser-emitted metrics: lines_read, bytes_read, tokens, any numeric values merged under `parser_*` keys.

## Reliability Rules
- Job is created before heavy work; every exit path marks status with metrics.
- Registry does not suppress parser exceptions; if no parser succeeds, raise a structured error and record a failed job.
- Change detection failures fall back to full parse but are recorded as warnings.
- RawLog state updates are centralized (create/update/state) to keep offsets/partial_hash consistent.
- Default workspace/project/developer resolution happens once per ingest to avoid deadlocks.

## Observability
- Use `IngestContext` to thread job_id/parser/change_type through logs for correlation.
- API surfaces parser/change-type usage and warning counts from ingestion_jobs.metrics.
- Dry-run preflight command shows which parser will be selected and why (confidence/reasons).

## Migration Plan
1. Implement contracts/types (ParseResult, ProbeResult), registry changes, and parser updates.
2. Unify orchestrator as the only entry; route CLI/upload/watch through it; remove legacy append path in ingestion and watch incremental helper.
3. Refactor ingestion into composable steps with RawLog state manager; enforce job lifecycle and metrics schema.
4. Add integration tests: full ingest, duplicate skip, append incremental, truncate→replace, parser failure, watch/upload orchestration.

## Alternatives Considered
- Keep multiple entry paths with adapters: rejected for complexity and drift risk.
- Push change detection into parsers: rejected; cross-parser consistency belongs in orchestrator.

## Impact
- Small breaking changes for parser plugins (must return ParseResult metadata).
- Cleaner observability via ingestion_job metrics and logs.
- Reduced duplication and fewer race conditions around dedup/change detection.
