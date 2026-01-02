"""
Database connection management for CatSyphon.

Provides database session management, connection handling, and transaction support.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from catsyphon.config import settings

# Create engine instance (singleton pattern)
if settings.database_url.startswith("sqlite"):
    from sqlalchemy import JSON, event
    from sqlalchemy.dialects import postgresql

    engine = create_engine(
        settings.database_url,
        echo=settings.environment == "development",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    from catsyphon.models.db import Base

    # Replace JSONB with JSON for SQLite compatibility
    @event.listens_for(Base.metadata, "before_create")
    def _set_json_type(target, connection, **kw):  # pragma: no cover - compat hook
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, postgresql.JSONB):
                    column.type = JSON()

else:
    # Connection pool settings optimized for multi-worker deployment:
    # With 8 uvicorn workers, each worker gets its own pool.
    # Total connections = workers × (pool_size + max_overflow)
    # To stay under PostgreSQL's max_connections (100), we use conservative settings:
    # 8 workers × (5 + 5) = 80 connections for API, leaves 20 for watch daemons/admin
    engine = create_engine(
        settings.database_url,
        echo=False,  # Disable SQL logging for performance
        pool_size=5,  # Base connections per worker (8 workers × 5 = 40)
        max_overflow=5,  # Extra connections per worker (8 workers × 5 = 40)
        pool_pre_ping=True,  # Verify connections before using
        pool_timeout=10,  # Faster timeout to fail fast
        pool_recycle=300,  # Recycle connections every 5 minutes to prevent stale connections
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Ensure tables exist for SQLite test runs (in-memory databases don't persist schema)
if settings.database_url.startswith("sqlite"):
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """
    Get a new database session.

    Returns:
        Session: A new SQLAlchemy session

    Example:
        >>> session = get_session()
        >>> try:
        >>>     # Use session
        >>>     session.commit()
        >>> except Exception:
        >>>     session.rollback()
        >>> finally:
        >>>     session.close()
    """
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database sessions with automatic cleanup.

    Yields:
        Session: A SQLAlchemy session

    Example (FastAPI):
        >>> @app.get("/users")
        >>> def get_users(db: Session = Depends(get_db)):
        >>>     return db.query(User).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Yields:
        Session: A SQLAlchemy session

    Example:
        >>> with db_session() as db:
        >>>     user = db.query(Developer).first()
        >>>     print(user.username)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transaction() -> Generator[Session, None, None]:
    """
    Context manager for explicit transaction handling.

    Yields:
        Session: A SQLAlchemy session with transaction support

    Example:
        >>> with transaction() as db:
        >>>     project = Project(name="My Project")
        >>>     db.add(project)
        >>>     # Commits automatically on success
        >>>     # Rolls back on exception
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Initialize the database.

    This function can be used to create tables programmatically,
    but in production we use Alembic migrations instead.

    Note:
        Prefer using Alembic migrations: `alembic upgrade head`
    """
    from catsyphon.models.db import Base

    Base.metadata.create_all(bind=engine)


def check_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection successful, False otherwise

    Example:
        >>> if check_connection():
        >>>     print("Database is accessible")
        >>> else:
        >>>     print("Cannot connect to database")
    """
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
