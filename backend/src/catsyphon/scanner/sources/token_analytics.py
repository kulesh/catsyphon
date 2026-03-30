"""a01 — Token analytics from Claude stats-cache.json."""

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

SOURCE_TYPE = "token_analytics"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def scan_token_analytics(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    base = _find_dir(data_dirs, "claude")
    if not base:
        return

    path = base / "stats-cache.json"
    file_state = stat_file(path)
    repo = ArtifactRepository(session)
    existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, str(path))
    change = detect_change(file_state, existing)

    if change == "unchanged":
        return
    if change == "deleted":
        repo.mark_missing(workspace_id, SOURCE_TYPE, str(path))
        return

    content = path.read_bytes()
    content_hash = hash_content(content)
    if existing and content_hash == existing.content_hash:
        return

    body = json.loads(content)
    prev_hash = existing.content_hash if existing else None

    snapshot, change_type = repo.upsert_snapshot(
        workspace_id=workspace_id,
        source_type=SOURCE_TYPE,
        source_path=str(path),
        content_hash=content_hash,
        file_size_bytes=file_state.size,
        file_mtime=mtime_to_datetime(file_state.mtime),
        body=body,
    )
    if change_type in ("created", "modified"):
        repo.record_change(snapshot, change_type, prev_hash, content_hash)
        log.info("token_analytics %s: %s", change_type, path)
