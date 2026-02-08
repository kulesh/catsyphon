# Remote Collector System Architecture

**Status:** Implementation Complete (Epic 2)
**Date:** 2025-12-28

## 1. High-Level Components

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              COLLECTORS (Data Sources)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  aiobscura  │    │   Watcher   │    │   Watcher   │    │  SDK/Other  │      │
│  │  (remote)   │    │  (direct)   │    │ (API mode)  │    │  Collectors │      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘      │
│         │                  │                  │                  │              │
│         │  HTTP/JSON       │  Direct DB       │  HTTP/JSON       │  HTTP/JSON   │
│         │  (Collector API) │  (SQLAlchemy)    │  (Collector API) │              │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CATSYPHON SERVER                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI REST API Layer                           │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │   │
│  │  │ /collectors/*  │  │ /conversations │  │ /projects, /stats, etc.   │ │   │
│  │  │ (Events API)   │  │ (Query API)    │  │ (Analytics API)           │ │   │
│  │  └───────┬────────┘  └───────┬────────┘  └────────────┬───────────────┘ │   │
│  └──────────┼───────────────────┼────────────────────────┼─────────────────┘   │
│             │                   │                        │                      │
│             ▼                   │                        │                      │
│  ┌─────────────────────┐        │                        │                      │
│  │  CollectorSession   │        │                        │                      │
│  │    Repository       │        │                        │                      │
│  │ ┌─────────────────┐ │        │                        │                      │
│  │ │ Session Create  │ │        │                        │                      │
│  │ │ Sequence Track  │ │        │                        │                      │
│  │ │ Deduplication   │ │        │                        │                      │
│  │ │ Message Create  │ │        │                        │                      │
│  │ │ Parent Linking  │ │        │                        │                      │
│  │ └─────────────────┘ │        │                        │                      │
│  └──────────┬──────────┘        │                        │                      │
│             │                   │                        │                      │
│  ┌──────────┴───────────────────┴────────────────────────┴─────────────────┐   │
│  │                     Direct Ingestion Pipeline                            │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │   │
│  │  │ Parser Registry│  │ Deduplication  │  │ ingest_conversation()     │ │   │
│  │  │ (Claude, etc.) │  │ (Hash-based)   │  │ (creates DB records)      │ │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        Tagging Pipeline (Optional)                        │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │   │
│  │  │  Rule Tagger   │  │   LLM Tagger   │  │  Tag Cache (File-based)   │ │   │
│  │  │ (regex-based)  │  │ (OpenAI GPT-4) │  │  (30-day TTL)             │ │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                          PostgreSQL Database                              │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────────┐ │   │
│  │  │ Workspaces │ │  Projects  │ │ Developers │ │ CollectorConfigs       │ │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │   │
│  │  │                      Conversations                                  │  │   │
│  │  │  - collector_session_id (original session ID from collector)       │  │   │
│  │  │  - last_event_sequence (for resumption tracking)                   │  │   │
│  │  │  - parent_conversation_id (for agent hierarchy)                    │  │   │
│  │  └────────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────────────────────┐│   │
│  │  │    Messages    │ │   Epochs       │ │   FilesTouched               ││   │
│  │  └────────────────┘ └────────────────┘ └────────────────────────────────┘│   │
│  │  ┌────────────────┐ ┌────────────────────────────────────────────────────┐│   │
│  │  │ IngestionJobs  │ │   RawLogs (for direct file ingestion)            ││   │
│  │  └────────────────┘ └────────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React + TypeScript)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                    │
│  │   Dashboard    │  │ ConversationList│ │ProjectDetail   │                    │
│  │ (Overview)     │  │ (Archive)       │ │(Project View)  │                    │
│  └────────────────┘  └────────────────┘  └────────────────┘                    │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    TanStack Query (Data Fetching)                         │   │
│  │  - Auto-refresh polling (15s)                                             │   │
│  │  - Caching & deduplication                                                │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                              ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     API Client (lib/api.ts)                               │   │
│  │  - getConversations(), getConversation(), getMessages()                   │   │
│  │  - getProjects(), getProjectSessions(), getProjectFiles()                 │   │
│  │  - getIngestionJobs(), getWatchConfigs()                                  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                   │
│                          /api/*  (Vite proxy to :8000)                          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 2. On-Wire Protocol Schema

### 2.1 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/collectors` | POST | Register new collector, get API credentials |
| `/collectors/events` | POST | Submit event batch |
| `/collectors/sessions/{id}` | GET | Get session status (for resumption) |
| `/collectors/sessions/{id}/complete` | POST | Mark session complete |
| `/collectors/builtin/credentials` | GET | Get built-in watcher credentials (internal) |

### 2.2 Authentication

```
Headers:
  Authorization: Bearer cs_live_xxxxxxxxxxxx
  X-Collector-ID: <uuid>
```

- API keys use format: `cs_{environment}_{random_32_chars}`
- Stored as SHA-256 hash in `collector_configs.api_key_hash`
- Scoped to a single workspace

### 2.3 Event Batch Schema

**Request: POST /collectors/events**

```json
{
  "session_id": "claude-session-abc123",
  "events": [
    {
      "sequence": 1,
      "type": "session_start",
      "emitted_at": "2025-12-27T10:00:00.000Z",
      "observed_at": "2025-12-27T10:00:00.050Z",
      "data": {
        "agent_type": "claude-code",
        "agent_version": "1.0.45",
        "working_directory": "/Users/dev/project",
        "git_branch": "feature/auth",
        "parent_session_id": null,
        "slug": "implement-auth",
        "summaries": [...],
        "compaction_events": [...]
      }
    },
    {
      "sequence": 2,
      "type": "message",
      "emitted_at": "...",
      "observed_at": "...",
      "data": {
        "author_role": "human",
        "message_type": "prompt",
        "content": "Help me implement authentication"
      }
    },
    {
      "sequence": 3,
      "type": "message",
      "emitted_at": "...",
      "observed_at": "...",
      "data": {
        "author_role": "assistant",
        "message_type": "response",
        "content": "I'll help you...",
        "model": "claude-sonnet-4-20250514",
        "token_usage": {"input_tokens": 1500, "output_tokens": 250},
        "thinking_content": "...",
        "stop_reason": "end_turn"
      }
    },
    {
      "sequence": 4,
      "type": "tool_call",
      "emitted_at": "...",
      "observed_at": "...",
      "data": {
        "tool_name": "Read",
        "tool_use_id": "toolu_abc123",
        "parameters": {"file_path": "/src/auth.py"}
      }
    },
    {
      "sequence": 5,
      "type": "tool_result",
      "emitted_at": "...",
      "observed_at": "...",
      "data": {
        "tool_use_id": "toolu_abc123",
        "success": true,
        "result": "# auth.py contents..."
      }
    },
    {
      "sequence": 6,
      "type": "session_end",
      "emitted_at": "...",
      "observed_at": "...",
      "data": {
        "outcome": "success",
        "summary": "Implemented auth feature",
        "plans": [...],
        "files_touched": ["/src/auth.py", "/tests/test_auth.py"]
      }
    }
  ]
}
```

**Response: 202 Accepted**

```json
{
  "accepted": 6,
  "last_sequence": 6,
  "conversation_id": "uuid",
  "warnings": []
}
```

### 2.4 Timestamp Semantics (Three-Tier)

| Timestamp | Set By | Description |
|-----------|--------|-------------|
| `emitted_at` | Source (logs) | When event was originally produced |
| `observed_at` | Collector | When parser/collector first saw it |
| `server_received_at` | Server | When CatSyphon API received it |

This enables latency debugging across the pipeline.

### 2.5 Event Types

| Type | Required Fields | Purpose |
|------|-----------------|---------|
| `session_start` | agent_type, agent_version | Begin conversation |
| `session_end` | outcome | End conversation |
| `message` | author_role, message_type, content | User/assistant message |
| `tool_call` | tool_name, tool_use_id, parameters | Tool invocation |
| `tool_result` | tool_use_id, success, result | Tool response |
| `thinking` | content | Extended thinking |
| `error` | error_type, message | Error occurred |
| `metadata` | (any) | Session metadata update |

## 3. Event Pipeline & Transformations

### 3.1 Collector API Path (HTTP)

```
External Collector (aiobscura, SDK)
        │
        │  POST /collectors/events
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   collectors.py:submit_events()                  │
│  1. Authenticate collector (verify API key hash)                │
│  2. Create IngestionJob for tracking                            │
│  3. Sort events by sequence                                      │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│              CollectorSessionRepository                          │
│  4. get_or_create_session():                                     │
│     - Look up by collector_session_id                            │
│     - If new: create Conversation, Project, Developer, Epoch     │
│     - Resolve parent_conversation_id if parent_session_id exists │
│     - Inherit project/developer from parent if not resolved      │
│  5. check_sequence_gap() → 409 if gap detected                  │
│  6. filter_duplicate_sequences() → idempotent processing        │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Event Processing Loop                        │
│  For each new event:                                             │
│  7. add_message():                                               │
│     - Map event type → author_role, message_type enums           │
│     - Create Message with tool_calls JSONB if tool_call          │
│     - Store token_usage, model in extra_data                     │
│  8. add_file_touched():                                          │
│     - Track Edit/Write/Read tool calls → FileTouched records     │
│  9. complete_session() if session_end:                           │
│     - Set status="completed", end_time, success                  │
│     - Store plans in extra_data                                  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Post-Processing                               │
│  10. update_sequence() - track last_event_sequence               │
│  11. update_last_activity() - update end_time to latest event   │
│  12. link_orphaned_collectors() - deferred parent linking       │
│  13. Update IngestionJob metrics and commit                     │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
    PostgreSQL
```

### 3.2 Direct Ingestion Path (File-based)

```
Watcher (direct mode) / CLI ingest
        │
        │  File system event or CLI command
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ParserRegistry.parse()                         │
│  1. Detect agent type from file path/content                    │
│  2. Route to appropriate parser (ClaudeCodeParser, etc.)        │
│  3. Return ParsedConversation with messages, plans, files       │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│              pipeline/ingestion.py:ingest_conversation()         │
│  4. Check deduplication (hash-based via RawLog)                 │
│  5. Resolve project from working_directory                      │
│  6. Resolve developer from path (/Users/username/...)           │
│  7. Create Conversation, Epochs, Messages                       │
│  8. Create FileTouched records from tool calls                  │
│  9. Handle parent-child linking                                  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│               TaggingPipeline (Optional, --enable-tagging)       │
│  10. RuleTagger: regex-based extraction (errors, tool patterns)  │
│  11. LLMTagger: OpenAI GPT-4o-mini for semantic analysis        │
│      - Sentiment: positive/neutral/negative/frustrated           │
│      - Intent: feature_add/bug_fix/refactor/learning/debugging   │
│      - Outcome: success/partial/failed/abandoned                 │
│      - Features & Problems lists                                 │
│  12. TagCache: File-based cache (30-day TTL) for cost reduction │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
    PostgreSQL
```

### 3.3 Watcher API Mode Path (Hybrid)

```
Watcher (--use-api mode)
        │
        │  File system event
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ParserRegistry.parse()                         │
│  (Same as direct: parse file to ParsedConversation)             │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│              CollectorClient.ingest_conversation()               │
│  1. Convert ParsedConversation → event stream                   │
│  2. Create session_start event with metadata                    │
│  3. Convert messages → message/tool_call/tool_result events     │
│  4. Create session_end event with outcome, plans, files         │
│  5. Batch events and POST to /collectors/events                 │
│  6. Call /collectors/sessions/{id}/complete                     │
└─────────────────────────────────────────────────────────────────┘
        │
        │  HTTP to localhost:8000
        ▼
    Collector API Path (same as section 3.1)
```

### 3.4 Semantic Parity Guarantees

Both paths produce identical database records:

| Field | Collector API | Direct Ingestion |
|-------|---------------|------------------|
| `conversation.project_id` | From working_directory or inherited | From working_directory or inherited |
| `conversation.developer_id` | From username in path | From username in path |
| `conversation.parent_conversation_id` | Deferred linking via parent_session_id | Same |
| `conversation.extra_data.slug` | From session_start | From parser |
| `conversation.extra_data.summaries` | From session_start | From parser |
| `conversation.extra_data.plans` | From session_end | From parser |
| `message.tool_calls` | From tool_call events | From parsed messages |
| `message.extra_data.token_usage` | From message events | From parsed messages |
| `files_touched` | From tool_call events | From parsed messages |

## 4. Database → Frontend Interactions

### 4.1 Query APIs

```
Frontend                          Backend                         Database
   │                                 │                                │
   │  GET /conversations             │                                │
   │  ?page=1&project=...&...        │                                │
   │ ─────────────────────────────►  │                                │
   │                                 │  ConversationRepository        │
   │                                 │  .get_with_counts_hierarchical()│
   │                                 │ ────────────────────────────►  │
   │                                 │                                │
   │                                 │  SQL: SELECT with JOINs       │
   │                                 │  - conversations               │
   │                                 │  - messages (count)            │
   │                                 │  - files_touched (count)       │
   │                                 │  - projects, developers        │
   │                                 │ ◄────────────────────────────  │
   │                                 │                                │
   │  ConversationListResponse       │                                │
   │  {items, total, page, pages}    │                                │
   │ ◄─────────────────────────────  │                                │
   │                                 │                                │
   │  GET /conversations/{id}        │                                │
   │ ─────────────────────────────►  │                                │
   │                                 │  JOIN with all related tables  │
   │                                 │  + extra_data (plans, summaries)│
   │  ConversationDetail             │                                │
   │ ◄─────────────────────────────  │                                │
   │                                 │                                │
   │  GET /conversations/{id}/messages│                               │
   │ ─────────────────────────────►  │                                │
   │                                 │  MessageRepository             │
   │  MessageResponse[]              │  .get_by_conversation()        │
   │ ◄─────────────────────────────  │                                │
```

### 4.2 Frontend Data Flow

```typescript
// ConversationList.tsx
const { data: conversations } = useQuery({
  queryKey: ['conversations', filters],
  queryFn: () => getConversations(filters),
  refetchInterval: 15000,  // Auto-refresh every 15s
});

// ConversationDetail.tsx
const { data: conversation } = useQuery({
  queryKey: ['conversation', id],
  queryFn: () => getConversation(id),
});

const { data: messages } = useQuery({
  queryKey: ['messages', id, page],
  queryFn: () => getConversationMessages(id, page),
});
```

### 4.3 Key Response Types

**ConversationListResponse:**
```typescript
{
  items: Array<{
    id: string;
    project_name: string;
    developer: string;
    start_time: string;
    status: 'active' | 'completed';
    success: boolean | null;
    message_count: number;
    files_count: number;
    agent_type: string;
  }>;
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
```

**ConversationDetail:**
```typescript
{
  id: string;
  // ... base fields
  extra_data: {
    slug?: string;
    summaries?: Array<{...}>;
    plans?: Array<{...}>;
    working_directory?: string;
    git_branch?: string;
  };
  children?: ConversationDetail[];  // Sub-agent conversations
}
```

**MessageResponse:**
```typescript
{
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tool_calls?: Array<{
    tool_name: string;
    tool_use_id: string;
    parameters: object;
    result?: string;
    success?: boolean;
  }>;
  extra_data?: {
    model?: string;
    token_usage?: { input_tokens, output_tokens };
    thinking_content?: string;
  };
}
```

## 5. Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **CollectorClient** | `collector_client.py` | Convert ParsedConversation → events, HTTP batching |
| **Collector API Routes** | `api/routes/collectors.py` | Auth, validation, sequence tracking |
| **CollectorSessionRepository** | `db/repositories/collector_session.py` | Session CRUD, dedup, parent linking |
| **ParserRegistry** | `parsers/registry.py` | Route files to correct parser |
| **ClaudeCodeParser** | `parsers/claude_code.py` | Parse .jsonl logs to ParsedConversation |
| **IngestConversation** | `pipeline/ingestion.py` | Direct DB ingestion from parsed data |
| **TaggingPipeline** | `tagging/pipeline.py` | LLM + rule-based tag enrichment |
| **ConversationRepository** | `db/repositories/conversation.py` | Query & filter conversations |
| **Watcher/WatchDaemon** | `watch.py` | File monitoring, ingestion orchestration |

## 6. Gaps & Design Considerations

### 6.1 Tagging Not Integrated with Collector API

**Current State:** Collector API path does NOT run the TaggingPipeline.

**Impact:** Conversations ingested via Collector API lack:
- Sentiment analysis
- Intent classification
- LLM-derived outcome
- Problem/feature extraction

**Options:**
1. Post-ingestion tagging job (async)
2. Add tagging to Collector API (increases latency)
3. Keep tagging as batch job for analytics

### 6.2 No Real-Time Frontend Updates

**Current State:** Frontend uses 15-second polling.

**Impact:** New conversations from Collector API don't appear immediately.

**Options:**
1. WebSocket for live updates (future Epic 3)
2. Server-Sent Events for ingestion notifications
3. Reduce polling interval (increases server load)

### 6.3 Parent Linking is Eventually Consistent

**Current State:** If child session arrives before parent, linking is deferred.

**Mechanism:** `link_orphaned_collectors()` runs after each batch.

**Edge Case:** If parent never arrives, child remains orphaned (has parent_session_id in extra_data but null parent_conversation_id).

### 6.4 No Rate Limiting

**Current State:** No request/event rate limits enforced.

**Risk:** Runaway collector could overwhelm server.

**Documented Plan:** 1000 events/min, 100 requests/min per collector (not implemented).

---

## 7. Mission Assessment: Planning vs Implementation

This section compares the original architectural planning documents with what was actually built, identifying decisions made and work remaining.

### 7.1 Planning Documents Reviewed

Three documents defined the original vision:

1. **[type-system-reconciliation.md](../architecture/type-system-reconciliation.md)** - Type system alignment between aiobscura and CatSyphon
2. **[log-collection.md](./log-collection.md)** - High-level product vision and protocol design
3. **[implementation-plan.md](./implementation-plan.md)** - Detailed phase-by-phase implementation plan

### 7.2 What Was Planned vs What Was Built

| Planned Feature | Status | Notes |
|-----------------|--------|-------|
| **Protocol: gRPC/OTLP (port 4317)** | ❌ Changed | Used HTTP/JSON REST API instead |
| **Protocol: OTLP/HTTP fallback (4318)** | ❌ Dropped | Single HTTP/JSON API at /collectors/* |
| **Custom protobuf schema** | ❌ Dropped | JSON event schemas with Pydantic validation |
| **AuthorRole enum (6 values)** | ✅ Built | human, caller, assistant, agent, tool, system |
| **MessageType enum (8 values)** | ✅ Built | prompt, response, tool_call, tool_result, etc. |
| **Thread model (hierarchy)** | ❌ Deferred | Parent-child via parent_conversation_id instead |
| **BackingModel table** | ❌ Deferred | Model info stored in message extra_data |
| **Dual timestamps** | ✅ Built | emitted_at, observed_at, server_received_at |
| **Event streaming model** | ✅ Built | session_start, message, tool_call, tool_result, session_end |
| **Sequence tracking** | ✅ Built | Per-session sequence numbers for resumption |
| **Deferred parent linking** | ✅ Built | link_orphaned_collectors() handles out-of-order arrival |
| **API key authentication** | ✅ Built | cs_xxx format with SHA-256 hash storage |
| **Multi-tenancy security audit** | ❌ Deferred | Basic workspace scoping exists |
| **Rate limiting** | ❌ Deferred | Not implemented |
| **OTEL ecosystem compat** | ❌ Dropped | Not an OTEL-compatible endpoint |

### 7.3 Key Architectural Decisions

**Decision 1: HTTP/JSON over gRPC/OTLP**

The original plan called for:
- Native gRPC service (port 4317) with custom protobuf
- OTLP/HTTP adapter (port 4318) for ecosystem compatibility

What was built:
- Simple HTTP/JSON REST API at `/collectors/*`
- Pydantic-validated JSON event schemas

*Rationale*: HTTP/JSON is simpler to implement, debug, and integrate. gRPC adds complexity without clear benefit for our use case (batch ingestion, not real-time streaming). The OTLP ecosystem compatibility was deprioritized since aiobscura is our primary collector.

**Decision 2: Flat Events over Hierarchical Threads**

The original plan called for:
- Thread model for conversation hierarchies (main, agent, background)
- Explicit parent_thread_id relationships

What was built:
- Flat event stream with parent_session_id for child conversations
- Parent-child linking via parent_conversation_id on conversations table

*Rationale*: The simpler approach handles the primary use case (Claude Code sub-agents) without the complexity of a full thread hierarchy. Can be extended later if needed.

**Decision 3: Inline Model Info over BackingModel Table**

The original plan called for:
- Dedicated backing_models table
- Foreign key from conversations

What was built:
- Model info stored in message.extra_data.model
- No separate tracking table

*Rationale*: Model tracking was lower priority than core ingestion. The current approach captures the data; structured extraction can be added later.

### 7.4 Implementation Phases: Actual vs Planned

**Phase 0: Type System Alignment**
- Planned: Full enum adoption, Thread table, BackingModel table, migrations
- Actual: Partial - author_role and message_type exist as string fields, mapped at ingestion time
- Status: **Partial** (core types aligned, structural changes deferred)

**Phase 1: Multi-Tenancy Security Fixes**
- Planned: AuthContext, workspace-scoped queries, security audit
- Actual: Basic workspace_id scoping exists, no formal security audit
- Status: **Deferred**

**Phase 2: CatSyphon Collector API**
- Planned: gRPC server, protobuf codegen, rate limiting
- Actual: HTTP/JSON API with full CRUD, event ingestion, session management
- Status: **Complete** (different implementation than planned)

**Phase 3: aiobscura gRPC Client**
- Planned: tonic/prost client, export command
- Actual: Not started (aiobscura hasn't been updated)
- Status: **Not Started**

**Phase 4: Integration Testing**
- Planned: End-to-end gRPC testing
- Actual: Watcher API mode provides integration testing path
- Status: **Partial** (watcher validates the API, no aiobscura integration)

### 7.5 What Remains

**High Priority (for production use):**
1. Security audit of multi-tenancy (Phase 1)
2. Rate limiting implementation
3. aiobscura integration (once aiobscura catches up)

**Medium Priority (for completeness):**
1. BackingModel table for structured LLM tracking
2. Thread model if sub-agent hierarchies become complex
3. Tagging integration with Collector API path

**Low Priority (deferred):**
1. gRPC/OTLP endpoint (only if ecosystem compatibility needed)
2. Bidirectional sync (Phase 4 of original plan)
3. Cross-developer analytics dashboards

### 7.6 Semantic Parity Achievement

The core goal of semantic parity between ingestion paths was achieved:

| Aspect | Direct Ingestion | Collector API | Parity |
|--------|------------------|---------------|--------|
| Conversation creation | ✅ | ✅ | ✅ |
| Message storage | ✅ | ✅ | ✅ |
| Tool call extraction | ✅ | ✅ | ✅ |
| Files touched tracking | ✅ | ✅ | ✅ |
| Parent-child linking | ✅ | ✅ | ✅ |
| Slug/summaries/metadata | ✅ | ✅ | ✅ |
| Plan extraction | ✅ | ✅ | ✅ |
| AI Tagging | ✅ | ❌ | ❌ |

The only gap is AI tagging, which runs on the direct ingestion path but not on Collector API ingestion.
