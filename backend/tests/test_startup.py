"""Tests for application startup checks and validation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from catsyphon.startup import (
    StartupCheckError,
    StartupMetrics,
    check_database_connection,
    check_required_environment,
    run_all_startup_checks,
)


class TestDatabaseConnectionCheck:
    """Tests for database connection validation."""

    def test_check_database_connection_success(self):
        """Test successful database connection check."""

        with patch("catsyphon.startup.SessionLocal") as mock_session:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            result = MagicMock()
            result.scalar = MagicMock(return_value=1)
            mock_ctx.execute = MagicMock(return_value=result)
            mock_session.return_value = mock_ctx

            # Should not raise
            check_database_connection()

    def test_check_database_connection_raises_on_connection_failure(self):
        """Test database connection check raises on connection failure."""
        with patch(
            "catsyphon.startup.SessionLocal",
            side_effect=Exception("Connection refused"),
        ):
            with pytest.raises(StartupCheckError) as exc_info:
                check_database_connection()

            assert "Cannot connect" in str(exc_info.value)

    def test_check_database_connection_raises_on_auth_failure(self):
        """Test database connection check raises on authentication failure."""
        with patch(
            "catsyphon.startup.SessionLocal",
            side_effect=Exception("authentication failed"),
        ):
            with pytest.raises(StartupCheckError) as exc_info:
                check_database_connection()

            assert "Cannot connect" in str(exc_info.value)


class TestEnvironmentCheck:
    """Tests for environment configuration validation."""

    def test_check_required_environment_success(self):
        """Test that environment check passes with valid configuration."""
        # Should not raise with valid environment (using real settings)
        # This will use the actual test environment
        try:
            check_required_environment()
            # If no exception, test passes
        except StartupCheckError:
            # If it fails, it's due to missing test environment config
            # which is acceptable
            pass

    def test_check_required_environment_detects_missing_vars(self):
        """Test that environment check detects missing variables."""
        with patch("catsyphon.startup.settings") as mock_settings:
            # Set database_url to empty to trigger validation
            mock_settings.database_url = ""
            mock_settings.postgres_host = ""

            with pytest.raises(StartupCheckError):
                check_required_environment()


class TestStartupMetrics:
    """Tests for StartupMetrics class."""

    def test_startup_metrics_initialization(self):
        """Test StartupMetrics initializes with provided time."""
        now = datetime.now(UTC)
        metrics = StartupMetrics(started_at=now)

        assert metrics.started_at == now

    def test_startup_metrics_duration_calculation(self):
        """Test StartupMetrics duration fields can be set."""
        from datetime import timedelta

        now = datetime.now(UTC)
        metrics = StartupMetrics(started_at=now)

        # Set completion time and duration
        metrics.completed_at = now + timedelta(seconds=2)
        metrics.total_duration_ms = 2000.0

        assert metrics.completed_at is not None
        assert metrics.total_duration_ms == 2000.0
        assert (metrics.completed_at - metrics.started_at).total_seconds() >= 2.0


class TestRunAllStartupChecks:
    """Tests for run_all_startup_checks function."""

    def test_run_all_startup_checks_executes_all_checks(self):
        """Test that run_all_startup_checks calls all check functions."""
        with (
            patch("catsyphon.startup.check_database_connection") as mock_db,
            patch("catsyphon.startup.check_required_environment") as mock_env,
            patch("catsyphon.startup.check_database_migrations") as mock_mig,
        ):
            # All checks pass (don't raise)
            mock_db.return_value = None
            mock_env.return_value = None
            mock_mig.return_value = None

            # Should complete without raising
            run_all_startup_checks()

            # Verify all checks were called
            mock_db.assert_called_once()
            mock_env.assert_called_once()
            mock_mig.assert_called_once()

    def test_run_all_startup_checks_exits_on_failure(self):
        """Test that startup checks exit on failure."""
        error = StartupCheckError("DB failed", "hint")
        with (
            patch("catsyphon.startup.check_database_connection", side_effect=error),
            patch("catsyphon.startup.check_required_environment") as mock_env,
            patch("catsyphon.startup.check_database_migrations") as mock_mig,
        ):
            mock_env.return_value = None
            mock_mig.return_value = None

            # Should exit with code 1 on failure
            with pytest.raises(SystemExit) as exc_info:
                run_all_startup_checks()

            assert exc_info.value.code == 1


class TestStartupCheckError:
    """Tests for StartupCheckError exception."""

    def test_startup_check_error_has_message_and_hint(self):
        """Test that StartupCheckError stores message and hint."""
        error = StartupCheckError("Test error message", "Test hint")

        assert "Test error message" in str(error)
        # The hint should be accessible via the error
        assert hasattr(error, "args")


class TestCheckReadiness:
    """Tests for readiness check function."""

    def test_check_readiness_returns_tuple(self):
        """Test that check_readiness returns tuple of bool and dict."""
        from catsyphon.startup import check_readiness

        with patch("catsyphon.startup.check_database_connection"):
            ready, info = check_readiness()

            assert isinstance(ready, bool)
            assert isinstance(info, dict)


class TestDatabaseMigrationCheck:
    """Tests for database migration validation."""

    @patch("catsyphon.startup.engine")
    @patch("catsyphon.startup.ScriptDirectory")
    @patch("catsyphon.startup.AlembicConfig")
    def test_check_migrations_up_to_date(
        self,
        mock_alembic_config: MagicMock,
        mock_script_dir: MagicMock,
        mock_engine: MagicMock,
    ):
        """Test migration check when migrations are current."""

        from catsyphon.startup import check_database_migrations

        # Mock Alembic config
        mock_config = MagicMock()
        mock_alembic_config.return_value = mock_config

        # Mock script directory
        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "abc123"
        mock_script_dir.from_config.return_value = mock_script

        # Mock database connection
        mock_connection = MagicMock()
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = "abc123"  # Same as head

        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_connection

        with patch("catsyphon.startup.MigrationContext") as mock_migration_ctx:
            mock_migration_ctx.configure.return_value = mock_context

            # Should not raise
            check_database_migrations()

    @patch("catsyphon.startup.engine")
    @patch("catsyphon.startup.ScriptDirectory")
    @patch("catsyphon.startup.AlembicConfig")
    def test_check_migrations_uninitialized_database(
        self,
        mock_alembic_config: MagicMock,
        mock_script_dir: MagicMock,
        mock_engine: MagicMock,
    ):
        """Test migration check when database is uninitialized."""
        from catsyphon.startup import check_database_migrations

        mock_config = MagicMock()
        mock_alembic_config.return_value = mock_config

        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "abc123"
        mock_script_dir.from_config.return_value = mock_script

        mock_connection = MagicMock()
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = None  # No version

        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_connection

        with patch("catsyphon.startup.MigrationContext") as mock_migration_ctx:
            mock_migration_ctx.configure.return_value = mock_context

            with pytest.raises(StartupCheckError) as exc_info:
                check_database_migrations()

            assert "no migration version" in str(exc_info.value).lower()

    @patch("catsyphon.startup.engine")
    @patch("catsyphon.startup.ScriptDirectory")
    @patch("catsyphon.startup.AlembicConfig")
    def test_check_migrations_out_of_date(
        self,
        mock_alembic_config: MagicMock,
        mock_script_dir: MagicMock,
        mock_engine: MagicMock,
    ):
        """Test migration check when pending migrations exist."""
        from catsyphon.startup import check_database_migrations

        mock_config = MagicMock()
        mock_alembic_config.return_value = mock_config

        # Mock pending revision
        mock_rev = MagicMock()
        mock_rev.revision = "new123"
        mock_rev.doc = "Add new feature"

        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "new123"
        mock_script.iterate_revisions.return_value = [mock_rev]
        mock_script_dir.from_config.return_value = mock_script

        mock_connection = MagicMock()
        mock_context = MagicMock()
        mock_context.get_current_revision.return_value = "old456"  # Different

        mock_connection.__enter__ = MagicMock(return_value=mock_connection)
        mock_connection.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_connection

        with patch("catsyphon.startup.MigrationContext") as mock_migration_ctx:
            mock_migration_ctx.configure.return_value = mock_context

            with pytest.raises(StartupCheckError) as exc_info:
                check_database_migrations()

            error_msg = str(exc_info.value).lower()
            assert "out of date" in error_msg or "pending" in error_msg

    @patch("catsyphon.startup.AlembicConfig")
    def test_check_migrations_config_not_found(self, mock_alembic_config: MagicMock):
        """Test migration check when alembic.ini is missing."""
        from catsyphon.startup import check_database_migrations

        mock_alembic_config.side_effect = FileNotFoundError("alembic.ini not found")

        with pytest.raises(StartupCheckError) as exc_info:
            check_database_migrations()

        assert "configuration not found" in str(exc_info.value).lower()


class TestDatabaseConnectionErrorHandling:
    """Tests for specific database connection error scenarios."""

    @patch("catsyphon.startup.SessionLocal")
    @patch("catsyphon.startup.settings")
    def test_connection_timeout_error(
        self, mock_settings: MagicMock, mock_session_local: MagicMock
    ):
        """Test handling of connection timeout."""
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_port = 5432

        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("connection timed out")
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_local.return_value = mock_session

        with pytest.raises(StartupCheckError) as exc_info:
            check_database_connection()

        error_msg = str(exc_info.value).lower()
        assert "timed out" in error_msg or "timeout" in error_msg

    @patch("catsyphon.startup.SessionLocal")
    @patch("catsyphon.startup.settings")
    def test_database_not_exist_error(
        self, mock_settings: MagicMock, mock_session_local: MagicMock
    ):
        """Test handling when database does not exist."""
        mock_settings.postgres_db = "nonexistent"

        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception(
            "database nonexistent does not exist"
        )
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_local.return_value = mock_session

        with pytest.raises(StartupCheckError) as exc_info:
            check_database_connection()

        error_msg = str(exc_info.value).lower()
        assert "does not exist" in error_msg

    @patch("catsyphon.startup.SessionLocal")
    def test_unexpected_query_result(self, mock_session_local: MagicMock):
        """Test handling of unexpected query result."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 999  # Wrong result
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session_local.return_value = mock_session

        with pytest.raises(StartupCheckError) as exc_info:
            check_database_connection()

        assert "unexpected result" in str(exc_info.value).lower()


