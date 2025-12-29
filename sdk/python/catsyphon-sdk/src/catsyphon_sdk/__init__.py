"""
CatSyphon SDK - Push AI agent conversation logs to a centralized server.

Usage:
    from catsyphon_sdk import CollectorClient, AsyncCollectorClient

    # Register a new collector (one-time setup)
    client = CollectorClient.register(
        server_url="https://catsyphon.example.com",
        workspace_id="your-workspace-uuid",
    )

    # Or use existing credentials
    client = CollectorClient(
        server_url="https://catsyphon.example.com",
        collector_id="your-collector-uuid",
        api_key="cs_live_xxx",
    )

    # Stream events for a session
    with client.session("session-123") as session:
        session.start(agent_type="my-agent")
        session.message(role="user", content="Hello")
        session.message(role="assistant", content="Hi!")
        session.complete(outcome="success")
"""

from catsyphon_sdk.batch import AsyncBatchWriter, BatchWriter
from catsyphon_sdk.client import AsyncCollectorClient, CollectorClient
from catsyphon_sdk.credentials import CredentialStore
from catsyphon_sdk.models import (
    Event,
    EventData,
    EventType,
    MessageData,
    SessionEndData,
    SessionStartData,
    ToolCallData,
    ToolResultData,
)
from catsyphon_sdk.retry import RetryConfig
from catsyphon_sdk.session import AsyncSession, Session

__version__ = "0.1.0"

__all__ = [
    # Clients
    "CollectorClient",
    "AsyncCollectorClient",
    # Sessions
    "Session",
    "AsyncSession",
    # Batch Writers
    "BatchWriter",
    "AsyncBatchWriter",
    # Credentials
    "CredentialStore",
    # Configuration
    "RetryConfig",
    # Models
    "Event",
    "EventType",
    "EventData",
    "SessionStartData",
    "SessionEndData",
    "MessageData",
    "ToolCallData",
    "ToolResultData",
]
