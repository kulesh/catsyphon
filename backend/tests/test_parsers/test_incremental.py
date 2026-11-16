"""
Tests for chunked parsing infrastructure.

Tests the core parsing utilities including change detection
and partial hashing.
"""

from pathlib import Path

import pytest

from catsyphon.parsers.incremental import (
    ChangeType,
    calculate_content_partial_hash,
    calculate_partial_hash,
    detect_file_change_type,
)


class TestCalculatePartialHash:
    """Tests for calculate_partial_hash function."""

    def test_full_file_hash(self, tmp_path: Path):
        """Test hashing entire file content."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!\n"
        test_file.write_text(content, encoding="utf-8")

        # Hash entire file
        hash_result = calculate_partial_hash(test_file, len(content.encode("utf-8")))

        # Verify it's a valid SHA-256 hash
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_partial_file_hash(self, tmp_path: Path):
        """Test hashing only part of file content."""
        test_file = tmp_path / "test.txt"
        content = "Line 1\nLine 2\nLine 3\n"
        test_file.write_text(content, encoding="utf-8")

        # Hash only first 7 bytes ("Line 1\n")
        hash_first_line = calculate_partial_hash(test_file, 7)

        # Hash first 14 bytes ("Line 1\nLine 2\n")
        hash_two_lines = calculate_partial_hash(test_file, 14)

        # Hashes should be different
        assert hash_first_line != hash_two_lines

    def test_zero_offset(self, tmp_path: Path):
        """Test hashing with zero offset (empty hash)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content", encoding="utf-8")

        hash_result = calculate_partial_hash(test_file, 0)

        # SHA-256 of empty string
        import hashlib

        expected = hashlib.sha256(b"").hexdigest()
        assert hash_result == expected

    def test_negative_offset_raises(self, tmp_path: Path):
        """Test that negative offset raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Content", encoding="utf-8")

        with pytest.raises(ValueError, match="non-negative"):
            calculate_partial_hash(test_file, -1)

    def test_offset_exceeds_size_raises(self, tmp_path: Path):
        """Test that offset beyond file size raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Short", encoding="utf-8")

        with pytest.raises(ValueError, match="exceeds file size"):
            calculate_partial_hash(test_file, 1000)

    def test_large_file_chunked_reading(self, tmp_path: Path):
        """Test that large files are read in chunks efficiently."""
        test_file = tmp_path / "large.txt"

        # Create a 20KB file
        content = "A" * 20000
        test_file.write_text(content, encoding="utf-8")

        # Hash first 15KB
        hash_result = calculate_partial_hash(test_file, 15000)

        # Verify it's a valid hash (tests chunked reading)
        assert len(hash_result) == 64


class TestCalculateContentPartialHash:
    """Tests for calculate_content_partial_hash function."""

    def test_full_content_hash(self):
        """Test hashing entire string content."""
        content = "Hello, World!"
        content_bytes = content.encode("utf-8")

        hash_result = calculate_content_partial_hash(content, len(content_bytes))

        assert len(hash_result) == 64

    def test_partial_content_hash(self):
        """Test hashing only part of string content."""
        content = "Line 1\nLine 2\nLine 3"

        # Hash first 7 bytes ("Line 1\n")
        hash_first = calculate_content_partial_hash(content, 7)

        # Hash first 14 bytes ("Line 1\nLine 2")
        hash_two = calculate_content_partial_hash(content, 14)

        assert hash_first != hash_two

    def test_negative_offset_raises(self):
        """Test that negative offset raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            calculate_content_partial_hash("content", -1)

    def test_offset_exceeds_length_raises(self):
        """Test that offset beyond content length raises ValueError."""
        with pytest.raises(ValueError, match="exceeds content length"):
            calculate_content_partial_hash("short", 1000)


class TestDetectFileChangeType:
    """Tests for detect_file_change_type function."""

    def test_unchanged_file(self, tmp_path: Path):
        """Test detection when file hasn't changed."""
        test_file = tmp_path / "test.jsonl"
        content = '{"message": "Hello"}\n'
        test_file.write_text(content, encoding="utf-8")

        file_size = test_file.stat().st_size
        partial_hash = calculate_partial_hash(test_file, file_size)

        change_type = detect_file_change_type(
            test_file, file_size, file_size, partial_hash
        )

        assert change_type == ChangeType.UNCHANGED

    def test_append_detected(self, tmp_path: Path):
        """Test detection when content is appended to file."""
        test_file = tmp_path / "test.jsonl"

        # Initial content
        initial = '{"message": "Line 1"}\n'
        test_file.write_text(initial, encoding="utf-8")

        initial_size = test_file.stat().st_size
        initial_hash = calculate_partial_hash(test_file, initial_size)

        # Append more content
        appended = '{"message": "Line 2"}\n'
        test_file.write_text(initial + appended, encoding="utf-8")

        change_type = detect_file_change_type(
            test_file, initial_size, initial_size, initial_hash
        )

        assert change_type == ChangeType.APPEND

    def test_truncate_detected(self, tmp_path: Path):
        """Test detection when file is truncated (shrunk)."""
        test_file = tmp_path / "test.jsonl"

        # Initial content
        initial = '{"message": "Line 1"}\n{"message": "Line 2"}\n'
        test_file.write_text(initial, encoding="utf-8")

        initial_size = test_file.stat().st_size
        initial_hash = calculate_partial_hash(test_file, initial_size)

        # Truncate file
        truncated = '{"message": "Line 1"}\n'
        test_file.write_text(truncated, encoding="utf-8")

        change_type = detect_file_change_type(
            test_file, initial_size, initial_size, initial_hash
        )

        assert change_type == ChangeType.TRUNCATE

    def test_rewrite_detected(self, tmp_path: Path):
        """Test detection when mid-file content is rewritten."""
        test_file = tmp_path / "test.jsonl"

        # Initial content
        initial = '{"message": "Line 1"}\n{"message": "Line 2"}\n'
        test_file.write_text(initial, encoding="utf-8")

        initial_size = test_file.stat().st_size
        # Get hash of first line only
        first_line_size = len('{"message": "Line 1"}\n'.encode("utf-8"))
        initial_hash = calculate_partial_hash(test_file, first_line_size)

        # Rewrite file (change first line, keep size similar)
        rewritten = '{"message": "CHANGED"}\n{"message": "Line 2"}\n'
        test_file.write_text(rewritten, encoding="utf-8")

        change_type = detect_file_change_type(
            test_file, first_line_size, initial_size, initial_hash
        )

        assert change_type == ChangeType.REWRITE

    def test_file_deleted_treated_as_truncate(self, tmp_path: Path):
        """Test that deleted file is treated as truncate."""
        test_file = tmp_path / "deleted.jsonl"

        # Don't create the file (simulate deletion)
        change_type = detect_file_change_type(test_file, 0, 100, "somehash")

        assert change_type == ChangeType.TRUNCATE

    def test_append_without_hash_check(self, tmp_path: Path):
        """Test append detection when no previous hash exists."""
        test_file = tmp_path / "test.jsonl"

        # Initial content
        initial = '{"message": "Line 1"}\n'
        test_file.write_text(initial, encoding="utf-8")

        initial_size = test_file.stat().st_size

        # Append more content
        test_file.write_text(initial + '{"message": "Line 2"}\n', encoding="utf-8")

        # No hash provided (None)
        change_type = detect_file_change_type(
            test_file, initial_size, initial_size, None
        )

        # Should still detect as append (size check only)
        assert change_type == ChangeType.APPEND


