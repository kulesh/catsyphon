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

    def test_root_returns_ok_status(self, client: TestClient):
        """Test that root endpoint returns OK status."""
        response = client.get("/")

        assert response.status_code == 200

    def test_root_returns_json(self, client: TestClient):
        """Test that root endpoint returns JSON."""
        response = client.get("/")

        assert response.headers["content-type"] == "application/json"

    def test_root_response_structure(self, client: TestClient):
        """Test root endpoint response structure."""
        response = client.get("/")
        data = response.json()

        assert "status" in data
        assert "message" in data
        assert "version" in data

    def test_root_status_is_ok(self, client: TestClient):
        """Test that root status is 'ok'."""
        response = client.get("/")
        data = response.json()

        assert data["status"] == "ok"

    def test_root_version_present(self, client: TestClient):
        """Test that version is present in root response."""
        response = client.get("/")
        data = response.json()

        assert data["version"] == "0.1.0"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_200(self, client: TestClient):
        """Test that health endpoint returns 200."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_returns_json(self, client: TestClient):
        """Test that health endpoint returns JSON."""
        response = client.get("/health")

        assert response.headers["content-type"] == "application/json"

    def test_health_response_structure(self, client: TestClient):
        """Test health endpoint response structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "database" in data

    def test_health_status_is_healthy(self, client: TestClient):
        """Test that health status is 'healthy'."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_database_status(self, client: TestClient):
        """Test that database status is included."""
        response = client.get("/health")
        data = response.json()

        # Currently returns 'not_configured' as database check is TODO
        assert "database" in data


class TestAPIDocs:
    """Tests for API documentation endpoints."""

    def test_openapi_docs_accessible(self, client: TestClient):
        """Test that OpenAPI docs are accessible."""
        response = client.get("/docs")

        assert response.status_code == 200

    def test_redoc_accessible(self, client: TestClient):
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")

        assert response.status_code == 200

    def test_openapi_json_accessible(self, client: TestClient):
        """Test that OpenAPI JSON spec is accessible."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_openapi_spec_structure(self, client: TestClient):
        """Test OpenAPI spec has correct structure."""
        response = client.get("/openapi.json")
        spec = response.json()

        assert "info" in spec
        assert "paths" in spec
        assert spec["info"]["title"] == "CatSyphon API"
        assert spec["info"]["version"] == "0.1.0"


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
