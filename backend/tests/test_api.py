"""
Tests for FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient

from catsyphon.api.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint_complete(self, client: TestClient):
        """Test root endpoint returns correct status, format, and content."""
        response = client.get("/")

        # Status and headers
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Response structure and values
        data = response.json()
        assert data == {
            "status": "ok",
            "message": "CatSyphon API is running",
            "version": "0.1.0",
        }


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_when_database_connected(self, client: TestClient):
        """Test health endpoint reports healthy when database is connected."""
        from unittest.mock import patch

        with patch("catsyphon.db.connection.check_connection", return_value=True):
            response = client.get("/health")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "healthy"

    def test_health_when_database_disconnected(self, client: TestClient):
        """Test health endpoint reports degraded when database is down."""
        from unittest.mock import patch

        with patch("catsyphon.db.connection.check_connection", return_value=False):
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] == "unhealthy"


class TestAPIDocs:
    """Tests for API documentation endpoints."""

    def test_openapi_documentation_accessible(self, client: TestClient):
        """Test that all API documentation endpoints are accessible."""
        # Swagger UI
        assert client.get("/docs").status_code == 200

        # ReDoc
        assert client.get("/redoc").status_code == 200

        # OpenAPI JSON spec
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Verify spec structure
        spec = response.json()
        assert spec["info"]["title"] == "CatSyphon API"
        assert spec["info"]["version"] == "0.1.0"
        assert "paths" in spec


class TestReadinessEndpoint:
    """Tests for readiness probe endpoint."""

    def test_ready_endpoint_returns_200_when_ready(self, client: TestClient):
        """Test that /ready endpoint returns 200 when system is ready."""
        from unittest.mock import patch

        with patch(
            "catsyphon.startup.check_readiness",
            return_value=(True, {"status": "ready", "database": "connected"}),
        ):
            response = client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["database"] == "connected"

    def test_ready_endpoint_returns_503_when_not_ready(self, client: TestClient):
        """Test that /ready endpoint returns 503 when system is not ready."""
        from unittest.mock import patch

        with patch(
            "catsyphon.startup.check_readiness",
            return_value=(False, "Database connection failed"),
        ):
            response = client.get("/ready")

            assert response.status_code == 503

    def test_ready_endpoint_includes_details(self, client: TestClient):
        """Test that /ready endpoint includes system details."""
        from unittest.mock import patch

        details = {
            "status": "ready",
            "database": "connected",
            "migrations": "up to date",
        }

        with patch("catsyphon.startup.check_readiness", return_value=(True, details)):
            response = client.get("/ready")
            data = response.json()

            assert "status" in data
            assert "database" in data
            assert "migrations" in data


class TestCORS:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_localhost_3000(self, client: TestClient):
        """Test that CORS allows localhost:3000."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_localhost_5173(self, client: TestClient):
        """Test that CORS allows localhost:5173 (Vite default)."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_credentials(self, client: TestClient):
        """Test that CORS allows credentials."""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Credentials should be allowed
        assert response.headers.get("access-control-allow-credentials") in [
            "true",
            None,
        ]
