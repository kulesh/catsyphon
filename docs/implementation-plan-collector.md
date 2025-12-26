# Implementation Plan: Collector Integration

## Overview

This plan covers implementing the collector integration across both repositories:
- **aiobscura**: Add gRPC export capability (push to CatSyphon)
- **CatSyphon**: Add gRPC ingestion service (receive from collectors)

Both products continue to work standalone; integration is opt-in.

---

## Shared: Protobuf Schema

The canonical schema lives in CatSyphon and is copied/vendored to aiobscura:

```
catsyphon/proto/catsyphon/telemetry/v1/sessions.proto  (source of truth)
aiobscura/proto/catsyphon/telemetry/v1/sessions.proto  (vendored copy)
```

**Status**: ✅ Already created in CatSyphon

---

## Phase 1: CatSyphon - gRPC Ingestion Service

### 1.1 Protobuf Codegen Setup

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

### 1.2 Collector REST API

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

### 1.3 gRPC Authentication Interceptor

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

### 1.4 SessionIngestion Service

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

### 1.5 gRPC Server Integration

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

### 1.6 Database Simplification

Since we don't need migrations, simplify the schema:

**Update `models/db.py`:**
- Add `author_role` column (enum)
- Add `message_type` column (enum)
- Add `emitted_at`, `observed_at` columns
- Add `Thread` table
- Add `BackingModel` table
- Rename internal references to use "Session" terminology

---

## Phase 2: aiobscura - gRPC Export Client

### 2.1 Protobuf Codegen Setup

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

### 2.2 Export Client

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

### 2.3 Internal → Proto Mapper

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

### 2.4 Export Configuration

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

### 2.5 Sync Command Enhancement

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

### 2.6 CLI Integration

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

## Phase 3: Integration Testing

### 3.1 End-to-End Test Flow

```
1. Start CatSyphon server (HTTP:8000, gRPC:4317)
2. Register collector via REST API → get API key
3. Configure aiobscura with endpoint + API key
4. Run aiobscura sync with Claude Code logs
5. Verify sessions appear in CatSyphon web UI
```

### 3.2 Test Cases

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

### Week 1: CatSyphon Foundation
1. [ ] Set up protobuf codegen
2. [ ] Create Collector REST API (CRUD)
3. [ ] Implement API key generation/validation

### Week 2: CatSyphon gRPC Server
4. [ ] Create gRPC server skeleton
5. [ ] Implement auth interceptor
6. [ ] Implement SessionIngestion service
7. [ ] Wire proto → existing ingestion pipeline

### Week 3: aiobscura Client
8. [ ] Vendor proto file, set up codegen
9. [ ] Create gRPC client
10. [ ] Implement internal → proto mapper
11. [ ] Add export config to TOML

### Week 4: Integration
12. [ ] Add sync --export flag
13. [ ] Add export command
14. [ ] End-to-end testing
15. [ ] Documentation

---

## Files Changed Summary

### CatSyphon (new files)
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
