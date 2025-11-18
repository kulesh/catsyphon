"""
Pytest configuration and fixtures for CatSyphon tests.

This module provides shared fixtures for testing database models, repositories,
and other components.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from catsyphon.models.db import (
    Base,
    CollectorConfig,
    Conversation,
    ConversationTag,
    Developer,
    Epoch,
    FileTouched,
    IngestionJob,
    Message,
    Organization,
    Project,
    RawLog,
    WatchConfiguration,
    Workspace,
)


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine using SQLite in-memory."""
    # Use SQLite for tests (faster, no PostgreSQL required)
    # Note: SQLite uses JSON instead of JSONB, handled automatically by SQLAlchemy
    from sqlalchemy import JSON, event
    from sqlalchemy.dialects import postgresql

    # Replace JSONB with JSON for SQLite
    @event.listens_for(Base.metadata, "before_create")
    def _set_json_type(target, connection, **kw):
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, postgresql.JSONB):
                    column.type = JSON()

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={
            "check_same_thread": False
        },  # Allow cross-thread access for TestClient
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Create a new database session for a test.

    Each test gets a fresh session with a transaction that is rolled back
    after the test completes, ensuring test isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def api_client(db_session: Session):
    """Create a test client for FastAPI with database dependency override."""
    from unittest.mock import MagicMock, patch

    from fastapi.testclient import TestClient

    from catsyphon.api.app import app
    from catsyphon.db.connection import get_db

    # Override the get_db dependency to use test database
    def override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    # Mock DaemonManager for watch endpoints
    mock_daemon_manager = MagicMock()
    mock_daemon_manager.start_daemon.return_value = None
    mock_daemon_manager.stop_daemon.return_value = None
    mock_daemon_manager.get_daemon_status.return_value = {
        "is_running": True,
        "pid": 12345,
        "stats": {},
    }
    mock_daemon_manager.get_all_status.return_value = {
        "running_daemons": 0,
        "total_daemons": 0,
        "daemons": [],
    }

    # Disable lifespan startup checks for testing
    with patch("catsyphon.api.app.run_all_startup_checks"):
        client = TestClient(app)
        # Add daemon_manager to app state
        client.app.state.daemon_manager = mock_daemon_manager
        yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def sample_organization(db_session: Session) -> Organization:
    """Create a sample organization for testing."""
    organization = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        settings={"billing_plan": "enterprise"},
        is_active=True,
    )
    db_session.add(organization)
    db_session.commit()
    db_session.refresh(organization)
    return organization


