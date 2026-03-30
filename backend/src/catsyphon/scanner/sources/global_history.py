"""a03 — Global history (JSONL) for Claude and Codex."""

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

SOURCE_TYPE = "global_history"
_MAX_LATEST = 50


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def _scan_history_file(
    repo: ArtifactRepository,
    workspace_id: UUID,
    path: Path,
    source_label: str,
) -> None:
    file_state = stat_file(path)
    existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, str(path))
    change = detect_change(file_state, existing)

    if change == "unchanged":
        return
    if change == "deleted":
        repo.mark_missing(workspace_id, SOURCE_TYPE, str(path))
        return

    # Determine resume offset from previous body
    last_offset = 0
    prev_total = 0
    prev_latest: list[dict] = []
    if existing and existing.body:
        last_offset = existing.body.get("last_offset", 0)
        prev_total = existing.body.get("total_entries", 0)
        prev_latest = existing.body.get("latest_entries", [])

    # Read all lines (needed for hashing), then process incrementally
    raw = path.read_bytes()
    content_hash = hash_content(raw)
    if existing and content_hash == existing.content_hash:
        return

    lines = raw.decode("utf-8", errors="replace").splitlines()
    total_lines = len(lines)

    # Parse new lines from offset
    new_entries: list[dict] = []
    for line in lines[last_offset:]:
        line = line.strip()
        if not line:
            continue
        try:
            new_entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Merge latest entries: append new to previous, keep last N
    combined = prev_latest + new_entries
    latest = combined[-_MAX_LATEST:]

    body = {
        "total_entries": total_lines,
        "last_offset": total_lines,
        "latest_entries": latest,
        "source": source_label,
    }

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
        log.info(
            "global_history %s: %s (+%d entries, %d total)",
            change_type,
            path,
            len(new_entries),
            total_lines,
        )


def scan_global_history(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    repo = ArtifactRepository(session)

    claude_dir = _find_dir(data_dirs, "claude")
    if claude_dir:
        _scan_history_file(
            repo, workspace_id, claude_dir / "history.jsonl", "claude"
        )

    codex_dir = _find_dir(data_dirs, "codex")
    if codex_dir:
        _scan_history_file(
            repo, workspace_id, codex_dir / "history.jsonl", "codex"
        )
