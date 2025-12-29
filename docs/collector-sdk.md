# Collector SDK Guide

**For developers building HTTP clients that push data to CatSyphon.**

This guide covers implementing the Collector Events API in any language.

---

## Overview

Collectors are clients that:
1. Parse conversation logs from AI coding assistants
2. Convert them to the CatSyphon event format
3. Push events to the CatSyphon server via HTTP

### Existing Collectors

| Collector | Language | Status |
|-----------|----------|--------|
| aiobscura | Rust | In Development |
| CatSyphon Watcher | Python | Built-in |
| Your Collector | Any | This Guide |

---

## Quick Start

### 1. Register Your Collector

```bash
curl -X POST https://catsyphon.example.com/collectors \
  -H "Content-Type: application/json" \
  -d '{
    "collector_type": "my-collector",
    "collector_version": "1.0.0",
    "hostname": "dev-machine.local",
    "workspace_id": "your-workspace-uuid"
  }'
```

**Response:**
```json
{
  "collector_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "cs_live_xK7mN2pQ9rS4tU6vW8xY0zA1bC3dE5fG",
  "api_key_prefix": "cs_live_xK7m",
  "created_at": "2025-12-28T10:00:00Z"
}
```

**Save the `api_key`!** It's only shown once.

### 2. Submit Events

```bash
curl -X POST https://catsyphon.example.com/collectors/events \
  -H "Authorization: Bearer cs_live_xK7mN2pQ9rS4tU6vW8xY0zA1bC3dE5fG" \
  -H "X-Collector-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-123",
    "events": [
      {
        "sequence": 1,
        "type": "session_start",
        "emitted_at": "2025-12-28T10:00:00Z",
        "observed_at": "2025-12-28T10:00:00.050Z",
        "data": {
          "agent_type": "claude-code",
          "agent_version": "1.0.45"
        }
      },
      {
        "sequence": 2,
        "type": "message",
        "emitted_at": "2025-12-28T10:00:01Z",
        "observed_at": "2025-12-28T10:00:01.050Z",
        "data": {
          "author_role": "human",
          "message_type": "prompt",
          "content": "Help me implement authentication"
        }
      }
    ]
  }'
```

**Response (202 Accepted):**
```json
{
  "accepted": 2,
  "last_sequence": 2,
  "conversation_id": "660e8400-e29b-41d4-a716-446655440001",
  "warnings": []
}
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/collectors` | Register a new collector |
| POST | `/collectors/events` | Submit event batch |
| GET | `/collectors/sessions/{session_id}` | Get session status |
| POST | `/collectors/sessions/{session_id}/complete` | Mark session complete |

### Authentication

All requests (except registration) require:

```
Authorization: Bearer cs_live_xxxxxxxxxxxx
X-Collector-ID: <collector-uuid>
```

---

## Event Types

### session_start

Marks the beginning of a conversation.

```json
{
  "sequence": 1,
  "type": "session_start",
  "emitted_at": "2025-12-28T10:00:00Z",
  "observed_at": "2025-12-28T10:00:00.050Z",
  "data": {
    "agent_type": "claude-code",
    "agent_version": "1.0.45",
    "working_directory": "/Users/dev/project",
    "git_branch": "feature/auth",
    "parent_session_id": null
  }
}
```

### message

A message from human or assistant.

```json
{
  "sequence": 2,
  "type": "message",
  "emitted_at": "2025-12-28T10:00:01Z",
  "observed_at": "2025-12-28T10:00:01.050Z",
  "data": {
    "author_role": "human",
    "message_type": "prompt",
    "content": "Help me implement authentication"
  }
}
```

**Required fields for `message` type:**
- `author_role`: `human`, `assistant`, `agent`, `tool`, `system`
- `message_type`: `prompt`, `response`, `tool_call`, `tool_result`, `plan`, `context`, `error`
- `content`: Message text

**Optional fields:**
- `model`: LLM model name (e.g., `claude-sonnet-4-20250514`)
- `token_usage`: `{ input_tokens, output_tokens }`
- `thinking_content`: Extended thinking text