@pytest.fixture
def sample_workspace(
    db_session: Session, sample_organization: Organization
) -> Workspace:
    """Create a sample workspace for testing."""
    workspace = Workspace(
        id=uuid.uuid4(),
        organization_id=sample_organization.id,
        name="Test Workspace",
        slug="test-workspace",
        settings={"retention_days": 90},
        is_active=True,
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def sample_collector(
    db_session: Session, sample_workspace: Workspace
) -> CollectorConfig:
    """Create a sample collector for testing."""
    collector = CollectorConfig(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        name="Test Collector",
        collector_type="python-sdk",
        api_key_hash="$2b$12$hashed_key_here",  # bcrypt hash
        api_key_prefix="cs_test123",
        is_active=True,
        version="1.0.0",
        hostname="test-machine.local",
        extra_data={"os": "macOS", "python_version": "3.11"},
        total_uploads=0,
        total_conversations=0,
    )
    db_session.add(collector)
    db_session.commit()
    db_session.refresh(collector)
    return collector


@pytest.fixture
def sample_project(db_session: Session, sample_workspace: Workspace) -> Project:
    """Create a sample project for testing."""
    project = Project(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        name="Test Project",
        directory_path="/Users/test/catsyphon",
        description="A test project for CatSyphon",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_developer(db_session: Session, sample_workspace: Workspace) -> Developer:
    """Create a sample developer for testing."""
    developer = Developer(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        username="test_developer",
        email="test@example.com",
        extra_data={"team": "engineering"},
    )
    db_session.add(developer)
    db_session.commit()
    db_session.refresh(developer)
    return developer


@pytest.fixture
def sample_conversation(
    db_session: Session,
    sample_workspace: Workspace,
    sample_project: Project,
    sample_developer: Developer,
) -> Conversation:
    """Create a sample conversation for testing."""
    conversation = Conversation(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        project_id=sample_project.id,
        developer_id=sample_developer.id,
        agent_type="claude-code",
        agent_version="1.0.0",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(minutes=10),
        status="completed",
        success=True,
        iteration_count=3,
        tags={"feature": "authentication"},
        extra_data={"session_id": "test-session-123"},
        # Initialize denormalized counts
        message_count=0,
        epoch_count=0,
        files_count=0,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


@pytest.fixture
def sample_epoch(db_session: Session, sample_conversation: Conversation) -> Epoch:
    """Create a sample epoch for testing."""
    epoch = Epoch(
        id=uuid.uuid4(),
        conversation_id=sample_conversation.id,
        sequence=1,
        intent="feature_add",
        outcome="success",
        sentiment="positive",
        sentiment_score=0.8,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(minutes=5),
        duration_seconds=300,
        extra_data={"complexity": "medium"},
    )
    db_session.add(epoch)
    # Update denormalized epoch count
    sample_conversation.epoch_count += 1
    db_session.commit()
    db_session.refresh(epoch)
    return epoch


@pytest.fixture
def sample_message(
    db_session: Session, sample_conversation: Conversation, sample_epoch: Epoch
) -> Message:
    """Create a sample message for testing."""
    message = Message(
        id=uuid.uuid4(),
        epoch_id=sample_epoch.id,
        conversation_id=sample_conversation.id,
        role="user",
        content="Please implement user authentication",
        timestamp=datetime.now(UTC),
        sequence=1,
        tool_calls=[{"tool": "Write", "file": "auth.py"}],
        tool_results=[{"success": True}],
        code_changes=[
            {"file_path": "auth.py", "change_type": "create", "lines_added": 50}
        ],
        entities={"files": ["auth.py"], "technologies": ["Python", "FastAPI"]},
    )
    db_session.add(message)
    # Update denormalized message count
    sample_conversation.message_count += 1
    db_session.commit()
    db_session.refresh(message)
    return message


@pytest.fixture
def sample_file_touched(
    db_session: Session,
    sample_conversation: Conversation,
    sample_epoch: Epoch,
    sample_message: Message,
) -> FileTouched:
    """Create a sample file touched record for testing."""
    file_touched = FileTouched(
        id=uuid.uuid4(),
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        message_id=sample_message.id,
        file_path="src/auth.py",
        change_type="created",
        lines_added=50,
        lines_deleted=0,
        lines_modified=0,
        timestamp=datetime.now(UTC),
        extra_data={"language": "python"},
    )
    db_session.add(file_touched)
    db_session.commit()
    db_session.refresh(file_touched)
    return file_touched


@pytest.fixture
def sample_conversation_tag(
    db_session: Session, sample_conversation: Conversation
) -> ConversationTag:
    """Create a sample conversation tag for testing."""
    tag = ConversationTag(
        id=uuid.uuid4(),
        conversation_id=sample_conversation.id,
        tag_type="technology",
        tag_value="FastAPI",
        confidence=0.95,
        extra_data={"source": "llm_tagger"},
    )
    db_session.add(tag)
    db_session.commit()
    db_session.refresh(tag)
    return tag


@pytest.fixture
def sample_raw_log(db_session: Session, sample_conversation: Conversation) -> RawLog:
    """Create a sample raw log for testing."""
    from catsyphon.utils.hashing import calculate_content_hash

    raw_content = '{"messages": [{"role": "user", "content": "test"}]}'
    raw_log = RawLog(
        id=uuid.uuid4(),
        conversation_id=sample_conversation.id,
        agent_type="claude-code",
        log_format="json",
        raw_content=raw_content,
        file_path="/path/to/log.json",
        file_hash=calculate_content_hash(raw_content),
        extra_data={"size_bytes": 1024},
    )
    db_session.add(raw_log)
    db_session.commit()
    db_session.refresh(raw_log)
    return raw_log


@pytest.fixture
def watch_config(
    db_session: Session,
    sample_workspace: Workspace,
    sample_project: Project,
    sample_developer: Developer,
) -> WatchConfiguration:
    """Create a sample watch configuration (inactive) for testing."""
    config = WatchConfiguration(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        directory="/Users/test/.claude/projects",
        project_id=sample_project.id,
        developer_id=sample_developer.id,
        enable_tagging=False,
        is_active=False,
        stats={"files_processed": 0, "files_skipped": 0},
        extra_config={"poll_interval": 2, "retry_interval": 300},
        created_by="test_user",
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture
def active_watch_config(
    db_session: Session, sample_workspace: Workspace, sample_project: Project
) -> WatchConfiguration:
    """Create an active watch configuration for testing."""
    config = WatchConfiguration(
        id=uuid.uuid4(),
        workspace_id=sample_workspace.id,
        directory="/Users/test/.claude/active",
        project_id=sample_project.id,
        developer_id=None,
        enable_tagging=True,
        is_active=True,
        stats={"files_processed": 5, "files_skipped": 2},
        extra_config={"poll_interval": 5},
        created_by="test_user",
        last_started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture
def ingestion_job_success(
    db_session: Session,
    sample_conversation: Conversation,
    sample_raw_log: RawLog,
    watch_config: WatchConfiguration,
) -> IngestionJob:
    """Create a successful ingestion job for testing."""
    job = IngestionJob(
        id=uuid.uuid4(),
        source_type="watch",
        source_config_id=watch_config.id,
        file_path="/path/to/conversation.jsonl",
        raw_log_id=sample_raw_log.id,
        conversation_id=sample_conversation.id,
        status="success",
        error_message=None,
        processing_time_ms=1500,
        incremental=False,
        messages_added=10,
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        completed_at=datetime.now(UTC) - timedelta(minutes=4, seconds=30),
        created_by="watch_daemon",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def ingestion_job_failed(
    db_session: Session, watch_config: WatchConfiguration
) -> IngestionJob:
    """Create a failed ingestion job for testing."""
    job = IngestionJob(
        id=uuid.uuid4(),
        source_type="watch",
        source_config_id=watch_config.id,
        file_path="/path/to/invalid.jsonl",
        raw_log_id=None,
        conversation_id=None,
        status="failed",
        error_message="Invalid JSON format in log file",
        processing_time_ms=200,
        incremental=False,
        messages_added=0,
        started_at=datetime.now(UTC) - timedelta(minutes=10),
        completed_at=datetime.now(UTC) - timedelta(minutes=9, seconds=59),
        created_by="watch_daemon",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def ingestion_job_upload(
    db_session: Session,
    sample_conversation: Conversation,
    sample_raw_log: RawLog,
) -> IngestionJob:
    """Create an upload-based ingestion job for testing."""
    job = IngestionJob(
        id=uuid.uuid4(),
        source_type="upload",
        source_config_id=None,
        file_path="/tmp/upload/conversation.jsonl",
        raw_log_id=sample_raw_log.id,
        conversation_id=sample_conversation.id,
        status="success",
        error_message=None,
        processing_time_ms=2000,
        incremental=False,
        messages_added=15,
        started_at=datetime.now(UTC) - timedelta(hours=2),
        completed_at=datetime.now(UTC) - timedelta(hours=2, seconds=-2),
        created_by="web_user@example.com",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture(autouse=True)
def use_polling_observer_for_tests(monkeypatch):
    """
    Use PollingObserver instead of FSEventsObserver in all tests.

    This avoids fsevents C extension crashes during rapid observer
    start/stop cycles in tests. See bug catsyphon-7ri.

    The fsevents observer has thread safety issues that cause
    "Fatal Python error: Bus error" on macOS during test runs.
    """
    from watchdog.observers.polling import PollingObserver

    from catsyphon import watch

    # Monkey-patch Observer to use PollingObserver
    monkeypatch.setattr(watch, "Observer", PollingObserver)


@pytest.fixture
def mock_observer():
    """
    Create a mock Observer for fast unit tests.

    Use this for tests that only need daemon lifecycle management,
    not actual file watching behavior. This makes tests ~10x faster
    by eliminating real filesystem I/O.

    Example:
        def test_start_daemon(watch_config, mock_observer):
            manager = DaemonManager()
            with patch('catsyphon.watch.Observer', return_value=mock_observer):
                manager.start_daemon(watch_config)
            # No time.sleep needed - instant with mock!
    """
    from unittest.mock import Mock

    mock_obs = Mock(
        spec=["start", "stop", "join", "is_alive", "schedule", "unschedule"]
    )
    mock_obs.is_alive.return_value = True
    mock_obs.start.return_value = None
    mock_obs.stop.return_value = None
    mock_obs.join.return_value = None
    mock_obs.schedule.return_value = None
    mock_obs.unschedule.return_value = None
    return mock_obs


@pytest.fixture
def mock_openai_api_key(monkeypatch):
    """
    Mock OpenAI API key for tagging tests.

    Sets a fake API key and mocks the OpenAI client to avoid actual API calls.
    This allows testing the tagging endpoint without making real OpenAI requests.
    """
    from unittest.mock import Mock

    from catsyphon.config import settings

    # Set fake API key
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-test-key-12345")

    # Mock the OpenAI client to avoid real API calls
    mock_client = Mock()
    mock_completion = Mock()
    mock_completion.choices = [
        Mock(
            message=Mock(
                content='{"intent": "bug_fix", "outcome": "success", '
                '"sentiment": "positive", "sentiment_score": 0.8, '
                '"features": ["debugging"], "problems": []}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_completion

    # Patch the OpenAI class to return our mock
    from unittest.mock import patch

    with patch("catsyphon.tagging.llm_tagger.OpenAI", return_value=mock_client):
        yield
