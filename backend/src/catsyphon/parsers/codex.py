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

from catsyphon.models.parsed import (
    ConversationMetadata,
    ParsedConversation,
    ParsedMessage,
)
from catsyphon.parsers.base import ParseDataError, ParseFormatError
from catsyphon.parsers.incremental import (
    IncrementalParseResult,
    MessageChunk,
    calculate_partial_hash,
)
from catsyphon.parsers.metadata import ParserCapability, ParserMetadata
from catsyphon.parsers.types import ProbeResult
from catsyphon.parsers.utils import parse_iso_timestamp

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
            capabilities={
                ParserCapability.BATCH,
                ParserCapability.INCREMENTAL,
                ParserCapability.STREAMING,
            },
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
        return self.probe(file_path).can_parse

    def probe(self, file_path: Path) -> ProbeResult:
        if file_path.suffix.lower() != ".jsonl":
            return ProbeResult(can_parse=False, confidence=0.0, reasons=["not .jsonl"])
        if not file_path.is_file():
            return ProbeResult(
                can_parse=False, confidence=0.0, reasons=["file missing or unreadable"]
            )

        reasons: list[str] = []
        confidence = 0.25

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
                    reasons.append("originator=codex")
                    return ProbeResult(can_parse=True, confidence=0.9, reasons=reasons)
                if payload.get("model_provider") in {"openai", "openai-codex"}:
                    reasons.append("model_provider=openai")
                    confidence = max(confidence, 0.8)
            if rec_type in {"response_item", "event_msg"} and payload.get("type"):
                # Heuristic: Codex message scaffolding
                if "content" in payload or "message" in payload:
                    reasons.append("response_item scaffold found")
                    confidence = max(confidence, 0.6)

        return ProbeResult(
            can_parse=bool(reasons), confidence=confidence, reasons=reasons
        )

    # ------------------------------------------------------------------
    # Deprecated: IncrementalParser protocol (ADR-003)
    # Use parse_metadata() + parse_messages() instead (ADR-009).
    # ------------------------------------------------------------------

    def supports_incremental(self, file_path: Path) -> bool:
        """.. deprecated:: ADR-009
        Use ``parse_messages(offset=N)`` instead.
        """
        return self.can_parse(file_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_from_line(
        self, line: str, file_path: Optional[Path] = None
    ) -> Optional[_CodexRecord]:
        """Parse a single JSONL line into a _CodexRecord."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            if file_path:
                logger.debug("Skipping invalid JSON line in %s", file_path)
            return None

        ts = data.get("timestamp")
        try:
            ts_dt = parse_iso_timestamp(ts) if ts else datetime.now(UTC)
        except ValueError:
            ts_dt = datetime.now(UTC)

        return _CodexRecord(
            timestamp=ts_dt,
            type=data.get("type", ""),
            payload=data.get("payload") or {},
        )

    def _load_records(self, file_path: Path) -> list[_CodexRecord]:
        records: list[_CodexRecord] = []
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = self._record_from_line(line, file_path=file_path)
                if rec:
                    records.append(rec)
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
                            thinking_content=(
                                "\n".join(thinking_parts) if thinking_parts else None
                            ),
                        )
                    )
                elif p_type == "reasoning":
                    # Treat reasoning blocks as assistant thinking attached to last assistant msg
                    reasoning_texts = []
                    summary = rec.payload.get("summary") or []
                    for item in summary:
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "summary_text"
                        ):
                            reasoning_texts.append(item.get("text", ""))
                    if messages and reasoning_texts:
                        last = messages[-1]
                        existing = last.thinking_content or ""
                        joiner = "\n\n" if existing else ""
                        reasoning_joined = "\n".join(reasoning_texts)
                        last.thinking_content = f"{existing}{joiner}{reasoning_joined}"
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

    # ------------------------------------------------------------------
    # ADR-009: Chunked parsing (ChunkedParser protocol)
    # ------------------------------------------------------------------

    def _parse_lines_limited(
        self,
        file_path: Path,
        start_offset: int,
        start_line: int,
        limit: int,
    ) -> tuple[list[_CodexRecord], int, int, bool]:
        """Read up to *limit* valid JSONL records from *start_offset*.

        Defers partial trailing lines at EOF (same as ``parse_incremental``).

        Returns:
            ``(records, new_offset, new_line, is_eof)``
        """
        records: list[_CodexRecord] = []
        line_num = start_line
        file_size = file_path.stat().st_size
        last_good_offset = start_offset
        last_good_line = start_line

        with file_path.open("r", encoding="utf-8") as f:
            f.seek(start_offset)
            while len(records) < limit:
                line = f.readline()
                if not line:
                    return records, last_good_offset, last_good_line, True

                line_num += 1
                if not line.strip():
                    last_good_offset = f.tell()
                    last_good_line = line_num
                    continue

                rec = self._record_from_line(line)
                if rec is None:
                    # At EOF, partial line — defer to next pass
                    if f.tell() >= file_size:
                        logger.debug(
                            "Deferring partial trailing line at %s:%s",
                            file_path,
                            line_num,
                        )
                        return records, last_good_offset, last_good_line, False
                    # Otherwise skip malformed line but advance offset
                    last_good_offset = f.tell()
                    last_good_line = line_num
                    continue

                records.append(rec)
                last_good_offset = f.tell()
                last_good_line = line_num

        # Reached limit — not EOF
        return records, last_good_offset, last_good_line, False

    def parse_metadata(self, file_path: Path) -> ConversationMetadata:
        """Extract session-level metadata from the first few Codex log lines.

        Reads until ``session_meta`` is found (typically line 1).
        """
        records, _, _, _ = self._parse_lines_limited(file_path, 0, 0, 20)

        session_meta = next(
            (r for r in records if r.type == "session_meta" and r.payload), None
        )
        if not session_meta:
            raise ParseDataError("Codex log missing session_meta")

        payload = session_meta.payload
        session_id = payload.get("id") or payload.get("session_id")
        if not session_id:
            raise ParseDataError("Codex session_meta missing id")

        return ConversationMetadata(
            session_id=session_id,
            agent_type="codex",
            start_time=records[0].timestamp if records else datetime.now(UTC),
            agent_version=payload.get("cli_version"),
            working_directory=payload.get("cwd"),
            git_branch=None,
            conversation_type="main",
            parent_session_id=None,
            metadata={
                "source": payload.get("source") or payload.get("originator"),
                "model_provider": payload.get("model_provider"),
            },
        )

    def parse_messages(
        self,
        file_path: Path,
        offset: int = 0,
        limit: int = 500,
    ) -> MessageChunk:
        """Parse up to *limit* Codex messages starting from byte *offset*."""
        records, new_offset, new_line, is_eof = self._parse_lines_limited(
            file_path, offset, 0, limit
        )

        file_size = file_path.stat().st_size

        if not records:
            partial_hash = calculate_partial_hash(file_path, new_offset)
            return MessageChunk(
                messages=[],
                next_offset=new_offset,
                next_line=new_line,
                is_last=is_eof,
                partial_hash=partial_hash,
                file_size=file_size,
            )

        messages = self._build_messages(records)
        messages.sort(key=lambda m: m.timestamp)

        partial_hash = calculate_partial_hash(file_path, new_offset)
        return MessageChunk(
            messages=messages,
            next_offset=new_offset,
            next_line=new_line,
            is_last=is_eof,
            partial_hash=partial_hash,
            file_size=file_size,
        )

    # ------------------------------------------------------------------
    # Convenience wrapper (tests, scripts, backward compatibility)
    # ------------------------------------------------------------------

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse a Codex log via chunked methods for backward compatibility."""
        if not self.can_parse(file_path):
            raise ParseFormatError(f"Not a Codex log: {file_path}")

        meta = self.parse_metadata(file_path)
        all_messages: list[ParsedMessage] = []
        offset = 0

        while True:
            chunk = self.parse_messages(file_path, offset)
            all_messages.extend(chunk.messages)
            offset = chunk.next_offset
            if chunk.is_last:
                break

        if not all_messages and not meta.session_id:
            raise ParseDataError("Codex log is empty")

        start_time = meta.start_time
        end_time = all_messages[-1].timestamp if all_messages else start_time

        return ParsedConversation(
            agent_type="codex",
            agent_version=meta.agent_version,
            start_time=start_time,
            end_time=end_time,
            messages=all_messages,
            metadata=meta.metadata,
            session_id=meta.session_id,
            git_branch=None,
            working_directory=meta.working_directory,
            files_touched=[],
            code_changes=[],
            conversation_type="main",
            parent_session_id=None,
            context_semantics={},
            agent_metadata={},
        )

    # ------------------------------------------------------------------
    # Deprecated: parse_incremental (ADR-003)
    # ------------------------------------------------------------------

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """
        Parse only new Codex log lines appended since last_offset.

        Handles partial trailing lines by deferring them until the next pass.
        """
        if not file_path.exists():
            raise ParseFormatError(f"File does not exist: {file_path}")

        file_size = file_path.stat().st_size
        if last_offset < 0 or last_offset > file_size:
            raise ValueError(
                f"Offset {last_offset} out of bounds for {file_path} (size={file_size})"
            )

        logger.info(
            "Incremental parse (codex): %s from offset %s (line %s)",
            file_path,
            last_offset,
            last_line,
        )

        new_records: list[_CodexRecord] = []
        line_num = last_line
        last_good_offset = last_offset
        last_good_line = last_line

        with file_path.open("r", encoding="utf-8") as f:
            f.seek(last_offset)
            while True:
                line = f.readline()
                if not line:
                    break

                line_num += 1
                if not line.strip():
                    last_good_offset = f.tell()
                    last_good_line = line_num
                    continue

                rec = self._record_from_line(line)
                if rec is None:
                    # If we're at EOF, treat this as a partial line and retry next pass.
                    if f.tell() >= file_size:
                        logger.debug(
                            "Deferring partial/invalid trailing line at %s:%s",
                            file_path,
                            line_num,
                        )
                        break
                    # Otherwise skip malformed line but advance offset so we don't loop.
                    last_good_offset = f.tell()
                    last_good_line = line_num
                    continue

                new_records.append(rec)
                last_good_offset = f.tell()
                last_good_line = line_num

        parsed_messages = self._build_messages(new_records)
        parsed_messages.sort(key=lambda m: m.timestamp)
        last_message_timestamp = (
            parsed_messages[-1].timestamp if parsed_messages else None
        )

        partial_hash = calculate_partial_hash(file_path, last_good_offset)

        return IncrementalParseResult(
            new_messages=parsed_messages,
            last_processed_offset=last_good_offset,
            last_processed_line=last_good_line,
            file_size_bytes=file_size,
            partial_hash=partial_hash,
            last_message_timestamp=last_message_timestamp,
        )
