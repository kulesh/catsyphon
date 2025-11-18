"""
Tests for database connection management.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from catsyphon.db.connection import (
    check_connection,
    get_db,
    get_session,
    init_db,
    transaction,
)
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

    def test_get_db_yields_session(self):
        """Test that get_db yields a session."""
        # Mock SessionLocal to avoid PostgreSQL dependency
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            # get_db() is a generator, use contextlib to make it a context manager

            gen = get_db()
            session = next(gen)

            assert session is mock_session

            # Close the generator
            try:
                next(gen)
            except StopIteration:
                pass

            # Verify session lifecycle
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_db_commits_on_success(self):
        """Test that get_db commits on successful context exit."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            gen = get_db()
            session = next(gen)
            # Simulate adding data
            session.add(MagicMock())

            # Close generator normally
            try:
                next(gen)
            except StopIteration:
                pass

            # Should commit on successful exit
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()
            mock_session.close.assert_called_once()

    def test_get_db_rollback_on_exception(self):
        """Test that get_db rolls back on exception."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            gen = get_db()
            _ = next(gen)  # Get session from generator

            try:
                # Simulate an error
                raise ValueError("Test error")
            except ValueError:
                # Send exception to generator
                try:
                    gen.throw(ValueError("Test error"))
                except ValueError:
                    pass

            # Should rollback on exception
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()
            mock_session.close.assert_called_once()

    def test_get_db_closes_session_always(self):
        """Test that get_db always closes session even on error."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            # Test with exception
            gen = get_db()
            _ = next(gen)  # Get session from generator
            try:
                gen.throw(RuntimeError("Error"))
            except RuntimeError:
                pass

            mock_session.close.assert_called_once()

            # Reset and test without exception
            mock_session.reset_mock()
            gen = get_db()
            _ = next(gen)  # Get session from generator
            try:
                next(gen)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()


class TestTransactionContextManager:
    """Tests for transaction context manager."""

    def test_transaction_yields_session(self):
        """Test that transaction yields a session."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            with transaction() as session:
                assert session is mock_session

            # Verify session lifecycle
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_transaction_commits_on_success(self):
        """Test that transaction commits on successful context exit."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            with transaction() as session:
                # Simulate transaction work
                session.add(MagicMock())

            # Should commit on successful exit
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()
            mock_session.close.assert_called_once()

    def test_transaction_rollback_on_error(self):
        """Test that transaction rolls back on error."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            try:
                with transaction():
                    # Simulate an error during transaction
                    raise RuntimeError("Transaction error")
            except RuntimeError:
                pass

            # Should rollback on exception
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()
            mock_session.close.assert_called_once()

    def test_transaction_closes_session_always(self):
        """Test that transaction always closes session."""
        mock_session = MagicMock(spec=Session)

        with patch("catsyphon.db.connection.SessionLocal", return_value=mock_session):
            # Test with exception
            try:
                with transaction():
                    raise ValueError("Error")
            except ValueError:
                pass

            mock_session.close.assert_called_once()

            # Reset and test without exception
            mock_session.reset_mock()
            with transaction():
                pass

            mock_session.close.assert_called_once()


class TestDatabaseOperations:
    """Tests for common database operations."""

    def test_create_and_retrieve(self, db_session: Session, sample_workspace):
        """Test basic create and retrieve operations."""
        project = Project(
            workspace_id=sample_workspace.id,
            name="Integration Test Project",
            description="Testing database operations",
            directory_path="/tmp/integration-test-project",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Retrieve
        retrieved = db_session.query(Project).filter_by(id=project.id).first()
        assert retrieved.name == "Integration Test Project"

    def test_update_record(self, db_session: Session, sample_workspace):
        """Test updating a record."""
        developer = Developer(
            workspace_id=sample_workspace.id,
            username="original_name",
            email="test@example.com",
        )
        db_session.add(developer)
        db_session.commit()
        db_session.refresh(developer)

        # Update
        developer.email = "updated@example.com"
        db_session.commit()

        # Verify
        db_session.refresh(developer)
        assert developer.email == "updated@example.com"

    def test_delete_record(self, db_session: Session, sample_workspace):
        """Test deleting a record."""
        project = Project(
            workspace_id=sample_workspace.id,
            name="To Be Deleted",
            directory_path="/tmp/to-be-deleted",
        )
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

    def test_query_filtering(self, db_session: Session, sample_workspace):
        """Test querying with filters."""
        # Create test data
        dev1 = Developer(
            workspace_id=sample_workspace.id,
            username="alice",
            email="alice@example.com",
        )
        dev2 = Developer(
            workspace_id=sample_workspace.id,
            username="bob",
            email="bob@example.com",
        )
        db_session.add_all([dev1, dev2])
        db_session.commit()

        # Query with filter
        alice = db_session.query(Developer).filter_by(username="alice").first()
        assert alice is not None
        assert alice.email == "alice@example.com"

    def test_query_ordering(self, db_session: Session, sample_workspace):
        """Test querying with ordering."""
        # Create projects
        for i in range(3):
            project = Project(
                workspace_id=sample_workspace.id,
                name=f"Project {i}",
                directory_path=f"/tmp/project-{i}",
            )
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
        with patch("catsyphon.db.connection.db_session") as mock_db_session:
            # Mock successful database connection
            mock_session = MagicMock()
            mock_session.execute.return_value = None
            mock_db_session.return_value.__enter__.return_value = mock_session

            result = check_connection()

            assert result is True
            mock_session.execute.assert_called_once()

    def test_check_connection_returns_false_on_failure(self):
        """Test that check_connection returns False when connection fails."""
        with patch("catsyphon.db.connection.db_session") as mock_db_session:
            # Mock failed database connection
            mock_db_session.return_value.__enter__.side_effect = Exception(
                "Connection failed"
            )

            result = check_connection()

            assert result is False
