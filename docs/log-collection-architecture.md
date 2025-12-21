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
| Push Ingestion Endpoint | ❌ Missing | Collectors cannot send data; only file upload exists |
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
                            ▼ HTTPS + API Key Auth
┌───────────────────────────────────────────────────────────────────┐
│                        CATSYPHON SERVER                            │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Collector Gateway                         │  │
│  │   • API key authentication & rate limiting                   │  │
│  │   • Workspace isolation enforcement                          │  │
│  │   • Batch ingestion with deduplication                       │  │
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

**Goal**: Enable basic push-based data ingestion from collectors

**Features**:
1. **Collector Registration API**
   - `POST /api/collectors` - Register new collector
   - `GET /api/collectors` - List collectors in workspace
   - `PATCH /api/collectors/{id}` - Update collector settings
   - `POST /api/collectors/{id}/rotate-key` - Rotate API key

2. **Push Ingestion Endpoint**
   - `POST /api/collectors/{id}/ingest` - Accept batch of sessions/messages
   - Support for both raw JSONL and pre-parsed formats
   - Deduplication via session ID + timestamp

3. **Authentication Middleware**
   - API key validation via `Authorization: Bearer cs_xxx` header
   - Workspace scoping enforced automatically
   - Request logging for audit

4. **Heartbeat Monitoring**
   - `POST /api/collectors/heartbeat` - Collector health check
   - Stale collector detection and alerting

**Success Criteria**:
- aiobscura can push sessions to CatSyphon with single command
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
                          HTTPS POST /api/collectors/{id}/ingest
                          Authorization: Bearer cs_xxxxx
                          Content-Type: application/json
                                                         │
                                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         CATSYPHON SERVER                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     API Gateway Layer                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │   │
│  │  │ Auth Middleware │ Rate Limiter  │  │ Request Validator   │   │   │
│  │  │ (API Key)      │ (per collector)│  │ (JSON Schema)       │   │   │
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

### 4.2 API Contract: Collector Ingestion

**Request Format**:

```json
POST /api/collectors/{collector_id}/ingest
Authorization: Bearer cs_abc12345...
Content-Type: application/json

{
  "format_version": "1.0",
  "collector": {
    "type": "aiobscura",
    "version": "0.5.0",
    "hostname": "dev-laptop-123"
  },
  "batch_id": "uuid-for-idempotency",
  "sessions": [
    {
      "id": "session-uuid-from-log",
      "assistant": "claude-code",
      "backing_model": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-20250514"
      },
      "project": {
        "path": "/home/user/myproject",
        "name": "myproject"
      },
      "developer": {
        "username": "jdoe",
        "email": "jdoe@company.com"
      },
      "started_at": "2025-12-21T10:00:00Z",
      "last_activity_at": "2025-12-21T10:45:00Z",
      "status": "inactive",
      "threads": [
        {
          "id": "thread-uuid",
          "type": "main",
          "parent_thread_id": null,
          "messages": [
            {
              "seq": 1,
              "author_role": "human",
              "message_type": "prompt",
              "content": "Help me refactor the auth module",
              "emitted_at": "2025-12-21T10:00:00Z",
              "observed_at": "2025-12-21T10:00:05Z",
              "raw_data": { /* original log entry */ }
            },
            {
              "seq": 2,
              "author_role": "assistant",
              "message_type": "response",
              "content": "I'll help you refactor...",
              "emitted_at": "2025-12-21T10:00:30Z",
              "tokens_in": 150,
              "tokens_out": 500,
              "tool_calls": [
                {
                  "id": "tool-123",
                  "name": "Read",
                  "input": {"file_path": "/home/user/myproject/auth.py"}
                }
              ]
            }
          ]
        }
      ],
      "plans": [
        {
          "id": "plan-uuid",
          "path": "auth-refactor.md",
          "title": "Auth Module Refactoring",
          "status": "active"
        }
      ]
    }
  ]
}
```

**Response Format**:

