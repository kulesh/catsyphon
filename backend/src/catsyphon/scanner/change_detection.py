"""File change detection for the artifact scanner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from catsyphon.models.db import ArtifactSnapshot


@dataclass
class FileState:
    path: Path
    exists: bool
    size: int = 0
    mtime: float = 0.0
    content_hash: str = ""


def stat_file(path: Path) -> FileState:
    """Gather filesystem metadata for a file."""
    if not path.exists():
        return FileState(path=path, exists=False)
    stat = path.stat()
    return FileState(
        path=path,
        exists=True,
        size=stat.st_size,
        mtime=stat.st_mtime,
    )


def hash_content(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def detect_change(
    file_state: FileState,
    existing: Optional[ArtifactSnapshot],
) -> str:
    """Return change type: 'new', 'modified', 'unchanged', or 'deleted'."""
    if not file_state.exists:
        return "deleted" if existing else "unchanged"

    if existing is None:
        return "new"

    # Fast path: if size and mtime match, skip hash
    if (
        file_state.size == existing.file_size_bytes
        and existing.file_mtime
        and abs(file_state.mtime - existing.file_mtime.timestamp()) < 1.0
    ):
        return "unchanged"

    # Content changed — caller should compute hash and compare
    return "modified"


def mtime_to_datetime(mtime: float) -> datetime:
    """Convert filesystem mtime to timezone-aware datetime."""
    return datetime.fromtimestamp(mtime, tz=timezone.utc)
