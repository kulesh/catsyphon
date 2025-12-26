# Implementation Plan: Collector Integration

## Overview

This plan covers implementing the collector integration across both repositories:
- **aiobscura**: Add gRPC export capability (push to CatSyphon)
- **CatSyphon**: Add gRPC ingestion service (receive from collectors)

Both products continue to work standalone; integration is opt-in.

---

## Phase 0: Type System Alignment (Foundation)

The type systems of aiobscura and CatSyphon have diverged. Before adding integration or security fixes, we must establish a stable, aligned foundation. See `docs/type-system-reconciliation.md` for full analysis.

### 0.1 Summary of Changes

**CatSyphon must adopt from aiobscura:**

| Type | Change | Priority |
|------|--------|----------|
| `AuthorRole` enum | Add 6 values: human, caller, assistant, agent, tool, system | High |
| `MessageType` enum | Add 8 values: prompt, response, tool_call, tool_result, plan, summary, context, error | High |
| `Thread` table | Add parent-child thread hierarchy | High |
| `BackingModel` table | Track LLM provider/model | High |
| Dual timestamps | Add `emitted_at`, `observed_at` to messages | High |
| `raw_data` field | Add JSONB per message for lossless capture | Medium |

**aiobscura verification:**
- Types already match protobuf schema ✅
- No changes expected (confirm during implementation)

### 0.2 CatSyphon Schema Changes

**Migration 1: Add AuthorRole enum**

```sql
-- Create enum type
CREATE TYPE author_role AS ENUM (
    'human', 'caller', 'assistant', 'agent', 'tool', 'system'
);

-- Add column
ALTER TABLE messages ADD COLUMN author_role author_role;

-- Backfill from existing role string
UPDATE messages SET author_role = CASE role
    WHEN 'user' THEN 'human'::author_role
    WHEN 'system' THEN 'system'::author_role
    ELSE 'assistant'::author_role
END;

-- Make NOT NULL after backfill
ALTER TABLE messages ALTER COLUMN author_role SET NOT NULL;
```

**Migration 2: Add MessageType enum**

```sql
CREATE TYPE message_type AS ENUM (
    'prompt', 'response', 'tool_call', 'tool_result',
    'plan', 'summary', 'context', 'error'
);

ALTER TABLE messages ADD COLUMN message_type message_type;

-- Backfill based on role and content analysis
UPDATE messages SET message_type = CASE
    WHEN role = 'user' THEN 'prompt'::message_type
    WHEN tool_calls IS NOT NULL THEN 'tool_call'::message_type
    WHEN tool_results IS NOT NULL THEN 'tool_result'::message_type
    ELSE 'response'::message_type
END;

ALTER TABLE messages ALTER COLUMN message_type SET NOT NULL;
```

**Migration 3: Add Thread table**

```sql
CREATE TYPE thread_type AS ENUM ('main', 'agent', 'background');

CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    thread_type thread_type NOT NULL DEFAULT 'main',
    spawned_by_message_id UUID REFERENCES messages(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_parent_thread_same_conversation CHECK (
        parent_thread_id IS NULL OR
        parent_thread_id IN (SELECT id FROM threads WHERE conversation_id = threads.conversation_id)
    )
);

CREATE INDEX idx_threads_conversation ON threads(conversation_id);
CREATE INDEX idx_threads_parent ON threads(parent_thread_id);

-- Add thread reference to messages
ALTER TABLE messages ADD COLUMN thread_id UUID REFERENCES threads(id);
CREATE INDEX idx_messages_thread ON messages(thread_id);
```

**Migration 4: Add BackingModel table**

```sql
CREATE TABLE backing_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}',
    UNIQUE (provider, model_id)
);

ALTER TABLE conversations ADD COLUMN backing_model_id UUID REFERENCES backing_models(id);
CREATE INDEX idx_conversations_backing_model ON conversations(backing_model_id);
```

**Migration 5: Add dual timestamps**

```sql
ALTER TABLE messages
ADD COLUMN emitted_at TIMESTAMPTZ,
ADD COLUMN observed_at TIMESTAMPTZ;

-- Backfill: use timestamp for emitted, created_at for observed
UPDATE messages SET
    emitted_at = COALESCE(timestamp, created_at),
    observed_at = created_at;

-- Make NOT NULL after backfill
ALTER TABLE messages ALTER COLUMN emitted_at SET NOT NULL;
ALTER TABLE messages ALTER COLUMN observed_at SET NOT NULL;
```

