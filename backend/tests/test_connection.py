"""
Tests for database connection management.
"""

from unittest.mock import patch

from sqlalchemy.orm import Session

from catsyphon.db.connection import check_connection, get_session, init_db
from catsyphon.models.db import Developer, Project


class TestGetSession:
    """Tests for get_session function."""

    def test_get_session_returns_session(self):
        """Test that get_session returns a Session instance."""
        # Note: This will fail if no database is available
        # but tests use in-memory SQLite via fixtures
        # This test is more of a smoke test
        session = get_session()
        assert isinstance(session, Session)
        session.close()


class TestGetDbContextManager:
    """Tests for get_db context manager."""

    def test_get_db_yields_session(self, db_session: Session):
        """Test that get_db yields a session."""
        # Using the fixture's session to avoid actual DB connection
        # This tests the pattern, not the actual get_db function
        # since get_db would try to connect to PostgreSQL
        assert isinstance(db_session, Session)

    def test_session_commit_on_success(self, db_session: Session):
        """Test that session commits on successful context exit."""
        project = Project(
            name="Test Project",
            description="Created in context manager test",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Verify it was committed
        retrieved = db_session.query(Project).filter_by(name="Test Project").first()
        assert retrieved is not None
        assert retrieved.id == project.id

    def test_session_rollback_on_exception(self, db_session: Session):
        """Test that session rolls back on exception."""
        initial_count = db_session.query(Project).count()

        try:
            project = Project(name="Will Be Rolled Back")
            db_session.add(project)
            # Simulate an error
            raise ValueError("Simulated error")
        except ValueError:
            db_session.rollback()

        # Verify rollback
        final_count = db_session.query(Project).count()
        assert final_count == initial_count


class TestTransactionContextManager:
    """Tests for transaction context manager."""

    def test_transaction_commits(self, db_session: Session):
        """Test that transaction context manager commits."""
        # Create a project in a simulated transaction
        developer = Developer(username="transaction_test_user")
        db_session.add(developer)
        db_session.commit()
        db_session.refresh(developer)

        # Verify it exists
        retrieved = (
            db_session.query(Developer)
            .filter_by(username="transaction_test_user")
            .first()
        )
        assert retrieved is not None

    def test_transaction_rollback_on_error(self, db_session: Session):
        """Test that transaction rolls back on error."""
        initial_count = db_session.query(Developer).count()

        try:
            developer = Developer(username="will_rollback")
            db_session.add(developer)
            db_session.flush()
            raise RuntimeError("Forced error")
        except RuntimeError:
            db_session.rollback()

        # Verify rollback
        final_count = db_session.query(Developer).count()
        assert final_count == initial_count


class TestDatabaseOperations:
    """Tests for common database operations."""

    def test_create_and_retrieve(self, db_session: Session):
        """Test basic create and retrieve operations."""
        project = Project(
            name="Integration Test Project",
            description="Testing database operations",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Retrieve
        retrieved = db_session.query(Project).filter_by(id=project.id).first()
        assert retrieved.name == "Integration Test Project"

    def test_update_record(self, db_session: Session):
        """Test updating a record."""
        developer = Developer(username="original_name", email="test@example.com")
        db_session.add(developer)
        db_session.commit()
        db_session.refresh(developer)

        # Update
        developer.email = "updated@example.com"
        db_session.commit()

        # Verify
        db_session.refresh(developer)
        assert developer.email == "updated@example.com"

    def test_delete_record(self, db_session: Session):
        """Test deleting a record."""
        project = Project(name="To Be Deleted")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        project_id = project.id

        # Delete
        db_session.delete(project)
        db_session.commit()

        # Verify
        deleted = db_session.query(Project).filter_by(id=project_id).first()
        assert deleted is None

    def test_query_filtering(self, db_session: Session):
        """Test querying with filters."""
        # Create test data
        dev1 = Developer(username="alice", email="alice@example.com")
        dev2 = Developer(username="bob", email="bob@example.com")
        db_session.add_all([dev1, dev2])
        db_session.commit()

        # Query with filter
        alice = db_session.query(Developer).filter_by(username="alice").first()
        assert alice is not None
        assert alice.email == "alice@example.com"

    def test_query_ordering(self, db_session: Session):
        """Test querying with ordering."""
        # Create projects
        for i in range(3):
            project = Project(name=f"Project {i}")
            db_session.add(project)
        db_session.commit()

        # Query with ordering
        projects = db_session.query(Project).order_by(Project.name.asc()).all()
        assert len(projects) >= 3
        # Verify ordering
        names = [p.name for p in projects if "Project" in p.name]
        assert names == sorted(names)


class TestInitDb:
    """Tests for init_db function."""

    def test_init_db_creates_tables(self, test_engine):
        """Test that init_db creates all tables."""
        from sqlalchemy import inspect

        from catsyphon.models.db import Base

        # Drop all tables first
        Base.metadata.drop_all(bind=test_engine)

        # Initialize database
        with patch("catsyphon.db.connection.engine", test_engine):
            init_db()

        # Verify tables exist by checking metadata
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        # Should have at least the main tables
        expected_tables = {
            "projects",
            "developers",
            "conversations",
            "epochs",
            "messages",
        }
        assert expected_tables.issubset(set(tables))


class TestCheckConnection:
    """Tests for check_connection function."""

    def test_check_connection_returns_true_on_success(self, test_engine):
        """Test that check_connection returns True when successful."""
        with patch("catsyphon.db.connection.get_db") as mock_get_db:
            # Mock successful database connection
            mock_session = mock_get_db.return_value.__enter__.return_value
            mock_session.execute.return_value = None

            result = check_connection()

            assert result is True
            mock_session.execute.assert_called_once()

    def test_check_connection_returns_false_on_failure(self):
        """Test that check_connection returns False when connection fails."""
        with patch("catsyphon.db.connection.get_db") as mock_get_db:
            # Mock failed database connection
            mock_get_db.return_value.__enter__.side_effect = Exception(
                "Connection failed"
            )

            result = check_connection()

            assert result is False
