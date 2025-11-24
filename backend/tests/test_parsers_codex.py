import json
from datetime import datetime, UTC
from pathlib import Path

from catsyphon.parsers.codex import CodexParser


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
