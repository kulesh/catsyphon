# ADR-001: Monorepo Structure

**Status:** Accepted
**Date:** 2025-11-01

## Context

CatSyphon consists of a Python FastAPI backend and a React TypeScript frontend. These components share conceptual types (conversation structures, API contracts), evolve together on every feature, and deploy as a coordinated unit. We needed a repository strategy that minimizes coordination overhead during development and deployment.

## Decision

Single monorepo with top-level `backend/` and `frontend/` directories. Each directory maintains its own dependency management (`uv` for Python, `pnpm` for Node), build tooling, and test suites. Shared concerns (Docker Compose, CI workflows, documentation) live at the repository root.

```
catsyphon/
├── backend/       # Python FastAPI + SQLAlchemy
├── frontend/      # React + TypeScript + Vite
├── docs/          # Shared documentation
├── scripts/       # Development automation
└── docker-compose.yml
```

## Alternatives Considered

**Separate repositories.** Clean ownership boundaries, but cross-stack changes require synchronized PRs, version pinning between repos, and separate CI pipelines. The coordination tax is disproportionate for a two-person team.

**Polyrepo with git submodules.** Preserves repo separation while allowing a unified checkout. In practice, submodule workflows are fragile -- stale references, detached HEAD states, and recursive clone confusion add friction without meaningful isolation benefits at our scale.

## Consequences

- Atomic commits across frontend and backend when API contracts change.
- Single clone, single CI pipeline, single branch to reason about.
- `scripts/dev.sh` orchestrates the full stack from one place.
- Risk: tight coupling between frontend and backend if boundaries aren't maintained. Mitigated by keeping dependency management and build tooling strictly separate per directory.
- Monorepo tooling (Nx, Turborepo) is unnecessary at current scale but available if build times grow.
