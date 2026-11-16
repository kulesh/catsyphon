"""Tests for log file backup utility."""

from pathlib import Path

from catsyphon.utils.log_backup import backup_log_file


def test_backup_creates_file(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    log_file = watch_dir / "session.jsonl"
    log_file.write_text('{"msg": "hello"}\n')

    backup_dir = tmp_path / "backup"

    result = backup_log_file(log_file, watch_dir, backup_dir)

    assert result is not None
    assert result.exists()
    assert result.read_text() == '{"msg": "hello"}\n'


def test_backup_mirrors_source_structure(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch"
    nested = watch_dir / "projects" / "myapp"
    nested.mkdir(parents=True)
    log_file = nested / "abc123.jsonl"
    log_file.write_text("{}\n")

    backup_dir = tmp_path / "backup"

    result = backup_log_file(log_file, watch_dir, backup_dir)

    assert result is not None
    assert result == backup_dir / "projects" / "myapp" / "abc123.jsonl"
    assert result.exists()


def test_backup_overwrites_existing(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    log_file = watch_dir / "session.jsonl"
    log_file.write_text("v1\n")

    backup_dir = tmp_path / "backup"
    backup_log_file(log_file, watch_dir, backup_dir)

    log_file.write_text("v1\nv2\n")
    result = backup_log_file(log_file, watch_dir, backup_dir)

    assert result is not None
    assert result.read_text() == "v1\nv2\n"


def test_backup_returns_none_on_missing_source(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    missing = watch_dir / "gone.jsonl"
    backup_dir = tmp_path / "backup"

    result = backup_log_file(missing, watch_dir, backup_dir)

    assert result is None


def test_backup_handles_file_outside_watch_dir(tmp_path: Path) -> None:
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    log_file = other_dir / "stray.jsonl"
    log_file.write_text("{}\n")

    backup_dir = tmp_path / "backup"

    result = backup_log_file(log_file, watch_dir, backup_dir)

    assert result is not None
    assert result == backup_dir / "stray.jsonl"
