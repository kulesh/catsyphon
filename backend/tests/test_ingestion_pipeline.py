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

    ProjectRepository(db_session)

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


def test_ingestion_failure_tracking(db_session: Session, tmp_path):
    """
    Test that ingestion failures are properly caught and persisted to ingestion_jobs table.

    This test verifies the try-catch wrapper added to ingest_conversation() properly
    updates the ingestion_job record with status='failed', error_message, and
    processing_time_ms when an exception occurs during ingestion.
    """
    from unittest.mock import patch

    from catsyphon.db.repositories.ingestion_job import IngestionJobRepository

    ingestion_repo = IngestionJobRepository(db_session)

    # Create a temporary file for the test
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"messages": []}\n')

    # Create parsed conversation
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
        session_id="test-failure-session",
    )

    # Mock ConversationRepository.create to raise an exception
    with patch(
        "catsyphon.pipeline.ingestion.ConversationRepository"
    ) as mock_repo_class:
        mock_repo = mock_repo_class.return_value
        mock_repo.create.side_effect = ValueError("Simulated database failure")

        # Attempt ingestion (should raise exception)
        with pytest.raises(ValueError, match="Simulated database failure"):
            ingest_conversation(
                session=db_session,
                parsed=parsed,
                file_path=test_file,
                source_type="cli",
            )

    # Verify ingestion_job was created and marked as failed
    failed_jobs = ingestion_repo.get_by_status("failed")
    assert len(failed_jobs) == 1

    failed_job = failed_jobs[0]
    assert failed_job.status == "failed"
    assert failed_job.error_message is not None
    assert "ValueError: Simulated database failure" in failed_job.error_message
    assert failed_job.processing_time_ms is not None
    assert failed_job.processing_time_ms > 0  # Should have non-zero processing time
    assert failed_job.completed_at is not None
    assert failed_job.file_path == str(test_file)
    assert failed_job.source_type == "cli"
