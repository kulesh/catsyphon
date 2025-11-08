"""Tests for deduplication functionality in ingestion pipeline."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from catsyphon.db.repositories import RawLogRepository
from catsyphon.exceptions import DuplicateFileError
from catsyphon.models.parsed import ParsedConversation, ParsedMessage
from catsyphon.pipeline.ingestion import ingest_conversation
from catsyphon.utils.hashing import calculate_file_hash


@pytest.fixture
def sample_parsed_conversation() -> ParsedConversation:
    """Create a sample parsed conversation for testing."""
    return ParsedConversation(
        agent_type="claude-code",
        agent_version="1.0.0",
        session_id="test-session",
        start_time=datetime.now(UTC),
        end_time=None,
        messages=[
            ParsedMessage(
                role="user",
                content="Test message",
                timestamp=datetime.now(UTC),
                tool_calls=[],
                code_changes=[],
                entities={},
                model=None,
                token_usage=None,
            )
        ],
        git_branch=None,
        working_directory=None,
        files_touched=[],
        code_changes=[],
        metadata={},
    )


class TestFileHashTracking:
    """Tests for file hash tracking in RawLog repository."""

    def test_create_from_file_calculates_hash(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that create_from_file automatically calculates file hash."""
        # First ingest a conversation to get conversation_id
        conv = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
        )
        db_session.commit()

        # Create a test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        # Create raw log from file
        raw_log_repo = RawLogRepository(db_session)
        raw_log = raw_log_repo.create_from_file(
            conversation_id=conv.id,
            agent_type="claude-code",
            log_format="jsonl",
            file_path=test_file,
        )
        db_session.commit()

        # Verify hash was calculated
        assert raw_log.file_hash is not None
        assert len(raw_log.file_hash) == 64

        # Verify hash matches manual calculation
        expected_hash = calculate_file_hash(test_file)
        assert raw_log.file_hash == expected_hash

    def test_create_from_content_calculates_hash(
        self, db_session: Session, sample_parsed_conversation: ParsedConversation
    ):
        """Test that create_from_content automatically calculates content hash."""
        # First ingest a conversation to get conversation_id
        conv = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
        )
        db_session.commit()

        # Create raw log from content
        raw_log_repo = RawLogRepository(db_session)
        content = '{"test": "content"}'
        raw_log = raw_log_repo.create_from_content(
            conversation_id=conv.id,
            agent_type="claude-code",
            log_format="jsonl",
            raw_content=content,
        )
        db_session.commit()

        # Verify hash was calculated
        assert raw_log.file_hash is not None
        assert len(raw_log.file_hash) == 64

    def test_get_by_file_hash(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test getting raw log by file hash."""
        conv = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
        )
        db_session.commit()

        # Create a test file and raw log
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        raw_log_repo = RawLogRepository(db_session)
        raw_log = raw_log_repo.create_from_file(
            conversation_id=conv.id,
            agent_type="claude-code",
            log_format="jsonl",
            file_path=test_file,
        )
        db_session.commit()

        # Get by hash
        found_raw_log = raw_log_repo.get_by_file_hash(raw_log.file_hash)

        assert found_raw_log is not None
        assert found_raw_log.id == raw_log.id

    def test_exists_by_file_hash(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test checking if file hash exists."""
        conv = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
        )
        db_session.commit()

        # Create a test file and raw log
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        raw_log_repo = RawLogRepository(db_session)
        raw_log = raw_log_repo.create_from_file(
            conversation_id=conv.id,
            agent_type="claude-code",
            log_format="jsonl",
            file_path=test_file,
        )
        db_session.commit()

        # Check existence
        assert raw_log_repo.exists_by_file_hash(raw_log.file_hash) is True
        assert raw_log_repo.exists_by_file_hash("0" * 64) is False  # Non-existent hash


class TestIngestionDeduplication:
    """Tests for deduplication in ingestion pipeline."""

    def test_skip_duplicates_true_returns_existing_conversation(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that skip_duplicates=True returns existing conversation."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        # First ingestion
        conv1 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=test_file,
            skip_duplicates=True,
        )
        db_session.commit()
        conv1_id = conv1.id

        # Second ingestion with same file (duplicate)
        conv2 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=test_file,
            skip_duplicates=True,
        )
        db_session.commit()

        # Should return the same conversation
        assert conv2.id == conv1_id

    def test_skip_duplicates_false_raises_error(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that skip_duplicates=False raises DuplicateFileError."""
        # Create test file
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        # First ingestion
        ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=test_file,
            skip_duplicates=False,
        )
        db_session.commit()

        # Second ingestion with same file should raise error
        with pytest.raises(DuplicateFileError) as exc_info:
            ingest_conversation(
                session=db_session,
                parsed=sample_parsed_conversation,
                project_name="test-project",
                file_path=test_file,
                skip_duplicates=False,
            )

        # Verify error details
        assert str(test_file) in str(exc_info.value)
        assert exc_info.value.file_path == str(test_file)
        assert len(exc_info.value.file_hash) == 64

    def test_different_files_with_same_content_are_duplicates(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that files with identical content are treated as duplicates."""
        # Create two files with same content
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        content = '{"test": "content"}'
        file1.write_text(content)
        file2.write_text(content)

        # First ingestion
        conv1 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=file1,
            skip_duplicates=True,
        )
        db_session.commit()

        # Second ingestion with different file but same content
        conv2 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=file2,
            skip_duplicates=True,
        )
        db_session.commit()

        # Should return the same conversation (duplicate)
        assert conv2.id == conv1.id

    def test_different_content_creates_new_conversation(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that files with different content create separate conversations."""
        # Create two files with different content
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        file1.write_text('{"test": "content1"}')
        file2.write_text('{"test": "content2"}')

        # First ingestion
        conv1 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=file1,
            skip_duplicates=True,
        )
        db_session.commit()

        # Second ingestion with different content
        conv2 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=file2,
            skip_duplicates=True,
        )
        db_session.commit()

        # Should create a new conversation
        assert conv2.id != conv1.id

    def test_no_file_path_skips_duplicate_check(
        self, db_session: Session, sample_parsed_conversation: ParsedConversation
    ):
        """Test that ingestion without file_path skips duplicate checking."""
        # Ingest multiple times without file_path
        conv1 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=None,  # No file path
            skip_duplicates=True,
        )
        db_session.commit()

        conv2 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            file_path=None,  # No file path
            skip_duplicates=True,
        )
        db_session.commit()

        # Should create separate conversations (no deduplication)
        assert conv2.id != conv1.id

    def test_duplicate_check_happens_before_processing(
        self,
        db_session: Session,
        sample_parsed_conversation: ParsedConversation,
        tmp_path: Path,
    ):
        """Test that duplicate check happens early without creating new records."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text('{"test": "content"}')

        # First ingestion
        conv1 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            developer_username="developer1",
            file_path=test_file,
        )
        db_session.commit()

        # Count conversations before second ingestion
        from catsyphon.models.db import Conversation

        initial_count = db_session.query(Conversation).count()

        # Second ingestion (duplicate)
        conv2 = ingest_conversation(
            session=db_session,
            parsed=sample_parsed_conversation,
            project_name="test-project",
            developer_username="developer1",
            file_path=test_file,
        )
        db_session.commit()

        # Should not create new conversation
        final_count = db_session.query(Conversation).count()
        assert final_count == initial_count
        assert conv2.id == conv1.id
