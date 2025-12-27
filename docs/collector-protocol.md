# Collector Events Protocol Design

**Status:** DRAFT - For Review
**Epic:** catsyphon-collector-api
**Author:** Claude
**Date:** 2025-12-27

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

---

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  aiobscura  │     │   Watcher   │
│  (remote)   │     │   (local)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  POST /collect/events
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

### 1. POST /collect/register

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

### 2. POST /collect/events

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
      "timestamp": "2025-12-27T10:00:00.000Z",
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
      "timestamp": "2025-12-27T10:00:01.000Z",
      "data": {
        "role": "user",
        "content": "Help me implement authentication"
      }
    },
    {
      "sequence": 3,
      "type": "message",
      "timestamp": "2025-12-27T10:00:05.000Z",
      "data": {
        "role": "assistant",
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
      "timestamp": "2025-12-27T10:00:06.000Z",
      "data": {
        "tool_name": "Read",
        "tool_use_id": "toolu_abc123",
        "parameters": {"file_path": "/src/auth.py"}
      }
    },
    {
      "sequence": 5,
      "type": "tool_result",
      "timestamp": "2025-12-27T10:00:07.000Z",
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

### 3. GET /collect/status/{session_id}

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

### 4. POST /collect/sessions/{session_id}/complete

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
| `message` | User or assistant message | role, content |
| `tool_call` | Tool invocation | tool_name, tool_use_id, parameters |
| `tool_result` | Tool response | tool_use_id, success, result |
| `thinking` | Extended thinking content | content |
| `error` | Error occurred | error_type, message |
| `metadata` | Session metadata update | (any key-value pairs) |

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
- Stored: bcrypt hash in `collector_configs.api_key_hash`
- Scoped: To a single workspace
- Rotatable: Old keys can be revoked, new keys issued

### Flow

```
1. Admin creates workspace (out of scope for this protocol)
2. Admin/user calls POST /collect/register with workspace auth
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
| 409 | Conflict | Sequence gap - call /status and resend |
| 429 | Rate limited | Back off and retry |
| 500 | Server error | Retry with backoff |

### Retry Strategy

```python
def send_with_retry(events, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = post("/collect/events", events)
            if response.status == 202:
                return response
            if response.status == 409:
                # Sequence gap - get status and resend from last_sequence
                status = get(f"/collect/status/{session_id}")
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
        self.buffer.append({
            "sequence": self.sequence,
            "type": "message",
            "timestamp": message.timestamp.isoformat(),
            "data": message.to_dict()
        })
        if len(self.buffer) >= 10:  # Batch size
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        self.post("/collect/events", {
            "session_id": self.session_id,
            "events": self.buffer
        })
        self.buffer = []
```

### Watcher (Reference Implementation)

The existing watcher will be refactored to:
1. Parse log file changes locally
2. Convert to event stream
3. POST to /collect/events instead of calling ingest_conversation()

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
- Implement /collect/events, /collect/status, /collect/register
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
        "required": ["sequence", "type", "timestamp", "data"],
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
          "timestamp": {
            "type": "string",
            "format": "date-time"
          },
          "data": {
            "type": "object"
          }
        }
      }
    }
  }
}
```