```json
{
  "batch_id": "uuid-for-idempotency",
  "status": "accepted",
  "results": [
    {
      "session_id": "session-uuid-from-log",
      "catsyphon_id": "uuid-assigned-by-catsyphon",
      "status": "created",
      "messages_ingested": 42,
      "threads_ingested": 3
    },
    {
      "session_id": "another-session-uuid",
      "status": "duplicate",
      "existing_catsyphon_id": "uuid-of-existing"
    }
  ],
  "metrics": {
    "processing_time_ms": 234,
    "sessions_created": 1,
    "sessions_updated": 0,
    "sessions_duplicate": 1
  }
}
```

### 4.3 Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                              │
│                                                                          │
│  1. Collector Registration (Admin Action)                                │
│     ────────────────────────────────────────                            │
│     POST /api/collectors                                                 │
│     └──▶ Generate API Key: cs_abc12345... (shown once)                  │
│     └──▶ Store bcrypt hash in collector_configs.api_key_hash            │
│     └──▶ Store prefix (cs_abc1) in collector_configs.api_key_prefix     │
│                                                                          │
│  2. Collector Request (Runtime)                                          │
│     ──────────────────────────────                                      │
│     Authorization: Bearer cs_abc12345...                                 │
│           │                                                              │
│           ▼                                                              │
│     ┌─────────────────────────────────────────────────────────────┐     │
│     │                    Auth Middleware                           │     │
│     │  1. Extract key from header                                  │     │
│     │  2. Parse prefix (cs_abc1)                                   │     │
│     │  3. Query: SELECT * FROM collector_configs                   │     │
│     │            WHERE api_key_prefix = 'cs_abc1' AND is_active    │     │
│     │  4. Verify bcrypt(key) == api_key_hash                       │     │
│     │  5. If valid: inject collector + workspace into request      │     │
│     │  6. If invalid: return 401 Unauthorized                      │     │
│     └─────────────────────────────────────────────────────────────┘     │
│           │                                                              │
│           ▼                                                              │
│     ┌─────────────────────────────────────────────────────────────┐     │
│     │                    Authorization                             │     │
│     │  • Collector can only write to its workspace                 │     │
│     │  • Workspace ID from collector_configs enforced              │     │
│     │  • Rate limits applied per collector                         │     │
│     └─────────────────────────────────────────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Type System Alignment

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

### 4.5 Deduplication Strategy

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

### 4.6 Error Handling & Reliability

**Collector-Side (aiobscura)**:
- Retry with exponential backoff (2s, 4s, 8s, 16s, max 60s)
- Dead letter queue for permanently failed batches
- Offline mode: queue batches locally when CatSyphon unreachable

**Server-Side (CatSyphon)**:
- Transaction per session (partial batch success OK)
- Detailed error responses per session
- Circuit breaker for database overload
- Async processing option for large batches

**Error Response Format**:
```json
{
  "batch_id": "uuid",
  "status": "partial_failure",
  "results": [
    {"session_id": "...", "status": "created"},
    {"session_id": "...", "status": "failed", "error": {
      "code": "VALIDATION_ERROR",
      "message": "Invalid timestamp format",
      "field": "messages[3].emitted_at"
    }}
  ]
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

1. **Schema Versioning**: How to handle collector sending older format?
   - Option A: Server maintains backward compatibility
   - Option B: Require collector upgrade with breaking changes

2. **Large Session Handling**: What if a session has 10,000+ messages?
   - Option A: Split into chunks on collector side
   - Option B: Streaming ingestion endpoint

3. **Offline-First**: Should CatSyphon support queuing when DB is down?
   - Option A: Return 503, let collector retry
   - Option B: Accept and queue internally

4. **Content Storage**: Store full message content or references?
   - Option A: Store everything (current approach)
   - Option B: Store summaries, reference aiobscura for full content

5. **Plan Synchronization**: How to handle plan updates across sessions?
   - Option A: Plans are immutable per sync
   - Option B: Plans can be updated with version tracking

---

## 9. Next Steps

### Immediate (This Sprint)
1. ✅ Document current state and gaps (this document)
2. Review and approve product/architecture plan
3. Create detailed implementation plan for Phase 1

### Phase 1 Implementation
1. Add collector REST API endpoints
2. Implement API key authentication middleware
3. Create push ingestion endpoint
4. Add basic rate limiting
5. Update aiobscura-sync to use new endpoint

### Follow-up
1. Collect feedback from beta users
2. Iterate on API contract based on real usage
3. Begin Phase 2 type system alignment