### tool_call

Tool invocation by the assistant.

```json
{
  "sequence": 3,
  "type": "tool_call",
  "emitted_at": "2025-12-28T10:00:02Z",
  "observed_at": "2025-12-28T10:00:02.050Z",
  "data": {
    "tool_name": "Read",
    "tool_use_id": "toolu_abc123",
    "parameters": {
      "file_path": "/src/auth.py"
    }
  }
}
```

**Required fields for `tool_call` type:**
- `tool_name`: Name of the tool

### tool_result

Result from a tool execution.

```json
{
  "sequence": 4,
  "type": "tool_result",
  "emitted_at": "2025-12-28T10:00:03Z",
  "observed_at": "2025-12-28T10:00:03.050Z",
  "data": {
    "tool_use_id": "toolu_abc123",
    "success": true,
    "result": "# auth.py contents..."
  }
}
```

### session_end

Marks the end of a conversation.

```json
{
  "sequence": 50,
  "type": "session_end",
  "emitted_at": "2025-12-28T10:30:00Z",
  "observed_at": "2025-12-28T10:30:00.050Z",
  "data": {
    "outcome": "success",
    "summary": "Implemented user authentication"
  }
}
```

---

## Timestamp Semantics

Events have two required timestamps:

| Timestamp | Meaning | Who Sets It |
|-----------|---------|-------------|
| `emitted_at` | When the event occurred at source | Collector (from logs) |
| `observed_at` | When collector parsed the event | Collector |
| `server_received_at` | When server received event | Server (automatic) |

**Example flow:**
```
10:00:00.000  User types message (emitted_at)
10:00:00.050  Collector parses log (observed_at)
10:00:00.100  Server receives HTTP request (server_received_at)
```

This chain enables latency debugging and causality tracking.

---

## Sequence Numbers

### Rules

1. **Monotonic**: Start at 1, increment by 1 for each event
2. **Per-session**: Sequences are scoped to `session_id`
3. **No gaps**: Server rejects batches with gaps
4. **Idempotent**: Re-sending same sequence is ignored (not an error)

### Sequence Gap Response

If you skip sequences, you'll get a 409 Conflict:

```json
{
  "error": "sequence_gap",
  "message": "Expected sequence 3, got 5",
  "last_received_sequence": 2,
  "expected_sequence": 3
}
```

**Recovery**: Query session status and resend from `last_sequence + 1`.

---

## Session Resumption

If your collector crashes or disconnects:

### 1. Check Session Status

```bash
curl -X GET https://catsyphon.example.com/collectors/sessions/my-session-123 \
  -H "Authorization: Bearer cs_live_xxxxxxxxxxxx" \
  -H "X-Collector-ID: your-collector-id"
```

**Response:**
```json
{
  "session_id": "my-session-123",
  "conversation_id": "660e8400-e29b-41d4-a716-446655440001",
  "last_sequence": 42,
  "event_count": 42,
  "status": "active"
}
```

### 2. Resume from Last Sequence

Continue sending events from sequence 43 onward.

---

## Complete Session

When a conversation ends:

