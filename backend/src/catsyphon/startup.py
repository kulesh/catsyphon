"""
Startup dependency checks for CatSyphon backend.

Validates critical dependencies before the application starts serving requests.
Fails fast with clear, actionable error messages when requirements aren't met.
"""

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from catsyphon.config import settings
from catsyphon.db.connection import SessionLocal, engine


@dataclass
class StartupMetrics:
    """Metrics collected during startup checks."""

    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    environment_check_ms: Optional[float] = None
    database_check_ms: Optional[float] = None
    migrations_check_ms: Optional[float] = None
    openai_check_ms: Optional[float] = None
    cache_check_ms: Optional[float] = None
    checks_passed: bool = False
    last_check_time: Optional[datetime] = None


# Global startup metrics (populated during startup)
startup_metrics = StartupMetrics(started_at=datetime.now(timezone.utc))


class StartupCheckError(Exception):
    """Raised when a critical startup check fails."""

    def __init__(self, message: str, hint: Optional[str] = None):
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        error_msg = f"\n{'='*70}\n❌ STARTUP CHECK FAILED\n{'='*70}\n\n{self.message}\n"
        if self.hint:
            error_msg += f"\n💡 Hint: {self.hint}\n"
        error_msg += f"{'='*70}\n"
        return error_msg


def check_database_connection() -> None:
    """
    Verify PostgreSQL database is accessible and responsive.

    Raises:
        StartupCheckError: If database connection fails
    """
    try:
        # Attempt to create a connection and execute a simple query
        with SessionLocal() as session:
            result = session.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise StartupCheckError(
                    "Database query returned unexpected result",
                    "Database may be corrupted or misconfigured",
                )
    except StartupCheckError:
        raise
    except Exception as e:
        # Determine specific error type for helpful messages
        error_str = str(e).lower()

        if "could not connect" in error_str or "connection refused" in error_str:
            hint = (
                "PostgreSQL is not running.\n"
                "  - Start with Docker: docker-compose up -d\n"
                "  - Or check Colima status: colima status"
            )
        elif "authentication failed" in error_str or "password" in error_str:
            hint = (
                "Database authentication failed.\n"
                "  - Check credentials in .env file\n"
                f"  - Current user: {settings.postgres_user}\n"
                f"  - Current database: {settings.postgres_db}"
            )
        elif "database" in error_str and "does not exist" in error_str:
            hint = (
                f"Database '{settings.postgres_db}' does not exist.\n"
                "  - Create it: createdb {settings.postgres_db}\n"
                "  - Or run migrations: alembic upgrade head"
            )
        elif "timeout" in error_str or "timed out" in error_str:
            hint = (
                "Database connection timed out.\n"
                "  - Check if PostgreSQL is running\n"
                "  - Verify network connectivity\n"
                f"  - Current host: {settings.postgres_host}:{settings.postgres_port}"
            )
        else:
            hint = f"Check your database configuration in .env\nError: {str(e)}"

        raise StartupCheckError(
            f"Cannot connect to PostgreSQL database\n"
            f"Host: {settings.postgres_host}:{settings.postgres_port}\n"
            f"Database: {settings.postgres_db}\n"
            f"User: {settings.postgres_user}",
            hint,
        ) from e


