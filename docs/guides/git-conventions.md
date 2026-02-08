# Git Conventions

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): description

[optional body]
```

### Types

| Type | When |
|------|------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Build, tooling, dependencies, beads sync |

### Scopes

| Scope | Area |
|-------|------|
| `parser` | Log parsers (`backend/src/catsyphon/parsers/`) |
| `api` | REST API endpoints and schemas |
| `frontend` | React UI, components, pages |
| `pipeline` | Ingestion pipeline and ETL |
| `watch` | Watch daemon and directory monitoring |
| `docs` | Documentation changes |
| `db` | Database models, migrations, repositories |
| `tagging` | AI-powered metadata tagging |

### Examples

```
feat(parser): add Cursor log format support
fix(pipeline): prevent deadlock on concurrent session ingestion
refactor(frontend): extract TabNavigation component from page files
docs: create ADR framework with 7 decision records
test(api): add error scenario coverage for conversation endpoints
chore(beads): sync issue state
```

## Rules

### Beads State Commits

Beads issue state (`.beads/issues.jsonl`) must be committed separately from code changes:

```bash
# Good: separate commits
git commit -m "feat(parser): add incremental codex parsing"
bd sync  # creates its own "chore(beads): sync" commit
```

Do not mix `.beads/issues.jsonl` changes with feature/fix commits.

### Branch Hygiene

- Rebase feature branches before merging to main (eliminates merge commits and duplicate history)
- Branch naming: `feature/short-description`, `fix/short-description`, `refactor/short-description`

### Commit Discipline

- Every commit message states **what changed and why**
- No vague messages: "amendments", "fix things", "updates" are not acceptable
- Keep commits atomic — one logical change per commit
- If a commit touches both backend and frontend, that's fine if they're part of the same logical change
