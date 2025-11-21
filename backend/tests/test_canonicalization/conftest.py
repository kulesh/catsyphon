"""Pytest fixtures for canonicalization tests."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from catsyphon.models.db import Base, Conversation, Epoch, Message, Organization, Workspace


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine using SQLite in-memory."""
    from sqlalchemy import JSON
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
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create test session with rollback."""
    SessionLocal = sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )

    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def sample_organization(test_session):
    """Create a sample organization for testing."""
    org = Organization(
        name="Test Organization",
        slug="test-org",
    )
    test_session.add(org)
    test_session.flush()
    test_session.refresh(org)
    return org


@pytest.fixture
def sample_workspace(test_session, sample_organization):
    """Create a sample workspace for testing."""
    workspace = Workspace(
        organization_id=sample_organization.id,
        name="Test Workspace",
        slug="test-workspace",
    )
    test_session.add(workspace)
    test_session.flush()
    test_session.refresh(workspace)
    return workspace


@pytest.fixture
def sample_conversation(test_session, sample_workspace):
    """Create a sample conversation for testing."""
    conversation = Conversation(
        workspace_id=sample_workspace.id,
        agent_type="claude-code",
        agent_version="2.0.28",
        start_time=datetime.now(),
        status="completed",
        message_count=10,
        epoch_count=1,
    )
    test_session.add(conversation)
    test_session.flush()
    test_session.refresh(conversation)
    return conversation


@pytest.fixture
def sample_epoch(test_session, sample_conversation):
    """Create a sample epoch for testing."""
    epoch = Epoch(
        conversation_id=sample_conversation.id,
        sequence=0,
        start_time=datetime.now(),
    )
    test_session.add(epoch)
    test_session.flush()
    test_session.refresh(epoch)
    return epoch


@pytest.fixture
def sample_message(test_session, sample_conversation, sample_epoch):
    """Create a sample message for testing."""
    message = Message(
        conversation_id=sample_conversation.id,
        epoch_id=sample_epoch.id,
        role="user",
        content="Test message",
        timestamp=datetime.now(),
        sequence=0,
    )
    test_session.add(message)
    test_session.flush()
    test_session.refresh(message)
    return message
