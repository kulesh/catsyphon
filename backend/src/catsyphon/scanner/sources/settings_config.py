"""a06 — Settings and config files (JSON + TOML)."""

from __future__ import annotations

import json
import logging
import tomllib
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

SOURCE_TYPE = "settings_config"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def _scan_single(
    repo: ArtifactRepository,
    workspace_id: UUID,
    path: Path,
    parser: str,
) -> None:
    file_state = stat_file(path)
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

    if parser == "json":
        body = json.loads(content)
    else:
        body = tomllib.loads(content.decode("utf-8"))

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
        log.info("settings_config %s: %s", change_type, path)


def scan_settings_config(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    repo = ArtifactRepository(session)

    claude_dir = _find_dir(data_dirs, "claude")
    if claude_dir:
        _scan_single(repo, workspace_id, claude_dir / "settings.json", "json")

    codex_dir = _find_dir(data_dirs, "codex")
    if codex_dir:
        _scan_single(repo, workspace_id, codex_dir / "config.toml", "toml")
