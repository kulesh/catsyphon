# Collector Events Protocol Design

**Status:** IMPLEMENTED (Phase 1 Complete)
**Epic:** catsyphon-collector-api
**Author:** Claude
**Date:** 2025-12-27
**Implementation:** 2025-12-28

## Implementation Notes

Phase 1 of the Collector Events API is complete:

- ✅ `POST /collectors` - Register collector with API key generation
- ✅ `POST /collectors/events` - Submit event batches with sequence tracking
- ✅ `GET /collectors/sessions/{id}` - Check session status for resumption
- ✅ `POST /collectors/sessions/{id}/complete` - Mark session as completed

**Key Implementation Details:**
- API keys use SHA-256 hashing (not bcrypt as originally proposed) for simplicity
- Sequence gap detection and deduplication implemented
- Event validation for type-specific required fields (e.g., `author_role` for messages)
- Three-tier timestamps: `emitted_at`, `observed_at`, `server_received_at`

**Files:**
- Routes: `backend/src/catsyphon/api/routes/collectors.py`
- Schemas: `backend/src/catsyphon/api/schemas.py` (collector section)
- Repository: `backend/src/catsyphon/db/repositories/collector_session.py`
- Tests: `backend/tests/test_api_collectors.py`

---

## Overview

This document specifies the HTTP-based collector events protocol for streaming conversation data from aiobscura and the CatSyphon watcher to the CatSyphon server.

### Goals

1. **Incremental ingestion**: Stream events as they occur, not bulk uploads
2. **Resumable**: Recover from disconnects without data loss
3. **Simple**: HTTP/JSON, no gRPC complexity initially
4. **Unified**: Same protocol for aiobscura and watcher

### Non-Goals

1. Real-time WebSocket streaming (future enhancement)
2. gRPC support (Phase 2, separate epic)
3. Multi-region replication

### OTEL Ingestion (Codex)

CatSyphon also supports OTLP HTTP log ingestion for Codex via `POST /v1/logs`.
This is separate from the collector events protocol and is intended for
OpenTelemetry exporters. OTEL ingestion is opt-in and gated by configuration.

See [OTEL Ingestion](../reference/otel-ingestion.md) for setup details and required headers.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  aiobscura  │     │   Watcher   │
│  (remote)   │     │   (local)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  POST /collectors/events
       │                   │
       └───────────┬───────┘
                   ▼
         ┌─────────────────┐
         │   CatSyphon     │
         │   Collector API │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │   PostgreSQL    │
         │   (normalized)  │
         └─────────────────┘
```

---

## API Endpoints

### 1. POST /collectors

Register a new collector instance and obtain API credentials.

**Request:**
```json
{
  "collector_type": "aiobscura" | "watcher" | "sdk",
  "collector_version": "1.0.0",
  "hostname": "dev-machine.local",
  "workspace_id": "uuid",           // Required for multi-tenancy
  "metadata": {                      // Optional
    "os": "macOS 14.0",
    "user": "developer@example.com"
  }
}
```

**Response (201 Created):**
```json
{
  "collector_id": "uuid",
  "api_key": "cs_live_xxxxxxxxxxxx",  // Only returned once
  "api_key_prefix": "cs_live_xxxx",   // For display/identification
  "created_at": "2025-12-27T10:00:00Z"
}
```

**Authentication:** Requires workspace-level auth (TBD: how workspaces auth initially)

---

### 2. POST /collectors/events

Submit a batch of events from an active session.

**Headers:**
```
Authorization: Bearer cs_live_xxxxxxxxxxxx
X-Collector-ID: uuid
X-Idempotency-Key: uuid  // Optional, for retry safety
```

**Request:**
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
        "git_branch": "feature/auth"
      }
    },
    {
      "sequence": 2,
      "type": "message",
      "emitted_at": "2025-12-27T10:00:01.000Z",
      "observed_at": "2025-12-27T10:00:01.050Z",
      "data": {
        "author_role": "human",
        "message_type": "prompt",
        "content": "Help me implement authentication"
      }
    },
    {
      "sequence": 3,
      "type": "message",
      "emitted_at": "2025-12-27T10:00:05.000Z",
      "observed_at": "2025-12-27T10:00:05.050Z",
      "data": {
        "author_role": "assistant",
        "message_type": "response",
        "content": "I'll help you implement authentication...",
        "model": "claude-sonnet-4-20250514",
        "token_usage": {
          "input_tokens": 1500,
          "output_tokens": 250
        }
      }
    },
    {
      "sequence": 4,
      "type": "tool_call",
      "emitted_at": "2025-12-27T10:00:06.000Z",
      "observed_at": "2025-12-27T10:00:06.050Z",
      "data": {
        "tool_name": "Read",
        "tool_use_id": "toolu_abc123",
        "parameters": {"file_path": "/src/auth.py"}
      }
    },
    {
      "sequence": 5,
      "type": "tool_result",
      "emitted_at": "2025-12-27T10:00:07.000Z",
      "observed_at": "2025-12-27T10:00:07.050Z",
      "data": {
        "tool_use_id": "toolu_abc123",
        "success": true,
        "result": "# auth.py contents..."
      }
    }
  ]
}
```