**Migration 6: Add raw_data per message**

```sql
ALTER TABLE messages ADD COLUMN raw_data JSONB;
-- raw_data is optional, NULL for messages ingested before this migration
```

### 0.3 CatSyphon Model Updates

**File:** `backend/src/catsyphon/models/db.py`

```python
# Add enum classes
class AuthorRole(str, Enum):
    HUMAN = "human"
    CALLER = "caller"
    ASSISTANT = "assistant"
    AGENT = "agent"
    TOOL = "tool"
    SYSTEM = "system"

class MessageType(str, Enum):
    PROMPT = "prompt"
    RESPONSE = "response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PLAN = "plan"
    SUMMARY = "summary"
    CONTEXT = "context"
    ERROR = "error"

class ThreadType(str, Enum):
    MAIN = "main"
    AGENT = "agent"
    BACKGROUND = "background"

# Add Thread model
class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"))
    parent_thread_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("threads.id"))
    thread_type: Mapped[ThreadType] = mapped_column(default=ThreadType.MAIN)
    spawned_by_message_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("messages.id"))
    started_at: Mapped[datetime]
    ended_at: Mapped[Optional[datetime]]
    last_activity_at: Mapped[datetime]
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    conversation = relationship("Conversation", back_populates="threads")
    parent_thread = relationship("Thread", remote_side=[id])
    messages = relationship("Message", back_populates="thread")

# Add BackingModel model
class BackingModel(Base):
    __tablename__ = "backing_models"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(50))
    model_id: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

# Update Message model
class Message(Base):
    # ... existing fields ...

    # New fields
    author_role: Mapped[AuthorRole]
    message_type: Mapped[MessageType]
    thread_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("threads.id"))
    emitted_at: Mapped[datetime]
    observed_at: Mapped[datetime]
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # New relationship
    thread = relationship("Thread", back_populates="messages")

# Update Conversation model
class Conversation(Base):
    # ... existing fields ...

    # New field
    backing_model_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("backing_models.id")
    )

    # New relationships
    threads = relationship("Thread", back_populates="conversation")
    backing_model = relationship("BackingModel")
```

### 0.4 CatSyphon Parser Updates

Update Claude Code parser to populate new fields:

**File:** `backend/src/catsyphon/parsers/claude_code.py`

```python
def _parse_message(self, raw_message: dict) -> ParsedMessage:
    # Map role to AuthorRole enum
    role_mapping = {
        "user": AuthorRole.HUMAN,
        "assistant": AuthorRole.ASSISTANT,
        "system": AuthorRole.SYSTEM,
    }
    author_role = role_mapping.get(raw_message.get("role"), AuthorRole.ASSISTANT)

    # Determine message type
    if author_role == AuthorRole.HUMAN:
        message_type = MessageType.PROMPT
    elif raw_message.get("tool_calls"):
        message_type = MessageType.TOOL_CALL
    elif raw_message.get("tool_result"):
        message_type = MessageType.TOOL_RESULT
    else:
        message_type = MessageType.RESPONSE

    return ParsedMessage(
        author_role=author_role,
        message_type=message_type,
        content=raw_message.get("content"),
        emitted_at=self._parse_timestamp(raw_message.get("timestamp")),
        observed_at=datetime.utcnow(),
        raw_data=raw_message,  # Preserve original for reprocessing
        # ... other fields
    )
```

### 0.5 aiobscura Verification

Verify aiobscura's types match the protobuf schema:

```rust
// src/domain/types.rs - verify these exist and match:

pub enum AuthorRole {
    Human,
    Caller,
    Assistant,
    Agent,
    Tool,
    System,
}

pub enum MessageType {
    Prompt,
    Response,
    ToolCall,
    ToolResult,
    Plan,
    Summary,
    Context,
    Error,
}

pub enum ThreadType {
    Main,
    Agent,
    Background,
}
```

If any mismatches found, update aiobscura to match protobuf.

### 0.6 Testing: Independent Product Validation

Before proceeding to Phase 1, verify each product works independently:

**CatSyphon Tests:**
```bash
cd backend

# Run migrations
uv run alembic upgrade head

# Run all tests
python3 -m pytest

# Verify new types work
python3 -m pytest tests/test_models/ -v
python3 -m pytest tests/test_parsers/ -v

# Test ingestion with new schema
uv run catsyphon ingest /path/to/claude/logs --project "test"
```

