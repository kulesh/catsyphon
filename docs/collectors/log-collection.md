# Log Collection Architecture: CatSyphon + Collectors

## Executive Summary

This document outlines the product vision and architecture for enabling external collectors (like aiobscura-sync) to push coding agent conversation data to CatSyphon. The goal is to establish CatSyphon as an **enterprise analytics backend** while collectors like aiobscura serve as **local developer tools** that capture and forward data.

---

## 1. Current State Analysis

### 1.1 CatSyphon Architecture (What Exists)

**Strengths - Foundation Ready:**

| Component | Status | Details |
|-----------|--------|---------|
| Multi-tenancy | ✅ Complete | `Organization → Workspace` hierarchy with full isolation |
| CollectorConfig table | ✅ Complete | Database schema for collector registration with API key auth fields |
| CollectorRepository | ✅ Complete | Full CRUD + `get_by_api_key_prefix()`, `update_heartbeat()`, `increment_uploads()` |
| Ingestion Pipeline | ✅ Complete | ETL with deduplication, workspace/project/developer resolution |
| Incremental Parsing | ✅ Complete | 10-106x performance gains for appended content |
| Parser Plugin System | ✅ Complete | Extensible `ParserRegistry` with auto-detection |
| Conversation Hierarchy | ✅ Complete | `parent_conversation_id` for agent/MCP/skill relationships |
| Audit Trail | ✅ Complete | `IngestionJob` with `source_type='collector'` support |
| Pipeline Metrics | ✅ Complete | Stage-level timing in JSONB |

**Gaps - Missing for Collector Integration:**

| Component | Status | Impact |
|-----------|--------|--------|
| Collector REST API | ❌ Missing | No endpoints to register, manage, or ingest from collectors |
| Authentication Middleware | ❌ Missing | No API key validation for incoming requests |
| OTLP/gRPC Ingestion | ❌ Missing | No OpenTelemetry-compatible ingestion endpoint |
| OTLP/HTTP Fallback | ❌ Missing | No HTTP-based OTLP endpoint for simpler integrations |
| Rate Limiting | ❌ Missing | No protection against abuse or quota enforcement |
| Collector Management UI | ❌ Missing | No web interface for collector lifecycle management |

### 1.2 aiobscura Architecture (Collector Reference)

**Key Design Decisions to Adopt:**

