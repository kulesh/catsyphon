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
    Conversation,
    ConversationTag,
    Developer,
    Epoch,
    FileTouched,
    Message,
    Project,
    RawLog,
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
    from unittest.mock import patch

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

    # Disable lifespan startup checks for testing
    with patch("catsyphon.api.app.run_all_startup_checks"):
        client = TestClient(app)
        yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def sample_project(db_session: Session) -> Project:
    """Create a sample project for testing."""
    project = Project(
        id=uuid.uuid4(),
        name="Test Project",
        description="A test project for CatSyphon",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_developer(db_session: Session) -> Developer:
    """Create a sample developer for testing."""
    developer = Developer(
        id=uuid.uuid4(),
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
    db_session: Session, sample_project: Project, sample_developer: Developer
) -> Conversation:
    """Create a sample conversation for testing."""
    conversation = Conversation(
        id=uuid.uuid4(),
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
    raw_log = RawLog(
        id=uuid.uuid4(),
        conversation_id=sample_conversation.id,
        agent_type="claude-code",
        log_format="json",
        raw_content='{"messages": [{"role": "user", "content": "test"}]}',
        file_path="/path/to/log.json",
        extra_data={"size_bytes": 1024},
    )
    db_session.add(raw_log)
    db_session.commit()
    db_session.refresh(raw_log)
    return raw_log
