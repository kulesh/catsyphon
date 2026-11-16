# Contributing to CatSyphon

Thank you for your interest in contributing to CatSyphon! This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Issue Tracking](#issue-tracking)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 20 LTS**
- **Docker Desktop** (for PostgreSQL)
- **[mise](https://mise.jdx.dev/)** (recommended for tool version management)
### Development Setup

```bash
# Clone the repository
git clone https://github.com/kulesh/catsyphon.git
cd catsyphon

# Install tool versions with mise
mise install

# Start PostgreSQL
docker-compose up -d

# Backend setup
cd backend
uv sync --all-extras
uv run alembic upgrade head

# Frontend setup
cd ../frontend
pnpm install
```

## Issue Tracking

Use [GitHub Issues](https://github.com/kulesh/catsyphon/issues) for all task tracking.

## Code Style

### Python (Backend)

We enforce strict code quality with automated tools:

```bash
cd backend

# Format code with Black (line length: 88)
uv run black src/ tests/

# Lint with Ruff
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/  # Auto-fix issues

# Type checking with MyPy (strict mode)
uv run mypy src/
```

**Requirements:**
- Black formatting (mandatory)
- Ruff linting passes (E, F, I, N, W rules)
- MyPy strict type checking passes
- Async/await throughout (FastAPI + SQLAlchemy)

### TypeScript (Frontend)

```bash
cd frontend

# Lint with ESLint
pnpm lint

# Type check
pnpm tsc --noEmit
```

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/catsyphon --cov-report=html

# Run specific test file
uv run pytest tests/test_parsers/test_claude_code.py

# Run tests matching a pattern
uv run pytest -k "incremental"

# Run with verbose output
uv run pytest -v
```

**Test categories:**
- `tests/test_parsers/` - Parser unit tests
- `tests/test_api_*.py` - API endpoint tests
- `tests/test_pipeline.py` - Integration tests
- `tests/test_performance.py` - Benchmark tests

### Frontend Tests

```bash
cd frontend

# Run tests in watch mode
pnpm test

# Run once (CI mode)
pnpm test -- --run

# With coverage
pnpm run test:coverage
```

### Coverage Requirements

- Maintain existing coverage levels
- New features should include tests
- Bug fixes should include regression tests

## Pull Request Process

### 1. Find or Create a Task

Check [GitHub Issues](https://github.com/kulesh/catsyphon/issues) for existing work, or open a new issue.

### 2. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 3. Make Your Changes

- Write clean, well-documented code
- Follow the code style guidelines
- Add tests for new functionality
- Update documentation if needed

### 4. Run Quality Checks

```bash
cd backend
uv run pytest                    # Tests pass
uv run mypy src/                 # Type checking passes
uv run black src/ tests/         # Code is formatted
uv run ruff check src/ tests/    # Linting passes

cd ../frontend
pnpm test -- --run              # Frontend tests pass
pnpm tsc --noEmit               # TypeScript compiles
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: description of your change"
git push origin feature/your-feature-name
```

### 6. Create Pull Request

- Use a clear, descriptive title
- Reference the GitHub issue (e.g., "Fixes #42")
- Describe what changed and why
- List any breaking changes
- Include screenshots for UI changes

### PR Checklist

- [ ] All tests pass
- [ ] Type checking passes
- [ ] Code is formatted (Black/ESLint)
- [ ] Linting passes (Ruff/ESLint)
- [ ] Documentation updated (if needed)
- [ ] No unnecessary files included

## Adding a Parser Plugin

If you're adding support for a new AI coding assistant:

1. Create parser in `backend/src/catsyphon/parsers/`
2. Inherit from `ConversationParser` base class
3. Implement `can_parse()` and `parse()` methods
4. Register in `parsers/registry.py`
5. Add tests in `tests/test_parsers/`

See [docs/parser-quickstart.md](./docs/parser-quickstart.md) for a 15-minute tutorial.

## Questions?

- Check existing documentation in [docs/](./docs/)
- Review [AGENTS.md](./AGENTS.md) for workflow details
- Open an issue on [GitHub](https://github.com/kulesh/catsyphon/issues)

Thank you for contributing to CatSyphon!