**Response (202 Accepted):**
```json
{
  "accepted": 5,
  "last_sequence": 5,
  "conversation_id": "uuid",  // CatSyphon's internal ID
  "warnings": []              // Non-fatal issues
}
```

**Response (409 Conflict) - Sequence gap:**
```json
{
  "error": "sequence_gap",
  "message": "Expected sequence 3, got 5",
  "last_received_sequence": 2,
  "expected_sequence": 3
}
```

---

### 3. GET /collectors/sessions/{session_id}

Check the last received sequence for a session (for resumption).

**Headers:**
```
Authorization: Bearer cs_live_xxxxxxxxxxxx
```

**Response (200 OK):**
```json
{
  "session_id": "claude-session-abc123",
  "conversation_id": "uuid",
  "last_sequence": 42,
  "event_count": 42,
  "first_event_at": "2025-12-27T10:00:00Z",
  "last_event_at": "2025-12-27T10:15:30Z",
  "status": "active" | "completed"
}
```

**Response (404 Not Found):**
```json
{
  "error": "session_not_found",
  "message": "No events received for session claude-session-abc123"
}
```

---

### 4. POST /collectors/sessions/{session_id}/complete

Mark a session as completed (no more events expected).

**Request:**
```json
{
  "final_sequence": 150,
  "outcome": "success" | "partial" | "failed" | "abandoned",
  "summary": "Implemented user authentication feature"  // Optional
}
```

**Response (200 OK):**
```json
{
  "session_id": "claude-session-abc123",
  "conversation_id": "uuid",
  "status": "completed",
  "total_events": 150
}
```

---

## Event Types

| Type | Description | Required Fields |
|------|-------------|-----------------|
| `session_start` | Begin a new conversation | agent_type, agent_version |
| `session_end` | Conversation ended | outcome |
| `message` | User or assistant message | author_role, message_type, content |
| `tool_call` | Tool invocation | tool_name, tool_use_id, parameters |
| `tool_result` | Tool response | tool_use_id, success, result |
| `thinking` | Extended thinking content | content |
| `error` | Error occurred | error_type, message |
| `metadata` | Session metadata update | (any key-value pairs) |

---

## Event Schema (Phase 0 Aligned)

All events share a common envelope with type-specific data. The schema aligns with the aiobscura type system from Phase 0.

### Common Event Envelope

```json
{
  "sequence": 1,
  "type": "message",
  "emitted_at": "2025-12-27T10:00:01.000Z",
  "observed_at": "2025-12-27T10:00:01.050Z",
  "data": { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | integer | Monotonic sequence number (1-based) |
| `type` | string | Event type (see table above) |
| `emitted_at` | ISO 8601 | When the event was originally produced by the source (from logs) |
| `observed_at` | ISO 8601 | When the collector (parser) observed the event |
| `data` | object | Type-specific payload |

### Timestamp Semantics

Events flow through a pipeline where each stage can record when it observed the event:

```
Source (Claude/Codex logs)  →  Parser (aiobscura/watcher)  →  CatSyphon API  →  Storage
        emitted_at                   observed_at                server_received_at