**aiobscura Tests:**
```bash
cd aiobscura

# Run all tests
cargo test

# Verify types compile and match
cargo test domain::types
```

### 0.7 Implementation Checklist

```
CatSyphon:
[ ] Create migration: Add author_role enum + column
[ ] Create migration: Add message_type enum + column
[ ] Create migration: Add threads table + message FK
[ ] Create migration: Add backing_models table + conversation FK
[ ] Create migration: Add emitted_at, observed_at columns
[ ] Create migration: Add raw_data column
[ ] Run migrations and backfill existing data
[ ] Update Message model with new fields
[ ] Add Thread model
[ ] Add BackingModel model
[ ] Update Conversation model with new relationships
[ ] Update Claude Code parser to populate new fields
[ ] Update API schemas to expose new fields
[ ] Update tests for new types
[ ] Verify full test suite passes

aiobscura:
[ ] Verify AuthorRole enum matches protobuf
[ ] Verify MessageType enum matches protobuf
[ ] Verify ThreadType enum matches protobuf
[ ] Verify all tests pass
```

---

## Phase 1: Multi-Tenancy Security Fixes

A security audit revealed that CatSyphon's multi-tenancy is schema-ready but not enforcement-ready. The following issues must be fixed before adding collector integration:

### 1.1 Current State

| Layer | Status | Issue |
|-------|--------|-------|
| Database Schema | ✅ Ready | Proper FK relationships, workspace_id columns |
| Repository Layer | ⚠️ Partial | Methods exist but require callers to pass workspace_id |
| API Layer | ❌ Critical | 12+ endpoints bypass workspace validation |
| Authentication | ❌ Missing | Uses "first workspace" hack |

**Attack Vector**: Anyone knowing a `conversation_id` can call `GET /conversations/{id}` and retrieve data from ANY workspace.

### 1.2 API Endpoints to Fix

**Priority 1 - Conversation Data Access:**
```
backend/src/catsyphon/api/routes/conversations.py
  - GET /conversations/{id}         → Add workspace_id filter
  - GET /conversations/{id}/messages → Add workspace_id filter

backend/src/catsyphon/api/routes/canonical.py
  - GET /conversations/{id}/canonical  → Add workspace_id filter
  - PUT /conversations/{id}/canonical  → Add workspace_id filter
  - POST /conversations/{id}/canonical/generate → Add workspace_id filter
  - GET /conversations/{id}/canonical/status    → Add workspace_id filter
```

**Priority 2 - Project/Developer Access:**
```
backend/src/catsyphon/api/routes/projects.py
  - GET /projects/{id}             → Add workspace_id filter
  - PUT /projects/{id}             → Add workspace_id filter
  - DELETE /projects/{id}          → Add workspace_id filter
  - GET /projects/{id}/conversations → Add workspace_id filter
  - GET /projects/{id}/developers  → Add workspace_id filter
  - GET /projects/{id}/stats       → Add workspace_id filter
```

**Priority 3 - Ingestion Pipeline:**
```
backend/src/catsyphon/api/routes/ingestion.py
  - GET /ingestion/jobs/{id}       → Add workspace_id filter
  - DELETE /ingestion/jobs/{id}    → Add workspace_id filter
```

### 1.3 Authentication Context

Create a proper authentication dependency that provides workspace context:

**File:** `backend/src/catsyphon/api/auth.py`

```python
from fastapi import Depends, HTTPException, Header
from uuid import UUID
from typing import Optional

class AuthContext:
    """Authenticated request context."""
    workspace_id: UUID
    user_id: Optional[UUID]
    collector_id: Optional[UUID]

async def get_auth_context(
    authorization: Optional[str] = Header(None),
    x_workspace_id: Optional[str] = Header(None),
) -> AuthContext:
    """
    Extract authentication context from request.

    For now (development), accept X-Workspace-Id header.
    Later, this will validate JWT tokens or API keys.
    """
    if x_workspace_id:
        return AuthContext(workspace_id=UUID(x_workspace_id))

    # For collector API keys (cs_xxx format)
    if authorization and authorization.startswith("Bearer cs_"):
        collector = await validate_collector_key(authorization[7:])
        if collector:
            return AuthContext(
                workspace_id=collector.workspace_id,
                collector_id=collector.id
            )

    raise HTTPException(
        status_code=401,
        detail="Missing or invalid authentication"
    )
```

