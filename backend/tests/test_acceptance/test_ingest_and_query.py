"""
Acceptance test: Ingest a log file and query it via API.

Given a raw Claude Code JSONL log file
When parsed through the ClaudeCodeParser
Then the ParsedConversation has correct session_id, messages, and agent_type

Given the parsed conversation
When ingested into the database via the pipeline
Then the conversation appears in the API with correct message count, developer, and project
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from catsyphon.models.db import Conversation, Workspace
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.pipeline.ingestion import ingest_conversation


FIXTURES_DIR = Path(__file__).parent.parent / "test_parsers" / "fixtures"


class TestIngestAndQuery:
    """
    Scenario: A developer ingests a Claude Code log and queries it back.

    Exercises the full path from raw JSONL file through the parser,
    ingestion pipeline, database persistence, and REST API query layer.
    """

    # -- fixtures --------------------------------------------------------

    @pytest.fixture
    def parser(self) -> ClaudeCodeParser:
        return ClaudeCodeParser()

    @pytest.fixture
    def minimal_fixture(self) -> Path:
        """The smallest valid Claude Code log (2 messages)."""
        return FIXTURES_DIR / "minimal_conversation.jsonl"

    @pytest.fixture
    def full_fixture(self) -> Path:
        """A richer log with tool calls and multiple turns (6 messages)."""
        return FIXTURES_DIR / "full_conversation.jsonl"

    # -- Given/When/Then: parser produces correct ParsedConversation ------

    def test_parser_extracts_session_id(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a minimal JSONL log, the parser extracts session_id."""
        parsed = parser.parse(minimal_fixture)

        assert parsed.session_id == "test-session-001"

    def test_parser_extracts_agent_type(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a minimal JSONL log, agent_type is 'claude-code'."""
        parsed = parser.parse(minimal_fixture)

        assert parsed.agent_type == "claude-code"

    def test_parser_extracts_correct_message_count(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a 2-line JSONL log, the parser returns 2 messages."""
        parsed = parser.parse(minimal_fixture)

        assert len(parsed.messages) == 2
        assert parsed.messages[0].role == "user"
        assert parsed.messages[1].role == "assistant"

    def test_parser_extracts_working_directory(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a JSONL log with cwd field, working_directory is set."""
        parsed = parser.parse(minimal_fixture)

        assert parsed.working_directory == "/Users/test/project"

    def test_parser_extracts_git_branch(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a JSONL log with gitBranch field, git_branch is set."""
        parsed = parser.parse(minimal_fixture)

        assert parsed.git_branch == "main"

    def test_parser_extracts_timestamps(
        self, parser: ClaudeCodeParser, minimal_fixture: Path
    ):
        """Given a JSONL log, start_time and end_time are populated."""
        parsed = parser.parse(minimal_fixture)

        assert parsed.start_time is not None
        assert parsed.end_time is not None
        assert parsed.start_time <= parsed.end_time

    def test_full_log_has_tool_calls(
        self, parser: ClaudeCodeParser, full_fixture: Path
    ):
        """Given a log with tool use, the parser extracts tool calls."""
        parsed = parser.parse(full_fixture)

        tool_bearing_messages = [
            m for m in parsed.messages if len(m.tool_calls) > 0
        ]
        assert len(tool_bearing_messages) >= 1, (
            "Full conversation should contain at least one message with tool calls"
        )

    # -- Given/When/Then: pipeline persists and API returns the data ------

    def test_ingest_creates_conversation_in_db(
        self,
        parser: ClaudeCodeParser,
        minimal_fixture: Path,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a parsed conversation
        When ingested via the pipeline
        Then a Conversation row exists in the database.
        """
        parsed = parser.parse(minimal_fixture)

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="acceptance-test",
            developer_username="acceptance-bot",
            file_path=minimal_fixture,
        )
        db_session.commit()

        assert conversation.id is not None
        assert conversation.agent_type == "claude-code"

    def test_ingested_conversation_has_correct_message_count(
        self,
        parser: ClaudeCodeParser,
        minimal_fixture: Path,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a 2-message log ingested via the pipeline
        Then the conversation's denormalized message_count is 2.
        """
        parsed = parser.parse(minimal_fixture)

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="acceptance-test",
            developer_username="acceptance-bot",
            file_path=minimal_fixture,
        )
        db_session.commit()

        assert conversation.message_count == 2

    def test_ingested_conversation_has_project_association(
        self,
        parser: ClaudeCodeParser,
        minimal_fixture: Path,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a parsed conversation ingested with project_name
        Then the conversation is associated with that project.
        """
        parsed = parser.parse(minimal_fixture)

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="acceptance-project",
            developer_username="acceptance-bot",
            file_path=minimal_fixture,
        )
        db_session.commit()

        assert conversation.project_id is not None

    def test_ingested_conversation_has_developer_association(
        self,
        parser: ClaudeCodeParser,
        minimal_fixture: Path,
        db_session: Session,
        sample_workspace: Workspace,
    ):
        """
        Given a parsed conversation ingested with developer_username
        Then the conversation is associated with that developer.
        """
        parsed = parser.parse(minimal_fixture)

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="acceptance-project",
            developer_username="acceptance-bot",
            file_path=minimal_fixture,
        )
        db_session.commit()

        assert conversation.developer_id is not None

    def test_ingested_conversation_queryable_via_api(
        self,
        parser: ClaudeCodeParser,
        full_fixture: Path,
        db_session: Session,
        api_client,
        sample_workspace: Workspace,
    ):
        """
        Given a conversation ingested into the database
        When the API is queried for conversations
        Then the ingested conversation appears in the list with correct fields.
        """
        parsed = parser.parse(full_fixture)

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="api-query-test",
            developer_username="acceptance-bot",
            file_path=full_fixture,
        )
        db_session.commit()

        response = api_client.get("/conversations")
        assert response.status_code == 200

        data = response.json()
        conv_ids = [item["id"] for item in data["items"]]
        assert str(conversation.id) in conv_ids

        # Verify detail endpoint
        detail_response = api_client.get(f"/conversations/{conversation.id}")
        assert detail_response.status_code == 200

        detail = detail_response.json()
        assert detail["agent_type"] == "claude-code"
        assert detail["message_count"] == len(parsed.messages)