```

| Timestamp | Set By | Description |
|-----------|--------|-------------|
| `emitted_at` | Source | When the event was originally produced (inferred from log timestamps) |
| `observed_at` | Collector | When the parser/collector first observed the event |
| `server_received_at` | Server | When CatSyphon API received the event (set automatically) |

This chain enables:
- **Latency debugging**: Identify delays between source → collector → server
- **Causality tracking**: Preserve the temporal ordering of observations
- **Pipeline monitoring**: Measure end-to-end ingestion latency

### Message Event Data

```json
{
  "author_role": "human" | "assistant" | "agent" | "tool" | "system",
  "message_type": "prompt" | "response" | "tool_call" | "tool_result" | "context" | "error",
  "content": "Help me implement authentication",
  "model": "claude-sonnet-4-20250514",
  "token_usage": {
    "input_tokens": 1500,
    "output_tokens": 250,
    "cache_creation_tokens": 0,
    "cache_read_tokens": 1200
  },
  "thinking_content": "Let me analyze the requirements...",
  "thinking_metadata": {
    "level": "high",
    "disabled": false
  },
  "stop_reason": "end_turn",
  "raw_data": { }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `author_role` | string | Yes | Who produced the message (Phase 0 AuthorRole) |
| `message_type` | string | Yes | Semantic type of message (Phase 0 MessageType) |
| `content` | string | Yes | Message text content |
| `model` | string | No | LLM model used (assistant messages) |
| `token_usage` | object | No | Token consumption stats |
| `thinking_content` | string | No | Extended thinking blocks |
| `thinking_metadata` | object | No | Thinking level settings |
| `stop_reason` | string | No | Why generation stopped |
| `raw_data` | object | No | Original message for lossless capture |

### AuthorRole Values (Phase 0)

| Value | Description |
|-------|-------------|
| `human` | Human user input |
| `caller` | Calling system/API |
| `assistant` | LLM response |
| `agent` | Sub-agent response |
| `tool` | Tool execution |
| `system` | System prompts/context |

### MessageType Values (Phase 0)

| Value | Description |
|-------|-------------|
| `prompt` | User input/request |
| `response` | LLM text response |
| `tool_call` | Tool invocation |
| `tool_result` | Tool output |
| `plan` | Planning content |
| `summary` | Conversation summary |
| `context` | System context |
| `error` | Error information |

### Tool Call Event Data

```json
{
  "tool_name": "Read",
  "tool_use_id": "toolu_abc123",
  "parameters": {
    "file_path": "/src/auth.py"
  }
}
```

### Tool Result Event Data

```json
{
  "tool_use_id": "toolu_abc123",
  "success": true,
  "result": "# auth.py contents...",
  "error_message": null
}
```

### Session Start Event Data

```json
{
  "agent_type": "claude-code",
  "agent_version": "1.0.45",
  "working_directory": "/Users/dev/project",
  "git_branch": "feature/auth",
  "parent_session_id": null,
  "context_semantics": {
    "shares_parent_context": false,
    "can_use_parent_tools": true
  }
}
```

### Session End Event Data

```json
{
  "outcome": "success" | "partial" | "failed" | "abandoned",
  "summary": "Implemented user authentication feature",
  "total_messages": 42,
  "total_tool_calls": 15
}
```

---

## Sequencing & Ordering

### Rules

1. **Monotonic sequences**: Each event has a sequence number, starting at 1
2. **Per-session**: Sequences are scoped to session_id
3. **Gap detection**: Server rejects batches with sequence gaps
4. **Idempotent**: Re-sending same sequence is ignored (not an error)
5. **Out-of-order**: Not supported; client must buffer and send in order

### Deduplication

Events are deduplicated by `(session_id, sequence)`. If a batch includes events already received:
- Already-received events are silently ignored
- New events in the batch are processed
- Response includes count of actually new events

---

## Authentication

### API Keys

- Format: `cs_{environment}_{random}` (e.g., `cs_live_a1b2c3d4e5f6`)
- Stored: SHA-256 hash in `collector_configs.api_key_hash`
- Scoped: To a single workspace
- Rotatable: Old keys can be revoked, new keys issued

### Flow

```
1. Admin creates workspace (out of scope for this protocol)
2. Admin/user calls POST /collectors with workspace auth
3. Server returns collector_id + api_key
4. Client stores api_key securely
5. All subsequent calls use Authorization: Bearer {api_key}
```

### Rate Limiting (Future)

- 1000 events/minute per collector
- 100 requests/minute per collector
- Burst: 50 events per request max

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Client Action |
|------|---------|---------------|
| 200 | Success | Continue |
| 201 | Created | Store credentials |
| 202 | Accepted | Events queued |
| 400 | Bad request | Fix payload |
| 401 | Unauthorized | Check API key |
| 403 | Forbidden | Wrong workspace |
| 404 | Not found | Session doesn't exist |
| 409 | Conflict | Sequence gap - call GET /collectors/sessions/{id} and resend |
| 429 | Rate limited | Back off and retry |
| 500 | Server error | Retry with backoff |

### Retry Strategy

```python
def send_with_retry(events, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = post("/collectors/events", events)
            if response.status == 202:
                return response
            if response.status == 409:
                # Sequence gap - get status and resend from last_sequence
                status = get(f"/collectors/sessions/{session_id}")
                events = filter_events_after(status.last_sequence)
                continue
            if response.status >= 500:
                sleep(2 ** attempt)  # Exponential backoff
                continue
            raise PermanentError(response)
        except NetworkError:
            sleep(2 ** attempt)
    raise MaxRetriesExceeded()
```

---

## Client Implementation Notes

### aiobscura

```python
class CatSyphonExporter:
    def __init__(self, api_key: str, server_url: str):
        self.api_key = api_key
        self.server_url = server_url
        self.sequence = 0
        self.buffer = []

    def on_message(self, message: Message):
        self.sequence += 1
        observed_at = datetime.now(UTC).isoformat()
        self.buffer.append({
            "sequence": self.sequence,
            "type": "message",
            "emitted_at": message.emitted_at.isoformat(),
            "observed_at": observed_at,  # When we (the collector) observed it
            "data": {
                "author_role": message.author_role,
                "message_type": message.message_type,
                "content": message.content,
                "model": message.model,
                "token_usage": message.token_usage,
            }
        })
        if len(self.buffer) >= 10:  # Batch size
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        self.post("/collectors/events", {
            "session_id": self.session_id,
            "events": self.buffer
        })
        self.buffer = []
```

### Watcher (Reference Implementation)

The existing watcher will be refactored to:
1. Parse log file changes locally
2. Convert to event stream
3. POST to /collectors/events instead of calling ingest_conversation()

This makes the watcher a reference implementation for the protocol.

---

## Database Changes

### New Tables

None required - uses existing schema:
- `collector_configs` - Already exists
- `conversations` - Events create/update conversations
- `messages` - Events create messages

### New Columns

`conversations` table:
- `collector_session_id` (varchar) - Original session_id from collector
- `last_event_sequence` (int) - For resumption tracking

---

## Open Questions

1. **Workspace bootstrap**: How does the first workspace get created? Admin API? CLI?

2. **Event size limits**: Max size per event? Max batch size?
   - Proposal: 1MB per event, 50 events per batch, 10MB per request

3. **Retention of sequence state**: How long to keep sequence tracking for dedup?
   - Proposal: 7 days after last event, then require session_start

4. **Parsed vs raw content**: Should events contain parsed content or raw JSON lines?
   - Proposal: Parsed (structured) - parsing happens on collector side

5. **Compression**: Support gzip for large batches?
   - Proposal: Yes, Accept-Encoding: gzip

---

## Migration Path

### Phase 1: HTTP API (This Epic)
- Implement /collectors, /collectors/events, /collectors/sessions/{id}
- Refactor watcher to use HTTP API
- Manual testing with curl/httpie

### Phase 2: aiobscura Integration
- Implement CatSyphonExporter in aiobscura
- End-to-end testing

### Phase 3: gRPC (Future)
- Add gRPC interface for high-throughput scenarios
- HTTP remains for simplicity/compatibility

---

## Appendix: Full Event Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["session_id", "events"],
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Unique session identifier from the agent"
    },
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sequence", "type", "emitted_at", "observed_at", "data"],
        "properties": {
          "sequence": {
            "type": "integer",
            "minimum": 1
          },
          "type": {
            "type": "string",
            "enum": ["session_start", "session_end", "message",
                     "tool_call", "tool_result", "thinking",
                     "error", "metadata"]
          },
          "emitted_at": {
            "type": "string",
            "format": "date-time",
            "description": "When the event was originally produced by the source"
          },
          "observed_at": {
            "type": "string",
            "format": "date-time",
            "description": "When the collector observed the event"
          },
          "data": {
            "type": "object",
            "description": "Type-specific payload (see Event Schema section)"
          }
        }
      }
    }
  }
}
```