### 1.4 Updated Endpoint Pattern

Before:
```python
@router.get("/conversations/{id}")
async def get_conversation(
    id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    conversation = await repo.get(db, id)  # NO ISOLATION!
    if not conversation:
        raise HTTPException(404)
    return conversation
```

After:
```python
@router.get("/conversations/{id}")
async def get_conversation(
    id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    conversation = await repo.get_by_workspace(
        db, id, workspace_id=auth.workspace_id
    )
    if not conversation:
        raise HTTPException(404)  # Returns 404 even if exists in other workspace
    return conversation
```

### 1.5 Repository Updates

Add workspace-aware methods to repositories:

```python
class ConversationRepository:
    async def get_by_workspace(
        self,
        db: AsyncSession,
        id: UUID,
        workspace_id: UUID
    ) -> Optional[Conversation]:
        """Get conversation only if it belongs to the workspace."""
        stmt = select(Conversation).where(
            Conversation.id == id,
            Conversation.workspace_id == workspace_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
```

### 1.6 Implementation Checklist

```
[ ] Create backend/src/catsyphon/api/auth.py
[ ] Add get_by_workspace() to ConversationRepository
[ ] Add get_by_workspace() to ProjectRepository
[ ] Add get_by_workspace() to DeveloperRepository
[ ] Add get_by_workspace() to IngestionJobRepository
[ ] Update conversations.py endpoints (2 endpoints)
[ ] Update canonical.py endpoints (4 endpoints)
[ ] Update projects.py endpoints (6 endpoints)
[ ] Update ingestion.py endpoints (2 endpoints)
[ ] Add integration tests for cross-workspace access denial
[ ] Remove _get_default_workspace_id() usage
```

---

## Shared: Protobuf Schema

The canonical schema lives in CatSyphon and is copied/vendored to aiobscura:

```
catsyphon/proto/catsyphon/telemetry/v1/sessions.proto  (source of truth)
aiobscura/proto/catsyphon/telemetry/v1/sessions.proto  (vendored copy)
```

**Status**: ✅ Already created in CatSyphon

---

## Phase 2: CatSyphon - gRPC Ingestion Service

### 2.1 Protobuf Codegen Setup

**Files to create:**
```
backend/
├── proto/                          # Symlink or copy from repo root
├── src/catsyphon/
│   ├── grpc/
│   │   ├── __init__.py
│   │   ├── generated/              # Generated Python code
│   │   │   ├── __init__.py
│   │   │   ├── sessions_pb2.py
│   │   │   └── sessions_pb2_grpc.py
│   │   ├── server.py               # gRPC server setup
│   │   ├── interceptors.py         # Auth interceptor
│   │   └── services/
│   │       ├── __init__.py
│   │       └── session_ingestion.py  # SessionIngestion service impl
```

**Dependencies to add** (`pyproject.toml`):
```toml
grpcio = "^1.60"
grpcio-tools = "^1.60"
protobuf = "^4.25"
```

**Build script** (`scripts/generate_proto.sh`):
```bash
#!/bin/bash
python -m grpc_tools.protoc \
  -I../../proto \
  --python_out=src/catsyphon/grpc/generated \
  --grpc_python_out=src/catsyphon/grpc/generated \
  ../../proto/catsyphon/telemetry/v1/sessions.proto
```

### 2.2 Collector REST API

**Files to create:**
```
backend/src/catsyphon/api/routes/collectors.py
```

**Endpoints:**
```python
# POST /api/collectors - Register new collector
@router.post("/collectors", response_model=CollectorResponse)
async def create_collector(
    request: CollectorCreate,
    workspace_id: UUID,  # From auth context
    db: Session = Depends(get_db)
) -> CollectorResponse:
    # Generate API key: cs_ + 32 random bytes (base62)
    # Store bcrypt hash
    # Return collector info + plaintext key (shown once)

# GET /api/collectors - List collectors
# PATCH /api/collectors/{id} - Update collector
# DELETE /api/collectors/{id} - Deactivate collector
# POST /api/collectors/{id}/rotate-key - Rotate API key
```

