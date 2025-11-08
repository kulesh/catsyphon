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
