"""Tests for the artifact scanner infrastructure and scanners."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from catsyphon.models.db import ArtifactHistory, ArtifactSnapshot
from catsyphon.scanner.change_detection import (
    FileState,
    detect_change,
    hash_content,
    mtime_to_datetime,
    stat_file,
)
from catsyphon.scanner.repository import ArtifactRepository


# ── Change Detection Tests ──────────────────────────────────────────


class TestChangeDetection:
    def test_stat_file_exists(self, tmp_path: Path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        state = stat_file(f)
        assert state.exists is True
        assert state.size > 0
        assert state.mtime > 0

    def test_stat_file_missing(self, tmp_path: Path):
        state = stat_file(tmp_path / "nonexistent.json")
        assert state.exists is False

    def test_hash_content(self):
        h1 = hash_content(b"hello")
        h2 = hash_content(b"hello")
        h3 = hash_content(b"world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64

    def test_detect_change_new(self):
        state = FileState(path=Path("/tmp/x"), exists=True, size=100, mtime=1.0)
        assert detect_change(state, None) == "new"

    def test_detect_change_deleted(self):
        snapshot = ArtifactSnapshot(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            source_type="test",
            source_path="/tmp/x",
            content_hash="abc",
            file_size_bytes=100,
        )
        state = FileState(path=Path("/tmp/x"), exists=False)
        assert detect_change(state, snapshot) == "deleted"

    def test_detect_change_unchanged_missing_both(self):
        state = FileState(path=Path("/tmp/x"), exists=False)
        assert detect_change(state, None) == "unchanged"

    def test_mtime_to_datetime(self):
        dt = mtime_to_datetime(0.0)
        assert dt.year == 1970


# ── Repository Tests ────────────────────────────────────────────────


class TestArtifactRepository:
    def test_upsert_creates_new(self, db_session, sample_workspace):
        repo = ArtifactRepository(db_session)
        snapshot, change = repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="abc123",
            file_size_bytes=42,
            file_mtime=datetime.now(UTC),
            body={"key": "value"},
        )
        assert change == "created"
        assert snapshot.source_type == "test_source"
        assert snapshot.body == {"key": "value"}

    def test_upsert_detects_modification(self, db_session, sample_workspace):
        repo = ArtifactRepository(db_session)
        repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="abc123",
            file_size_bytes=42,
            file_mtime=datetime.now(UTC),
            body={"v": 1},
        )
        snapshot, change = repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="def456",
            file_size_bytes=50,
            file_mtime=datetime.now(UTC),
            body={"v": 2},
        )
        assert change == "modified"
        assert snapshot.body == {"v": 2}

    def test_upsert_detects_unchanged(self, db_session, sample_workspace):
        repo = ArtifactRepository(db_session)
        repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="same",
            file_size_bytes=42,
            file_mtime=datetime.now(UTC),
            body={"v": 1},
        )
        _, change = repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="same",
            file_size_bytes=42,
            file_mtime=datetime.now(UTC),
            body={"v": 1},
        )
        assert change == "unchanged"

    def test_record_change_appends_history(self, db_session, sample_workspace):
        repo = ArtifactRepository(db_session)
        snapshot, _ = repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="test_source",
            source_path="/data/test.json",
            content_hash="abc",
            file_size_bytes=42,
            file_mtime=datetime.now(UTC),
            body={},
        )
        history = repo.record_change(snapshot, "created", None, "abc")
        assert history.change_type == "created"
        assert history.new_content_hash == "abc"

    def test_get_snapshots_by_source(self, db_session, sample_workspace):
        repo = ArtifactRepository(db_session)
        repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="type_a",
            source_path="/a",
            content_hash="h1",
            file_size_bytes=1,
            file_mtime=datetime.now(UTC),
            body={},
        )
        repo.upsert_snapshot(
            workspace_id=sample_workspace.id,
            source_type="type_b",
            source_path="/b",
            content_hash="h2",
            file_size_bytes=2,
            file_mtime=datetime.now(UTC),
            body={},
        )
        results = repo.get_snapshots_by_source(sample_workspace.id, "type_a")
        assert len(results) == 1
        assert results[0].source_path == "/a"


# ── Scanner Source Tests (using temp fixtures) ──────────────────────


class TestTokenAnalyticsScanner:
    def test_scans_stats_cache(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.token_analytics import scan_token_analytics

        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        stats_file = claude_dir / "stats-cache.json"
        stats_file.write_text(json.dumps({
            "version": 1,
            "totalSessions": 42,
            "totalMessages": 1000,
        }))

        scan_token_analytics(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        snapshots = repo.get_snapshots_by_source(sample_workspace.id, "token_analytics")
        assert len(snapshots) == 1
        assert snapshots[0].body["totalSessions"] == 42

    def test_skips_when_unchanged(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.token_analytics import scan_token_analytics

        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        stats_file = claude_dir / "stats-cache.json"
        stats_file.write_text(json.dumps({"version": 1}))

        # First scan
        scan_token_analytics(db_session, sample_workspace.id, [str(claude_dir)])
        # Second scan (same content)
        scan_token_analytics(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        _, total = repo.get_history(sample_workspace.id, "token_analytics")
        # Only 1 history record (created), not 2
        assert total == 1


class TestPluginInventoryScanner:
    def test_scans_plugins(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.plugin_inventory import scan_plugin_inventory

        claude_dir = tmp_path / "claude"
        (claude_dir / "plugins").mkdir(parents=True)
        (claude_dir / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {"test": []}})
        )

        scan_plugin_inventory(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        snapshots = repo.get_snapshots_by_source(sample_workspace.id, "plugin_inventory")
        assert len(snapshots) == 1
        assert snapshots[0].body["version"] == 2


class TestSettingsConfigScanner:
    def test_scans_settings_json(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.settings_config import scan_settings_config

        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(
            json.dumps({"effortLevel": "high"})
        )

        scan_settings_config(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        snapshots = repo.get_snapshots_by_source(sample_workspace.id, "settings_config")
        assert len(snapshots) >= 1
        settings_snap = [s for s in snapshots if "settings.json" in s.source_path]
        assert len(settings_snap) == 1
        assert settings_snap[0].body["effortLevel"] == "high"


class TestProjectMemoryScanner:
    def test_scans_memory_files(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.project_memory import scan_project_memory

        claude_dir = tmp_path / "claude"
        mem_dir = claude_dir / "projects" / "-Users-test-proj" / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text("# Project Memory\nSome notes.")
        (mem_dir / "arch.md").write_text("# Architecture\nDetails here.")

        scan_project_memory(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        snapshots = repo.get_snapshots_by_source(sample_workspace.id, "project_memory")
        assert len(snapshots) == 2


class TestStandalonePlansScanner:
    def test_scans_plan_files(self, db_session, sample_workspace, tmp_path):
        from catsyphon.scanner.sources.standalone_plans import scan_standalone_plans

        claude_dir = tmp_path / "claude"
        plans_dir = claude_dir / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "cool-plan.md").write_text("# My Plan\nSteps here.")

        scan_standalone_plans(db_session, sample_workspace.id, [str(claude_dir)])

        repo = ArtifactRepository(db_session)
        snapshots = repo.get_snapshots_by_source(sample_workspace.id, "standalone_plans")
        assert len(snapshots) == 1
        assert snapshots[0].body["filename"] == "cool-plan.md"
