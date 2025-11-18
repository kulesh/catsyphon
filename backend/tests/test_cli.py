"""
Tests for CLI commands.
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from catsyphon.cli import app

# Disable Rich formatting in tests using NO_COLOR environment variable
runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


class TestIngestCommand:
    """Tests for ingest command."""

    def test_ingest_requires_path_argument(self):
        """Test that ingest command requires path argument."""
        result = runner.invoke(app, ["ingest"])

        assert result.exit_code != 0

    def test_ingest_with_nonexistent_path_fails(self):
        """Test that ingest fails with nonexistent path."""
        result = runner.invoke(app, ["ingest", "/nonexistent/path", "--dry-run"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_ingest_single_file_dry_run(self):
        """Test ingesting a single file in dry-run mode."""
        # Create a minimal test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(app, ["ingest", temp_path, "--dry-run"])

            assert result.exit_code == 0
            assert "Successful: 1" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_directory_dry_run(self):
        """Test ingesting a directory in dry-run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test JSONL file
            test_file = Path(temp_dir) / "test.jsonl"
            test_file.write_text(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )

            result = runner.invoke(app, ["ingest", temp_dir, "--dry-run"])

            assert result.exit_code == 0
            assert "Found 1 file(s)" in result.stdout

    def test_ingest_empty_directory(self):
        """Test ingesting an empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(app, ["ingest", temp_dir, "--dry-run"])

            assert result.exit_code == 0
            assert "No .jsonl files found" in result.stdout

    def test_ingest_with_project_option(self):
        """Test ingest command with project option."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(
                app, ["ingest", temp_path, "--project", "myproject", "--dry-run"]
            )

            assert "Project: myproject" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_with_developer_option(self):
        """Test ingest command with developer option."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(
                app, ["ingest", temp_path, "--developer", "john", "--dry-run"]
            )

            assert "Developer: john" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_shows_summary_statistics(self):
        """Test that ingest shows summary statistics."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(app, ["ingest", temp_path, "--dry-run"])

            assert "Summary:" in result.stdout
            assert "Successful:" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_invalid_jsonl_file(self):
        """Test ingesting an invalid JSONL file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not valid json\n")
            temp_path = f.name

        try:
            result = runner.invoke(app, ["ingest", temp_path, "--dry-run"])

            # Should fail gracefully
            assert "Failed:" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_dry_run_no_database(self, db_session):
        """Test that dry-run mode doesn't persist to database."""
        from catsyphon.db.repositories import ConversationRepository

        @contextmanager
        def mock_get_db():
            yield db_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            # Get initial conversation count
            repo = ConversationRepository(db_session)
            initial_count = repo.count()

            # Run in dry-run mode (no database access expected)
            result = runner.invoke(app, ["ingest", temp_path, "--dry-run"])
            assert result.exit_code == 0

            # Verify no new conversations were created
            final_count = repo.count()

            assert final_count == initial_count  # No change
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_creates_database_records(self, db_session, sample_workspace):
        """Test that ingest creates database records."""
        from catsyphon.db.repositories import ConversationRepository

        @contextmanager
        def mock_db_session():
            yield db_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-db-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"DB Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
                '{"sessionId":"test-db-123","version":"2.0.17","type":"assistant",'
                '"message":{"role":"assistant","content":"Response"},"uuid":"msg-2",'
                '"timestamp":"2025-01-01T00:00:01Z"}\n'
            )
            temp_path = f.name

        try:
            # Get initial count for this workspace
            repo = ConversationRepository(db_session)
            initial_count = repo.count_by_workspace(sample_workspace.id)

            # Run ingestion (without dry-run) - mock db_session to use test session
            with patch("catsyphon.db.connection.db_session", mock_db_session):
                result = runner.invoke(
                    app,
                    [
                        "ingest",
                        temp_path,
                        "--project",
                        "cli-test-project",
                        "--developer",
                        "cli-test-user",
                    ],
                )

            assert result.exit_code == 0
            assert "✓ Stored" in result.stdout

            # Verify conversation was created
            final_count = repo.count_by_workspace(sample_workspace.id)

            # Should have one more conversation
            assert final_count == initial_count + 1

            # Get the conversation
            recent = repo.get_recent(sample_workspace.id, limit=1)
            assert len(recent) == 1

            conversation = recent[0]
            assert conversation.project.name == "cli-test-project"
            assert conversation.developer.username == "cli-test-user"
            assert len(conversation.messages) == 2

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_shows_conversation_id(self, db_session, sample_workspace):
        """Test that successful ingestion shows conversation ID."""

        @contextmanager
        def mock_db_session():
            yield db_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-id-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            # Mock db_session to use test session
            with patch("catsyphon.db.connection.db_session", mock_db_session):
                result = runner.invoke(
                    app, ["ingest", temp_path, "--project", "id-test"]
                )

            assert result.exit_code == 0
            assert "✓ Stored" in result.stdout
            assert "conversation=" in result.stdout

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_force_flag_shows_update_mode_replace(self):
        """Test that --force flag sets update_mode to replace."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(app, ["ingest", temp_path, "--force", "--dry-run"])

            assert result.exit_code == 0
            assert "Force: True" in result.stdout
            assert "Update mode: replace" in result.stdout
            assert "Skip duplicates: False" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_no_skip_duplicates_shows_deprecation_warning(self):
        """Test that --no-skip-duplicates shows deprecation warning."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            result = runner.invoke(
                app, ["ingest", temp_path, "--no-skip-duplicates", "--dry-run"]
            )

            assert result.exit_code == 0
            assert "deprecated" in result.stdout.lower()
            assert "Use --force instead" in result.stdout
            # Should still set update_mode to replace for backward compatibility
            assert "Update mode: replace" in result.stdout
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_ingest_force_calls_ingest_conversation_with_replace_mode(
        self, db_session, sample_workspace
    ):
        """Test that --force flag passes update_mode='replace' to ingest_conversation."""
        from catsyphon.pipeline.ingestion import ingest_conversation

        @contextmanager
        def mock_db_session():
            yield db_session

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                '{"sessionId":"test-force-123","version":"2.0.17","type":"user",'
                '"message":{"role":"user","content":"Test"},"uuid":"msg-1",'
                '"timestamp":"2025-01-01T00:00:00Z"}\n'
            )
            temp_path = f.name

        try:
            # Mock ingest_conversation to verify it's called with correct parameters
            with patch("catsyphon.db.connection.db_session", mock_db_session):
                with patch(
                    "catsyphon.pipeline.ingestion.ingest_conversation"
                ) as mock_ingest:
                    # Setup mock to return a minimal conversation object
                    mock_conv = Mock()
                    mock_conv.id = "conv-123"
                    mock_ingest.return_value = mock_conv

                    result = runner.invoke(app, ["ingest", temp_path, "--force"])

                    assert result.exit_code == 0

                    # Verify ingest_conversation was called with update_mode='replace'
                    assert mock_ingest.called
                    call_kwargs = mock_ingest.call_args.kwargs
                    assert call_kwargs["update_mode"] == "replace"
                    assert call_kwargs["skip_duplicates"] is False

        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestServeCommand:
    """Tests for serve command."""

    @patch("uvicorn.run")
    def test_serve_command_starts_server(self, mock_run: Mock):
        """Test that serve command starts uvicorn server."""
        runner.invoke(app, ["serve"])

        # Command should attempt to start server
        mock_run.assert_called_once()

    @patch("uvicorn.run")
    def test_serve_with_custom_host(self, mock_run: Mock):
        """Test serve command with custom host."""
        runner.invoke(app, ["serve", "--host", "127.0.0.1"])

        args, kwargs = mock_run.call_args
        assert kwargs.get("host") == "127.0.0.1"

    @patch("uvicorn.run")
    def test_serve_with_custom_port(self, mock_run: Mock):
        """Test serve command with custom port."""
        runner.invoke(app, ["serve", "--port", "9000"])

        args, kwargs = mock_run.call_args
        assert kwargs.get("port") == 9000

    @patch("uvicorn.run")
    def test_serve_with_reload_enabled(self, mock_run: Mock):
        """Test serve command with reload enabled."""
        runner.invoke(app, ["serve", "--reload"])

        args, kwargs = mock_run.call_args
        assert kwargs.get("reload") is True


class TestCLIHelp:
    """Tests for CLI help functionality."""

    def test_no_args_shows_help(self):
        """Test that running with no args shows help."""
        result = runner.invoke(app, [])

        # Should show help message
        assert "CatSyphon" in result.stdout or "Usage" in result.stdout

    def test_help_flag_works(self):
        """Test that --help flag works."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "CatSyphon" in result.stdout or "Usage" in result.stdout

    def test_ingest_help_shows_options(self):
        """Test that ingest --help shows all options."""
        result = runner.invoke(app, ["ingest", "--help"])

        assert result.exit_code == 0
        assert "--project" in result.stdout
        assert "--developer" in result.stdout
        assert "--dry-run" in result.stdout