**Schemas to add** (`api/schemas.py`):
```python
class CollectorCreate(BaseModel):
    name: str
    collector_type: str  # 'aiobscura', 'ci-server', etc.

class CollectorResponse(BaseModel):
    id: UUID
    name: str
    collector_type: str
    api_key_prefix: str
    is_active: bool
    created_at: datetime
    # api_key only included on create response

class CollectorWithKey(CollectorResponse):
    api_key: str  # Only on create/rotate
```

### 2.3 gRPC Authentication Interceptor

**File:** `backend/src/catsyphon/grpc/interceptors.py`

```python
class ApiKeyInterceptor(grpc.ServerInterceptor):
    """Validates API key from gRPC metadata."""

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        auth_header = metadata.get('authorization', '')

        if not auth_header.startswith('Bearer '):
            return self._unauthenticated()

        api_key = auth_header[7:]  # Strip "Bearer "
        collector = self._validate_key(api_key)

        if not collector:
            return self._unauthenticated()

        # Inject collector context for downstream handlers
        context.collector = collector
        context.workspace_id = collector.workspace_id

        return continuation(handler_call_details)
```

### 2.4 SessionIngestion Service

**File:** `backend/src/catsyphon/grpc/services/session_ingestion.py`

```python
class SessionIngestionServicer(sessions_pb2_grpc.SessionIngestionServicer):

    async def ExportSessions(self, request, context):
        collector = context.collector
        batch_id = request.batch_id

        # Check idempotency (batch_id already processed?)
        if await self._is_duplicate_batch(batch_id):
            return self._cached_response(batch_id)

        results = []
        for session_proto in request.sessions:
            try:
                # Convert protobuf → internal model
                parsed = self._proto_to_parsed_session(session_proto)

                # Use existing ingestion pipeline
                conversation = await ingest_session(
                    parsed,
                    workspace_id=collector.workspace_id,
                    collector_id=collector.id
                )

                results.append(SessionResult(
                    session_id=session_proto.id,
                    catsyphon_id=str(conversation.id),
                    status=SessionStatus.CREATED
                ))
            except DuplicateError:
                results.append(SessionResult(
                    session_id=session_proto.id,
                    status=SessionStatus.DUPLICATE
                ))
            except Exception as e:
                results.append(SessionResult(
                    session_id=session_proto.id,
                    status=SessionStatus.FAILED,
                    error=Error(code=ErrorCode.INTERNAL, message=str(e))
                ))

        # Cache response for idempotency
        response = ExportSessionsResponse(
            batch_id=batch_id,
            status=self._compute_batch_status(results),
            results=results
        )
        await self._cache_response(batch_id, response)

        return response
```

### 2.5 gRPC Server Integration

**File:** `backend/src/catsyphon/grpc/server.py`

```python
async def create_grpc_server(port: int = 4317) -> grpc.aio.Server:
    server = grpc.aio.server(
        interceptors=[ApiKeyInterceptor()]
    )

    sessions_pb2_grpc.add_SessionIngestionServicer_to_server(
        SessionIngestionServicer(), server
    )

    # Health check service
    health_pb2_grpc.add_HealthServicer_to_server(
        HealthServicer(), server
    )

    server.add_insecure_port(f'[::]:{port}')
    return server
```

**Update CLI** (`cli.py`):
```python
@app.command()
def serve(
    http_port: int = 8000,
    grpc_port: int = 4317,
):
    """Start both HTTP and gRPC servers."""
    # Run both servers concurrently
    asyncio.run(run_servers(http_port, grpc_port))
```

### 2.6 Proto → Model Mapping

Wire protobuf types to existing ingestion pipeline (schema already updated in Phase 0):

**File:** `backend/src/catsyphon/grpc/services/mapper.py`

