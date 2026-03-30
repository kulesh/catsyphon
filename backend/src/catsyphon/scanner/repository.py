"""Repository for artifact snapshot and history persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from catsyphon.models.db import ArtifactHistory, ArtifactSnapshot


class ArtifactRepository:
    """Handles upsert of snapshots and append of history records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_snapshot(
        self,
        workspace_id: uuid.UUID,
        source_type: str,
        source_path: str,
    ) -> Optional[ArtifactSnapshot]:
        return (
            self.session.query(ArtifactSnapshot)
            .filter(
                ArtifactSnapshot.workspace_id == workspace_id,
                ArtifactSnapshot.source_type == source_type,
                ArtifactSnapshot.source_path == source_path,
            )
            .first()
        )

    def upsert_snapshot(
        self,
        workspace_id: uuid.UUID,
        source_type: str,
        source_path: str,
        content_hash: str,
        file_size_bytes: int,
        file_mtime: Optional[datetime],
        body: dict,
        scan_status: str = "ok",
        error_message: Optional[str] = None,
    ) -> tuple[ArtifactSnapshot, str]:
        """Upsert a snapshot. Returns (snapshot, change_type)."""
        now = datetime.now(timezone.utc)
        existing = self.get_snapshot(workspace_id, source_type, source_path)

        if existing is None:
            snapshot = ArtifactSnapshot(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                source_type=source_type,
                source_path=source_path,
                content_hash=content_hash,
                file_size_bytes=file_size_bytes,
                file_mtime=file_mtime,
                body=body,
                scan_status=scan_status,
                error_message=error_message,
                scanned_at=now,
            )
            self.session.add(snapshot)
            self.session.flush()
            return snapshot, "created"

        prev_hash = existing.content_hash
        change_type = "modified" if prev_hash != content_hash else "unchanged"

        existing.content_hash = content_hash
        existing.file_size_bytes = file_size_bytes
        existing.file_mtime = file_mtime
        existing.body = body
        existing.scan_status = scan_status
        existing.error_message = error_message
        existing.scanned_at = now
        self.session.flush()

        return existing, change_type

    def mark_missing(
        self,
        workspace_id: uuid.UUID,
        source_type: str,
        source_path: str,
    ) -> Optional[ArtifactSnapshot]:
        """Mark a previously seen file as missing."""
        existing = self.get_snapshot(workspace_id, source_type, source_path)
        if existing and existing.scan_status != "missing":
            existing.scan_status = "missing"
            existing.scanned_at = datetime.now(timezone.utc)
            self.session.flush()
        return existing

    def record_change(
        self,
        snapshot: ArtifactSnapshot,
        change_type: str,
        prev_content_hash: Optional[str],
        new_content_hash: str,
        diff_summary: Optional[dict] = None,
    ) -> ArtifactHistory:
        """Append a history record."""
        record = ArtifactHistory(
            id=uuid.uuid4(),
            workspace_id=snapshot.workspace_id,
            snapshot_id=snapshot.id,
            source_type=snapshot.source_type,
            change_type=change_type,
            prev_content_hash=prev_content_hash,
            new_content_hash=new_content_hash,
            diff_summary=diff_summary or {},
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_snapshots_by_source(
        self,
        workspace_id: uuid.UUID,
        source_type: str,
    ) -> list[ArtifactSnapshot]:
        return (
            self.session.query(ArtifactSnapshot)
            .filter(
                ArtifactSnapshot.workspace_id == workspace_id,
                ArtifactSnapshot.source_type == source_type,
            )
            .order_by(ArtifactSnapshot.source_path)
            .all()
        )

    def get_all_source_stats(
        self,
        workspace_id: uuid.UUID,
    ) -> list[dict]:
        """Aggregate stats per source_type for the sources listing."""
        from sqlalchemy import func

        rows = (
            self.session.query(
                ArtifactSnapshot.source_type,
                func.count(ArtifactSnapshot.id).label("snapshot_count"),
                func.max(ArtifactSnapshot.scanned_at).label("last_scanned_at"),
            )
            .filter(ArtifactSnapshot.workspace_id == workspace_id)
            .group_by(ArtifactSnapshot.source_type)
            .all()
        )
        return [
            {
                "source_type": r.source_type,
                "snapshot_count": r.snapshot_count,
                "last_scanned_at": r.last_scanned_at,
            }
            for r in rows
        ]

    def get_history(
        self,
        workspace_id: uuid.UUID,
        source_type: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ArtifactHistory], int]:
        """Paginated history for a source type."""
        from sqlalchemy import func

        base = self.session.query(ArtifactHistory).filter(
            ArtifactHistory.workspace_id == workspace_id,
            ArtifactHistory.source_type == source_type,
        )
        total = base.with_entities(func.count(ArtifactHistory.id)).scalar() or 0
        items = (
            base.order_by(ArtifactHistory.detected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
