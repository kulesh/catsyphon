import tempfile
from pathlib import Path

from catsyphon.db.repositories import ConversationRepository
from catsyphon.services.ingestion_service import IngestionService


def _write_jsonl(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n")


def test_ingest_log_file_full_parse(db_session, sample_workspace):
    """Integration: full parse + ingest via ingestion service creates conversation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    _write_jsonl(
        path,
        [
            '{"sessionId":"orchestrator-1","version":"2.0.17","type":"user","message":{"role":"user","content":"Hi"},"uuid":"m1","timestamp":"2025-01-01T00:00:00Z"}',
            '{"sessionId":"orchestrator-1","version":"2.0.17","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hello"}]},"uuid":"m2","timestamp":"2025-01-01T00:00:01Z"}',
        ],
    )

    service = IngestionService(db_session)
    outcome = service.ingest_from_file(
        file_path=path,
        workspace_id=sample_workspace.id,
        project_name=None,
        developer_username=None,
        source_type="cli",
    )
    db_session.commit()

    conv = ConversationRepository(db_session).get(outcome.conversation_id)
    assert conv is not None
    assert outcome.status == "success"
    assert conv.message_count == 2


def test_ingest_log_file_incremental_append(db_session, sample_workspace):
    """Integration: reingesting appended file increases message_count."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    _write_jsonl(
        path,
        [
            '{"sessionId":"orchestrator-inc","version":"2.0.17","type":"user","message":{"role":"user","content":"Hi"},"uuid":"m1","timestamp":"2025-01-01T00:00:00Z"}',
        ],
    )

    service = IngestionService(db_session)
    outcome = service.ingest_from_file(
        file_path=path,
        workspace_id=sample_workspace.id,
    )
    db_session.commit()
    conv = ConversationRepository(db_session).get(outcome.conversation_id)
    assert conv is not None
    assert conv.message_count == 1

    # Append a new line and re-run with incremental enabled
    _write_jsonl(
        path,
        [
            '{"sessionId":"orchestrator-inc","version":"2.0.17","type":"user","message":{"role":"user","content":"Hi"},"uuid":"m1","timestamp":"2025-01-01T00:00:00Z"}',
            '{"sessionId":"orchestrator-inc","version":"2.0.17","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"More"}]},"uuid":"m2","timestamp":"2025-01-01T00:00:02Z"}',
        ],
    )

    outcome2 = service.ingest_from_file(
        file_path=path,
        workspace_id=sample_workspace.id,
    )
    db_session.commit()
    conv2 = ConversationRepository(db_session).get(outcome2.conversation_id)
    assert conv2 is not None
    assert conv2.id == conv.id
    assert conv2.message_count == 2
    assert outcome2.messages_added == 1


def test_ingest_log_file_duplicate_returns_duplicate_status(db_session, sample_workspace):
    """Ingesting the same file twice does not add new messages."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    _write_jsonl(
        path,
        [
            '{"sessionId":"orchestrator-dupe","version":"2.0.17","type":"user","message":{"role":"user","content":"Hi"},"uuid":"m1","timestamp":"2025-01-01T00:00:00Z"}',
        ],
    )

    service = IngestionService(db_session)
    first = service.ingest_from_file(
        file_path=path,
        workspace_id=sample_workspace.id,
    )
    db_session.commit()
    assert first.status == "success"
    assert first.conversation_id is not None

    second = service.ingest_from_file(
        file_path=path,
        workspace_id=sample_workspace.id,
    )
    db_session.commit()
    assert second.status == "success"
    assert second.messages_added == 0
    assert second.conversation_id == first.conversation_id
