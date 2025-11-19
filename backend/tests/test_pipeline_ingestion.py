"""
Tests for ingestion pipeline.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from catsyphon.db.repositories import (
    ConversationRepository,
    DeveloperRepository,
    EpochRepository,
    MessageRepository,
    ProjectRepository,
    RawLogRepository,
)
from catsyphon.models.parsed import (
    CodeChange,
    ParsedConversation,
    ParsedMessage,
    ToolCall,
)
from catsyphon.pipeline.ingestion import ingest_conversation, link_orphaned_agents


class TestBasicIngestion:
    """Tests for basic conversation ingestion."""

    def test_ingest_simple_conversation(self, db_session: Session):
        """Test ingesting a minimal conversation."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(minutes=5),
            messages=[
                ParsedMessage(
                    role="user",
                    content="Hello",
                    timestamp=datetime.now(UTC),
                ),
                ParsedMessage(
                    role="assistant",
                    content="Hi there!",
                    timestamp=datetime.now(UTC) + timedelta(seconds=1),
                ),
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        assert conversation.id is not None
        assert conversation.agent_type == "claude-code"
        assert len(conversation.messages) == 2
        assert len(conversation.epochs) == 1

    def test_ingest_with_project(self, db_session: Session, sample_workspace):
        """Test ingestion creates/gets project."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Ingest with project name
        conversation = ingest_conversation(
            db_session, parsed, project_name="test-project"
        )

        assert conversation.project_id is not None
        assert conversation.project.name == "test-project"

        # Verify project was created
        project_repo = ProjectRepository(db_session)
        project = project_repo.get_by_name("test-project", sample_workspace.id)
        assert project is not None

    def test_ingest_with_existing_project(self, db_session: Session, sample_workspace):
        """Test ingestion reuses existing project."""
        # Create project first
        project_repo = ProjectRepository(db_session)
        existing_project = project_repo.create(
            workspace_id=sample_workspace.id,
            name="existing-project",
            directory_path="/tmp/existing-project",
        )
        db_session.flush()

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Ingest with same project name
        conversation = ingest_conversation(
            db_session, parsed, project_name="existing-project"
        )

        # Should reuse existing project
        assert conversation.project_id == existing_project.id

        # Should not create duplicate
        all_projects = project_repo.get_all()
        project_names = [p.name for p in all_projects]
        assert project_names.count("existing-project") == 1

    def test_ingest_with_developer(self, db_session: Session, sample_workspace):
        """Test ingestion creates/gets developer."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        # Ingest with developer username
        conversation = ingest_conversation(
            db_session, parsed, developer_username="john"
        )

        assert conversation.developer_id is not None
        assert conversation.developer.username == "john"

        # Verify developer was created
        dev_repo = DeveloperRepository(db_session)
        developer = dev_repo.get_by_username("john", sample_workspace.id)
        assert developer is not None

    def test_ingest_creates_conversation(self, db_session: Session):
        """Test that conversation record is created correctly."""
        start_time = datetime.now(UTC)
        end_time = start_time + timedelta(minutes=10)

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=start_time,
            end_time=end_time,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=start_time,
                )
            ],
            session_id="test-session-123",
            git_branch="main",
            working_directory="/home/user/project",
        )

        conversation = ingest_conversation(db_session, parsed)

        assert conversation.agent_type == "claude-code"
        assert conversation.agent_version == "2.0.17"
        # SQLite doesn't preserve timezone, compare naive datetimes
        assert conversation.start_time.replace(tzinfo=None) == start_time.replace(
            tzinfo=None
        )
        assert conversation.end_time.replace(tzinfo=None) == end_time.replace(
            tzinfo=None
        )
        assert conversation.status == "completed"
        assert conversation.extra_data["session_id"] == "test-session-123"
        assert conversation.extra_data["git_branch"] == "main"
        assert conversation.extra_data["working_directory"] == "/home/user/project"

    def test_ingest_creates_epoch(self, db_session: Session):
        """Test that epoch is created."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(minutes=5),
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify epoch was created
        epoch_repo = EpochRepository(db_session)
        epochs = epoch_repo.get_by_conversation(conversation.id)

        assert len(epochs) == 1
        assert epochs[0].sequence == 0
        assert epochs[0].conversation_id == conversation.id


class TestMessageIngestion:
    """Tests for message ingestion."""

    def test_ingest_creates_messages(self, db_session: Session):
        """Test that all messages are stored."""
        now = datetime.now(UTC)
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            messages=[
                ParsedMessage(
                    role="user",
                    content="Message 1",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Message 2",
                    timestamp=now + timedelta(seconds=1),
                ),
                ParsedMessage(
                    role="user",
                    content="Message 3",
                    timestamp=now + timedelta(seconds=2),
                ),
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify all messages were created
        message_repo = MessageRepository(db_session)
        messages = message_repo.get_by_conversation(conversation.id)

        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"
        assert messages[2].content == "Message 3"

    def test_ingest_preserves_tool_calls(self, db_session: Session):
        """Test that tool calls are preserved in JSON."""
        now = datetime.now(UTC)
        tool_call = ToolCall(
            tool_name="Read",
            parameters={"file_path": "test.py"},
            result="file contents here",
            success=True,
            timestamp=now,
        )

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            messages=[
                ParsedMessage(
                    role="assistant",
                    content="Reading file",
                    timestamp=now,
                    tool_calls=[tool_call],
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify tool calls were preserved
        message_repo = MessageRepository(db_session)
        messages = message_repo.get_by_conversation(conversation.id)

        assert len(messages) == 1
        assert len(messages[0].tool_calls) == 1
        assert messages[0].tool_calls[0]["tool_name"] == "Read"
        assert messages[0].tool_calls[0]["parameters"]["file_path"] == "test.py"
        assert messages[0].tool_calls[0]["result"] == "file contents here"

    def test_ingest_preserves_code_changes(self, db_session: Session):
        """Test that code changes are preserved in JSON."""
        now = datetime.now(UTC)
        code_change = CodeChange(
            file_path="test.py",
            change_type="edit",
            old_content="old code",
            new_content="new code",
            lines_added=5,
            lines_deleted=3,
        )

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            messages=[
                ParsedMessage(
                    role="assistant",
                    content="Editing file",
                    timestamp=now,
                    code_changes=[code_change],
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify code changes were preserved
        message_repo = MessageRepository(db_session)
        messages = message_repo.get_by_conversation(conversation.id)

        assert len(messages) == 1
        assert len(messages[0].code_changes) == 1
        assert messages[0].code_changes[0]["file_path"] == "test.py"
        assert messages[0].code_changes[0]["change_type"] == "edit"
        assert messages[0].code_changes[0]["lines_added"] == 5
        assert messages[0].code_changes[0]["lines_deleted"] == 3

    def test_ingest_message_sequence(self, db_session: Session):
        """Test that messages maintain correct sequence order."""
        now = datetime.now(UTC)
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            messages=[
                ParsedMessage(role="user", content="First", timestamp=now),
                ParsedMessage(role="assistant", content="Second", timestamp=now),
                ParsedMessage(role="user", content="Third", timestamp=now),
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify sequence numbers
        message_repo = MessageRepository(db_session)
        messages = message_repo.get_by_conversation(conversation.id)

        assert messages[0].sequence == 0
        assert messages[1].sequence == 1
        assert messages[2].sequence == 2


class TestFilesTouchedIngestion:
    """Tests for files touched ingestion."""

    def test_ingest_files_from_files_touched(self, db_session: Session):
        """Test that files_touched list is stored."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
            files_touched=["src/main.py", "src/utils.py", "tests/test_main.py"],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify FilesTouched records were created
        assert len(conversation.files_touched) >= 3

        file_paths = [ft.file_path for ft in conversation.files_touched]
        assert "src/main.py" in file_paths
        assert "src/utils.py" in file_paths
        assert "tests/test_main.py" in file_paths

    def test_ingest_files_from_code_changes(self, db_session: Session):
        """Test that code_changes list creates FilesTouched records."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
            code_changes=[
                CodeChange(
                    file_path="edited.py",
                    change_type="edit",
                    lines_added=10,
                    lines_deleted=5,
                ),
                CodeChange(
                    file_path="created.py",
                    change_type="create",
                    lines_added=50,
                    lines_deleted=0,
                ),
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Verify FilesTouched records with change types
        file_changes = {
            ft.file_path: ft.change_type for ft in conversation.files_touched
        }

        assert "edited.py" in file_changes
        assert file_changes["edited.py"] == "edit"
        assert "created.py" in file_changes
        assert file_changes["created.py"] == "create"

    def test_ingest_file_change_types(self, db_session: Session):
        """Test that change types are correctly stored."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
            code_changes=[
                CodeChange(
                    file_path="test.py",
                    change_type="edit",
                    lines_added=5,
                    lines_deleted=3,
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed)

        # Find the file touched record
        edited_file = next(
            ft for ft in conversation.files_touched if ft.file_path == "test.py"
        )

        assert edited_file.change_type == "edit"
        assert edited_file.lines_added == 5
        assert edited_file.lines_deleted == 3


class TestRawLogIngestion:
    """Tests for raw log storage."""

    def test_ingest_stores_raw_log(self, db_session: Session, tmp_path):
        """Test that raw log is stored when file_path provided."""
        # Create a temporary log file
        log_file = tmp_path / "conversation.jsonl"
        log_file.write_text('{"test": "data"}\n{"more": "data"}')

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed, file_path=log_file)

        # Verify raw log was created
        raw_log_repo = RawLogRepository(db_session)
        raw_logs = raw_log_repo.get_by_conversation(conversation.id)

        assert len(raw_logs) == 1
        assert raw_logs[0].agent_type == "claude-code"
        assert raw_logs[0].log_format == "jsonl"
        assert str(log_file) in raw_logs[0].file_path

    def test_ingest_raw_log_content(self, db_session: Session, tmp_path):
        """Test that full JSONL content is preserved."""
        # Create a log file with actual content
        log_file = tmp_path / "test.jsonl"
        content = '{"sessionId": "123"}\n{"type": "user"}'
        log_file.write_text(content)

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed, file_path=log_file)

        # Verify content is preserved exactly
        raw_log_repo = RawLogRepository(db_session)
        raw_logs = raw_log_repo.get_by_conversation(conversation.id)

        assert len(raw_logs) == 1
        assert raw_logs[0].raw_content == content


