# Collector Events Protocol

**Status:** Implemented (current behavior)
**Applies to:** `POST /collectors/events`, `GET /collectors/sessions/{session_id}`, `POST /collectors/sessions/{session_id}/complete`

## Overview

CatSyphon accepts collector events over HTTP/JSON from external clients (for example aiobscura or watcher-style collectors).

The protocol is **content-hash idempotent**:
- Each event may include `event_hash`.
- If omitted, CatSyphon computes it from `(type, emitted_at, data)`.
- Duplicate hashes for the same conversation are ignored.

CatSyphon stores its own internal ordering (`Message.sequence`) and updates conversation progress using accepted events.

## Authentication

Collector endpoints require:
- `Authorization: Bearer <api_key>`
- `X-Collector-ID: <collector_uuid>`

Collector registration:
- `POST /collectors` creates a collector and returns API credentials.

## Endpoints

### `POST /collectors/events`

Submit an event batch for one collector session.

Request:
```json
{
  "session_id": "session-123",
  "events": [
    {
      "type": "session_start",
      "emitted_at": "2026-02-24T10:00:00Z",
      "observed_at": "2026-02-24T10:00:01Z",
      "event_hash": "optional-32-char-hash",
      "data": {
        "agent_type": "claude_code",
        "agent_version": "1.0.0",
        "working_directory": "/Users/dev/project",
        "git_branch": "main"
      }
    },
    {
      "type": "message",
      "emitted_at": "2026-02-24T10:00:02Z",
      "observed_at": "2026-02-24T10:00:03Z",
      "data": {
        "author_role": "human",
        "message_type": "prompt",
        "content": "Implement auth"
      }
    }
  ]
}
```

Response (`202 Accepted`):
```json
{
  "accepted": 2,
  "last_sequence": 2,
  "conversation_id": "uuid",
  "warnings": []
}
```

Notes:
- `accepted` = newly accepted (non-duplicate) events.
- `last_sequence` is retained for compatibility and is effectively conversation progress.
- Request batch size is capped by schema (`1..50`).
- The API currently does **not** enforce client-supplied event sequence numbers.
- There is no active `409 sequence_gap` flow in current implementation.

### `GET /collectors/sessions/{session_id}`

Returns current session/conversation ingestion status.

Response (`200 OK`):
```json
{
  "session_id": "session-123",
  "conversation_id": "uuid",
  "last_sequence": 42,
  "event_count": 42,
  "first_event_at": "2026-02-24T10:00:00Z",
  "last_event_at": "2026-02-24T10:15:00Z",
  "status": "active"
}
```

`404` means CatSyphon has not seen this session.

### `POST /collectors/sessions/{session_id}/complete`

Marks a session complete.

Request:
```json
{
  "event_count": 42,
  "outcome": "success",
  "summary": "Optional completion summary"
}
```

Response (`200 OK`):
```json
{
  "session_id": "session-123",
  "conversation_id": "uuid",
  "status": "completed",
  "total_events": 42
}
```

Notes:
- Legacy `final_sequence` semantics are deprecated in server implementation.
- Completion can trigger downstream tagging workflows.

## Event Schema

Common envelope:
```json
{
  "type": "message|tool_call|tool_result|thinking|error|session_start|session_end|metadata",
  "emitted_at": "ISO-8601",
  "observed_at": "ISO-8601",
  "event_hash": "optional",
  "data": {}
}
```

Validation rules currently enforced:
- `session_start`: requires `data.agent_type`
- `message`: requires `data.author_role`, `data.message_type`
- `tool_call`: requires `data.tool_name`, `data.tool_use_id`
- `tool_result`: requires `data.tool_use_id`
- `session_end`: requires `data.outcome`

`data` supports additional fields (`extra="allow"`) for forward compatibility.

## Recommended Collector Lifecycle

1. Send `session_start` once per local session.
2. Send incremental event batches via `/collectors/events`.
3. On shutdown/end, call `/collectors/sessions/{session_id}/complete`.
4. For recovery, use `/collectors/sessions/{session_id}` to check whether the session already exists.

## Timestamp Semantics

- `emitted_at`: when source system produced the event.
- `observed_at`: when collector observed/parsed the event.
- server ingest time is tracked internally by CatSyphon.

