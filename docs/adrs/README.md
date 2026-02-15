# Architecture Decision Records

This directory captures key architectural decisions for CatSyphon using the lightweight ADR format from Michael Nygard.

## Status Legend

| Status | Meaning |
|---|---|
| **Accepted** | Active and governing current implementation |
| **Superseded** | Replaced by a newer ADR (link provided) |
| **Deprecated** | No longer relevant; kept for historical context |

## Index

| ADR | Title | Status |
|---|---|---|
| [001](001-monorepo-structure.md) | Monorepo Structure | Accepted |
| [002](002-plugin-based-parser-system.md) | Plugin-Based Parser System | Accepted |
| [003](003-incremental-parsing.md) | Incremental Parsing | Accepted |
| [004](004-repository-pattern.md) | Repository Pattern | Accepted |
| [005](005-hash-based-deduplication.md) | Hash-Based Deduplication | Accepted |
| [006](006-polling-over-websockets.md) | Polling Over WebSockets | Accepted |
| [007](007-unified-ingestion-architecture.md) | Unified Ingestion Architecture | Accepted |
| [008](008-skill-native-analytics-architecture.md) | Skill-Native Analytics Architecture | Accepted |

## Template

```markdown
# ADR-NNN: Title

**Status:** Accepted
**Date:** YYYY-MM-DD

## Context
What problem prompted this decision?

## Decision
What did we decide?

## Alternatives Considered
What else did we evaluate?

## Consequences
What are the trade-offs?
```

To propose a new ADR: copy the template, assign the next sequential number, and submit with your change.
