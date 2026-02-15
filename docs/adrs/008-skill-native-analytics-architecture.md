# ADR-008: Skill-Native Analytics Architecture

**Status:** Accepted  
**Date:** 2026-02-12

## Context

CatSyphon analytics capabilities (Weekly Digest, AI Insights, and dashboard analytics modules) are currently implemented as backend/frontend code paths. This model creates four recurring problems:

- Feature delivery bottleneck: each analytics variation requires application code changes and deployment.
- Limited customization: workspace-specific analytics needs cannot be met without adding new code branches.
- Weak provenance: outputs are not consistently linked to an immutable logic version.
- Growing maintenance burden: every new analytics module increases permanent code complexity.

The product direction is to make analytics a configurable platform capability while preserving correctness and operational safety.

## Decision

CatSyphon will adopt a skill-native analytics architecture:

1. **All analytics outputs are produced by skills.**
- Weekly Digest, AI Insights, recommendation modules, and dashboard analytics are bound to skills rather than hardcoded execution paths.

2. **Skill logic is versioned domain data.**
- Skills and skill versions are first-class entities with immutable version records.
- Every run persists lineage and output artifacts.

3. **A trusted runtime kernel remains code-based.**
- Policy enforcement, semantic data contracts, execution orchestration, scheduling, and observability remain in core application code.
- Skill definitions are declarative and execute through approved operators.

4. **No arbitrary user code execution in v1.**
- Custom skills may not execute shell commands, arbitrary Python/JS, or unrestricted external calls.
- Capability policies gate access to datasets, operators, and optional LLM usage.

5. **Correctness is enforced as a platform invariant.**
- Input/output schema validation is mandatory.
- Certification gates are required before production promotion.
- Provenance (`skill_id@version`, inputs, runtime metadata) is attached to every artifact.

6. **Migration is incremental with compatibility facades.**
- Existing endpoints and surfaces remain stable during transition, but route internally through skill bindings.
- Legacy hardcoded analytics paths are removed only after parity and stability targets are met.

## Alternatives Considered

### 1. Keep analytics fully code-based

Rejected. This preserves current bottlenecks and does not support tenant-level adaptability.

### 2. Hybrid model (core analytics code-based, optional custom skills)

Rejected as a long-term architecture. It would split ownership and correctness models, causing drift between “official” and “custom” analytics behavior.

### 3. Allow arbitrary user-defined code plugins

Rejected for v1. Security, isolation, and reproducibility risks are too high for multi-tenant operation.

## Consequences

### Positive

- Analytics capability can evolve without coupling every change to app release cycles.
- Workspaces can tailor analytics behavior through governed customization.
- Outputs gain reliable provenance and reproducibility.
- Product surfaces become composable via skill bindings.

### Trade-offs

- New platform complexity: runtime, policy, certification, and lifecycle management.
- Upfront migration effort to convert existing analytics modules into built-in skill packs.
- Strong contract discipline required across semantic views, operator schemas, and version compatibility.

### Required Follow-Through

- Implement new skill-domain entities and APIs.
- Build runtime kernel, policy engine, and certification workflow.
- Migrate built-in analytics modules to internal skills with regression parity checks.
- Add provenance UI and operational runbooks.

