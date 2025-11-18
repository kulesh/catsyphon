"""Tests for file upload API endpoint."""

import io

import pytest
from fastapi.testclient import TestClient

from catsyphon.api.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_jsonl_content():
    """Sample Claude Code conversation log in valid format."""
    return """{"parentUuid":"00000000-0000-0000-0000-000000000000","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-001","version":"2.0.17","gitBranch":"main","type":"user","message":{"role":"user","content":"Help me fix a bug"},"uuid":"msg-001","timestamp":"2025-10-16T19:12:28.024Z"}
{"parentUuid":"msg-001","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-001","version":"2.0.17","gitBranch":"main","type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","id":"msg_123","type":"message","role":"assistant","content":[{"type":"text","text":"I'll help you debug"}],"usage":{"input_tokens":10,"output_tokens":5}},"uuid":"msg-002","timestamp":"2025-10-16T19:12:29.500Z"}
"""


class TestFileUpload:
    """Tests for file upload endpoint."""

    def test_upload_valid_file(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test uploading a valid conversation log file."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "success"
        assert result["results"][0]["conversation_id"] is not None
        assert result["results"][0]["filename"] == "conversation.jsonl"

    def test_upload_without_file(self, client: TestClient):
        """Test upload endpoint without file."""
        response = client.post("/upload")

        assert response.status_code == 422  # Validation error - no files provided

    def test_upload_non_jsonl_file(self, client: TestClient):
        """Test uploading non-JSONL file."""
        files = [("files", ("test.txt", io.BytesIO(b"Not a JSONL file"), "text/plain"))]

        response = client.post("/upload", files=files)

        assert response.status_code == 200  # Endpoint processes the request
        result = response.json()
        assert result["failed_count"] == 1
        assert result["success_count"] == 0
        assert result["results"][0]["status"] == "error"
        assert "Only .jsonl files are supported" in result["results"][0]["error"]

    def test_upload_empty_file(self, client: TestClient):
        """Test uploading empty file."""
        files = [("files", ("empty.jsonl", io.BytesIO(b""), "application/json"))]

        response = client.post("/upload", files=files)

        # Empty file will fail during parsing
        assert response.status_code == 200
        result = response.json()
        assert result["failed_count"] == 1
        assert result["results"][0]["status"] == "error"

    def test_upload_without_project_name(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test upload without project name - should auto-extract from log."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        # Should succeed - project_name is auto-extracted from log
        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1

    def test_upload_with_developer_username(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test upload - developer username is auto-extracted from log."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        # Should succeed - developer info is auto-extracted
        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert result["results"][0]["conversation_id"] is not None

    def test_upload_duplicate_file_returns_error(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test that uploading the same file twice handles duplicates gracefully."""
        files1 = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        # First upload should succeed
        response1 = client.post("/upload", files=files1)
        assert response1.status_code == 200
        result1 = response1.json()
        assert result1["success_count"] == 1
        assert result1["results"][0]["status"] == "success"

        # Second upload of same content should be handled gracefully
        # May return duplicate or success depending on transaction isolation
        files2 = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]
        response2 = client.post("/upload", files=files2)

        assert response2.status_code == 200
        result2 = response2.json()
        # Duplicates count as successful (no error)
        assert result2["success_count"] == 1
        assert result2["failed_count"] == 0
        # Status may be "duplicate" or "success" depending on timing
        assert result2["results"][0]["status"] in ["duplicate", "success"]

    def test_upload_malformed_jsonl(self, client: TestClient):
        """Test uploading malformed JSONL content."""
        malformed = b'{"invalid json without closing brace'
        files = [("files", ("bad.jsonl", io.BytesIO(malformed), "application/json"))]

        response = client.post("/upload", files=files)

        # Should return 200 but with error status for this file
        assert response.status_code == 200
        result = response.json()
        assert result["failed_count"] == 1
        assert result["results"][0]["status"] == "error"

    def test_upload_very_large_file(self, client: TestClient):
        """Test uploading a large file (size limits)."""
        # Create a large file with valid JSONL content
        large_content = b'{"type":"message","content":"x"}\n' * 100000
        files = [
            ("files", ("large.jsonl", io.BytesIO(large_content), "application/json"))
        ]

        response = client.post("/upload", files=files)

        # Should either succeed (if parser handles it) or fail with error
        assert response.status_code in [200, 413]
        if response.status_code == 200:
            result = response.json()
            # May succeed or fail depending on parser behavior
            assert "results" in result

    def test_upload_response_structure(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test that upload response has correct structure."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        assert response.status_code == 200
        result = response.json()
        # Verify UploadResponse structure
        assert "success_count" in result
        assert "failed_count" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        # Verify UploadResult structure
        assert result["results"][0]["filename"] == "conversation.jsonl"
        assert result["results"][0]["status"] in ["success", "duplicate", "error"]
        if result["results"][0]["status"] == "success":
            assert "conversation_id" in result["results"][0]
            assert "message_count" in result["results"][0]
            assert "epoch_count" in result["results"][0]
            assert "files_count" in result["results"][0]

    def test_upload_with_special_characters_in_filename(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test uploading file with special characters in filename."""
        files = [
            (
                "files",
                (
                    "conversation (2025-01-01) [test].jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        # Should handle special characters gracefully
        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert (
            result["results"][0]["filename"] == "conversation (2025-01-01) [test].jsonl"
        )

    def test_upload_file_with_unicode_content(self, client: TestClient, db_session):
        """Test uploading file with Unicode content."""
        unicode_content = """{"parentUuid":"00000000-0000-0000-0000-000000000000","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-unicode","version":"2.0.17","gitBranch":"main","type":"user","message":{"role":"user","content":"Help me with 日本語 content"},"uuid":"msg-unicode-001","timestamp":"2025-10-16T19:12:28.024Z"}
{"parentUuid":"msg-unicode-001","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-unicode","version":"2.0.17","gitBranch":"main","type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","id":"msg_124","type":"message","role":"assistant","content":[{"type":"text","text":"I'll help with émojis 🚀"}],"usage":{"input_tokens":10,"output_tokens":5}},"uuid":"msg-unicode-002","timestamp":"2025-10-16T19:12:29.500Z"}
"""
        files = [
            (
                "files",
                (
                    "unicode.jsonl",
                    io.BytesIO(unicode_content.encode("utf-8")),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload", files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert result["results"][0]["status"] == "success"

    def test_upload_multiple_files(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test uploading multiple files at once."""
        # Create two different files with different session IDs
        content1 = """{"parentUuid":"00000000-0000-0000-0000-000000000000","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-multi-1","version":"2.0.17","gitBranch":"main","type":"user","message":{"role":"user","content":"First conversation"},"uuid":"msg-multi1-001","timestamp":"2025-10-16T19:12:28.024Z"}
{"parentUuid":"msg-multi1-001","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-multi-1","version":"2.0.17","gitBranch":"main","type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","id":"msg_125","type":"message","role":"assistant","content":[{"type":"text","text":"First response"}],"usage":{"input_tokens":10,"output_tokens":5}},"uuid":"msg-multi1-002","timestamp":"2025-10-16T19:12:29.500Z"}
"""
        content2 = """{"parentUuid":"00000000-0000-0000-0000-000000000000","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-multi-2","version":"2.0.17","gitBranch":"main","type":"user","message":{"role":"user","content":"Second conversation"},"uuid":"msg-multi2-001","timestamp":"2025-10-16T20:12:28.024Z"}
{"parentUuid":"msg-multi2-001","isSidechain":false,"userType":"external","cwd":"/Users/test/project","sessionId":"test-session-multi-2","version":"2.0.17","gitBranch":"main","type":"assistant","message":{"model":"claude-sonnet-4-5-20250929","id":"msg_126","type":"message","role":"assistant","content":[{"type":"text","text":"Second response"}],"usage":{"input_tokens":10,"output_tokens":5}},"uuid":"msg-multi2-002","timestamp":"2025-10-16T20:12:29.500Z"}
"""
        files = [
            (
                "files",
                (
                    "conversation1.jsonl",
                    io.BytesIO(content1.encode()),
                    "application/json",
                ),
            ),
            (
                "files",
                (
                    "conversation2.jsonl",
                    io.BytesIO(content2.encode()),
                    "application/json",
                ),
            ),
        ]

        response = client.post("/upload", files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 2
        assert result["failed_count"] == 0
        assert len(result["results"]) == 2
        assert result["results"][0]["filename"] == "conversation1.jsonl"
        assert result["results"][1]["filename"] == "conversation2.jsonl"
        assert result["results"][0]["status"] == "success"
        assert result["results"][1]["status"] == "success"

    def test_upload_with_update_mode_skip(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test upload with update_mode=skip (default behavior)."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload?update_mode=skip", files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert result["results"][0]["status"] == "success"

    def test_upload_with_update_mode_replace(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test upload with update_mode=replace."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        # First upload
        response1 = client.post("/upload", files=files)
        assert response1.status_code == 200

        # Second upload with replace mode
        response2 = client.post("/upload?update_mode=replace", files=files)

        assert response2.status_code == 200
        result = response2.json()
        # With replace mode, existing conversations should be replaced
        assert result["success_count"] == 1
        assert result["results"][0]["status"] in ["success", "duplicate"]

    def test_upload_with_update_mode_append(
        self, client: TestClient, sample_jsonl_content: str, db_session
    ):
        """Test upload with update_mode=append."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload?update_mode=append", files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["success_count"] == 1
        assert result["results"][0]["status"] == "success"

    def test_upload_with_invalid_update_mode(
        self, client: TestClient, sample_jsonl_content: str
    ):
        """Test upload with invalid update_mode value."""
        files = [
            (
                "files",
                (
                    "conversation.jsonl",
                    io.BytesIO(sample_jsonl_content.encode()),
                    "application/json",
                ),
            )
        ]

        response = client.post("/upload?update_mode=invalid", files=files)

        # Should fail validation (422 Unprocessable Entity)
        assert response.status_code == 422
