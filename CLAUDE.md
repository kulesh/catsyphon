# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Things First

BEFORE ANYTHING ELSE: run 'bd ready' and review available work

## Assistant's Role

See [AGENTS.md](AGENTS.md) for philosophy, development guidelines, and communication style. Those rules apply here — do not duplicate them.

Key points: You are Kulesh's pairing buddy. Design bicycles, not Rube Goldberg machines. Own this codebase. Ultrathink always. Omit caveats and pleasantries.

## About This Project

**CatSyphon** parses, analyzes, and extracts insights from AI coding assistant conversation logs (Claude Code, Codex, Cursor, etc.). Full-stack monorepo: Python FastAPI backend + React TypeScript frontend + PostgreSQL.

**Current Status**: Phases 1-2 complete — core parsing/ingestion pipeline, web UI, live directory watching, file deduplication, and incremental parsing operational.

## Architecture

```
backend/src/catsyphon/
├── api/              # FastAPI REST endpoints
├── parsers/          # Plugin-based log parsers (registry pattern)
├── pipeline/         # ETL ingestion workflow
├── db/               # SQLAlchemy ORM + repositories
├── models/           # Data models (DB + Pydantic)
├── services/         # Ingestion service (chunked parsing orchestration)
├── tagging/          # AI metadata enrichment (OpenAI, optional)
├── cli.py            # Typer CLI
└── watch.py          # Live directory monitoring daemon

frontend/src/
├── pages/            # Dashboard, ConversationList, ConversationDetail, Upload, Ingestion
├── components/       # shadcn/ui based components
├── types/            # TypeScript API interfaces
└── lib/              # API client, TanStack Query setup
```

### Key Patterns

1. **Plugin-Based Parsers**: `ParserRegistry` dynamically routes log files to parsers. Parsers implement `ChunkedParser` protocol with `parse_metadata()` + `parse_messages(offset, limit)`.

2. **Chunked Parsing (ADR-009)**: All ingestion uses bounded-memory chunks (~3 MB peak). First-time = chunks from offset 0; appends = chunks from stored offset. Change detection (APPEND/TRUNCATE/REWRITE/UNCHANGED) via `raw_logs` table state tracking.

3. **Repository Pattern**: Data access through repository classes in `db/repositories/`.

4. **Async Throughout**: Backend uses async SQLAlchemy — always use `async with get_db()`.

5. **Frontend**: React 19 + shadcn/ui (not Tremor) + TanStack Query v5 with 15s polling auto-refresh.

6. **Database**: Normalized schema: Projects → Developers → Conversations → Epochs → Messages → Files Touched. JSONB columns for extensible metadata.

### Key Files for Chunked Parsing

- `parsers/incremental.py` — `ChunkedParser` protocol, `MessageChunk`, change detection
- `parsers/claude_code.py` — Claude Code parser implementation
- `parsers/codex.py` — OpenAI Codex parser implementation
- `services/ingestion_service.py` — Chunked ingestion orchestration
- `pipeline/ingestion.py` — `StageMetrics` class for pipeline instrumentation

## Running the App

### Docker (recommended)

```bash
./catsyphon up        # Detect AI tools, build, start all services → http://localhost:3000
./catsyphon down      # Stop
./catsyphon status    # Show status
./catsyphon logs      # Stream backend logs
./catsyphon reset     # Destroy all data and start fresh
```

### Native Development

```bash
./scripts/dev.sh start     # Full stack (Colima, PostgreSQL, API, Frontend)
./scripts/dev.sh backend   # Backend only
./scripts/dev.sh frontend  # Frontend only
./scripts/dev.sh status    # Service status
./scripts/dev.sh reset     # Reset DB (destructive)
```

## Development Commands

### Backend

```bash
cd backend

# Run
uv run catsyphon serve                          # Production server :8000
uv run uvicorn catsyphon.api.app:app --reload   # Dev server with hot reload

# Ingest
uv run catsyphon ingest <path> --project "name"        # One-time import
uv run catsyphon ingest <path> --enable-tagging         # With LLM tagging
uv run catsyphon ingest <path> --force                  # Force re-ingest (skip dedup)

# Test & quality
python3 -m pytest                                # All tests
python3 -m pytest tests/test_api_conversations.py  # Single file
python3 -m pytest -k "deduplication"              # Pattern match
python3 -m mypy src/                              # Type checking (strict)
python3 -m black src/ tests/                      # Format (88 cols)
python3 -m ruff check src/ tests/                 # Lint (E/F/I/N/W rules)
python3 -m ruff check --fix src/ tests/           # Lint with auto-fix

# Migrations
uv run alembic revision --autogenerate -m "Description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

### Frontend

```bash
cd frontend

pnpm dev                # Dev server (Vite + HMR)
pnpm build              # Production build (tsc + vite)
pnpm test               # Vitest watch mode
pnpm test -- --run      # Tests once (CI)
pnpm run test:coverage  # Coverage report
pnpm lint               # ESLint
pnpm tsc --noEmit       # TypeScript type check
```

### API Docs

- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Git Conventions

Conventional Commits format: `type(scope): description`

**Types**: feat, fix, refactor, docs, test, chore
**Scopes**: parser, api, frontend, pipeline, watch, db, tagging, docs

```bash
feat(parser): add Cursor log format support
fix(pipeline): prevent deadlock on concurrent session ingestion
```

Beads state (`.beads/issues.jsonl`) must be committed separately from code changes. See [docs/guides/git-conventions.md](docs/guides/git-conventions.md) for full rules.

## Issue Tracking with bd (beads)

**CRITICAL**: Always use `bd` for task tracking, never markdown TODOs.

```bash
bd ready                                           # Show unblocked work
bd create --title="Title" --type=bug|feature|task --priority=0-4  # Create issue
bd update <id> --status=in_progress               # Claim task
bd close <id> --reason="Completed"                # Complete task
```

Priority: 0=critical, 1=high, 2=medium (default), 3=low, 4=backlog. Always commit `.beads/issues.jsonl` with code changes.

## Configuration

Copy `.env.example` to `.env`. Key variables: `OPENAI_API_KEY` (optional, for AI tagging), `POSTGRES_*` (database), `LOG_LEVEL`. Managed via Pydantic Settings in `backend/src/catsyphon/config.py`.

## Documentation

- [docs/INDEX.md](docs/INDEX.md) — Navigation hub for all documentation
- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) — System design, pipeline, metrics
- [docs/architecture/incremental-parsing.md](docs/architecture/incremental-parsing.md) — Chunked parsing details
- [docs/reference/api-reference.md](docs/reference/api-reference.md) — REST API surface
- [docs/guides/plugin-sdk.md](docs/guides/plugin-sdk.md) — Building new parser plugins
- [docs/adrs/README.md](docs/adrs/README.md) — Architecture Decision Records