```python
from catsyphon.models.db import AuthorRole, MessageType, ThreadType

def proto_author_role_to_db(proto_role: int) -> AuthorRole:
    """Map protobuf AuthorRole enum to database enum."""
    mapping = {
        1: AuthorRole.HUMAN,
        2: AuthorRole.CALLER,
        3: AuthorRole.ASSISTANT,
        4: AuthorRole.AGENT,
        5: AuthorRole.TOOL,
        6: AuthorRole.SYSTEM,
    }
    return mapping.get(proto_role, AuthorRole.ASSISTANT)

def proto_message_type_to_db(proto_type: int) -> MessageType:
    """Map protobuf MessageType enum to database enum."""
    mapping = {
        1: MessageType.PROMPT,
        2: MessageType.RESPONSE,
        3: MessageType.TOOL_CALL,
        4: MessageType.TOOL_RESULT,
        5: MessageType.PLAN,
        6: MessageType.SUMMARY,
        7: MessageType.CONTEXT,
        8: MessageType.ERROR,
    }
    return mapping.get(proto_type, MessageType.RESPONSE)

def proto_session_to_parsed(session_proto) -> ParsedConversation:
    """Convert protobuf Session to internal ParsedConversation."""
    threads = [proto_thread_to_parsed(t) for t in session_proto.threads]
    messages = [msg for thread in threads for msg in thread.messages]

    return ParsedConversation(
        session_id=session_proto.id,
        assistant=session_proto.assistant.name.lower(),
        threads=threads,
        messages=messages,
        backing_model=proto_backing_model_to_db(session_proto.backing_model),
        # ... other fields
    )
```

---

## Phase 3: aiobscura - gRPC Export Client

### 3.1 Protobuf Codegen Setup

**Files to create:**
```
aiobscura/
├── proto/
│   └── catsyphon/telemetry/v1/sessions.proto  # Vendored copy
├── build.rs                                     # Protobuf codegen
├── src/
│   └── export/
│       ├── mod.rs
│       ├── client.rs                           # gRPC client
│       ├── mapper.rs                           # Internal → Proto conversion
│       └── config.rs                           # Export configuration
```

**Dependencies to add** (`Cargo.toml`):
```toml
[dependencies]
tonic = "0.11"
prost = "0.12"
prost-types = "0.12"

[build-dependencies]
tonic-build = "0.11"
```

**Build script** (`build.rs`):
```rust
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .build_server(false)  // Client only
        .compile(
            &["proto/catsyphon/telemetry/v1/sessions.proto"],
            &["proto/"],
        )?;
    Ok(())
}
```

### 3.2 Export Client

**File:** `src/export/client.rs`

```rust
pub struct CatSyphonClient {
    client: SessionIngestionClient<Channel>,
    collector_id: String,
    workspace_id: String,
    api_key: String,
}

impl CatSyphonClient {
    pub async fn connect(config: &ExportConfig) -> Result<Self> {
        let channel = Channel::from_shared(config.endpoint.clone())?
            .connect()
            .await?;

        let client = SessionIngestionClient::new(channel);

        Ok(Self {
            client,
            collector_id: config.collector_id.clone(),
            workspace_id: config.workspace_id.clone(),
            api_key: config.api_key.clone(),
        })
    }

    pub async fn export_sessions(&mut self, sessions: Vec<Session>) -> Result<ExportResult> {
        let batch_id = Uuid::new_v4().to_string();

        let request = ExportSessionsRequest {
            collector: Some(CollectorInfo {
                r#type: "aiobscura".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
                hostname: hostname::get()?.to_string_lossy().to_string(),
                collector_id: self.collector_id.clone(),
                workspace_id: self.workspace_id.clone(),
                metadata: HashMap::new(),
            }),
            batch_id: batch_id.clone(),
            sessions: sessions.into_iter().map(|s| s.into_proto()).collect(),
        };

        let mut request = tonic::Request::new(request);
        request.metadata_mut().insert(
            "authorization",
            format!("Bearer {}", self.api_key).parse()?,
        );

        let response = self.client.export_sessions(request).await?;
        Ok(ExportResult::from_proto(response.into_inner()))
    }
}
```

### 3.3 Internal → Proto Mapper

**File:** `src/export/mapper.rs`

```rust
impl Session {
    pub fn into_proto(self) -> proto::Session {
        proto::Session {
            id: self.id,
            assistant: self.assistant.into_proto(),
            backing_model: self.backing_model_id.map(|id| proto::BackingModel {
                provider: /* lookup */,
                model_id: id,
                display_name: None,
            }),
            project: Some(proto::Project {
                path: self.project_path,
                name: self.project_name,
                metadata: HashMap::new(),
            }),
            threads: self.threads.into_iter().map(|t| t.into_proto()).collect(),
            plans: self.plans.into_iter().map(|p| p.into_proto()).collect(),
            // ... timestamps, status
        }
    }
}

impl Message {
    pub fn into_proto(self) -> proto::Message {
        proto::Message {
            seq: self.seq,
            author_role: self.author_role.into_proto() as i32,
            message_type: self.message_type.into_proto() as i32,
            content: self.content.unwrap_or_default(),
            emitted_at_ns: self.emitted_at.timestamp_nanos(),
            observed_at_ns: self.observed_at.timestamp_nanos(),
            raw_data: serde_json::to_vec(&self.raw_data)?,
            // ... tokens, tool_calls
        }
    }
}
```

