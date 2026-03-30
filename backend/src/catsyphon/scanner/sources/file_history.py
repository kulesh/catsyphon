"""a07 — File history directory summary (no file content read)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from catsyphon.scanner.change_detection import (
    detect_change,
    hash_content,
    mtime_to_datetime,
    stat_file,
)
from catsyphon.scanner.repository import ArtifactRepository

log = logging.getLogger(__name__)

SOURCE_TYPE = "file_history"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def scan_file_history(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    base = _find_dir(data_dirs, "claude")
    if not base:
        return

    history_dir = base / "file-history"
    if not history_dir.is_dir():
        return

    repo = ArtifactRepository(session)

    sessions: list[dict] = []
    total_files = 0
    total_sessions = 0

    for entry in sorted(history_dir.iterdir()):
        if not entry.is_dir():
            continue
        total_sessions += 1
        file_count = 0
        total_bytes = 0
        for f in entry.iterdir():
            if f.is_file():
                file_count += 1
                total_bytes += f.stat().st_size
        total_files += file_count
        sessions.append(
            {
                "session_id": entry.name,
                "file_count": file_count,
                "total_bytes": total_bytes,
            }
        )

    body = {
        "sessions": sessions,
        "total_sessions": total_sessions,
        "total_files": total_files,
    }

    # Use a hash of the serialized body for change detection
    body_bytes = json.dumps(body, sort_keys=True).encode()
    content_hash = hash_content(body_bytes)

    source_path = str(history_dir)
    existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, source_path)
    if existing and content_hash == existing.content_hash:
        return

    # Use the directory mtime as the file_mtime
    dir_state = stat_file(history_dir)
    prev_hash = existing.content_hash if existing else None

    snapshot, change_type = repo.upsert_snapshot(
        workspace_id=workspace_id,
        source_type=SOURCE_TYPE,
        source_path=source_path,
        content_hash=content_hash,
        file_size_bytes=dir_state.size,
        file_mtime=mtime_to_datetime(dir_state.mtime) if dir_state.exists else None,
        body=body,
    )
    if change_type in ("created", "modified"):
        repo.record_change(snapshot, change_type, prev_hash, content_hash)
        log.info(
            "file_history %s: %d sessions, %d files",
            change_type,
            total_sessions,
            total_files,
        )
