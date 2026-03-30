"""a04 — Codex SQLite database scanner."""

from __future__ import annotations

import json
import logging
import sqlite3
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

SOURCE_TYPE = "codex_sqlite"


def _find_dir(data_dirs: list[str], keyword: str) -> Path | None:
    return next((Path(d) for d in data_dirs if keyword in d), None)


def scan_codex_sqlite(
    session: Session, workspace_id: UUID, data_dirs: list[str]
) -> None:
    base = _find_dir(data_dirs, "codex")
    if not base:
        return

    path = base / "state_5.sqlite"
    file_state = stat_file(path)
    repo = ArtifactRepository(session)
    existing = repo.get_snapshot(workspace_id, SOURCE_TYPE, str(path))
    change = detect_change(file_state, existing)

    if change == "unchanged":
        return
    if change == "deleted":
        repo.mark_missing(workspace_id, SOURCE_TYPE, str(path))
        return

    # Hash the entire file for change detection
    content = path.read_bytes()
    content_hash = hash_content(content)
    if existing and content_hash == existing.content_hash:
        return

    # Query the database read-only
    tables: list[dict] = []
    recent_threads: list[dict] = []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Get table names and row counts
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [row["name"] for row in cur.fetchall()]
        for tbl in table_names:
            cur.execute(f'SELECT COUNT(*) AS cnt FROM "{tbl}"')  # noqa: S608
            row_count = cur.fetchone()["cnt"]
            tables.append({"name": tbl, "row_count": row_count})

        # 10 most recent threads (best-effort; table/columns may vary)
        try:
            cur.execute(
                "SELECT id, title, model, tokens_used, created_at "
                "FROM threads ORDER BY created_at DESC LIMIT 10"
            )
            for row in cur.fetchall():
                recent_threads.append(
                    {
                        "id": str(row["id"]),
                        "title": row["title"],
                        "model": row["model"],
                        "tokens_used": row["tokens_used"],
                        "created_at": str(row["created_at"]),
                    }
                )
        except sqlite3.OperationalError:
            # threads table may not exist or have different schema
            log.debug("codex_sqlite: threads table not found or schema mismatch")
    finally:
        conn.close()

    body = {
        "tables": tables,
        "recent_threads": recent_threads,
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
            "codex_sqlite %s: %d tables, %d recent threads",
            change_type,
            len(tables),
            len(recent_threads),
        )