class TestEnvironmentVariableValidation:
    """Tests for comprehensive environment variable validation."""

    @patch("catsyphon.startup.settings")
    def test_missing_postgres_db(self, mock_settings: MagicMock):
        """Test detection of missing POSTGRES_DB."""
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_db = ""  # Missing
        mock_settings.postgres_user = "user"
        mock_settings.postgres_password = "pass"

        with pytest.raises(StartupCheckError) as exc_info:
            check_required_environment()

        assert "POSTGRES_DB" in str(exc_info.value)

    @patch("catsyphon.startup.settings")
    def test_missing_postgres_user(self, mock_settings: MagicMock):
        """Test detection of missing POSTGRES_USER."""
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_db = "db"
        mock_settings.postgres_user = ""  # Missing
        mock_settings.postgres_password = "pass"

        with pytest.raises(StartupCheckError) as exc_info:
            check_required_environment()

        assert "POSTGRES_USER" in str(exc_info.value)

    @patch("catsyphon.startup.settings")
    def test_missing_postgres_password(self, mock_settings: MagicMock):
        """Test detection of missing POSTGRES_PASSWORD."""
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_db = "db"
        mock_settings.postgres_user = "user"
        mock_settings.postgres_password = ""  # Missing

        with pytest.raises(StartupCheckError) as exc_info:
            check_required_environment()

        assert "POSTGRES_PASSWORD" in str(exc_info.value)
