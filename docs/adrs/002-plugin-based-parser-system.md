# ADR-002: Plugin-Based Parser System

**Status:** Accepted
**Date:** 2025-11-01

## Context

AI coding assistants (Claude Code, GitHub Copilot, Cursor, Codex, etc.) each produce conversation logs in different formats -- JSONL, structured JSON, markdown, proprietary binary. CatSyphon must ingest all of them. The set of supported agents will grow over time, and we cannot predict every format upfront.

## Decision

A `ParserRegistry` that dynamically discovers parser classes and routes each file to the appropriate parser. Each parser implements `BaseParser` with two key methods:

- `can_parse(path) -> ProbeResult`: lightweight probe that returns a confidence score (0.0-1.0) and reasoning, without reading the entire file.
- `parse(path) -> ParsedConversation`: full parse that normalizes agent-specific formats into a common `ParsedConversation` model.

The registry iterates registered parsers in priority order, selects the highest-confidence match above threshold, and dispatches. Parser registration is explicit in `parsers/registry.py`.

```
File → Registry.can_parse() probes → Select highest confidence → Parser.parse() → ParsedConversation
```

## Alternatives Considered

**Single monolithic parser with format switching.** Simpler initially, but every new agent format adds conditional branches to one growing module. Testing becomes combinatorial. Format-specific edge cases bleed across boundaries.

**Config-driven format mapping** (file extension or path pattern to parser). Fragile -- log files don't always have predictable extensions or paths. Content-based detection is more reliable than name-based heuristics.

## Consequences

- Adding a new agent requires only a new parser class with `can_parse()` and `parse()`. No changes to the registry, ingestion pipeline, or existing parsers.
- Probe overhead: every file is tested against all registered parsers. Acceptable at current scale (< 10 parsers); can add short-circuit optimization if needed.
- Parser ordering matters when confidence scores tie. Documented in registry with explicit priority values.
- All parsers normalize to `ParsedConversation`, creating a clean boundary between format-specific parsing and format-agnostic storage/analysis.
