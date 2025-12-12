"""
Tests for developer repository race condition fixes.

Tests that concurrent calls to get_or_create don't cause
IntegrityError or create duplicate developers.

NOTE: Concurrent tests require PostgreSQL (they use pg_insert with ON CONFLICT).
The test suite uses SQLite by default, so concurrent tests are skipped.
Run with PostgreSQL database to test the race condition fix.
"""

import threading

import pytest

from catsyphon.db.repositories.developer import DeveloperRepository

# Mark for PostgreSQL-only tests
requires_postgresql = pytest.mark.skipif(
    True,  # Skip by default (test suite uses SQLite)
    reason="Requires PostgreSQL for ON CONFLICT DO NOTHING support",
)


class TestConcurrentDeveloperCreation:
    """Test concurrent developer creation scenarios (PostgreSQL only)."""

    @requires_postgresql
    def test_concurrent_same_username(self, db_session, sample_workspace):
        """Test that concurrent calls for same username don't cause errors."""
        username = "concurrent_dev"
        results = []
        errors = []

        def create_developer():
            try:
                repo = DeveloperRepository(db_session)
                developer = repo.get_or_create(username, sample_workspace.id)
                db_session.flush()  # Flush to database
                results.append(developer.id)
            except Exception as e:
                errors.append(e)

        # Spawn 10 concurrent threads attempting to create same developer
        threads = [threading.Thread(target=create_developer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed (no IntegrityError)
        assert len(errors) == 0, f"Got errors: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # All threads should return the same developer ID
        unique_ids = set(results)
        assert len(unique_ids) == 1, f"Created multiple developers: {results}"

        # Verify only one developer exists in database
        repo = DeveloperRepository(db_session)
        developers = repo.get_by_workspace(sample_workspace.id)
        developer_usernames = [d.username for d in developers]
        assert username in developer_usernames
        assert (
            sum(1 for u in developer_usernames if u == username) == 1
        ), f"Expected 1 developer with username {username}, found: {developer_usernames}"

    @requires_postgresql
    def test_concurrent_different_usernames(self, db_session, sample_workspace):
        """Test that concurrent calls for different usernames work correctly."""
        usernames = [f"dev_{i}" for i in range(5)]
        results = {u: [] for u in usernames}
        errors = []

        def create_developer(username):
            try:
                repo = DeveloperRepository(db_session)
                developer = repo.get_or_create(username, sample_workspace.id)
                db_session.flush()
                results[username].append(developer.id)
            except Exception as e:
                errors.append(e)

        # Create 2 threads per username (10 total threads)
        threads = []
        for username in usernames:
            for _ in range(2):
                t = threading.Thread(target=create_developer, args=(username,))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Got errors: {errors}"

        # Each username should have exactly 1 unique developer ID
        for username, ids in results.items():
            assert len(ids) == 2, f"Expected 2 results for {username}, got {len(ids)}"
            assert len(set(ids)) == 1, f"Multiple developers for {username}: {ids}"

    def test_get_or_create_idempotency(self, db_session, sample_workspace):
        """Test that repeated calls return the same developer."""
        username = "idempotent_dev"

        # Create developer first time
        repo = DeveloperRepository(db_session)
        developer1 = repo.get_or_create(username, sample_workspace.id)
        db_session.flush()
        developer1_id = developer1.id

        # Call get_or_create multiple times
        developer_ids = []
        for _ in range(5):
            developer = repo.get_or_create(username, sample_workspace.id)
            developer_ids.append(developer.id)

        # All calls should return the same developer
        assert all(
            did == developer1_id for did in developer_ids
        ), f"Non-idempotent: {developer_ids}"

    def test_custom_email_preserved(self, db_session, sample_workspace):
        """Test that custom email is preserved."""
        username = "custom_email_dev"
        custom_email = "custom@example.com"

        repo = DeveloperRepository(db_session)
        developer = repo.get_or_create(
            username, sample_workspace.id, email=custom_email
        )
        db_session.flush()
        assert developer.email == custom_email

        # Subsequent calls should return same developer (with original custom email)
        developer = repo.get_or_create(username, sample_workspace.id)
        assert developer.email == custom_email

    def test_get_or_create_by_username_alias(self, db_session, sample_workspace):
        """Test that get_or_create_by_username is an alias for get_or_create."""
        username = "alias_dev"

        repo = DeveloperRepository(db_session)
        developer1 = repo.get_or_create(username, sample_workspace.id)
        db_session.flush()
        developer1_id = developer1.id

        # Call alias method
        developer2 = repo.get_or_create_by_username(username, sample_workspace.id)
        assert developer2.id == developer1_id

    @requires_postgresql
    def test_concurrent_with_custom_email(self, db_session, sample_workspace):
        """Test concurrent creation with custom email."""
        username = "concurrent_email_dev"
        custom_email = "concurrent@example.com"
        results = []
        errors = []

        def create_developer():
            try:
                repo = DeveloperRepository(db_session)
                developer = repo.get_or_create(
                    username, sample_workspace.id, email=custom_email
                )
                db_session.flush()
                results.append((developer.id, developer.email))
            except Exception as e:
                errors.append(e)

        # Spawn 5 concurrent threads
        threads = [threading.Thread(target=create_developer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0, f"Got errors: {errors}"

        # All should have same ID and email
        developer_ids = [r[0] for r in results]
        developer_emails = [r[1] for r in results]

        assert (
            len(set(developer_ids)) == 1
        ), f"Multiple developers created: {developer_ids}"
        assert all(
            e == custom_email for e in developer_emails
        ), f"Email mismatch: {developer_emails}"

    @requires_postgresql
    def test_race_condition_stress_test(self, db_session, sample_workspace):
        """Stress test with many concurrent threads."""
        username = "stress_dev"
        num_threads = 50
        results = []
        errors = []

        def create_developer():
            try:
                repo = DeveloperRepository(db_session)
                developer = repo.get_or_create(username, sample_workspace.id)
                db_session.flush()
                results.append(developer.id)
            except Exception as e:
                errors.append(e)

        # Spawn many concurrent threads
        threads = [
            threading.Thread(target=create_developer) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed
        assert (
            len(errors) == 0
        ), f"Got {len(errors)} errors in stress test: {errors[:5]}"
        assert len(results) == num_threads

        # Only one unique developer should exist
        assert (
            len(set(results)) == 1
        ), f"Stress test created {len(set(results))} developers instead of 1"


class TestDeveloperRepositoryBasics:
    """Test basic developer repository functionality."""

    def test_get_by_username_existing(self, db_session, sample_workspace):
        """Test getting an existing developer by username."""
        username = "existing_dev"

        # Create developer
        repo = DeveloperRepository(db_session)
        developer1 = repo.create(
            workspace_id=sample_workspace.id,
            username=username,
        )
        db_session.flush()
        developer1_id = developer1.id

        # Get by username
        developer2 = repo.get_by_username(username, sample_workspace.id)
        assert developer2 is not None
        assert developer2.id == developer1_id

    def test_get_by_username_nonexistent(self, db_session, sample_workspace):
        """Test getting a nonexistent developer returns None."""
        repo = DeveloperRepository(db_session)
        developer = repo.get_by_username("nonexistent", sample_workspace.id)
        assert developer is None

    def test_get_by_email(self, db_session, sample_workspace):
        """Test getting a developer by email."""
        username = "email_dev"
        email = "email@example.com"

        # Create developer
        repo = DeveloperRepository(db_session)
        developer1 = repo.create(
            workspace_id=sample_workspace.id,
            username=username,
            email=email,
        )
        db_session.flush()
        developer1_id = developer1.id

        # Get by email
        developer2 = repo.get_by_email(email, sample_workspace.id)
        assert developer2 is not None
        assert developer2.id == developer1_id
        assert developer2.email == email
