# CatSyphon SDK

Python SDK for pushing AI agent conversation logs to a [CatSyphon](https://github.com/kulesh/catsyphon) server.

## Installation

```bash
pip install catsyphon-sdk
```

## Quick Start

### 1. Register a Collector (One-time Setup)

```python
from catsyphon_sdk import CollectorClient

# Register with your CatSyphon server
client = CollectorClient.register(
    server_url="https://catsyphon.example.com",
    workspace_id="your-workspace-uuid",
    collector_type="my-agent",
)
# Credentials are automatically saved to ~/.catsyphon/credentials.json
```

### 2. Use the Client

```python
from catsyphon_sdk import CollectorClient

# Load from stored credentials
client = CollectorClient.from_stored(
    server_url="https://catsyphon.example.com",
    workspace_id="your-workspace-uuid",
)

# Or create directly with credentials
client = CollectorClient(
    server_url="https://catsyphon.example.com",
    collector_id="your-collector-uuid",
    api_key="cs_live_xxx",
)
```

### 3. Stream Events with Session API

The Session API provides a high-level interface for logging agent conversations:

```python
with client.session("unique-session-id") as session:
    # Start the session
    session.start(
        agent_type="my-agent",
        working_directory="/path/to/project",
        git_branch="main",
    )

    # Log messages
    session.message(role="user", content="Fix the login bug")
    session.message(role="assistant", content="I'll investigate the auth module...")

    # Log tool usage
    tool_id = session.tool_call(
        name="Read",
        parameters={"file_path": "/src/auth.py"}
    )
    session.tool_result(
        tool_use_id=tool_id,
        success=True,
        result="def login(user, password):..."
    )

    # Complete the session
    session.complete(outcome="success", summary="Fixed login validation")
```

## Async Support

```python
from catsyphon_sdk import AsyncCollectorClient

async def main():
    client = await AsyncCollectorClient.register(
        server_url="https://catsyphon.example.com",
        workspace_id="your-workspace-uuid",
    )

    async with client.session("session-123") as session:
        await session.start(agent_type="my-agent")
        await session.message(role="user", content="Hello")
        await session.message(role="assistant", content="Hi there!")
        await session.complete(outcome="success")
```

## Batch Writer

For more control over batching, use the BatchWriter:

```python
from catsyphon_sdk import BatchWriter, Event, EventType

with BatchWriter(client, "session-123", batch_size=10, flush_interval=5.0) as writer:
    # Add events - auto-flushes every 10 events or 5 seconds
    writer.add_raw(
        event_type=EventType.MESSAGE,
        data={"author_role": "human", "message_type": "prompt", "content": "Hello"}
    )
    # Explicitly flush if needed
    writer.flush()
```

## Configuration

### Retry Behavior

```python
from catsyphon_sdk import CollectorClient, RetryConfig

client = CollectorClient(
    server_url="...",
    collector_id="...",
    api_key="...",
    retry_config=RetryConfig(
        max_retries=5,
        initial_delay=0.5,
        max_delay=30.0,
        exponential_base=2.0,
    ),
)
```

### Credential Storage

Credentials are stored in `~/.catsyphon/credentials.json` with secure file permissions (600). You can manage them programmatically:

```python
from catsyphon_sdk import CredentialStore

store = CredentialStore()

# List all profiles
for cred in store.list_profiles():
    print(f"{cred.profile}: {cred.api_key_prefix}...")

# Delete a profile
store.delete(server_url, workspace_id, profile="default")
```

## Event Types

| Event Type | Description |
|------------|-------------|
| `session_start` | Session initialization with agent info |
| `session_end` | Session completion with outcome |
| `message` | User/assistant messages |
| `tool_call` | Tool invocation |
| `tool_result` | Tool response |
| `thinking` | Extended thinking content |
| `error` | Error events |

## API Reference

### CollectorClient

| Method | Description |
|--------|-------------|
| `register()` | Register a new collector |
| `from_stored()` | Load from stored credentials |
| `session(id)` | Create a session context manager |
| `send_events()` | Send raw event batch |
| `get_session_status()` | Check session status |
| `complete_session()` | Mark session complete |

### Session

| Method | Description |
|--------|-------------|
| `start()` | Start the session |
| `message()` | Add a message event |
| `tool_call()` | Add a tool call event |
| `tool_result()` | Add a tool result event |
| `thinking()` | Add thinking content |
| `error()` | Add an error event |
| `complete()` | Complete the session |
| `flush()` | Manually flush pending events |

## License

MIT
