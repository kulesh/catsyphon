"""
OpenAI Codex conversation log parser.

Codex stores JSONL session logs under ~/.codex/sessions/YYYY/MM/DD/*.jsonl.
Each line contains a JSON object with a `type` and `payload`.
Key record types:
- session_meta: session id, cwd, cli_version, model_provider, originator
- response_item: user/assistant messages, reasoning blocks, token usage
- event_msg: agent_reasoning / agent_message events
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from catsyphon.models.parsed import ParsedConversation, ParsedMessage, ToolCall
from catsyphon.parsers.base import ParseDataError, ParseFormatError
from catsyphon.parsers.metadata import ParserCapability, ParserMetadata
from catsyphon.parsers.utils import extract_text_content, parse_iso_timestamp

logger = logging.getLogger(__name__)


@dataclass
class _CodexRecord:
    timestamp: datetime
    type: str
    payload: dict[str, Any]


class CodexParser:
    """Parser for OpenAI Codex JSONL session logs."""

    def __init__(self) -> None:
        self._metadata = ParserMetadata(
            name="codex",
            version="1.0.0",
            supported_formats=[".jsonl"],
            capabilities={ParserCapability.BATCH},
            priority=60,  # Slightly above Claude to favor explicit Codex logs
            description="Parser for OpenAI Codex session logs",
        )

    @property
    def metadata(self) -> ParserMetadata:
        return self._metadata

    def _iter_sample_lines(self, file_path: Path, max_lines: int = 80) -> list[str]:
        """Read up to N lines to keep can_parse lightweight."""
        lines: list[str] = []
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f):
                if idx >= max_lines:
                    break
                if line.strip():
                    lines.append(line)
        return lines

    def can_parse(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != ".jsonl":
            return False
        if not file_path.is_file():
            return False

        for line in self._iter_sample_lines(file_path):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            rec_type = data.get("type")
            payload = data.get("payload") or {}
            if rec_type == "session_meta":
                origin = payload.get("originator", "") or payload.get("source", "")
                if "codex" in origin:
                    return True
                if payload.get("model_provider") in {"openai", "openai-codex"}:
                    return True
            if rec_type in {"response_item", "event_msg"} and payload.get("type"):
                # Heuristic: Codex message scaffolding
                if "content" in payload or "message" in payload:
                    return True
        return False

    def _load_records(self, file_path: Path) -> list[_CodexRecord]:
        records: list[_CodexRecord] = []
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping invalid JSON line in %s", file_path)
                    continue

                ts = data.get("timestamp")
                try:
                    ts_dt = parse_iso_timestamp(ts) if ts else datetime.now(UTC)
                except ValueError:
                    ts_dt = datetime.now(UTC)

                records.append(
                    _CodexRecord(
                        timestamp=ts_dt,
                        type=data.get("type", ""),
                        payload=data.get("payload") or {},
                    )
                )
        return records

    def _build_messages(self, records: list[_CodexRecord]) -> list[ParsedMessage]:
        messages: list[ParsedMessage] = []

        for rec in records:
            if rec.type == "response_item":
                p_type = rec.payload.get("type")
                role = rec.payload.get("role")
                if p_type == "message" and role in {"user", "assistant"}:
                    content_items = rec.payload.get("content") or []
                    text_parts = []
                    thinking_parts = []
                    for item in content_items:
                        if isinstance(item, dict):
                            if item.get("type") in {"input_text", "output_text"}:
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "reasoning":
                                thinking_parts.append(item.get("text", ""))
                        elif isinstance(item, str):
                            text_parts.append(item)
                    messages.append(
                        ParsedMessage(
                            role=role,
                            content="\n".join([p for p in text_parts if p]),
                            timestamp=rec.timestamp,
                            tool_calls=[],
                            code_changes=[],
                            entities={},
                            model=rec.payload.get("model"),
                            token_usage=rec.payload.get("token_usage")
                            or rec.payload.get("token_count"),
                            thinking_content="\n".join(thinking_parts)
                            if thinking_parts
                            else None,
                        )
                    )
                elif p_type == "reasoning":
                    # Treat reasoning blocks as assistant thinking attached to last assistant msg
                    reasoning_texts = []
                    summary = rec.payload.get("summary") or []
                    for item in summary:
                        if isinstance(item, dict) and item.get("type") == "summary_text":
                            reasoning_texts.append(item.get("text", ""))
                    if messages and reasoning_texts:
                        last = messages[-1]
                        existing = last.thinking_content or ""
                        joiner = "\n\n" if existing else ""
                        last.thinking_content = f"{existing}{joiner}{'\n'.join(reasoning_texts)}"
            elif rec.type == "event_msg":
                p_type = rec.payload.get("type")
                if p_type in {"agent_message", "agent_reasoning"}:
                    text = rec.payload.get("message") or rec.payload.get("text") or ""
                    role = "assistant"
                    thinking = text if p_type == "agent_reasoning" else None
                    if thinking and messages:
                        last = messages[-1]
                        existing = last.thinking_content or ""
                        joiner = "\n\n" if existing else ""
                        last.thinking_content = f"{existing}{joiner}{thinking}"
                    else:
                        messages.append(
                            ParsedMessage(
                                role=role,
                                content="" if thinking else text,
                                timestamp=rec.timestamp,
                                thinking_content=thinking,
                                tool_calls=[],
                                code_changes=[],
                                entities={},
                            )
                        )

        return messages

    def parse(self, file_path: Path) -> ParsedConversation:
        if not self.can_parse(file_path):
            raise ParseFormatError(f"Not a Codex log: {file_path}")

        records = self._load_records(file_path)
        if not records:
            raise ParseDataError("Codex log is empty")

        # Extract session metadata
        session_meta = next(
            (r for r in records if r.type == "session_meta" and r.payload), None
        )
        if not session_meta:
            raise ParseDataError("Codex log missing session_meta")

        payload = session_meta.payload
        session_id = payload.get("id") or payload.get("session_id")
        if not session_id:
            raise ParseDataError("Codex session_meta missing id")

        cwd = payload.get("cwd")
        cli_version = payload.get("cli_version")
        start_time = records[0].timestamp
        end_time = records[-1].timestamp if records else None

        messages = self._build_messages(records)

        return ParsedConversation(
            agent_type="codex",
            agent_version=cli_version,
            start_time=start_time,
            end_time=end_time,
            messages=messages,
            metadata={
                "source": payload.get("source") or payload.get("originator"),
                "model_provider": payload.get("model_provider"),
            },
            session_id=session_id,
            git_branch=None,
            working_directory=cwd,
            files_touched=[],
            code_changes=[],
            conversation_type="main",
            parent_session_id=None,
            context_semantics={},
            agent_metadata={},
        )
