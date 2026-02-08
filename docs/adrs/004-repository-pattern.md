# ADR-004: Repository Pattern

**Status:** Accepted
**Date:** 2025-11-01

## Context

CatSyphon accesses PostgreSQL through async SQLAlchemy 2.0 from three distinct contexts: FastAPI route handlers (async request/response), CLI commands (async Typer), and the watch daemon (long-running async loop). Each context needs the same queries but with different session lifecycle management. Scattering raw ORM queries across route handlers would couple business logic to SQLAlchemy specifics and make testing difficult without a live database.

## Decision

Typed repository classes that encapsulate all database queries for a given domain aggregate. Each repository accepts an `AsyncSession` and exposes domain-oriented methods:

```python
class ConversationRepository:
    def __init__(self, session: AsyncSession): ...
    async def get_by_id(self, id: UUID) -> Conversation | None: ...
    async def list_with_filters(self, filters: ConversationFilters) -> list[Conversation]: ...
    async def save(self, parsed: ParsedConversation) -> Conversation: ...
```

Repositories are instantiated per-request in API handlers via the `get_db()` async context manager. CLI and watch daemon create their own sessions.

## Alternatives Considered

**Direct ORM queries in route handlers.** Fewer files, but queries get duplicated across CLI and API. Testing requires mocking SQLAlchemy internals or running a full database. No natural place for query composition or caching logic.

**Django-style model managers** (class methods on ORM models). Ties query logic to model definitions. Harder to inject session context in async code. Conflates data shape (model) with data access (queries).

## Consequences

- Testable: repositories can be instantiated with an in-memory SQLite session for unit tests, or mocked entirely for handler tests.
- Consistent: all data access for a domain aggregate goes through one class. No scattered `session.execute()` calls.
- Extra abstraction layer between handlers and ORM. Justified by the three distinct calling contexts that share queries.
- Repository methods return ORM model instances, not Pydantic schemas. Schema conversion happens at the API boundary.
