"""
Collector client implementations for CatSyphon SDK.

Provides both synchronous and asynchronous clients for interacting
with the CatSyphon Collector API.
"""

import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx

from catsyphon_sdk.credentials import CredentialStore
from catsyphon_sdk.models import (
    Event,
    EventsResponse,
    RegisterResponse,
    SessionCompleteResponse,
    SessionStatusResponse,
)
from catsyphon_sdk.retry import (
    NonRetryableError,
    RetryableError,
    RetryConfig,
    check_response,
)

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """Configuration for the collector client."""

    server_url: str
    collector_id: str
    api_key: str
    timeout: float = 30.0
    batch_size: int = 20
    retry_config: RetryConfig = field(default_factory=RetryConfig)


class CollectorClient:
    """
    Synchronous HTTP client for the CatSyphon Collector API.

    Usage:
        # Register a new collector
        client = CollectorClient.register(
            server_url="https://catsyphon.example.com",
            workspace_id="uuid-here",
        )

        # Or use existing credentials
        client = CollectorClient(
            server_url="https://catsyphon.example.com",
            collector_id="uuid",
            api_key="cs_live_xxx",
        )

        # Use with session context manager
        with client.session("my-session") as session:
            session.start(agent_type="my-agent")
            session.message(role="user", content="Hello")
            session.complete(outcome="success")
    """

    def __init__(
        self,
        server_url: str,
        collector_id: str,
        api_key: str,
        timeout: float = 30.0,
        batch_size: int = 20,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize the collector client.

        Args:
            server_url: Base URL of the CatSyphon server
            collector_id: Collector UUID
            api_key: API key for authentication
            timeout: Request timeout in seconds
            batch_size: Maximum events per batch
            retry_config: Retry configuration
        """
        self.config = ClientConfig(
            server_url=server_url.rstrip("/"),
            collector_id=collector_id,
            api_key=api_key,
            timeout=timeout,
            batch_size=batch_size,
            retry_config=retry_config or RetryConfig(),
        )
        self._client: Optional[httpx.Client] = None

    @classmethod
    def register(
        cls,
        server_url: str,
        workspace_id: str,
        collector_type: str = "sdk",
        collector_version: str = "0.1.0",
        hostname: Optional[str] = None,
        store_credentials: bool = True,
        profile: str = "default",
        timeout: float = 30.0,
    ) -> "CollectorClient":
        """
        Register a new collector and return a configured client.

        Args:
            server_url: Base URL of the CatSyphon server
            workspace_id: Workspace UUID to register with
            collector_type: Type of collector (e.g., 'sdk', 'agent')
            collector_version: Version string
            hostname: Hostname (defaults to current machine)
            store_credentials: Whether to save credentials to disk
            profile: Credential profile name
            timeout: Request timeout

        Returns:
            Configured CollectorClient instance

        Raises:
            NonRetryableError: If registration fails
        """
        server_url = server_url.rstrip("/")
        hostname = hostname or socket.gethostname()

        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{server_url}/collectors",
                json={
                    "collector_type": collector_type,
                    "collector_version": collector_version,
                    "hostname": hostname,
                    "workspace_id": workspace_id,
                },
            )

            if not response.is_success:
                raise NonRetryableError(
                    f"Registration failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                )

            data = RegisterResponse.model_validate(response.json())

        logger.info(
            f"Registered collector {data.collector_id} ({data.api_key_prefix}...)"
        )

        # Store credentials if requested
        if store_credentials:
            store = CredentialStore()
            store.store(
                server_url=server_url,
                workspace_id=workspace_id,
                collector_id=str(data.collector_id),
                api_key=data.api_key,
                api_key_prefix=data.api_key_prefix,
                profile=profile,
            )

        return cls(
            server_url=server_url,
            collector_id=str(data.collector_id),
            api_key=data.api_key,
            timeout=timeout,
        )

    @classmethod
    def from_stored(
        cls,
        server_url: str,
        workspace_id: str,
        profile: str = "default",
        timeout: float = 30.0,
    ) -> Optional["CollectorClient"]:
        """
        Create a client from stored credentials.

        Args:
            server_url: CatSyphon server URL
            workspace_id: Workspace UUID
            profile: Credential profile name
            timeout: Request timeout

        Returns:
            CollectorClient if credentials found, None otherwise
        """
        store = CredentialStore()
        cred = store.get(server_url, workspace_id, profile)

        if cred is None:
            return None

        return cls(
            server_url=cred.server_url,
            collector_id=cred.collector_id,
            api_key=cred.api_key,
            timeout=timeout,
        )

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.server_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "X-Collector-ID": self.config.collector_id,
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "CollectorClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def send_events(
        self,
        session_id: str,
        events: list[Event],
    ) -> EventsResponse:
        """
        Send a batch of events for a session.

        Args:
            session_id: Unique session identifier
            events: List of events to send

        Returns:
            EventsResponse with acceptance info

        Raises:
            RetryableError: On transient failures
            NonRetryableError: On permanent failures
        """
        # Convert events to JSON-safe dicts
        events_data = [e.model_dump_json_safe() for e in events]

        response = self.client.post(
            "/collectors/events",
            json={
                "session_id": session_id,
                "events": events_data,
            },
        )

        check_response(response, self.config.retry_config)
        return EventsResponse.model_validate(response.json())

    def get_session_status(self, session_id: str) -> Optional[SessionStatusResponse]:
        """
        Get the status of a session.

        Args:
            session_id: Session identifier

        Returns:
            SessionStatusResponse if found, None otherwise
        """
        response = self.client.get(f"/collectors/sessions/{session_id}")

        if response.status_code == 404:
            return None

        check_response(response, self.config.retry_config)
        return SessionStatusResponse.model_validate(response.json())

    def complete_session(
        self,
        session_id: str,
        final_sequence: int,
        outcome: str = "success",
        summary: Optional[str] = None,
    ) -> SessionCompleteResponse:
        """
        Mark a session as completed.

        Args:
            session_id: Session identifier
            final_sequence: Expected final sequence number
            outcome: Session outcome
            summary: Optional summary text

        Returns:
            SessionCompleteResponse
        """
        response = self.client.post(
            f"/collectors/sessions/{session_id}/complete",
            json={
                "final_sequence": final_sequence,
                "outcome": outcome,
                "summary": summary,
            },
        )

        check_response(response, self.config.retry_config)
        return SessionCompleteResponse.model_validate(response.json())

    def session(self, session_id: str) -> "Session":
        """
        Create a session context manager.

        Args:
            session_id: Unique session identifier

        Returns:
            Session context manager
        """
        from catsyphon_sdk.session import Session

        return Session(self, session_id)


class AsyncCollectorClient:
    """
    Asynchronous HTTP client for the CatSyphon Collector API.

    Usage:
        # Register a new collector
        client = await AsyncCollectorClient.register(
            server_url="https://catsyphon.example.com",
            workspace_id="uuid-here",
        )

        # Use with async session context manager
        async with client.session("my-session") as session:
            await session.start(agent_type="my-agent")
            await session.message(role="user", content="Hello")
            await session.complete(outcome="success")
    """

    def __init__(
        self,
        server_url: str,
        collector_id: str,
        api_key: str,
        timeout: float = 30.0,
        batch_size: int = 20,
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize the async collector client."""
        self.config = ClientConfig(
            server_url=server_url.rstrip("/"),
            collector_id=collector_id,
            api_key=api_key,
            timeout=timeout,
            batch_size=batch_size,
            retry_config=retry_config or RetryConfig(),
        )
        self._client: Optional[httpx.AsyncClient] = None

    @classmethod
    async def register(
        cls,
        server_url: str,
        workspace_id: str,
        collector_type: str = "sdk",
        collector_version: str = "0.1.0",
        hostname: Optional[str] = None,
        store_credentials: bool = True,
        profile: str = "default",
        timeout: float = 30.0,
    ) -> "AsyncCollectorClient":
        """Register a new collector and return a configured async client."""
        server_url = server_url.rstrip("/")
        hostname = hostname or socket.gethostname()

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{server_url}/collectors",
                json={
                    "collector_type": collector_type,
                    "collector_version": collector_version,
                    "hostname": hostname,
                    "workspace_id": workspace_id,
                },
            )

            if not response.is_success:
                raise NonRetryableError(
                    f"Registration failed: {response.status_code} {response.text}",
                    status_code=response.status_code,
                )

            data = RegisterResponse.model_validate(response.json())

        logger.info(
            f"Registered collector {data.collector_id} ({data.api_key_prefix}...)"
        )

        if store_credentials:
            store = CredentialStore()
            store.store(
                server_url=server_url,
                workspace_id=workspace_id,
                collector_id=str(data.collector_id),
                api_key=data.api_key,
                api_key_prefix=data.api_key_prefix,
                profile=profile,
            )

        return cls(
            server_url=server_url,
            collector_id=str(data.collector_id),
            api_key=data.api_key,
            timeout=timeout,
        )

    @classmethod
    def from_stored(
        cls,
        server_url: str,
        workspace_id: str,
        profile: str = "default",
        timeout: float = 30.0,
    ) -> Optional["AsyncCollectorClient"]:
        """Create an async client from stored credentials."""
        store = CredentialStore()
        cred = store.get(server_url, workspace_id, profile)

        if cred is None:
            return None

        return cls(
            server_url=cred.server_url,
            collector_id=cred.collector_id,
            api_key=cred.api_key,
            timeout=timeout,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.server_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "X-Collector-ID": self.config.collector_id,
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncCollectorClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def send_events(
        self,
        session_id: str,
        events: list[Event],
    ) -> EventsResponse:
        """Send a batch of events for a session."""
        events_data = [e.model_dump_json_safe() for e in events]

        response = await self.client.post(
            "/collectors/events",
            json={
                "session_id": session_id,
                "events": events_data,
            },
        )

        check_response(response, self.config.retry_config)
        return EventsResponse.model_validate(response.json())

    async def get_session_status(
        self, session_id: str
    ) -> Optional[SessionStatusResponse]:
        """Get the status of a session."""
        response = await self.client.get(f"/collectors/sessions/{session_id}")

        if response.status_code == 404:
            return None

        check_response(response, self.config.retry_config)
        return SessionStatusResponse.model_validate(response.json())

    async def complete_session(
        self,
        session_id: str,
        final_sequence: int,
        outcome: str = "success",
        summary: Optional[str] = None,
    ) -> SessionCompleteResponse:
        """Mark a session as completed."""
        response = await self.client.post(
            f"/collectors/sessions/{session_id}/complete",
            json={
                "final_sequence": final_sequence,
                "outcome": outcome,
                "summary": summary,
            },
        )

        check_response(response, self.config.retry_config)
        return SessionCompleteResponse.model_validate(response.json())

    def session(self, session_id: str) -> "AsyncSession":
        """Create an async session context manager."""
        from catsyphon_sdk.session import AsyncSession

        return AsyncSession(self, session_id)