### 3.4 Export Configuration

**File:** `src/export/config.rs`

```rust
#[derive(Debug, Clone, Deserialize)]
pub struct ExportConfig {
    pub enabled: bool,
    pub endpoint: String,           // "https://catsyphon.example.com:4317"
    pub api_key: String,            // "cs_abc123..."
    pub collector_id: String,       // UUID from registration
    pub workspace_id: String,       // UUID from registration
    pub batch_size: usize,          // Sessions per batch (default: 10)
    pub retry_max: u32,             // Max retries (default: 4)
    pub retry_backoff_ms: u64,      // Initial backoff (default: 2000)
}
```

**Config file** (`~/.config/aiobscura/config.toml`):
```toml
[export]
enabled = true
endpoint = "https://catsyphon.mycompany.com:4317"
api_key = "cs_abc123..."
collector_id = "uuid-from-registration"
workspace_id = "uuid-from-registration"
batch_size = 10
```

### 3.5 Sync Command Enhancement

**Update:** `src/sync.rs`

```rust
pub async fn sync(
    db: &Database,
    export_client: Option<&mut CatSyphonClient>,
) -> Result<SyncStats> {
    // Existing: Parse local logs → SQLite
    let local_stats = sync_local(db).await?;

    // New: Export to CatSyphon (if configured)
    let export_stats = if let Some(client) = export_client {
        export_to_catsyphon(db, client).await?
    } else {
        ExportStats::default()
    };

    Ok(SyncStats {
        local: local_stats,
        export: export_stats,
    })
}

async fn export_to_catsyphon(
    db: &Database,
    client: &mut CatSyphonClient,
) -> Result<ExportStats> {
    // Get sessions not yet exported (track with exported_at column)
    let sessions = db.get_unexported_sessions()?;

    for batch in sessions.chunks(client.config.batch_size) {
        let result = client.export_sessions(batch.to_vec()).await?;

        // Mark as exported
        for session_result in result.results {
            if session_result.status == SessionStatus::Created
               || session_result.status == SessionStatus::Duplicate {
                db.mark_exported(&session_result.session_id)?;
            }
        }
    }

    Ok(ExportStats { ... })
}
```

### 3.6 CLI Integration

**Update CLI:**
```rust
#[derive(Subcommand)]
enum Commands {
    /// Sync local logs and optionally export to CatSyphon
    Sync {
        /// Export to CatSyphon (uses config.toml settings)
        #[arg(long)]
        export: bool,

        /// Watch mode - continuous sync
        #[arg(long)]
        watch: bool,
    },

    /// Export sessions to CatSyphon
    Export {
        /// Session IDs to export (or all unexported)
        #[arg(long)]
        session_ids: Option<Vec<String>>,

        /// Force re-export already exported sessions
        #[arg(long)]
        force: bool,
    },

    /// Register this collector with CatSyphon
    Register {
        /// CatSyphon endpoint
        #[arg(long)]
        endpoint: String,

        /// Collector name
        #[arg(long)]
        name: String,
    },
}
```

---

## Phase 4: Integration Testing

### 4.1 End-to-End Test Flow

```
1. Start CatSyphon server (HTTP:8000, gRPC:4317)
2. Register collector via REST API → get API key
3. Configure aiobscura with endpoint + API key
4. Run aiobscura sync with Claude Code logs
5. Verify sessions appear in CatSyphon web UI
```

### 4.2 Test Cases

**CatSyphon Tests:**
- gRPC auth: valid key, invalid key, expired key
- Session ingestion: new session, duplicate, partial failure
- Idempotency: same batch_id returns cached response
- Rate limiting: exceeds quota returns RESOURCE_EXHAUSTED

**aiobscura Tests:**
- Export success: sessions marked as exported
- Export failure: retry with backoff
- Offline mode: queue locally, export when connected
- Batch chunking: large session list split correctly

---

## Implementation Order