```bash
curl -X POST https://catsyphon.example.com/collectors/sessions/my-session-123/complete \
  -H "Authorization: Bearer cs_live_xxxxxxxxxxxx" \
  -H "X-Collector-ID: your-collector-id" \
  -H "Content-Type: application/json" \
  -d '{
    "final_sequence": 50,
    "outcome": "success",
    "summary": "Implemented user authentication feature"
  }'
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200/201/202 | Success | Continue |
| 400 | Bad request | Fix payload |
| 401 | Unauthorized | Check API key |
| 404 | Session not found | Start new session |
| 409 | Sequence gap | Get status, resend |
| 422 | Validation error | Fix event data |
| 429 | Rate limited | Back off |
| 500 | Server error | Retry with backoff |

### Retry Strategy

```python
def send_with_retry(events, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = post("/collectors/events", events)

            if response.status == 202:
                return response  # Success

            if response.status == 409:
                # Sequence gap - get status and resend
                status = get(f"/collectors/sessions/{session_id}")
                events = filter_events_after(status["last_sequence"])
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

## Implementation Examples

### Python

```python
import requests
from datetime import datetime, timezone

class CatSyphonCollector:
    def __init__(self, server_url: str, api_key: str, collector_id: str):
        self.server_url = server_url
        self.api_key = api_key
        self.collector_id = collector_id
        self.sequence = 0
        self.buffer = []

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Collector-ID": self.collector_id,
            "Content-Type": "application/json",
        }

    def add_message(self, session_id: str, role: str, content: str, emitted_at: datetime):
        self.sequence += 1
        observed_at = datetime.now(timezone.utc)

        self.buffer.append({
            "sequence": self.sequence,
            "type": "message",
            "emitted_at": emitted_at.isoformat(),
            "observed_at": observed_at.isoformat(),
            "data": {
                "author_role": role,
                "message_type": "prompt" if role == "human" else "response",
                "content": content,
            }
        })

        # Flush when buffer is full
        if len(self.buffer) >= 10:
            self.flush(session_id)

    def flush(self, session_id: str):
        if not self.buffer:
            return

        response = requests.post(
            f"{self.server_url}/collectors/events",
            headers=self._headers(),
            json={
                "session_id": session_id,
                "events": self.buffer,
            }
        )
        response.raise_for_status()
        self.buffer = []
        return response.json()
```

### TypeScript

```typescript
interface CollectorEvent {
  sequence: number;
  type: string;
  emitted_at: string;
  observed_at: string;
  data: Record<string, any>;
}

class CatSyphonCollector {
  private sequence = 0;
  private buffer: CollectorEvent[] = [];

  constructor(
    private serverUrl: string,
    private apiKey: string,
    private collectorId: string
  ) {}

  addMessage(sessionId: string, role: string, content: string, emittedAt: Date) {
    this.sequence++;

    this.buffer.push({
      sequence: this.sequence,
      type: 'message',
      emitted_at: emittedAt.toISOString(),
      observed_at: new Date().toISOString(),
      data: {
        author_role: role,
        message_type: role === 'human' ? 'prompt' : 'response',
        content,
      },
    });

    if (this.buffer.length >= 10) {
      return this.flush(sessionId);
    }
  }

  async flush(sessionId: string) {
    if (this.buffer.length === 0) return;

    const response = await fetch(`${this.serverUrl}/collectors/events`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'X-Collector-ID': this.collectorId,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        events: this.buffer,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to flush: ${response.status}`);
    }

    this.buffer = [];
    return response.json();
  }
}
```

---

## Best Practices

### Batching

- Send events in batches of 10-50
- Maximum 50 events per request
- Flush on session end or timeout

### Buffering

- Buffer events locally during network issues
- Persist buffer to disk for crash recovery
- Resume from last sequence on restart

### Performance

- Use connection pooling for HTTP clients
- Compress large batches with gzip
- Avoid blocking on network I/O

### Security

- Store API keys securely (keychain, env vars)
- Use HTTPS in production
- Rotate keys periodically

---

## Testing

### Mock Server

```bash
# Start CatSyphon locally
docker-compose up -d
cd backend && uv run catsyphon serve

# Register test collector
curl -X POST http://localhost:8000/collectors \
  -H "Content-Type: application/json" \
  -d '{"collector_type": "test", "collector_version": "1.0.0", "hostname": "localhost", "workspace_id": "..."}'
```

### Validation

CatSyphon validates:
- Event schema (required fields per type)
- Sequence ordering
- Timestamp format (ISO 8601)
- Batch size limits

Invalid events return 422 with details.

---

## Reference

- [Collector Protocol Specification](./collector-protocol.md) - Full protocol design
- [API Reference](./api-reference.md) - All REST endpoints
- [Parser SDK](./plugin-sdk.md) - For building log parsers (not collectors)

---

## Support

- **Issues**: https://github.com/kulesh/catsyphon/issues
- **Protocol Questions**: Tag with `collector-api`
