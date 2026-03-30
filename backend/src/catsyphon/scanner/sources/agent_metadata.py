"""a08 — Agent metadata JSON files (subagent descriptors)."""

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

SOURCE_TYPE = "agent_metadata"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def scan_agent_metadata(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    base = _find_dir(data_dirs, "claude")
    if not base:
        return

    repo = ArtifactRepository(session)

    # Two glob patterns: direct project subagents and session-nested subagents
    patterns = [
        "projects/*/subagents/agent-*.meta.json",
        "projects/*/*/subagents/agent-*.meta.json",
    ]

    seen: set[str] = set()
    for pattern in patterns:
        for path in sorted(base.glob(pattern)):
            path_str = str(path)
            if path_str in seen:
                continue
            seen.add(path_str)

            file_state = stat_file(path)
            existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, path_str)
            change = detect_change(file_state, existing)

            if change == "unchanged":
                continue
            if change == "deleted":
                repo.mark_missing(workspace_id, SOURCE_TYPE, path_str)
                continue

            content = path.read_bytes()
            content_hash = hash_content(content)
            if existing and content_hash == existing.content_hash:
                continue

            body = json.loads(content)
            prev_hash = existing.content_hash if existing else None

            snapshot, change_type = repo.upsert_snapshot(
                workspace_id=workspace_id,
                source_type=SOURCE_TYPE,
                source_path=path_str,
                content_hash=content_hash,
                file_size_bytes=file_state.size,
                file_mtime=mtime_to_datetime(file_state.mtime),
                body=body,
            )
            if change_type in ("created", "modified"):
                repo.record_change(snapshot, change_type, prev_hash, content_hash)
                log.info("agent_metadata %s: %s", change_type, path)