class TestTransactionHandling:
    """Tests for transaction and error handling."""

    def test_ingest_commit_on_success(self, db_session: Session):
        """Test that all data is persisted on successful ingestion."""
        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(
            db_session, parsed, project_name="test-project"
        )

        # Commit transaction
        db_session.commit()

        # Verify all data is persisted
        conv_repo = ConversationRepository(db_session)
        retrieved = conv_repo.get(conversation.id)

        assert retrieved is not None
        assert retrieved.project.name == "test-project"
        assert len(retrieved.messages) == 1
        assert len(retrieved.epochs) == 1

    def test_ingest_with_tags(self, db_session: Session):
        """Test ingestion with pre-computed tags."""
        tags = {
            "intent": "feature_add",
            "outcome": "success",
            "sentiment": "positive",
            "sentiment_score": 0.8,
        }

        parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=datetime.now(UTC),
                )
            ],
        )

        conversation = ingest_conversation(db_session, parsed, tags=tags)

        # Verify tags are stored
        assert conversation.tags == tags

        # Verify tags are also applied to epoch
        epoch = conversation.epochs[0]
        assert epoch.intent == "feature_add"
        assert epoch.outcome == "success"
        assert epoch.sentiment == "positive"
        assert epoch.sentiment_score == 0.8


class TestConversationUpdates:
    """Tests for conversation update modes (skip, replace, append)."""

    def test_update_mode_skip(self, db_session: Session):
        """Test that skip mode returns existing conversation without changes."""
        session_id = "test-session-skip"
        now = datetime.now(UTC)

        # Create initial conversation
        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Original message",
                    timestamp=now,
                )
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1)
        original_id = conv1.id
        original_message_count = len(conv1.messages)
        db_session.commit()

        # Try to ingest again with skip mode (default)
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=10),
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="New message",
                    timestamp=now,
                )
            ],
        )

        conv2 = ingest_conversation(db_session, parsed2, update_mode="skip")

        # Should return same conversation
        assert conv2.id == original_id
        assert len(conv2.messages) == original_message_count
        assert conv2.messages[0].content == "Original message"

    def test_update_mode_replace(self, db_session: Session):
        """Test that replace mode deletes children and recreates with new data."""
        session_id = "test-session-replace"
        now = datetime.now(UTC)

        # Create initial conversation with 2 messages
        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Message 1",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Message 2",
                    timestamp=now + timedelta(seconds=1),
                ),
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1)
        original_id = conv1.id
        db_session.commit()

        # Update with 3 messages using replace mode
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=10),
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Message 1",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Message 2",
                    timestamp=now + timedelta(seconds=1),
                ),
                ParsedMessage(
                    role="user",
                    content="Message 3 (new)",
                    timestamp=now + timedelta(seconds=2),
                ),
            ],
        )

        conv2 = ingest_conversation(db_session, parsed2, update_mode="replace")
        db_session.commit()

        # Should preserve conversation ID
        assert conv2.id == original_id

        # Should have new message count
        assert len(conv2.messages) == 3
        assert conv2.messages[2].content == "Message 3 (new)"

        # Verify denormalized count is updated
        assert conv2.message_count == 3

    def test_update_mode_replace_preserves_id(self, db_session: Session):
        """Test that replace mode preserves conversation ID."""
        session_id = "test-session-preserve-id"
        now = datetime.now(UTC)

        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Original",
                    timestamp=now,
                )
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1, project_name="project1")
        original_id = conv1.id
        db_session.commit()

        # Update with different project
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=now + timedelta(minutes=1),
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Updated",
                    timestamp=now,
                )
            ],
        )

        conv2 = ingest_conversation(
            db_session, parsed2, project_name="project2", update_mode="replace"
        )
        db_session.commit()

        # Verify ID is preserved
        assert conv2.id == original_id

        # Verify project was updated
        assert conv2.project.name == "project2"

    def test_update_mode_replace_updates_counts(self, db_session: Session):
        """Test that replace mode correctly updates denormalized counts."""
        session_id = "test-session-counts"
        now = datetime.now(UTC)

        # Create initial conversation with files
        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=now,
                )
            ],
            files_touched=["file1.py", "file2.py"],
        )

        conv1 = ingest_conversation(db_session, parsed1)
        db_session.commit()

        # Verify initial counts
        assert conv1.message_count == 1
        assert conv1.files_count == 2

        # Update with more files
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test 1",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Test 2",
                    timestamp=now + timedelta(seconds=1),
                ),
            ],
            files_touched=["file1.py", "file2.py", "file3.py", "file4.py"],
        )

        conv2 = ingest_conversation(db_session, parsed2, update_mode="replace")
        db_session.commit()

        # Verify counts were updated
        assert conv2.message_count == 2
        assert conv2.files_count == 4

    def test_update_mode_replace_with_raw_log(self, db_session: Session, tmp_path):
        """Test that replace mode handles raw_log updates correctly."""
        session_id = "test-session-raw-log"
        now = datetime.now(UTC)

        # Create initial conversation with raw log
        log_file1 = tmp_path / "log1.jsonl"
        log_file1.write_text('{"test": "data1"}')

        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=now,
                )
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1, file_path=log_file1)
        original_id = conv1.id
        db_session.commit()

        # Verify initial raw log
        raw_log_repo = RawLogRepository(db_session)
        raw_logs1 = raw_log_repo.get_by_conversation(conv1.id)
        assert len(raw_logs1) == 1

        # Update THE SAME log file with modified content (different hash)
        # Use same file path to test replacement of existing file
        log_file1.write_text('{"test": "data2", "more": "content"}')

        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Response",
                    timestamp=now + timedelta(seconds=1),
                ),
            ],
        )

        conv2 = ingest_conversation(
            db_session, parsed2, file_path=log_file1, update_mode="replace"
        )
        db_session.commit()

        # Verify conversation ID preserved
        assert conv2.id == original_id

        # Verify raw log was replaced (only one raw log should exist)
        raw_logs2 = raw_log_repo.get_by_conversation(conv2.id)
        assert len(raw_logs2) == 1
        assert '{"test": "data2"' in raw_logs2[0].raw_content

    def test_update_mode_append_not_implemented(self, db_session: Session):
        """Test that append mode raises NotImplementedError."""
        session_id = "test-session-append"
        now = datetime.now(UTC)

        # Create initial conversation
        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=now,
                )
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1)
        db_session.commit()

        # Try to update with append mode
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=session_id,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Response",
                    timestamp=now + timedelta(seconds=1),
                ),
            ],
        )

        # Append mode requires file_path
        try:
            ingest_conversation(db_session, parsed2, update_mode="append")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "append mode requires file_path" in str(e)

    def test_no_session_id_always_creates_new(self, db_session: Session):
        """Test that conversations without session_id always create new records."""
        now = datetime.now(UTC)

        # Create first conversation without session_id
        parsed1 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test 1",
                    timestamp=now,
                )
            ],
        )

        conv1 = ingest_conversation(db_session, parsed1)
        db_session.commit()

        # Create second conversation without session_id
        parsed2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.17",
            start_time=now,
            end_time=None,
            session_id=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Test 2",
                    timestamp=now,
                )
            ],
        )

        conv2 = ingest_conversation(db_session, parsed2, update_mode="replace")
        db_session.commit()

        # Should create new conversation even with replace mode
        assert conv2.id != conv1.id

        # Verify both exist
        conv_repo = ConversationRepository(db_session)
        all_convs = conv_repo.get_all()
        assert len(all_convs) >= 2