### Phase 0: Type System Alignment (Foundation)
1. [ ] Create migration: Add AuthorRole enum + column
2. [ ] Create migration: Add MessageType enum + column
3. [ ] Create migration: Add Thread table + message FK
4. [ ] Create migration: Add BackingModel table + conversation FK
5. [ ] Create migration: Add emitted_at, observed_at columns
6. [ ] Create migration: Add raw_data column
7. [ ] Update CatSyphon models (Message, Thread, BackingModel, Conversation)
8. [ ] Update Claude Code parser to populate new fields
9. [ ] Verify aiobscura types match protobuf
10. [ ] Run full test suites in both repos (independent validation)

### Phase 1: Security Foundation (CatSyphon)
11. [ ] Create `backend/src/catsyphon/api/auth.py` with AuthContext
12. [ ] Add `get_by_workspace()` to all repositories
13. [ ] Update all API endpoints to use AuthContext
14. [ ] Add cross-workspace access denial tests
15. [ ] Remove `_get_default_workspace_id()` hack

### Phase 2: CatSyphon gRPC Server
16. [ ] Set up protobuf codegen
17. [ ] Create Collector REST API (CRUD)
18. [ ] Implement API key generation/validation
19. [ ] Create gRPC server skeleton
20. [ ] Implement auth interceptor
21. [ ] Implement SessionIngestion service
22. [ ] Wire proto → internal models (mapper.py)

### Phase 3: aiobscura Client
23. [ ] Vendor proto file, set up codegen
24. [ ] Create gRPC client
25. [ ] Implement internal → proto mapper
26. [ ] Add export config to TOML
27. [ ] Add sync --export flag
28. [ ] Add export command

### Phase 4: Integration Testing
29. [ ] End-to-end testing
30. [ ] Documentation

---

## Files Changed Summary

### CatSyphon (Phase 0 - Type System)
```
backend/db/migrations/versions/xxx_add_author_role.py
backend/db/migrations/versions/xxx_add_message_type.py
backend/db/migrations/versions/xxx_add_threads.py
backend/db/migrations/versions/xxx_add_backing_models.py
backend/db/migrations/versions/xxx_add_dual_timestamps.py
backend/db/migrations/versions/xxx_add_raw_data.py
backend/src/catsyphon/models/db.py              # Updated models
backend/src/catsyphon/parsers/claude_code.py    # Updated parser
```

### CatSyphon (Phase 1 - Security)
```
backend/src/catsyphon/api/auth.py               # Auth context
backend/src/catsyphon/db/repositories/*.py      # get_by_workspace()
backend/src/catsyphon/api/routes/*.py           # AuthContext dependency
```

### CatSyphon (Phase 2 - gRPC)
```
proto/catsyphon/telemetry/v1/sessions.proto     ✅ Already exists
backend/src/catsyphon/grpc/__init__.py
backend/src/catsyphon/grpc/server.py
backend/src/catsyphon/grpc/interceptors.py
backend/src/catsyphon/grpc/services/__init__.py
backend/src/catsyphon/grpc/services/session_ingestion.py
backend/src/catsyphon/grpc/generated/           (auto-generated)
backend/src/catsyphon/api/routes/collectors.py
scripts/generate_proto.sh
```

### CatSyphon (modified files - Phase 0 security fixes)
```
backend/src/catsyphon/db/repositories/conversation.py  # Add get_by_workspace()
backend/src/catsyphon/db/repositories/project.py       # Add get_by_workspace()
backend/src/catsyphon/db/repositories/developer.py     # Add get_by_workspace()
backend/src/catsyphon/db/repositories/ingestion_job.py # Add get_by_workspace()
backend/src/catsyphon/api/routes/conversations.py      # Use AuthContext
backend/src/catsyphon/api/routes/canonical.py          # Use AuthContext
backend/src/catsyphon/api/routes/projects.py           # Use AuthContext
backend/src/catsyphon/api/routes/ingestion.py          # Use AuthContext
```

### aiobscura (new files)
```
proto/catsyphon/telemetry/v1/sessions.proto     (vendored)
build.rs
src/export/mod.rs
src/export/client.rs
src/export/mapper.rs
src/export/config.rs
```

### aiobscura (modified files)
```
Cargo.toml                                       (add tonic, prost)
src/sync.rs                                      (add export logic)
src/cli.rs                                       (add export command)
src/config.rs                                    (add ExportConfig)
src/db/schema.rs                                 (add exported_at column)
```
