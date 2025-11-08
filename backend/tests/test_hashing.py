"""Tests for file hashing utilities."""

from pathlib import Path

import pytest

from catsyphon.utils.hashing import calculate_content_hash, calculate_file_hash


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""

    def test_same_content_produces_same_hash(self, tmp_path: Path):
        """Test that identical files produce the same hash."""
        content = "test content"
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text(content)
        file2.write_text(content)

        hash1 = calculate_file_hash(file1)
        hash2 = calculate_file_hash(file2)

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self, tmp_path: Path):
        """Test that different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"

        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = calculate_file_hash(file1)
        hash2 = calculate_file_hash(file2)

        assert hash1 != hash2

    def test_hash_is_64_characters(self, tmp_path: Path):
        """Test that hash is 64 characters (SHA-256 hex)."""
        file = tmp_path / "file.txt"
        file.write_text("test content")

        hash_value = calculate_file_hash(file)

        assert len(hash_value) == 64
        assert hash_value.isalnum()  # Only alphanumeric characters

    def test_hash_is_deterministic(self, tmp_path: Path):
        """Test that hashing the same file multiple times produces same hash."""
        file = tmp_path / "file.txt"
        file.write_text("test content")

        hash1 = calculate_file_hash(file)
        hash2 = calculate_file_hash(file)
        hash3 = calculate_file_hash(file)

        assert hash1 == hash2 == hash3

    def test_handles_large_files(self, tmp_path: Path):
        """Test that large files are handled correctly with chunking."""
        file = tmp_path / "large_file.txt"
        # Create a 10MB file
        large_content = "a" * (10 * 1024 * 1024)
        file.write_text(large_content)

        hash_value = calculate_file_hash(file)

        # Should complete without error and produce valid hash
        assert len(hash_value) == 64

    def test_handles_empty_file(self, tmp_path: Path):
        """Test that empty files produce a consistent hash."""
        file = tmp_path / "empty.txt"
        file.write_text("")

        hash_value = calculate_file_hash(file)

        # Empty string SHA-256 hash
        assert (
            hash_value
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_raises_error_for_nonexistent_file(self, tmp_path: Path):
        """Test that FileNotFoundError is raised for nonexistent files."""
        nonexistent = tmp_path / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            calculate_file_hash(nonexistent)

    def test_raises_error_for_directory(self, tmp_path: Path):
        """Test that ValueError is raised for directories."""
        with pytest.raises(ValueError, match="Not a file"):
            calculate_file_hash(tmp_path)

    def test_handles_unicode_content(self, tmp_path: Path):
        """Test that files with unicode content are hashed correctly."""
        file = tmp_path / "unicode.txt"
        file.write_text("Hello 世界 🌍", encoding="utf-8")

        hash_value = calculate_file_hash(file)

        # Should produce consistent hash for unicode content
        assert len(hash_value) == 64

    def test_handles_binary_content(self, tmp_path: Path):
        """Test that binary files are hashed correctly."""
        file = tmp_path / "binary.bin"
        file.write_bytes(bytes([0, 1, 2, 3, 255, 254, 253]))

        hash_value = calculate_file_hash(file)

        assert len(hash_value) == 64


class TestCalculateContentHash:
    """Tests for calculate_content_hash function."""

    def test_same_content_produces_same_hash(self):
        """Test that identical content produces the same hash."""
        content = "test content"

        hash1 = calculate_content_hash(content)
        hash2 = calculate_content_hash(content)

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self):
        """Test that different content produces different hashes."""
        hash1 = calculate_content_hash("content 1")
        hash2 = calculate_content_hash("content 2")

        assert hash1 != hash2

    def test_hash_is_64_characters(self):
        """Test that hash is 64 characters (SHA-256 hex)."""
        hash_value = calculate_content_hash("test content")

        assert len(hash_value) == 64
        assert hash_value.isalnum()

    def test_handles_string_input(self):
        """Test that string input is handled correctly."""
        content = "test string"
        hash_value = calculate_content_hash(content)

        assert len(hash_value) == 64

    def test_handles_bytes_input(self):
        """Test that bytes input is handled correctly."""
        content = b"test bytes"
        hash_value = calculate_content_hash(content)

        assert len(hash_value) == 64

    def test_string_and_bytes_produce_same_hash(self):
        """Test that string and its bytes representation produce the same hash."""
        text = "test content"
        text_bytes = text.encode("utf-8")

        hash1 = calculate_content_hash(text)
        hash2 = calculate_content_hash(text_bytes)

        assert hash1 == hash2

    def test_handles_empty_content(self):
        """Test that empty content produces a consistent hash."""
        hash_value = calculate_content_hash("")

        # Empty string SHA-256 hash
        assert (
            hash_value
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_handles_unicode_content(self):
        """Test that unicode content is hashed correctly."""
        content = "Hello 世界 🌍"
        hash_value = calculate_content_hash(content)

        # Should produce consistent hash for unicode
        assert len(hash_value) == 64

    def test_handles_large_content(self):
        """Test that large content strings are handled correctly."""
        # 10MB string
        large_content = "a" * (10 * 1024 * 1024)
        hash_value = calculate_content_hash(large_content)

        assert len(hash_value) == 64


class TestHashConsistency:
    """Tests for consistency between file and content hashing."""

    def test_file_and_content_hash_match(self, tmp_path: Path):
        """Test that hashing a file and its content produce the same hash."""
        content = "test content for consistency"
        file = tmp_path / "test.txt"
        file.write_text(content, encoding="utf-8")

        file_hash = calculate_file_hash(file)
        content_hash = calculate_content_hash(content)

        assert file_hash == content_hash

    def test_jsonl_file_hash_consistency(self, tmp_path: Path):
        """Test that JSONL files hash consistently."""
        jsonl_content = (
            '{"role": "user", "content": "test"}\n'
            '{"role": "assistant", "content": "response"}\n'
        )
        file = tmp_path / "test.jsonl"
        file.write_text(jsonl_content, encoding="utf-8")

        file_hash = calculate_file_hash(file)
        content_hash = calculate_content_hash(jsonl_content)

        assert file_hash == content_hash
