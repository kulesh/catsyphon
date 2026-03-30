"""a09 — Shell snapshot file listing (no content read)."""

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

SOURCE_TYPE = "shell_snapshots"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def scan_shell_snapshots(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    base = _find_dir(data_dirs, "claude")
    if not base:
        return

    snap_dir = base / "shell-snapshots"
    if not snap_dir.is_dir():
        return

    repo = ArtifactRepository(session)

    files: list[dict] = []
    total_bytes = 0
    for path in sorted(snap_dir.glob("*.sh")):
        if not path.is_file():
            continue
        size = path.stat().st_size
        files.append({"name": path.name, "size_bytes": size})
        total_bytes += size

    body = {
        "files": files,
        "total_files": len(files),
        "total_bytes": total_bytes,
    }

    body_bytes = json.dumps(body, sort_keys=True).encode()
    content_hash = hash_content(body_bytes)

    source_path = str(snap_dir)
    existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, source_path)
    if existing and content_hash == existing.content_hash:
        return

    dir_state = stat_file(snap_dir)
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
            "shell_snapshots %s: %d files, %d bytes",
            change_type,
            len(files),
            total_bytes,
        )
