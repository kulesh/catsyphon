"""
Acceptance test: Deduplication prevents double ingestion.

Given a log file that has already been ingested
When the same file is ingested again without --force
Then no duplicate conversation is created
And the existing conversation remains unchanged
"""

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from catsyphon.models.db import Conversation, Workspace
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.pipeline.ingestion import ingest_conversation
from catsyphon.utils.hashing import calculate_file_hash

FIXTURES_DIR = Path(__file__).parent.parent / "test_parsers" / "fixtures"


class TestDedupPreventsDoubleIngest:
    """
    Scenario: An operator or watch daemon processes the same log file twice.

    The pipeline must recognize the duplicate via content hashing and return
    the existing conversation without creating a second row.
    """

    @pytest.fixture
    def parser(self) -> ClaudeCodeParser:
        return ClaudeCodeParser()

    @pytest.fixture
    def log_file(self, tmp_path: Path) -> Path:
        """Copy minimal fixture to a temp directory so hashing is stable."""
        src = FIXTURES_DIR / "minimal_conversation.jsonl"
        dst = tmp_path / "minimal_conversation.jsonl"
        shutil.copy2(src, dst)
        return dst

    # -- Given: first ingestion succeeds ----------------------------------

    @pytest.fixture
    def first_conversation(
        self,
        parser: ClaudeCodeParser,
        log_file: Path,
        db_session: Session,
        sample_workspace: Workspace,
    ) -> Conversation:
        """Ingest the log file once and return the resulting conversation."""
        parsed = parser.parse(log_file)
        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="dedup-test",
            developer_username="dedup-bot",
            file_path=log_file,
        )
        db_session.commit()
        return conversation

    # -- Then: content hash is stored in raw_logs -------------------------

    def test_file_hash_stored_after_first_ingest(
        self,
        first_conversation: Conversation,
        log_file: Path,
        db_session: Session,
    ):
        """
        Given a successfully ingested log file
        Then the raw_logs table contains a row with the file's content hash.
        """
        from catsyphon.models.db import RawLog

        raw_logs = (
            db_session.query(RawLog)
            .filter(RawLog.conversation_id == first_conversation.id)
            .all()
        )
        assert len(raw_logs) == 1

        expected_hash = calculate_file_hash(log_file)
        assert raw_logs[0].file_hash == expected_hash

    # -- When: same file is ingested again --------------------------------

    def test_second_ingest_returns_same_conversation(
        self,
        parser: ClaudeCodeParser,
        log_file: Path,
        first_conversation: Conversation,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a file that was already ingested
        When ingested a second time with skip_duplicates=True (default)
        Then the same Conversation is returned (no new row created).
        """
        parsed = parser.parse(log_file)
        second = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="dedup-test",
            developer_username="dedup-bot",
            file_path=log_file,
            skip_duplicates=True,
        )
        db_session.commit()

        assert second.id == first_conversation.id

    def test_no_duplicate_conversations_in_db(
        self,
        parser: ClaudeCodeParser,
        log_file: Path,
        first_conversation: Conversation,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a duplicate ingest attempt
        Then only one Conversation row exists for this session_id.
        """
        parsed = parser.parse(log_file)
        ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="dedup-test",
            developer_username="dedup-bot",
            file_path=log_file,
            skip_duplicates=True,
        )
        db_session.commit()

        count = (
            db_session.query(Conversation)
            .filter(Conversation.agent_type == "claude-code")
            .count()
        )
        assert count == 1

    def test_message_count_unchanged_after_duplicate(
        self,
        parser: ClaudeCodeParser,
        log_file: Path,
        first_conversation: Conversation,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a duplicate ingest attempt
        Then the existing conversation's message_count is unchanged.
        """
        original_count = first_conversation.message_count

        parsed = parser.parse(log_file)
        returned = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="dedup-test",
            developer_username="dedup-bot",
            file_path=log_file,
            skip_duplicates=True,
        )
        db_session.commit()

        assert returned.message_count == original_count

    # -- Edge case: identical content, different path ---------------------

    def test_duplicate_content_different_path_still_deduped(
        self,
        parser: ClaudeCodeParser,
        log_file: Path,
        first_conversation: Conversation,
        db_session: Session,
        sample_workspace: Workspace,
        tmp_path: Path,
    ):
        """
        Given the same file content copied to a different path
        When ingested with skip_duplicates=True
        Then it is recognized as a duplicate (hash-based, not path-based).
        """
        # Copy to a different filename
        alt_path = tmp_path / "renamed_copy.jsonl"
        shutil.copy2(log_file, alt_path)

        parsed = parser.parse(alt_path)
        returned = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="dedup-test",
            developer_username="dedup-bot",
            file_path=alt_path,
            skip_duplicates=True,
        )
        db_session.commit()

        assert returned.id == first_conversation.id