class TestHierarchicalConversationIngestion:
    """Tests for hierarchical conversation ingestion (agents and parent-child linking)."""

    def test_ingest_agent_links_to_existing_parent(self, db_session: Session, sample_workspace):
        """Test that agent conversation links to existing parent during ingestion."""
        parent_session_id = "parent-session-123"
        agent_id = "agent-456"
        now = datetime.now(UTC)

        # First, ingest parent conversation
        parent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=parent_session_id,
            conversation_type="main",
            parent_session_id=None,
            messages=[
                ParsedMessage(
                    role="user",
                    content="Main conversation",
                    timestamp=now,
                )
            ],
        )

        parent_conv = ingest_conversation(db_session, parent_parsed)
        db_session.commit()

        # Now ingest agent conversation
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now + timedelta(minutes=1),
            end_time=now + timedelta(minutes=3),
            session_id=agent_id,
            conversation_type="agent",
            parent_session_id=parent_session_id,
            agent_metadata={
                "agent_id": agent_id,
                "parent_session_id": parent_session_id,
            },
            context_semantics={
                "shares_parent_context": False,
                "can_use_parent_tools": True,
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent task",
                    timestamp=now + timedelta(minutes=1),
                )
            ],
        )

        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Verify linking
        assert agent_conv.conversation_type == "agent"
        assert agent_conv.parent_conversation_id == parent_conv.id
        assert agent_conv.agent_metadata["agent_id"] == agent_id

        # Verify parent has child
        db_session.refresh(parent_conv)
        assert len(parent_conv.children) == 1
        assert parent_conv.children[0].id == agent_conv.id

    def test_ingest_agent_before_parent_creates_orphan(self, db_session: Session, sample_workspace):
        """Test that agent ingested before parent becomes orphaned."""
        parent_session_id = "parent-session-789"
        agent_id = "agent-orphan"
        now = datetime.now(UTC)

        # Ingest agent first (parent doesn't exist yet)
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=2),
            session_id=agent_id,
            conversation_type="agent",
            parent_session_id=parent_session_id,
            agent_metadata={
                "agent_id": agent_id,
                "parent_session_id": parent_session_id,
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent task",
                    timestamp=now,
                )
            ],
        )

        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Verify agent is orphaned (parent_conversation_id is NULL)
        assert agent_conv.conversation_type == "agent"
        assert agent_conv.parent_conversation_id is None
        assert agent_conv.agent_metadata["parent_session_id"] == parent_session_id

    def test_ingest_parent_after_agent_links_orphans(self, db_session: Session, sample_workspace):
        """Test that ingesting parent after agent links orphaned agents."""
        parent_session_id = "parent-session-link"
        agent_id = "agent-link"
        now = datetime.now(UTC)

        # Ingest agent first (orphaned)
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=2),
            session_id=agent_id,
            conversation_type="agent",
            parent_session_id=parent_session_id,
            agent_metadata={
                "agent_id": agent_id,
                "parent_session_id": parent_session_id,
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent task",
                    timestamp=now,
                )
            ],
        )

        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()
        assert agent_conv.parent_conversation_id is None  # Orphaned

        # Now ingest parent
        parent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=parent_session_id,
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Main conversation",
                    timestamp=now,
                )
            ],
        )

        parent_conv = ingest_conversation(db_session, parent_parsed)
        db_session.commit()

        # Run link_orphaned_agents
        linked_count = link_orphaned_agents(db_session, sample_workspace.id)
        db_session.commit()

        # Verify linking
        assert linked_count == 1
        db_session.refresh(agent_conv)
        assert agent_conv.parent_conversation_id == parent_conv.id

    def test_link_orphaned_agents_finds_and_links(self, db_session: Session, sample_workspace):
        """Test link_orphaned_agents function finds and links orphaned agents."""
        now = datetime.now(UTC)

        # Create multiple orphaned agents
        for i in range(3):
            agent_parsed = ParsedConversation(
                agent_type="claude-code",
                agent_version="2.0.28",
                start_time=now,
                end_time=now + timedelta(minutes=1),
                session_id=f"agent-{i}",
                conversation_type="agent",
                parent_session_id="shared-parent",
                agent_metadata={
                    "agent_id": f"agent-{i}",
                    "parent_session_id": "shared-parent",
                },
                messages=[
                    ParsedMessage(
                        role="user",
                        content=f"Agent {i} task",
                        timestamp=now,
                    )
                ],
            )
            ingest_conversation(db_session, agent_parsed)

        db_session.commit()

        # Verify all are orphaned
        conv_repo = ConversationRepository(db_session)
        orphans = conv_repo.get_all()
        assert len([c for c in orphans if c.parent_conversation_id is None]) == 3

        # Ingest parent
        parent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=10),
            session_id="shared-parent",
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Parent conversation",
                    timestamp=now,
                )
            ],
        )
        ingest_conversation(db_session, parent_parsed)
        db_session.commit()

        # Link orphans
        linked_count = link_orphaned_agents(db_session, sample_workspace.id)
        db_session.commit()

        # Verify all were linked
        assert linked_count == 3
        all_convs = conv_repo.get_all()
        agents = [c for c in all_convs if c.conversation_type == "agent"]
        assert all(a.parent_conversation_id is not None for a in agents)

    def test_link_orphaned_agents_skips_already_linked(self, db_session: Session, sample_workspace):
        """Test that link_orphaned_agents skips already linked agents."""
        parent_session_id = "parent-existing"
        now = datetime.now(UTC)

        # Ingest parent first
        parent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=parent_session_id,
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Parent",
                    timestamp=now,
                )
            ],
        )
        parent_conv = ingest_conversation(db_session, parent_parsed)
        db_session.commit()

        # Ingest agent that gets linked immediately
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now + timedelta(minutes=1),
            end_time=now + timedelta(minutes=2),
            session_id="agent-linked",
            conversation_type="agent",
            parent_session_id=parent_session_id,
            agent_metadata={
                "agent_id": "agent-linked",
                "parent_session_id": parent_session_id,
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent",
                    timestamp=now + timedelta(minutes=1),
                )
            ],
        )
        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Verify already linked
        assert agent_conv.parent_conversation_id == parent_conv.id

        # Run link_orphaned_agents (should skip already linked)
        linked_count = link_orphaned_agents(db_session, sample_workspace.id)
        db_session.commit()

        # Should not link anything
        assert linked_count == 0

    def test_link_orphaned_agents_handles_missing_parent(self, db_session: Session, sample_workspace):
        """Test that link_orphaned_agents handles agents with non-existent parents."""
        now = datetime.now(UTC)

        # Create orphaned agent with parent that will never exist
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=1),
            session_id="agent-orphan-forever",
            conversation_type="agent",
            parent_session_id="non-existent-parent",
            agent_metadata={
                "agent_id": "agent-orphan-forever",
                "parent_session_id": "non-existent-parent",
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent",
                    timestamp=now,
                )
            ],
        )
        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Run link_orphaned_agents
        linked_count = link_orphaned_agents(db_session, sample_workspace.id)
        db_session.commit()

        # Should not link anything
        assert linked_count == 0

        # Agent should remain orphaned
        db_session.refresh(agent_conv)
        assert agent_conv.parent_conversation_id is None

    def test_ingest_duplicate_main_and_agent_different_types(self, db_session: Session, sample_workspace):
        """Test that same session_id with different conversation_type creates separate records."""
        session_id = "ambiguous-session"
        now = datetime.now(UTC)

        # Ingest main conversation
        main_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=session_id,
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Main",
                    timestamp=now,
                )
            ],
        )
        main_conv = ingest_conversation(db_session, main_parsed)
        db_session.commit()

        # Ingest agent conversation with same session_id (should create separate record)
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=2),
            session_id=session_id,
            conversation_type="agent",
            parent_session_id="some-parent",
            agent_metadata={
                "agent_id": session_id,
                "parent_session_id": "some-parent",
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent",
                    timestamp=now,
                )
            ],
        )
        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Should be different records
        assert main_conv.id != agent_conv.id
        assert main_conv.conversation_type == "main"
        assert agent_conv.conversation_type == "agent"

        # Verify both exist in database
        conv_repo = ConversationRepository(db_session)
        all_convs = conv_repo.get_all()
        session_convs = [c for c in all_convs if c.extra_data.get("session_id") == session_id]
        assert len(session_convs) == 2

    def test_update_mode_replace_preserves_children(self, db_session: Session, sample_workspace):
        """Test that replace mode on parent preserves child relationships."""
        parent_session_id = "parent-replace"
        agent_id = "agent-child"
        now = datetime.now(UTC)

        # Ingest parent
        parent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
            session_id=parent_session_id,
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Parent v1",
                    timestamp=now,
                )
            ],
        )
        parent_conv = ingest_conversation(db_session, parent_parsed)
        db_session.commit()
        original_parent_id = parent_conv.id

        # Ingest child agent
        agent_parsed = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now + timedelta(minutes=1),
            end_time=now + timedelta(minutes=2),
            session_id=agent_id,
            conversation_type="agent",
            parent_session_id=parent_session_id,
            agent_metadata={
                "agent_id": agent_id,
                "parent_session_id": parent_session_id,
            },
            messages=[
                ParsedMessage(
                    role="user",
                    content="Agent",
                    timestamp=now + timedelta(minutes=1),
                )
            ],
        )
        agent_conv = ingest_conversation(db_session, agent_parsed)
        db_session.commit()

        # Verify child is linked
        assert agent_conv.parent_conversation_id == original_parent_id

        # Replace parent conversation
        parent_parsed_v2 = ParsedConversation(
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=10),
            session_id=parent_session_id,
            conversation_type="main",
            messages=[
                ParsedMessage(
                    role="user",
                    content="Parent v2",
                    timestamp=now,
                ),
                ParsedMessage(
                    role="assistant",
                    content="Updated response",
                    timestamp=now + timedelta(seconds=1),
                ),
            ],
        )
        parent_conv_v2 = ingest_conversation(db_session, parent_parsed_v2, update_mode="replace")
        db_session.commit()

        # Parent ID should be same
        assert parent_conv_v2.id == original_parent_id

        # Child should still be linked to same parent
        db_session.refresh(agent_conv)
        assert agent_conv.parent_conversation_id == original_parent_id

        # Parent should still have child
        db_session.refresh(parent_conv_v2)
        assert len(parent_conv_v2.children) == 1
        assert parent_conv_v2.children[0].id == agent_conv.id
