"""File hashing utilities for deduplication."""

import hashlib
from pathlib import Path


def calculate_file_hash(file_path: Path | str, chunk_size: int = 8192) -> str:
    """
    Calculate SHA-256 hash of a file.

    Args:
        file_path: Path to the file to hash
        chunk_size: Size of chunks to read (default: 8KB)

    Returns:
        Hexadecimal string representation of the SHA-256 hash (64 characters)

    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If there's an error reading the file
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        while chunk := f.read(chunk_size):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def calculate_content_hash(content: str | bytes) -> str:
    """
    Calculate SHA-256 hash of content.

    Args:
        content: String or bytes content to hash

    Returns:
        Hexadecimal string representation of the SHA-256 hash (64 characters)
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    return hashlib.sha256(content).hexdigest()
