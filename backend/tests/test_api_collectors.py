"""
Tests for the Collector Events API.

Tests the collector events protocol:
- POST /collectors - Register collector
- POST /collectors/events - Submit events
- GET /collectors/sessions/{session_id} - Get session status
- POST /collectors/sessions/{session_id}/complete - Complete session
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from catsyphon.api.app import app
from catsyphon.api.routes.collectors import generate_api_key, verify_api_key
from catsyphon.db.repositories import CollectorRepository


@pytest.fixture
def client():
    """Test client for the API."""
    return TestClient(app)


@pytest.fixture
def workspace_with_collector(db_session, sample_workspace):
    """Create a workspace with a registered collector."""
    # Generate API key
    api_key, api_key_prefix, api_key_hash = generate_api_key()

    # Create collector
    collector_repo = CollectorRepository(db_session)
    collector = collector_repo.create(
        name="test-collector@localhost",
        collector_type="watcher",
        workspace_id=sample_workspace.id,
        api_key_hash=api_key_hash,
        api_key_prefix=api_key_prefix,
        is_active=True,
        extra_data={"collector_version": "1.0.0", "hostname": "localhost"},
    )
    db_session.commit()

    return {
        "workspace": sample_workspace,
        "collector": collector,
        "api_key": api_key,
        "api_key_prefix": api_key_prefix,
    }


class TestApiKeyGeneration:
    """Tests for API key generation and verification."""

    def test_generate_api_key_format(self):
        """Test that generated API keys have correct format."""
        api_key, prefix, key_hash = generate_api_key()

        assert api_key.startswith("cs_live_")
        assert prefix.startswith("cs_live_")
        assert len(prefix) == 12  # "cs_live_" + 4 chars
        assert len(key_hash) == 64  # SHA-256 hex digest

    def test_verify_api_key_valid(self):
        """Test that valid API keys verify correctly."""
        api_key, _, key_hash = generate_api_key()

        assert verify_api_key(api_key, key_hash) is True

    def test_verify_api_key_invalid(self):
        """Test that invalid API keys fail verification."""
        _, _, key_hash = generate_api_key()

        assert verify_api_key("wrong_key", key_hash) is False
        assert verify_api_key("cs_live_wrong", key_hash) is False


class TestCollectorRegistration:
    """Tests for POST /collectors endpoint."""

    def test_register_collector_success(self, client, db_session, sample_workspace):
        """Test successful collector registration."""
        response = client.post(
            "/collectors",
            json={
                "collector_type": "aiobscura",
                "collector_version": "1.0.0",
                "hostname": "dev-machine.local",
                "workspace_id": str(sample_workspace.id),
                "metadata": {"os": "macOS", "user": "dev@example.com"},
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert "collector_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("cs_live_")
        assert "api_key_prefix" in data
        assert "created_at" in data

    def test_register_collector_invalid_workspace(self, client):
        """Test registration with non-existent workspace."""
        fake_workspace_id = str(uuid.uuid4())
        response = client.post(
            "/collectors",
            json={
                "collector_type": "watcher",
                "collector_version": "1.0.0",
                "hostname": "localhost",
                "workspace_id": fake_workspace_id,
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestEventSubmission:
    """Tests for POST /collectors/events endpoint."""

    def test_submit_events_success(self, client, db_session, workspace_with_collector):
        """Test successful event submission."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        events = [
            {
                "sequence": 1,
                "type": "session_start",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "agent_type": "claude-code",
                    "agent_version": "1.0.45",
                    "working_directory": "/Users/dev/project",
                },
            },
            {
                "sequence": 2,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": "Help me implement authentication",
                },
            },
            {
                "sequence": 3,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "assistant",
                    "message_type": "response",
                    "content": "I'll help you implement authentication...",
                    "model": "claude-sonnet-4-20250514",
                },
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 202
        data = response.json()

        assert data["accepted"] == 3
        assert data["last_sequence"] == 3
        assert "conversation_id" in data
        assert data["warnings"] == []

    def test_submit_events_unauthorized(self, client, workspace_with_collector):
        """Test event submission with invalid API key."""
        collector = workspace_with_collector["collector"]

        response = client.post(
            "/collectors/events",
            json={
                "session_id": "test-session",
                "events": [
                    {
                        "sequence": 1,
                        "type": "session_start",
                        "emitted_at": datetime.now(timezone.utc).isoformat(),
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "data": {"agent_type": "test"},
                    }
                ],
            },
            headers={
                "Authorization": "Bearer wrong_key",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 401

    def test_submit_events_no_sequence_gap_check(
        self, client, db_session, workspace_with_collector
    ):
        """Test that events are accepted regardless of sequence order (content-based dedup)."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        # First, submit initial events
        first_batch = [
            {
                "type": "session_start",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {"agent_type": "claude-code"},
            },
            {
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": "Hello",
                },
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": first_batch},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )
        assert response.status_code == 202

        # Submit more events - no sequence gap error anymore
        more_events = [
            {
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "assistant",
                    "message_type": "response",
                    "content": "Response",
                },
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": more_events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        # Content-based dedup means no sequence validation - events accepted
        assert response.status_code == 202
        assert response.json()["accepted"] == 1

    def test_submit_events_deduplication(
        self, client, db_session, workspace_with_collector
    ):
        """Test that duplicate message events are ignored via content-based hashing."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        # Use fixed timestamp for deterministic content-based hashing
        fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()

        # First, create the session with a session_start event
        setup_events = [
            {
                "type": "session_start",
                "emitted_at": fixed_time,
                "observed_at": fixed_time,
                "data": {"agent_type": "claude-code"},
            },
        ]
        response_setup = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": setup_events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )
        assert response_setup.status_code == 202

        # Now submit a message event (which gets stored and can be deduplicated)
        message_events = [
            {
                "type": "message",
                "emitted_at": fixed_time,
                "observed_at": fixed_time,
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": "Test message for deduplication",
                },
            },
        ]

        # Submit first time
        response1 = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": message_events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )
        assert response1.status_code == 202
        assert response1.json()["accepted"] == 1

        # Submit same message events again - content hash should match
        response2 = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": message_events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )
        assert response2.status_code == 202
        assert response2.json()["accepted"] == 0  # Duplicate detected by content hash


class TestSessionStatus:
    """Tests for GET /collectors/sessions/{session_id} endpoint."""

    def test_get_session_status_success(
        self, client, db_session, workspace_with_collector
    ):
        """Test getting session status."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        # First submit some events
        events = [
            {
                "sequence": 1,
                "type": "session_start",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {"agent_type": "claude-code"},
            },
            {
                "sequence": 2,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": "Hello",
                },
            },
        ]

        client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        # Get status
        response = client.get(
            f"/collectors/sessions/{session_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == session_id
        assert data["last_sequence"] == 2
        assert data["status"] == "active"
        assert "conversation_id" in data

    def test_get_session_status_not_found(self, client, workspace_with_collector):
        """Test getting status for non-existent session."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]

        response = client.get(
            "/collectors/sessions/nonexistent-session",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 404


class TestSessionCompletion:
    """Tests for POST /collectors/sessions/{session_id}/complete endpoint."""

    def test_complete_session_success(
        self, client, db_session, workspace_with_collector
    ):
        """Test completing a session."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        # First submit some events
        events = [
            {
                "sequence": 1,
                "type": "session_start",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {"agent_type": "claude-code"},
            },
            {
                "sequence": 2,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": "Hello",
                },
            },
        ]

        client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        # Complete the session
        response = client.post(
            f"/collectors/sessions/{session_id}/complete",
            json={
                "final_sequence": 2,
                "outcome": "success",
                "summary": "Test session completed",
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == session_id
        assert data["status"] == "completed"

        # Verify status shows completed
        status_response = client.get(
            f"/collectors/sessions/{session_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )
        assert status_response.json()["status"] == "completed"


class TestEventValidation:
    """Tests for event validation."""

    def test_message_event_requires_author_role(self, client, workspace_with_collector):
        """Test that message events require author_role."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        events = [
            {
                "sequence": 1,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    # Missing author_role
                    "message_type": "prompt",
                    "content": "Hello",
                },
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 422  # Validation error

    def test_tool_call_event_requires_tool_name(self, client, workspace_with_collector):
        """Test that tool_call events require tool_name."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        events = [
            {
                "sequence": 1,
                "type": "tool_call",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    # Missing tool_name
                    "tool_use_id": "toolu_123",
                    "parameters": {},
                },
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 422  # Validation error

    def test_batch_size_limit(self, client, workspace_with_collector):
        """Test that batch size is limited to 50 events."""
        collector = workspace_with_collector["collector"]
        api_key = workspace_with_collector["api_key"]
        session_id = f"test-session-{uuid.uuid4()}"

        # Create 51 events (exceeds limit)
        events = [
            {
                "sequence": i + 1,
                "type": "message",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "author_role": "human",
                    "message_type": "prompt",
                    "content": f"Message {i}",
                },
            }
            for i in range(51)
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Collector-ID": str(collector.id),
            },
        )

        assert response.status_code == 422  # Validation error


class TestBuiltinCredentials:
    """Tests for GET /collectors/builtin/credentials endpoint."""

    def test_get_builtin_credentials_creates_new(
        self, client, db_session, sample_workspace
    ):
        """Test getting builtin credentials creates new collector if none exists."""
        response = client.get(
            "/collectors/builtin/credentials",
            params={"workspace_id": str(sample_workspace.id)},
        )

        assert response.status_code == 200
        data = response.json()

        # Should return valid credentials
        assert "collector_id" in data
        assert "api_key" in data
        assert "api_key_prefix" in data
        assert "created_at" in data

        # API key should have correct format
        assert data["api_key"].startswith("cs_live_")
        assert data["api_key_prefix"].startswith("cs_live_")

        # Verify the collector was created in DB
        collector_repo = CollectorRepository(db_session)
        builtin = collector_repo.get_builtin(sample_workspace.id)
        assert builtin is not None
        assert builtin.is_builtin is True
        assert str(builtin.id) == data["collector_id"]

    def test_get_builtin_credentials_returns_existing(
        self, client, db_session, sample_workspace
    ):
        """Test getting builtin credentials returns existing collector."""
        # First call creates the builtin
        response1 = client.get(
            "/collectors/builtin/credentials",
            params={"workspace_id": str(sample_workspace.id)},
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Second call should return same collector
        response2 = client.get(
            "/collectors/builtin/credentials",
            params={"workspace_id": str(sample_workspace.id)},
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Same collector_id and api_key
        assert data1["collector_id"] == data2["collector_id"]
        assert data1["api_key"] == data2["api_key"]

    def test_get_builtin_credentials_invalid_workspace(self, client):
        """Test getting builtin credentials with invalid workspace returns 404."""
        response = client.get(
            "/collectors/builtin/credentials",
            params={"workspace_id": str(uuid.uuid4())},  # Non-existent
        )

        assert response.status_code == 404
        assert "Workspace" in response.json()["detail"]

    def test_builtin_credentials_can_authenticate(
        self, client, db_session, sample_workspace
    ):
        """Test that builtin credentials can be used to authenticate API calls."""
        # Get builtin credentials
        creds_response = client.get(
            "/collectors/builtin/credentials",
            params={"workspace_id": str(sample_workspace.id)},
        )
        assert creds_response.status_code == 200
        creds = creds_response.json()

        # Use credentials to submit events
        session_id = f"test-builtin-{uuid.uuid4()}"
        events = [
            {
                "sequence": 1,
                "type": "session_start",
                "emitted_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "data": {"agent_type": "claude-code"},
            },
        ]

        response = client.post(
            "/collectors/events",
            json={"session_id": session_id, "events": events},
            headers={
                "Authorization": f"Bearer {creds['api_key']}",
                "X-Collector-ID": creds["collector_id"],
            },
        )

        # Should successfully authenticate and accept events
        assert response.status_code == 202
        assert response.json()["accepted"] == 1
