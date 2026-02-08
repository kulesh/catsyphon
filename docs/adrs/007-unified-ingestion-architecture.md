# ADR-007: Unified Ingestion Architecture

**Status:** Accepted
**Date:** 2025-11-01

## Context

CatSyphon has three ingestion entry points: CLI (`catsyphon ingest`), web upload (`POST /upload`), and the watch daemon. Each entry point had evolved its own deduplication checks, change detection logic, and error handling. This duplication caused:

- Inconsistent skip/fail semantics (CLI silently skipped duplicates; upload returned errors; watch logged warnings).
- Fragile RawLog state management split across the orchestrator, ingestion pipeline, and watch helper.
- Partial observability -- failures before job creation were invisible, and metrics were ad-hoc.
- Fragile incremental parsing due to scattered offset/hash state updates.

## Decision

A single ingestion state machine that all entry points route through. The pipeline processes each file through seven deterministic stages:

```
Detect → Dedup → Change Detect → Parse → Ingest → Post-process → Finalize
```

**Key design choices:**

1. **One orchestrator path.** CLI, upload, and watch all call the same `ingest_conversation()` function. Source-specific concerns (file validation, multipart handling, daemon context) are resolved before entering the pipeline.

2. **Hardened parser contract.** Parsers must return `ParseResult` carrying metadata (parser name, version, parse method, change type) and metrics (duration, message count, warnings). The pipeline never infers parser state -- the parser declares it.

3. **Centralized RawLog state.** All offset, hash, and file size updates happen in one place during the Ingest stage. No entry point modifies RawLog state directly.

4. **Job lifecycle guarantee.** An `IngestionJob` record is created before heavy work begins. Every exit path (success, duplicate, skip, failure) marks the job with status and metrics. No silent failures.

## Alternatives Considered

**Multiple entry paths with adapters.** Keep separate CLI/upload/watch pipelines, unify through adapter interfaces. Rejected: adapters drift over time, and the dedup/change-detection logic is identical regardless of source. Adapters add abstraction without reducing duplication.

**Push change detection into parsers.** Let each parser decide whether to do incremental or full parsing based on its own state. Rejected: change detection is a cross-cutting concern. A parser shouldn't need to know whether the file was appended or rewritten -- that's the orchestrator's job.

## Consequences

- Reduced duplication: dedup, change detection, and RawLog state management exist in exactly one place.
- Cleaner observability: every ingestion attempt produces a job record with stage-level metrics, parser metadata, and warnings.
- Fewer race conditions: centralized RawLog state eliminates conflicting updates from concurrent entry points.
- Breaking change for parser plugins: parsers must return `ParseResult` with metadata fields. Existing parsers required a migration to the new contract.
- Single point of failure: a bug in the orchestrator affects all ingestion paths. Mitigated by comprehensive integration tests covering full ingest, duplicate skip, incremental append, truncate-and-replace, and parser failure scenarios.
