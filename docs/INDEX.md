# CatSyphon Documentation

## 30-Minute Reading Path

New to CatSyphon? Read these in order:

1. [Getting Started](guides/getting-started.md) -- Setup and first ingestion
2. [Architecture](architecture/ARCHITECTURE.md) -- System design and data flow
3. [Claude Code Log Format](reference/claude-code-log-format.md) -- What we parse

---

## Guides

| Document | Description |
|----------|-------------|
| [Getting Started](guides/getting-started.md) | Setup for individual users |
| [Enterprise Deployment](guides/enterprise-deployment.md) | Team/organization deployment |
| [Parser Quickstart](guides/parser-quickstart.md) | Adding support for new agents |
| [Plugin SDK](guides/plugin-sdk.md) | Parser plugin development guide |
| [Git Conventions](guides/git-conventions.md) | Commit message format and workflow |

## Architecture

| Document | Description |
|----------|-------------|
| [System Architecture](architecture/ARCHITECTURE.md) | Core design, pipeline, data model |
| [Incremental Parsing](architecture/incremental-parsing.md) | Offset-based parsing optimization |
| [Type System](architecture/type-system-reconciliation.md) | Type alignment across stack |
| [AI Insights & Metrics](architecture/ai-insights-metrics-analysis.md) | Metrics analysis design |
| [Skill-Based Analytics Product Spec](architecture/skill-based-analytics-product-spec.md) | Product specification for skill-native analytics |
| [Skill-Based Analytics Implementation Plan](architecture/skill-based-analytics-implementation-plan.md) | Phased implementation and migration plan |

## Reference

| Document | Description |
|----------|-------------|
| [API Reference](reference/api-reference.md) | REST API endpoints and schemas |
| [Claude Code Log Format](reference/claude-code-log-format.md) | JSONL log format specification |
| [Benchmarks](reference/benchmarks.md) | Performance measurements |
| [OTEL Ingestion](reference/otel-ingestion.md) | OpenTelemetry event ingestion |

## Collectors

| Document | Description |
|----------|-------------|
| [Architecture](collectors/architecture.md) | Collector subsystem design |
| [Protocol](collectors/protocol.md) | Event streaming specification |
| [SDK](collectors/sdk.md) | Client SDK for collectors |
| [Edge Sensors (macOS)](collectors/edge-sensors-macos.md) | Multi-Mac edge sensor deployment to central collector |
| [Log Collection](collectors/log-collection.md) | Log collection architecture |
| [Implementation Plan](collectors/implementation-plan.md) | Collector implementation roadmap |

## Strategy

| Document | Description |
|----------|-------------|
| [Preceptor Platform Analysis](strategy/preceptor-platform-analysis.md) | Gap analysis: CatSyphon + AIObscura as AI mentoring platform |
| [Preceptor Platform Roadmap](strategy/preceptor-platform-roadmap.md) | Phased roadmap to close gaps across both tools |

## Decision Records

| ADR | Title |
|-----|-------|
| [001](adrs/001-monorepo-structure.md) | Monorepo Structure |
| [002](adrs/002-plugin-based-parser-system.md) | Plugin-Based Parser System |
| [003](adrs/003-incremental-parsing.md) | Incremental Parsing |
| [004](adrs/004-repository-pattern.md) | Repository Pattern |
| [005](adrs/005-hash-based-deduplication.md) | Hash-Based Deduplication |
| [006](adrs/006-polling-over-websockets.md) | Polling Over WebSockets |
| [007](adrs/007-unified-ingestion-architecture.md) | Unified Ingestion Architecture |
| [008](adrs/008-skill-native-analytics-architecture.md) | Skill-Native Analytics Architecture |

See [ADR Index](adrs/README.md) for template and status legend.
