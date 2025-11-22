"""
Tests for project repository race condition fixes.

Tests that concurrent calls to get_or_create_by_directory don't cause
IntegrityError or create duplicate projects.

NOTE: Concurrent tests require PostgreSQL (they use pg_insert with ON CONFLICT).
The test suite uses SQLite by default, so concurrent tests are skipped.
Run with PostgreSQL database to test the race condition fix.
"""

import threading

import pytest

from catsyphon.db.repositories.project import ProjectRepository

# Mark for PostgreSQL-only tests
requires_postgresql = pytest.mark.skipif(
    True,  # Skip by default (test suite uses SQLite)
    reason="Requires PostgreSQL for ON CONFLICT DO NOTHING support"
)


class TestConcurrentProjectCreation:
    """Test concurrent project creation scenarios (PostgreSQL only)."""

    @requires_postgresql
    def test_concurrent_same_directory(self, db_session, sample_workspace):
        """Test that concurrent calls for same directory don't cause errors."""
        directory = "/test/concurrent/project"
        results = []
        errors = []

        def create_project():
            try:
                repo = ProjectRepository(db_session)
                project = repo.get_or_create_by_directory(directory, sample_workspace.id)
                db_session.flush()  # Flush to database
                results.append(project.id)
            except Exception as e:
                errors.append(e)

        # Spawn 10 concurrent threads attempting to create same project
        threads = [threading.Thread(target=create_project) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed (no IntegrityError)
        assert len(errors) == 0, f"Got errors: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # All threads should return the same project ID
        unique_ids = set(results)
        assert len(unique_ids) == 1, f"Created multiple projects: {results}"

        # Verify only one project exists in database
        repo = ProjectRepository(db_session)
        projects = repo.get_by_workspace(sample_workspace.id)
        # Note: sample_project fixture creates one project, so we expect 2 total
        project_directories = [p.directory_path for p in projects]
        assert directory in project_directories
        assert sum(1 for d in project_directories if d == directory) == 1, \
            f"Expected 1 project with directory {directory}, found: {project_directories}"

    @requires_postgresql
    def test_concurrent_different_directories(self, db_session, sample_workspace):
        """Test that concurrent calls for different directories work correctly."""
        directories = [f"/test/project/{i}" for i in range(5)]
        results = {d: [] for d in directories}
        errors = []

        def create_project(directory):
            try:
                repo = ProjectRepository(db_session)
                project = repo.get_or_create_by_directory(directory, sample_workspace.id)
                db_session.flush()
                results[directory].append(project.id)
            except Exception as e:
                errors.append(e)

        # Create 2 threads per directory (10 total threads)
        threads = []
        for directory in directories:
            for _ in range(2):
                t = threading.Thread(target=create_project, args=(directory,))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Got errors: {errors}"

        # Each directory should have exactly 1 unique project ID
        for directory, ids in results.items():
            assert len(ids) == 2, f"Expected 2 results for {directory}, got {len(ids)}"
            assert len(set(ids)) == 1, f"Multiple projects for {directory}: {ids}"

    def test_get_or_create_idempotency(self, db_session, sample_workspace):
        """Test that repeated calls return the same project."""
        directory = "/test/idempotent/project"

        # Create project first time
        repo = ProjectRepository(db_session)
        project1 = repo.get_or_create_by_directory(directory, sample_workspace.id)
        db_session.flush()
        project1_id = project1.id

        # Call get_or_create multiple times
        project_ids = []
        for _ in range(5):
            project = repo.get_or_create_by_directory(directory, sample_workspace.id)
            project_ids.append(project.id)

        # All calls should return the same project
        assert all(pid == project1_id for pid in project_ids), \
            f"Non-idempotent: {project_ids}"

    def test_custom_name_preserved(self, db_session, sample_workspace):
        """Test that custom project name is preserved."""
        directory = "/test/custom/name"
        custom_name = "My Custom Project"

        repo = ProjectRepository(db_session)
        project = repo.get_or_create_by_directory(
            directory, sample_workspace.id, name=custom_name
        )
        db_session.flush()
        assert project.name == custom_name

        # Subsequent calls should return same project (with original custom name)
        project = repo.get_or_create_by_directory(directory, sample_workspace.id)
        assert project.name == custom_name

    def test_auto_generated_names(self, db_session, sample_workspace):
        """Test that auto-generated project names work correctly."""
        test_paths = [
            ("/Users/kulesh/dev/mycatsyphon", "mycatsyphon"),
            ("/home/user/projects/myapp", "myapp"),
            ("/var/www/api", "api"),
        ]

        repo = ProjectRepository(db_session)
        for directory, expected_name in test_paths:
            project = repo.get_or_create_by_directory(directory, sample_workspace.id)
            db_session.flush()
            assert project.name == expected_name, \
                f"Expected '{expected_name}' for {directory}, got '{project.name}'"

    @requires_postgresql
    def test_concurrent_with_custom_names(self, db_session, sample_workspace):
        """Test concurrent creation with custom names."""
        directory = "/test/concurrent/custom"
        custom_name = "Concurrent Custom"
        results = []
        errors = []

        def create_project():
            try:
                repo = ProjectRepository(db_session)
                project = repo.get_or_create_by_directory(
                    directory, sample_workspace.id, name=custom_name
                )
                db_session.flush()
                results.append((project.id, project.name))
            except Exception as e:
                errors.append(e)

        # Spawn 5 concurrent threads
        threads = [threading.Thread(target=create_project) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0, f"Got errors: {errors}"

        # All should have same ID and name
        project_ids = [r[0] for r in results]
        project_names = [r[1] for r in results]

        assert len(set(project_ids)) == 1, f"Multiple projects created: {project_ids}"
        assert all(n == custom_name for n in project_names), \
            f"Name mismatch: {project_names}"

    @requires_postgresql
    def test_race_condition_stress_test(self, db_session, sample_workspace):
        """Stress test with many concurrent threads."""
        directory = "/test/stress/project"
        num_threads = 50
        results = []
        errors = []

        def create_project():
            try:
                repo = ProjectRepository(db_session)
                project = repo.get_or_create_by_directory(directory, sample_workspace.id)
                db_session.flush()
                results.append(project.id)
            except Exception as e:
                errors.append(e)

        # Spawn many concurrent threads
        threads = [threading.Thread(target=create_project) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed
        assert len(errors) == 0, f"Got {len(errors)} errors in stress test: {errors[:5]}"
        assert len(results) == num_threads

        # Only one unique project should exist
        assert len(set(results)) == 1, \
            f"Stress test created {len(set(results))} projects instead of 1"


class TestProjectRepositoryBasics:
    """Test basic project repository functionality."""

    def test_get_by_directory_existing(self, db_session, sample_workspace):
        """Test getting an existing project by directory."""
        directory = "/test/existing/project"

        # Create project
        repo = ProjectRepository(db_session)
        project1 = repo.create(
            workspace_id=sample_workspace.id,
            name="Test Project",
            directory_path=directory,
        )
        db_session.flush()
        project1_id = project1.id

        # Get by directory
        project2 = repo.get_by_directory(directory, sample_workspace.id)
        assert project2 is not None
        assert project2.id == project1_id

    def test_get_by_directory_nonexistent(self, db_session, sample_workspace):
        """Test getting a nonexistent project returns None."""
        repo = ProjectRepository(db_session)
        project = repo.get_by_directory("/nonexistent/path", sample_workspace.id)
        assert project is None