def check_database_migrations() -> None:
    """
    Verify Alembic database migrations are current.

    Raises:
        StartupCheckError: If pending migrations exist
    """
    try:
        # Get Alembic configuration
        alembic_cfg = AlembicConfig("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)

        # Get current head revision from migration scripts
        head_revision = script.get_current_head()

        # Get current revision from database
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()

        if current_revision is None:
            raise StartupCheckError(
                "Database has no migration version\n" "Database appears uninitialized",
                "Run migrations: alembic upgrade head",
            )

        if current_revision != head_revision:
            # Get list of pending migrations
            pending = []
            for rev in script.iterate_revisions(head_revision, current_revision):
                if rev.revision != current_revision:
                    pending.append(f"  - {rev.revision[:8]}: {rev.doc}")

            pending_list = "\n".join(pending) if pending else "Unknown"

            raise StartupCheckError(
                f"Database migrations are out of date\n"
                f"Current revision: {current_revision[:8] if current_revision else 'None'}\n"
                f"Expected revision: {head_revision[:8] if head_revision else 'None'}\n"
                f"\nPending migrations:\n{pending_list}",
                "Run: alembic upgrade head",
            )

    except StartupCheckError:
        raise
    except FileNotFoundError:
        raise StartupCheckError(
            "Alembic configuration not found",
            "Ensure alembic.ini exists in the project root",
        )
    except Exception as e:
        raise StartupCheckError(
            f"Failed to check migration status: {str(e)}",
            "Verify Alembic is properly configured",
        ) from e


def check_required_environment() -> None:
    """
    Validate required environment variables are set.

    Raises:
        StartupCheckError: If critical environment variables are missing
    """
    missing = []

    # Check critical database settings
    if not settings.postgres_host:
        missing.append("POSTGRES_HOST")
    if not settings.postgres_db:
        missing.append("POSTGRES_DB")
    if not settings.postgres_user:
        missing.append("POSTGRES_USER")
    if not settings.postgres_password:
        missing.append("POSTGRES_PASSWORD")

    if missing:
        raise StartupCheckError(
            "Missing required environment variables:\n"
            + "\n".join(f"  - {var}" for var in missing),
            "Set these variables in your .env file",
        )


def check_openai_configuration() -> None:
    """Validate configured analytics LLM provider and model availability."""
    if not settings.llm_configured:
        print(
            "  ⚠️  SKIP (LLM provider not configured - analytics features disabled)"
        )
        return

    try:
        from catsyphon.llm import create_llm_client

        client = create_llm_client(settings)
        model = settings.active_llm_model
        if not model:
            raise StartupCheckError(
                f"LLM model is required for provider '{settings.active_llm_provider}'",
                "Set LLM_MODEL in .env",
            )

        client.health_check(model=model)
    except StartupCheckError:
        raise
    except Exception as e:
        raise StartupCheckError(
            (
                "LLM provider validation failed "
                f"({settings.active_llm_provider}/{settings.active_llm_model}): {e}"
            ),
            (
                f"Verify {settings.required_llm_api_key_env()} and LLM_MODEL "
                "settings"
            ),
        ) from e


def check_cache_directory() -> None:
    """
    Validate cache directory exists and is writable.

    Creates directory if it doesn't exist. Follows XDG Base Directory Specification.

    Raises:
        StartupCheckError: If cache directory cannot be created or is not writable
    """
    from pathlib import Path

    cache_dir = Path(settings.tagging_cache_dir)

    try:
        # Create directory if it doesn't exist (including parent directories)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions by creating a unique test file
        # Use PID to avoid race conditions with parallel processes
        test_file = cache_dir / f".write_test_{os.getpid()}"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Clean up test file
        except FileNotFoundError:
            pass  # Another process may have cleaned it up, that's OK
        except PermissionError:
            raise StartupCheckError(
                f"Cache directory exists but is not writable: {cache_dir}",
                f"Fix permissions: chmod u+w {cache_dir}",
            )

    except PermissionError as e:
        raise StartupCheckError(
            f"Cannot create cache directory: {cache_dir}\n"
            f"Permission denied: {str(e)}",
            f"Create directory manually: mkdir -p {cache_dir}\n"
            f"  Or check parent directory permissions",
        ) from e
    except OSError as e:
        raise StartupCheckError(
            f"Failed to create cache directory: {cache_dir}\n" f"Error: {str(e)}",
            "Check filesystem and parent directory permissions",
        ) from e
    except Exception as e:
        raise StartupCheckError(
            f"Unexpected error checking cache directory: {str(e)}",
            f"Verify TAGGING_CACHE_DIR setting: {cache_dir}",
        ) from e


def run_all_startup_checks() -> None:
    """
    Execute all startup dependency checks.

    Runs checks in order of dependency:
    1. Environment variables
    2. Database connection
    3. Database migrations
    4. Cache directory (XDG-compliant)
    5. LLM provider configuration (optional)

    Tracks timing metrics for each check.

    Raises:
        StartupCheckError: If any critical check fails
        SystemExit: After logging the error
    """
    global startup_metrics
    startup_start = time.time()

    checks = [
        ("Environment Variables", check_required_environment, "environment_check_ms"),
        ("Database Connection", check_database_connection, "database_check_ms"),
        ("Database Migrations", check_database_migrations, "migrations_check_ms"),
        ("Cache Directory", check_cache_directory, "cache_check_ms"),
        ("LLM Provider Configuration", check_openai_configuration, "openai_check_ms"),
    ]

    print("\n" + "=" * 70)
    print("🚀 Starting CatSyphon Backend - Running Startup Checks")
    print("=" * 70 + "\n")

    for check_name, check_func, metric_name in checks:
        try:
            print(f"  Checking {check_name}...", end=" ", flush=True)
            check_start = time.time()
            check_func()
            check_duration = (time.time() - check_start) * 1000  # Convert to ms
            setattr(startup_metrics, metric_name, check_duration)
            print(f"✅ PASS ({check_duration:.1f}ms)")
        except StartupCheckError as e:
            check_duration = (time.time() - check_start) * 1000
            setattr(startup_metrics, metric_name, check_duration)
            print(f"❌ FAIL ({check_duration:.1f}ms)")
            print(str(e))
            sys.exit(1)

    # Record successful completion
    startup_metrics.completed_at = datetime.now(timezone.utc)
    startup_metrics.total_duration_ms = (time.time() - startup_start) * 1000
    startup_metrics.checks_passed = True
    startup_metrics.last_check_time = datetime.now(timezone.utc)

    print("\n" + "=" * 70)
    print(
        f"✅ All startup checks passed - Server is ready ({startup_metrics.total_duration_ms:.1f}ms)"
    )
    print("=" * 70 + "\n")


def check_readiness() -> tuple[bool, dict]:
    """
    Quick readiness check for Kubernetes/load balancer probes.

    Returns:
        tuple: (is_ready: bool, details: dict) where details contains:
            - ready: bool
            - database: str (healthy/unhealthy)
            - startup_completed: bool
            - startup_metrics: dict with timing information
            - uptime_seconds: float
    """
    # Quick database ping (with timeout)
    db_ready = False
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            db_ready = True
    except Exception:
        db_ready = False

    # Calculate uptime
    uptime = (datetime.now(timezone.utc) - startup_metrics.started_at).total_seconds()

    # Build response
    ready = startup_metrics.checks_passed and db_ready
    details = {
        "ready": ready,
        "database": "healthy" if db_ready else "unhealthy",
        "startup_completed": startup_metrics.checks_passed,
        "uptime_seconds": uptime,
        "startup_metrics": {
            "total_duration_ms": startup_metrics.total_duration_ms,
            "environment_check_ms": startup_metrics.environment_check_ms,
            "database_check_ms": startup_metrics.database_check_ms,
            "migrations_check_ms": startup_metrics.migrations_check_ms,
            "started_at": startup_metrics.started_at.isoformat() + "Z",
            "completed_at": (
                startup_metrics.completed_at.isoformat() + "Z"
                if startup_metrics.completed_at
                else None
            ),
            "last_check_time": (
                startup_metrics.last_check_time.isoformat() + "Z"
                if startup_metrics.last_check_time
                else None
            ),
        },
    }

    return ready, details