1. **Ubiquitous Language**
   - `Human` (not "User") - the real person
   - `Assistant` - the AI coding assistant product
   - `Agent` - spawned subprocess, never interacts with humans directly
   - `Session` - primary unit of work (maps to CatSyphon's `Conversation`)
   - `Thread` - conversation flow within session (hierarchical)
   - `Message` - atomic unit of activity

2. **Author Roles** (6-role taxonomy)
   - `Human` - person writing prompts
   - `Caller` - CLI or parent assistant invoking session
   - `Assistant` - coding assistant responding
   - `Agent` - subprocess spawned by assistant
   - `Tool` - executable capability (Bash, Read, Edit)
   - `System` - internal events, snapshots, context loading

3. **Message Types** (8-type taxonomy)
   - `Prompt`, `Response`, `ToolCall`, `ToolResult`
   - `Plan`, `Summary`, `Context`, `Error`

4. **Three-Layer Architecture**
   ```
   Layer 0 (Raw):      Source files on disk (~/.claude/)
   Layer 1 (Canonical): Normalized data with full raw preservation
   Layer 2 (Derived):   Computed metrics, assessments, insights
   ```

5. **Timestamp Semantics**
   - `emitted_at` - when message was produced (from log)
   - `observed_at` - when parsed into system
   - Critical for accurate timeline reconstruction

6. **Checkpoint-Based Incremental Sync**
   - JSONL: Resume from byte offset
   - JSON: SHA256 hash detection
   - Enables efficient batch synchronization

---

## 2. Product Vision

### 2.1 Strategic Positioning

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEVELOPER WORKSTATION                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Claude Code │  │   Cursor    │  │    Aider    │  ... agents  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                    aiobscura                          │       │
│  │   • Local SQLite database (Layer 1)                   │       │
│  │   • Real-time TUI for developer self-service          │       │
│  │   • Personal analytics & session history              │       │
│  │   • Standalone operation (works without server)        │       │
│  └────────────────────────┬─────────────────────────────┘       │
│                           │ (opt-in sync)                        │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼ OTLP/gRPC (4317) or OTLP/HTTP (4318)
                              + API Key Auth + TLS
┌───────────────────────────────────────────────────────────────────┐
│                        CATSYPHON SERVER                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    OTLP Receiver Gateway                     │  │
│  │   • OpenTelemetry Protocol (gRPC primary, HTTP fallback)     │  │
│  │   • API key authentication & rate limiting                   │  │
│  │   • Workspace isolation enforcement                          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Enterprise Features                       │  │
│  │   • Cross-developer analytics                                │  │
│  │   • Team productivity dashboards                             │  │
│  │   • AI tagging (sentiment, intent, outcome)                  │  │
│  │   • Compliance & audit trails                                │  │
│  │   • Custom insights & reports                                │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Principles

1. **Secure by Design**: End-to-end encryption, API key authentication, audit trails
2. **Reliable Ingestion**: Guaranteed delivery with idempotency and retry semantics
3. **Multi-Tenant Isolation**: Complete workspace separation at every layer
4. **Lossless Capture**: Raw data preserved for reprocessing as parsers improve
5. **Incremental Sync**: Efficient bandwidth usage via checkpoint-based sync
6. **Governance-Ready**: Compliance reporting, retention policies, access controls

### 2.3 User Personas

| Persona | Tool | Primary Use Case |
|---------|------|------------------|
| Individual Developer | aiobscura (local) | Personal session history, productivity tracking |
| Team Lead | CatSyphon (web) | Team analytics, identifying coaching opportunities |
| Engineering Manager | CatSyphon (web) | Aggregate metrics, tool adoption insights |
| IT/Security Admin | CatSyphon (admin) | Collector management, compliance auditing |

---

## 3. Product Plan

### Phase 1: Collector Foundation (MVP)

**Goal**: Enable push-based data ingestion from collectors using industry-standard protocols

**Features**:
1. **Collector Registration API**
   - `POST /api/collectors` - Register new collector
   - `GET /api/collectors` - List collectors in workspace
   - `PATCH /api/collectors/{id}` - Update collector settings
   - `POST /api/collectors/{id}/rotate-key` - Rotate API key

2. **OTLP Ingestion Endpoints**
   - **gRPC** (port 4317) - Primary, high-performance endpoint for production
   - **HTTP** (port 4318) - Fallback for debugging and simpler integrations
   - Protocol Buffers serialization for efficient binary transport
   - Deduplication via session ID + timestamp

3. **Authentication Middleware**
   - API key validation via gRPC metadata or HTTP header
   - Workspace scoping enforced automatically
   - Request logging for audit

4. **Heartbeat Monitoring**
   - gRPC health check service (standard `grpc.health.v1.Health`)
   - Stale collector detection and alerting

**Success Criteria**:
- aiobscura can push sessions via OTLP exporter
- Compatible with standard OpenTelemetry tooling
- Duplicate sessions rejected gracefully
- 99.9% uptime for ingestion endpoint

### Phase 2: Type System Alignment

**Goal**: Adopt aiobscura's ubiquitous language for consistency

**Changes**:
1. **Database Migrations**
   - Add `author_role` enum: Human, Caller, Assistant, Agent, Tool, System
   - Add `message_type` enum: Prompt, Response, ToolCall, ToolResult, Plan, Summary, Context, Error
   - Add `emitted_at` vs `observed_at` timestamp distinction
   - Add `Thread` model for hierarchical conversation flows

2. **Model Harmonization**
   - Rename "Conversation" → "Session" (or add alias)
   - Add explicit "Plan" entity for plan document tracking
   - Add "BackingModel" for LLM version tracking

3. **Parser Updates**
   - Map parser output to new author/message types
   - Preserve backward compatibility with existing data

**Success Criteria**:
- Ingested data from aiobscura maps 1:1 to CatSyphon schema
- Existing conversations migrated without data loss
- API responses use aligned terminology

### Phase 3: Enterprise Features

**Goal**: Deliver value that justifies team/org-wide deployment

**Features**:
1. **Cross-Developer Analytics**
   - Team productivity dashboards
   - Tool usage comparison across developers
   - Session success rate by project/team

2. **Collector Fleet Management**
   - Bulk collector provisioning
   - Version tracking and upgrade notifications
   - Health monitoring dashboard

3. **Advanced Tagging**
   - Auto-classification of session intent
   - Sentiment analysis on human-assistant interactions
   - Problem/blocker extraction

4. **Compliance & Governance**
   - Data retention policies per workspace
   - Export capabilities for compliance
   - Audit log queries

**Success Criteria**:
- Teams can answer "How are we using AI coding assistants?"
- IT can manage collector fleet centrally
- Compliance team can generate required reports

### Phase 4: Bidirectional Sync

**Goal**: Enable CatSyphon insights to flow back to developers

**Features**:
1. **Insight Push to aiobscura**
   - CatSyphon assessments available in local TUI
   - Team benchmarks visible to individual developers

2. **Federated Queries**
   - Query across local + remote data seamlessly
   - Role-based access controls on data visibility

3. **Plugin Ecosystem**
   - Shared plugin marketplace between aiobscura and CatSyphon
   - Custom metrics that work in both environments

---

## 4. Architecture Plan

### 4.1 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           COLLECTOR (aiobscura)                          │
│                                                                          │
│  ~/.claude/ ──────┐                                                      │
│  ~/.codex/  ──────┼──▶ [Parser] ──▶ [SQLite Layer 1] ──┐                │
│  ~/.aider/  ──────┘         ▲                          │                │
│                             │                          ▼                │
│                    [Checkpoint System]        [Sync Manager]             │
│                             │                          │                │
│                             └──── offset/hash ─────────┘                │
│                                                        │                │
└────────────────────────────────────────────────────────┼────────────────┘
                                                         │
                             OTLP/gRPC (port 4317) ◄── Primary
                             OTLP/HTTP (port 4318) ◄── Fallback
                             ─────────────────────
                             • Protobuf serialization
                             • API key in metadata/header
                             • TLS encryption
                                                         │
                                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         CATSYPHON SERVER                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     OTLP Receiver Layer                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │   │
│  │  │ Auth Middleware │ Rate Limiter  │  │ Protobuf Decoder    │   │   │
│  │  │ (API Key)      │ (per collector)│  │ (OTLP → Internal)   │   │   │
│  │  └───────┬────────┘  └──────┬──────┘  └──────────┬──────────┘   │   │
│  └──────────┼──────────────────┼────────────────────┼──────────────┘   │
│             │                  │                    │                   │
│             ▼                  ▼                    ▼                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Ingestion Pipeline                            │   │
│  │                                                                  │   │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│  │   │ Deduplication │───▶│ Parsing/     │───▶│ Workspace   │      │   │
│  │   │ (session hash)│    │ Normalization │    │ Resolution   │      │   │
│  │   └──────────────┘    └──────────────┘    └──────────────┘      │   │
│  │           │                   │                   │              │   │
│  │           ▼                   ▼                   ▼              │   │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│  │   │ Project/Dev  │───▶│ Hierarchy    │───▶│ Database     │      │   │
│  │   │ Resolution   │    │ Linking      │    │ Persistence  │      │   │
│  │   └──────────────┘    └──────────────┘    └──────────────┘      │   │
│  │                                                  │               │   │
│  └──────────────────────────────────────────────────┼───────────────┘   │
│                                                     ▼                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      PostgreSQL                                  │   │
│  │                                                                  │   │
│  │   organizations ─▶ workspaces ─▶ collector_configs              │   │
│  │                         │                │                       │   │
│  │                         ▼                ▼                       │   │
│  │                    projects         ingestion_jobs               │   │
│  │                    developers                                    │   │
│  │                         │                                        │   │
│  │                         ▼                                        │   │
│  │                   conversations (sessions)                       │   │
│  │                         │                                        │   │
│  │            ┌────────────┼────────────┐                          │   │
│  │            ▼            ▼            ▼                          │   │
│  │         epochs      messages     raw_logs                        │   │
│  │            │                                                     │   │
│  │            ▼                                                     │   │
│  │       files_touched                                              │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Protocol Choice: Hybrid Approach

**Decision**: Use a custom protobuf schema as the canonical format, with OTLP adapter for ecosystem compatibility.

**Rationale**:

| Factor | Custom Protobuf | OTLP | Our Choice |
|--------|----------------|------|------------|
| **Type Safety** | ✅ Compile-time enum validation | ❌ String attributes | Custom |
| **Domain Fit** | ✅ Session→Thread→Message hierarchy | ❌ Flat LogRecords | Custom |
| **Ecosystem** | ❌ Must build tooling | ✅ OTEL Collector, exporters | OTLP adapter |
| **Performance** | ✅ Minimal payload | ⚠️ Unused fields | Custom |
| **Debugging** | ✅ Structured messages | ❌ Attribute inspection | Custom |

**Implementation Strategy**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HYBRID PROTOCOL ARCHITECTURE                      │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              proto/catsyphon/telemetry/v1/sessions.proto         │    │
│  │                     (Canonical Schema)                           │    │
│  │                                                                  │    │
│  │   • Session, Thread, Message - hierarchical domain model         │    │
│  │   • AuthorRole enum (6 values) - compile-time validated          │    │
│  │   • MessageType enum (8 values) - compile-time validated         │    │
│  │   • Source of truth for both Rust and Python codegen             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│              ┌───────────────┴───────────────┐                          │
│              ▼                               ▼                          │
│  ┌─────────────────────────┐    ┌─────────────────────────┐            │
│  │   Native gRPC Service   │    │    OTLP Adapter Layer   │            │
│  │      (Port 4317)        │    │     (Port 4318)         │            │
│  │                         │    │                         │            │
│  │ • SessionIngestion RPC  │    │ • Accepts OTLP Logs     │            │
│  │ • Streaming support     │    │ • Transforms attributes │            │
│  │ • Best performance      │    │ • OTEL Collector compat │            │
│  │ • Type-safe validation  │    │ • Ecosystem integration │            │
│  └────────────┬────────────┘    └────────────┬────────────┘            │
│               │                              │                          │
│               └──────────────┬───────────────┘                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Ingestion Pipeline                            │    │
│  │              (Same processing for both paths)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Port Allocation**:
- **4317**: Native gRPC (`SessionIngestion` service) - primary for aiobscura
- **4318**: OTLP/HTTP adapter - for ecosystem compatibility
- **8000**: REST API - collector management, web UI

### 4.3 Data Contract: Native Protocol

The canonical schema is defined in `proto/catsyphon/telemetry/v1/sessions.proto`.

**Service Definition**:
```protobuf
service SessionIngestion {
  // Batch export (small to medium batches)
  rpc ExportSessions(ExportSessionsRequest) returns (ExportSessionsResponse);

  // Streaming export (large sessions, continuous sync)
  rpc ExportSessionsStream(stream SessionBatch) returns (ExportSessionsResponse);
}
```

**Core Types** (matching aiobscura exactly):

```protobuf
// Enums - compile-time validated
enum AuthorRole {
  AUTHOR_ROLE_HUMAN = 1;      // Real person
  AUTHOR_ROLE_CALLER = 2;     // CLI or parent
  AUTHOR_ROLE_ASSISTANT = 3;  // Coding assistant
  AUTHOR_ROLE_AGENT = 4;      // Spawned subprocess
  AUTHOR_ROLE_TOOL = 5;       // Tool execution
  AUTHOR_ROLE_SYSTEM = 6;     // Internal events
}

enum MessageType {
  MESSAGE_TYPE_PROMPT = 1;
  MESSAGE_TYPE_RESPONSE = 2;
  MESSAGE_TYPE_TOOL_CALL = 3;
  MESSAGE_TYPE_TOOL_RESULT = 4;
  MESSAGE_TYPE_PLAN = 5;
  MESSAGE_TYPE_SUMMARY = 6;
  MESSAGE_TYPE_CONTEXT = 7;
  MESSAGE_TYPE_ERROR = 8;
}

// Hierarchical domain model
message Session {
  string id = 1;
  Assistant assistant = 2;
  BackingModel backing_model = 3;
  Project project = 4;
  Developer developer = 5;
  repeated Thread threads = 9;
  repeated Plan plans = 10;
  // ... timestamps, status, metadata
}

message Thread {
  string id = 1;
  optional string parent_thread_id = 2;
  ThreadType type = 3;
  repeated Message messages = 5;
  // ...
}

message Message {
  int32 seq = 1;
  AuthorRole author_role = 2;
  MessageType message_type = 4;
  string content = 5;
  int64 emitted_at_ns = 6;
  int64 observed_at_ns = 7;
  bytes raw_data = 12;  // Lossless preservation
  // ...
}
```

**Request/Response**:
```protobuf
message ExportSessionsRequest {
  CollectorInfo collector = 1;
  string batch_id = 2;          // Idempotency key
  repeated Session sessions = 3;
}

message ExportSessionsResponse {
  string batch_id = 1;
  BatchStatus status = 2;       // ACCEPTED, PARTIAL, REJECTED
  repeated SessionResult results = 3;
  BatchMetrics metrics = 4;
}
```

**Full schema**: See [`proto/catsyphon/telemetry/v1/sessions.proto`](../proto/catsyphon/telemetry/v1/sessions.proto)

### 4.3.1 OTLP Adapter (Ecosystem Compatibility)

For collectors that prefer OTLP, CatSyphon accepts standard OTLP LogRecords with `catsyphon.*` attributes.

**Attribute Mapping** (OTLP → Native):

| OTLP Attribute | Native Field |
|----------------|--------------|
| `catsyphon.session.id` | `Session.id` |
| `catsyphon.author.role` | `Message.author_role` (string → enum) |
| `catsyphon.message.type` | `Message.message_type` (string → enum) |
| `catsyphon.message.seq` | `Message.seq` |
| `LogRecord.body` | `Message.content` |
| `LogRecord.time_unix_nano` | `Message.emitted_at_ns` |
| `LogRecord.observed_time_unix_nano` | `Message.observed_at_ns` |

**Trade-offs**:
- OTLP path requires runtime string → enum validation
- Native path validates at protobuf decode time
- Both paths produce identical internal representation

**Response** (OTLP ExportLogsServiceResponse):
- Success: Empty response (standard OTLP)
- Partial failure: `partial_success.rejected_log_records` count + error message
- CatSyphon-specific headers for deduplication status:
  - `x-catsyphon-sessions-created: 1`
  - `x-catsyphon-sessions-duplicate: 0`
  - `x-catsyphon-messages-ingested: 42`

### 4.4 Authentication & Authorization

**API Key Transport**:
- **gRPC**: Metadata key `authorization` with value `Bearer cs_xxx`
- **HTTP**: Header `Authorization: Bearer cs_xxx`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                              │
│                                                                          │
│  1. Collector Registration (Admin Action via REST API)                   │
│     ─────────────────────────────────────────────────                   │
│     POST /api/collectors                                                 │
│     └──▶ Generate API Key: cs_abc12345... (shown once)                  │
│     └──▶ Store bcrypt hash in collector_configs.api_key_hash            │
│     └──▶ Store prefix (cs_abc1) in collector_configs.api_key_prefix     │
│                                                                          │
│  2. Collector OTLP Request (Runtime)                                     │
│     ─────────────────────────────────                                   │
│     gRPC metadata: authorization = "Bearer cs_abc12345..."               │
│     (or HTTP header: Authorization: Bearer cs_abc12345...)               │
│           │                                                              │
│           ▼                                                              │
│     ┌─────────────────────────────────────────────────────────────┐     │
│     │                 gRPC/HTTP Interceptor                        │     │
│     │  1. Extract key from metadata/header                         │     │
│     │  2. Parse prefix (cs_abc1)                                   │     │
│     │  3. Query: SELECT * FROM collector_configs                   │     │
│     │            WHERE api_key_prefix = 'cs_abc1' AND is_active    │     │
│     │  4. Verify bcrypt(key) == api_key_hash                       │     │
│     │  5. If valid: inject collector + workspace into context      │     │
│     │  6. If invalid: return UNAUTHENTICATED (gRPC) / 401 (HTTP)   │     │
│     └─────────────────────────────────────────────────────────────┘     │
│           │                                                              │
│           ▼                                                              │
│     ┌─────────────────────────────────────────────────────────────┐     │
│     │                    Authorization                             │     │
│     │  • Collector can only write to its workspace                 │     │
│     │  • Workspace ID from collector_configs enforced              │     │
│     │  • Rate limits applied per collector (token bucket)          │     │
│     └─────────────────────────────────────────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Type System Alignment

**Current CatSyphon → Proposed Alignment with aiobscura**:

| Current CatSyphon | Proposed | aiobscura Equivalent | Notes |
|-------------------|----------|---------------------|-------|
| `Conversation` | Keep + add `Session` alias | `Session` | Primary unit |
| `conversation_type` (enum) | Expand to include Thread types | `ThreadType` | main, agent, background |
| `role` (user/assistant/system) | `author_role` (6 values) | `AuthorRole` | Human, Caller, Assistant, Agent, Tool, System |
| N/A | Add `message_type` | `MessageType` | Prompt, Response, ToolCall, ToolResult, Plan, Summary, Context, Error |
| `timestamp` | `emitted_at` + `observed_at` | Both timestamps | Critical for accuracy |
| N/A | Add `Thread` model | `Thread` | Explicit hierarchy |
| N/A | Add `Plan` model | `Plan` | Track planning documents |
| N/A | Add `BackingModel` | `BackingModel` | LLM version tracking |
| `agent_type` (string) | `assistant` (enum) | `Assistant` | ClaudeCode, Codex, Aider, Cursor |

**Migration Strategy**:
1. Add new columns alongside existing (non-breaking)
2. Backfill existing data with sensible defaults
3. Update parsers to populate new fields
4. Eventually deprecate old columns

### 4.6 Deduplication Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      DEDUPLICATION STRATEGY                              │
│                                                                          │
│  Session-Level (Primary):                                                │
│  ─────────────────────────                                              │
│  Key: (workspace_id, assistant, session_id)                              │
│       └─ session_id from source log (e.g., Claude Code UUID)            │
│                                                                          │
│  Behavior:                                                               │
│  • New session_id → Create new conversation                              │
│  • Existing session_id → Compare last_activity_at                        │
│    • Newer activity → Merge/append new messages                          │
│    • Same or older → Skip (already processed)                            │
│                                                                          │
│  Message-Level (Secondary):                                              │
│  ───────────────────────────                                            │
│  Key: (session_id, thread_id, seq, emitted_at)                          │
│       └─ Sequence number + timestamp ensures uniqueness                  │
│                                                                          │
│  Behavior:                                                               │
│  • Before insert, check if message with same key exists                  │
│  • If exists, skip (idempotent)                                          │
│  • If new, insert                                                        │
│                                                                          │
│  Batch-Level (Idempotency):                                              │
│  ──────────────────────────                                             │
│  Key: batch_id (UUID generated by collector)                             │
│                                                                          │
│  Behavior:                                                               │
│  • Store processed batch_ids in Redis/memory cache (TTL: 1 hour)         │
│  • If same batch_id received, return cached response                     │
│  • Protects against network retries                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.7 Error Handling & Reliability

**Collector-Side (aiobscura)**:
- Retry with exponential backoff (2s, 4s, 8s, 16s, max 60s)
- Dead letter queue for permanently failed batches
- Offline mode: queue batches locally when CatSyphon unreachable

**Server-Side (CatSyphon)**:
- Transaction per session (partial batch success OK)
- Standard gRPC status codes for errors
- Circuit breaker for database overload
- Async processing option for large batches

**gRPC Status Codes**:
| Code | Meaning | When Used |
|------|---------|-----------|
| `OK` | Success | All records accepted |
| `UNAUTHENTICATED` | Invalid API key | Key missing, expired, or invalid |
| `PERMISSION_DENIED` | Workspace mismatch | Collector trying to write to wrong workspace |
| `RESOURCE_EXHAUSTED` | Rate limited | Collector exceeded quota |
| `INVALID_ARGUMENT` | Bad request | Malformed protobuf or invalid attributes |
| `UNAVAILABLE` | Server overload | Circuit breaker tripped, retry later |

**Partial Failure** (OTLP standard):
```protobuf
ExportLogsServiceResponse {
  partial_success: {
    rejected_log_records: 3
    error_message: "Invalid catsyphon.author.role value"
  }
}
```

---

## 5. Database Schema Changes

### 5.1 New Tables

```sql
-- Thread model for explicit hierarchy
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    thread_type VARCHAR(20) NOT NULL DEFAULT 'main',  -- main, agent, background
    spawned_by_message_id UUID REFERENCES messages(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Plan documents
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    path TEXT NOT NULL,
    title TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, completed, abandoned, unknown
    content TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- LLM version tracking
CREATE TABLE backing_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,  -- anthropic, openai, etc.
    model_id VARCHAR(100) NOT NULL,  -- claude-sonnet-4-20250514
    display_name VARCHAR(255),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}',
    UNIQUE (provider, model_id)
);

-- Ingestion batch tracking (idempotency)
CREATE TABLE ingestion_batches (
    id UUID PRIMARY KEY,  -- batch_id from collector
    collector_id UUID NOT NULL REFERENCES collector_configs(id),
    status VARCHAR(20) NOT NULL,  -- pending, processing, completed, failed
    sessions_count INTEGER NOT NULL DEFAULT 0,
    messages_count INTEGER NOT NULL DEFAULT 0,
    response_cache JSONB,  -- cached response for idempotency
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

### 5.2 Column Additions

```sql
-- Add author_role and message_type enums
ALTER TABLE messages
ADD COLUMN author_role VARCHAR(20),  -- human, caller, assistant, agent, tool, system
ADD COLUMN message_type VARCHAR(20), -- prompt, response, tool_call, tool_result, plan, summary, context, error
ADD COLUMN emitted_at TIMESTAMPTZ,   -- when message was produced
ADD COLUMN observed_at TIMESTAMPTZ;  -- when parsed into system

-- Add backing_model reference to conversations
ALTER TABLE conversations
ADD COLUMN backing_model_id UUID REFERENCES backing_models(id),
ADD COLUMN source_session_id VARCHAR(255);  -- original ID from collector

-- Add thread reference to messages
ALTER TABLE messages
ADD COLUMN thread_id UUID REFERENCES threads(id);
```

---

## 6. Security Considerations

### 6.1 API Key Management

- **Generation**: Cryptographically secure random bytes (32 bytes, base62 encoded)
- **Prefix**: `cs_` prefix for easy identification, first 8 chars stored for lookup
- **Storage**: bcrypt hash only (never store plaintext)
- **Rotation**: Old key invalidated immediately upon rotation
- **Revocation**: Soft delete (is_active = false) preserves audit trail

### 6.2 Data Privacy

- **Workspace Isolation**: All queries scoped to workspace_id from auth
- **No Cross-Tenant Queries**: Database enforces FK constraints
- **PII Handling**: Consider masking options for sensitive content
- **Audit Logging**: All ingestion operations logged to ingestion_jobs

### 6.3 Rate Limiting

| Tier | Requests/min | Sessions/batch | Retention |
|------|-------------|----------------|-----------|
| Free | 10 | 10 | 30 days |
| Team | 100 | 100 | 1 year |
| Enterprise | 1000 | 1000 | Unlimited |

---

## 7. Success Metrics

### 7.1 Technical Metrics

- **Ingestion Latency**: p50 < 100ms, p99 < 500ms per session
- **Availability**: 99.9% uptime for ingestion endpoint
- **Deduplication Accuracy**: 100% (no duplicates, no false positives)
- **Error Rate**: < 0.1% of valid requests

### 7.2 Product Metrics

- **Collector Adoption**: Number of active collectors per workspace
- **Sync Frequency**: Average batches per collector per day
- **Data Freshness**: Time from message emission to CatSyphon availability
- **Cross-Developer Insights**: Sessions analyzed with team context

---

## 8. Open Questions

1. **Schema Versioning**: How to handle collector sending older OTLP attribute schema?
   - Option A: Server maintains backward compatibility via attribute version detection
   - Option B: Require collector upgrade with breaking changes
   - Option C: Use OTLP schema URL mechanism for versioning

2. **Large Session Handling**: What if a session has 10,000+ messages?
   - Option A: Split into chunks on collector side (multiple OTLP batches)
   - Option B: gRPC streaming for continuous ingestion
   - **Recommendation**: gRPC streaming aligns with OTLP design

3. **Offline-First**: Should CatSyphon support queuing when DB is down?
   - Option A: Return `UNAVAILABLE`, let collector retry (standard gRPC)
   - Option B: Accept and queue internally (risk: memory pressure)
   - **Recommendation**: Option A, collectors should handle retries

4. **Content Storage**: Store full message content or references?
   - Option A: Store everything (current approach)
   - Option B: Store summaries, reference aiobscura for full content
   - **Note**: OTLP LogRecord body is designed for full content

5. **Plan Synchronization**: How to handle plan updates across sessions?
   - Option A: Plans are immutable per sync
   - Option B: Plans can be updated with version tracking

6. **OTLP Ecosystem Integration**: Should CatSyphon accept standard OTEL data?
   - Could receive spans/traces from instrumented apps alongside logs
   - Would position CatSyphon as general-purpose observability backend
   - **Recommendation**: Start with logs-only, expand to traces later

---

## 9. Next Steps

### Immediate (This Sprint)
1. ✅ Document current state and gaps (this document)
2. ✅ Define canonical protobuf schema (`proto/catsyphon/telemetry/v1/sessions.proto`)
3. Review and approve product/architecture plan
4. Create detailed implementation plan for Phase 1

### Phase 1 Implementation
1. Add collector REST API endpoints (registration, management)
2. Set up protobuf codegen (Python: grpcio-tools, Rust: prost/tonic)
3. Implement native gRPC `SessionIngestion` service (port 4317)
4. Implement OTLP/HTTP adapter (port 4318) for ecosystem compatibility
5. Add gRPC interceptor for API key authentication
6. Implement rate limiting (token bucket per collector)
7. Update aiobscura to export via native gRPC protocol

### Follow-up
1. Collect feedback from beta users
2. Iterate on API contract based on real usage
3. Begin Phase 2 type system alignment
