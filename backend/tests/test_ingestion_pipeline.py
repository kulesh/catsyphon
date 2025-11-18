"""
Tests for ingestion pipeline project auto-detection.
"""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.pipeline.ingestion import ingest_conversation


def test_auto_detect_project_from_working_directory(db_session: Session):
    """Test that projects are auto-created from working_directory."""
    from catsyphon.db.repositories.project import ProjectRepository

    project_repo = ProjectRepository(db_session)

    # Create parsed conversation with working_directory
    parsed = ParsedConversation(
        agent_type="claude-code",
        agent_version="2.0.17",
        start_time=datetime(2025, 1, 18, 10, 0, 0),
        end_time=datetime(2025, 1, 18, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Hello",
                timestamp=datetime(2025, 1, 18, 10, 0, 0),
            )
        ],
        working_directory="/Users/test/my-project",
        session_id="test-session-123",
    )

    # Ingest without --project flag (uses default workspace internally)
    conversation = ingest_conversation(
        session=db_session,
        parsed=parsed,
        developer_username="testuser",
    )

    # Verify project was auto-created
    assert conversation.project_id is not None

    project = project_repo.get(conversation.project_id)
    assert project is not None
    assert project.directory_path == "/Users/test/my-project"
    assert project.name == "my-project"  # Auto-generated from basename


def test_auto_detect_reuses_existing_project(db_session: Session):
    """Test that subsequent ingestions reuse the same project."""
    from catsyphon.db.repositories.project import ProjectRepository

    project_repo = ProjectRepository(db_session)

    # First ingestion
    parsed1 = ParsedConversation(
        agent_type="claude-code",
        agent_version="2.0.17",
        start_time=datetime(2025, 1, 18, 10, 0, 0),
        end_time=datetime(2025, 1, 18, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="First conversation",
                timestamp=datetime(2025, 1, 18, 10, 0, 0),
            )
        ],
        working_directory="/Users/test/shared-project",
        session_id="session-1",
    )

    conversation1 = ingest_conversation(session=db_session, parsed=parsed1)

    # Second ingestion with same directory
    parsed2 = ParsedConversation(
        agent_type="claude-code",
        agent_version="2.0.17",
        start_time=datetime(2025, 1, 18, 11, 0, 0),
        end_time=datetime(2025, 1, 18, 11, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Second conversation",
                timestamp=datetime(2025, 1, 18, 11, 0, 0),
            )
        ],
        working_directory="/Users/test/shared-project",
        session_id="session-2",
    )

    conversation2 = ingest_conversation(session=db_session, parsed=parsed2)

    # Both conversations should have same project
    assert conversation1.project_id == conversation2.project_id


def test_project_name_override_with_auto_detect(db_session: Session):
    """Test that --project flag overrides auto-generated name."""
    from catsyphon.db.repositories.project import ProjectRepository

    project_repo = ProjectRepository(db_session)

    parsed = ParsedConversation(
        agent_type="claude-code",
        agent_version="2.0.17",
        start_time=datetime(2025, 1, 18, 10, 0, 0),
        end_time=datetime(2025, 1, 18, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Hello",
                timestamp=datetime(2025, 1, 18, 10, 0, 0),
            )
        ],
        working_directory="/Users/test/myapp",
        session_id="test-session",
    )

    # Ingest with custom project name
    conversation = ingest_conversation(
        session=db_session,
        parsed=parsed,
        project_name="My Awesome Application",
    )

    # Verify project has custom name but auto-detected directory
    project = project_repo.get(conversation.project_id)
    assert project.name == "My Awesome Application"  # Custom name
    assert project.directory_path == "/Users/test/myapp"  # Auto-detected


def test_no_working_directory_warning(db_session: Session, caplog):
    """Test warning when working_directory is missing and no --project flag."""
    parsed = ParsedConversation(
        agent_type="claude-code",
        agent_version="2.0.17",
        start_time=datetime(2025, 1, 18, 10, 0, 0),
        end_time=datetime(2025, 1, 18, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Hello",
                timestamp=datetime(2025, 1, 18, 10, 0, 0),
            )
        ],
        working_directory=None,  # No working directory
        session_id="test-session",
    )

    # Ingest without project_name
    conversation = ingest_conversation(session=db_session, parsed=parsed)

    # Should log warning and conversation should have no project
    assert conversation.project_id is None
    assert "No project association" in caplog.text
