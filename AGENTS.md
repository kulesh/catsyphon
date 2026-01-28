# Agent Guidelines

## Project Snapshot

CatSyphon is a full-stack monorepo for parsing, analyzing, and visualizing AI coding assistant logs
(Claude Code, OpenAI Codex, Cursor, Copilot, etc.). The backend ingests and enriches logs, stores
them in PostgreSQL, and exposes a REST API. The frontend provides dashboards and analytics.

## Repo Map

```
catsyphon/
├── backend/               # FastAPI backend (Python 3.11+)
│   └── src/catsyphon/
│       ├── api/           # REST endpoints
│       ├── db/            # SQLAlchemy models + repos
│       ├── parsers/       # Parser registry + built-in parsers
│       ├── pipeline/      # Ingestion pipeline + dedup
│       ├── tagging/       # OpenAI tagging (optional)
│       ├── watch.py       # Directory watch daemon
│       └── cli.py         # Typer CLI
├── frontend/              # React + TS frontend (Vite)
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── lib/
│       └── types/
├── docs/                  # Product + engineering docs
└── scripts/dev.sh         # One-command dev environment
```

## Local Dev Workflow

Prefer the dev script (handles Colima/Docker, port forwarding, migrations, and services):

```bash
./scripts/dev.sh start     # Full stack
./scripts/dev.sh backend   # Backend only
./scripts/dev.sh frontend  # Frontend only
./scripts/dev.sh status    # Service status
./scripts/dev.sh logs      # Stream logs
./scripts/dev.sh reset     # Reset DB (destructive)
```

### Backend Commands

```bash
cd backend

uv run catsyphon serve                          # API server
uv run uvicorn catsyphon.api.app:app --reload   # Dev server

uv run catsyphon ingest <path> --project "name"       # One-time ingest
uv run catsyphon ingest <path> --enable-tagging       # With OpenAI tagging
uv run catsyphon ingest <path> --force                # Re-ingest (skip dedup)

# Tests + quality
python3 -m pytest
python3 -m pytest tests/test_api_conversations.py
python3 -m mypy src/
python3 -m black src/ tests/
python3 -m ruff check src/ tests/
```

Notes:
- `--no-skip-duplicates` is deprecated; use `--force`.
- Watch directories are managed in the Web UI (Ingestion page) or via API.

### Frontend Commands

```bash
cd frontend

pnpm dev
pnpm build
pnpm test
pnpm test -- --run
pnpm run test:coverage
pnpm lint
pnpm tsc --noEmit
```

## Code Quality Conventions

- Python: Black (88 cols), Ruff (E/F/I/N/W), MyPy strict.
- TypeScript: ESLint + TypeScript typecheck.
- Prefer async/await in backend codepaths.
- Add tests for new features or bug fixes.

## Docs to Reference

- docs/ARCHITECTURE.md: system overview, pipeline flow, metrics
- docs/CLAUDE_CODE_LOG_FORMAT.md: Claude Code log format details
- docs/incremental-parsing.md: incremental parse behavior and benchmarks
- docs/plugin-sdk.md: building new parser plugins
- docs/collector-sdk.md and docs/collector-protocol.md: external collector clients
- docs/api-reference.md: REST API surface

## Issue Tracking with bd (beads)

IMPORTANT: This project uses bd (beads) for ALL issue tracking.
Do NOT use markdown TODOs, task lists, or external trackers.

### Quick Start (always use --json)

```bash
bd ready --json

bd create "Issue title" -t bug|feature|task|epic|chore -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:catsyphon-123 --json

bd update catsyphon-123 --status in_progress --json
bd update catsyphon-123 --priority 1 --json

bd close catsyphon-123 --reason "Completed" --json
```

### Priorities

- 0: Critical (security, data loss, broken builds)
- 1: High (major features, important bugs)
- 2: Medium (default)
- 3: Low (polish, optimization)
- 4: Backlog (future ideas)

### Workflow for AI Agents

1. Check ready work: `bd ready --json`
2. Claim the task: `bd update <id> --status in_progress --json`
3. Implement, test, document
4. If you discover new work:
   `bd create "Found bug" -p 1 --deps discovered-from:<parent-id> --json`
5. Complete: `bd close <id> --reason "Done" --json`
6. Always commit `.beads/issues.jsonl` with code changes

### Rules

- Use bd for ALL task tracking.
- Always include `--json`.
- Link discovered work with `discovered-from` dependencies.
- Check `bd ready --json` before asking "what should I work on?"
- Do not create markdown TODO lists.
