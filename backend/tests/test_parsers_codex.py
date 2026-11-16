import json
from datetime import UTC, datetime
from pathlib import Path

from catsyphon.parsers.codex import CodexParser, _is_encrypted_content


def _session_meta(ts: str) -> dict:
    return {
        "timestamp": ts,
        "type": "session_meta",
        "payload": {
            "id": "codex-session-123",
            "cwd": "/Users/example/project",
            "originator": "codex_cli",
            "cli_version": "0.63.0",
            "model_provider": "openai",
        },
    }


def _write_jsonl(tmp_path: Path, lines: list[dict], name: str = "codex-log.jsonl") -> Path:
    log_file = tmp_path / name
    with log_file.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return log_file


def _write_codex_log(tmp_path: Path) -> Path:
    ts = datetime.now(UTC).isoformat()
    log_file = tmp_path / "codex-log.jsonl"
    lines = [
        {
            "timestamp": ts,
            "type": "session_meta",
            "payload": {
                "id": "codex-session-123",
                "cwd": "/Users/example/project",
                "originator": "codex_cli",
                "cli_version": "0.63.0",
                "model_provider": "openai",
            },
        },
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello Codex"}],
            },
        },
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hi there"}],
                "token_usage": {"input_tokens": 10, "output_tokens": 5},
            },
        },
    ]
    with log_file.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return log_file


def test_codex_parser_parses_basic_log(tmp_path):
    parser = CodexParser()
    file_path = _write_codex_log(tmp_path)

    assert parser.can_parse(file_path) is True

    parsed = parser.parse(file_path)

    assert parsed.agent_type == "codex"
    assert parsed.session_id == "codex-session-123"
    assert parsed.working_directory == "/Users/example/project"
    assert parsed.agent_version == "0.63.0"
    assert len(parsed.messages) == 2
    assert parsed.messages[0].role == "user"
    assert parsed.messages[0].content == "Hello Codex"
    assert parsed.messages[1].role == "assistant"
    assert parsed.messages[1].content == "Hi there"


def test_encrypted_delegation_record_flagged(tmp_path):
    """Whole-record encrypted delegation (Codex CLI 0.138.0+)."""
    ts = datetime.now(UTC).isoformat()
    lines = [
        _session_meta(ts),
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "delegate this"}],
            },
        },
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "encrypted_delegation",
                "role": "assistant",
                "data": "Y2lwaGVydGV4dC1ibG9i" * 20,
            },
        },
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Done with subtask"}],
            },
        },
    ]
    parsed = CodexParser().parse(_write_jsonl(tmp_path, lines))
    assert len(parsed.messages) == 3
    encrypted_msg = parsed.messages[1]
    assert encrypted_msg.content == "[encrypted delegation]"
    assert encrypted_msg.message_type == "encrypted"
    assert encrypted_msg.entities.get("content_encrypted") is True
    # Non-encrypted messages unaffected
    assert parsed.messages[0].content == "delegate this"
    assert parsed.messages[2].content == "Done with subtask"


def test_encrypted_content_block_within_message(tmp_path):
    """Message with a mix of readable and encrypted content blocks."""
    ts = datetime.now(UTC).isoformat()
    ciphertext = "A" * 200  # long base64-like string
    lines = [
        _session_meta(ts),
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Starting delegation..."},
                    {"type": "encrypted", "data": ciphertext},
                    {"type": "output_text", "text": "Subtask complete."},
                ],
            },
        },
    ]
    parsed = CodexParser().parse(_write_jsonl(tmp_path, lines))
    msg = parsed.messages[0]
    assert msg.content == "Starting delegation...\nSubtask complete."
    assert msg.entities.get("content_encrypted") is True


def test_encrypted_flag_on_payload(tmp_path):
    """Record-level encrypted flag on the payload."""
    ts = datetime.now(UTC).isoformat()
    lines = [
        _session_meta(ts),
        {
            "timestamp": ts,
            "type": "response_item",
            "payload": {
                "type": "message",
                "encrypted": True,
                "role": "assistant",
                "content": "opaque-bytes",
            },
        },
    ]
    parsed = CodexParser().parse(_write_jsonl(tmp_path, lines))
    msg = parsed.messages[0]
    assert msg.content == "[encrypted delegation]"
    assert msg.entities.get("content_encrypted") is True


def test_is_encrypted_content_detection():
    assert _is_encrypted_content({"type": "encrypted", "data": "abc"}) is True
    assert _is_encrypted_content({"type": "ciphertext", "data": "abc"}) is True
    assert _is_encrypted_content({"encrypted": True, "text": "x"}) is True
    assert _is_encrypted_content({"type": "output_text", "text": "hello"}) is False
    assert _is_encrypted_content({"type": "input_text", "text": "hello"}) is False
    # Long base64 blob detected
    assert _is_encrypted_content({"type": "unknown", "text": "A" * 200}) is True
    # Short strings are not flagged
    assert _is_encrypted_content({"type": "unknown", "text": "short"}) is False
    assert _is_encrypted_content("just a string") is False
