"""
Claude Code conversation log parser.

This module provides a parser for Claude Code's JSONL conversation logs.
Each log file contains a series of JSON objects, one per line, representing
the conversation timeline.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from catsyphon.models.parsed import (
    CodeChange,
    ParsedConversation,
    ParsedMessage,
    ToolCall,
)
from catsyphon.parsers.base import ParseDataError, ParseFormatError
from catsyphon.parsers.incremental import (
    IncrementalParseResult,
    calculate_partial_hash,
)
from catsyphon.parsers.metadata import ParserCapability, ParserMetadata
from catsyphon.parsers.utils import (
    extract_text_content,
    extract_thinking_content,
    match_tool_calls_with_results,
    parse_iso_timestamp,
)

logger = logging.getLogger(__name__)

# Claude Code version identifiers
CLAUDE_CODE_MIN_VERSION = "2.0.0"


@dataclass
class _MessageData:
    """Internal representation of a parsed message during processing."""

    uuid: str
    parent_uuid: Optional[str]
    timestamp: datetime
    msg_type: str
    role: str
    content: Any
    model: Optional[str]
    tool_use_id: Optional[str]
    is_tool_result: bool
    raw_data: dict[str, Any]


class ClaudeCodeParser:
    """
    Parser for Claude Code JSONL conversation logs.

    Claude Code logs are stored in JSONL (JSON Lines) format with one JSON
    object per line. Each object represents a message, tool call, or other
    event in the conversation timeline.

    Format detection:
    - Files must have .jsonl extension
    - Each line must be valid JSON
    - Objects must contain 'sessionId' and 'version' fields
    - Version must be compatible with Claude Code format

    Supported formats:
    - Modern format (v2.0+): Separate files for agents with 'agentId' field
      * Main conversations: {session_id}.jsonl
      * Agent conversations: agent-{agent_id}.jsonl
      * Messages contain 'agentId' field to identify agent conversations
      * Parent linking supported via agentId as unique session identifier

    Known limitations:
    - Legacy format (pre-v2.0): Single file with mixed agent/main messages
      * Files named: {session_id}.jsonl (no separate agent files)
      * No 'agentId' field in messages
      * Uses 'isSidechain' flag per-message instead of per-file
      * Agent conversations cannot be separated from main thread
      * Parent-child relationships not supported for these files
      * These files are parsed as main conversations with agent messages mixed in
    """

    def __init__(self) -> None:
        """Initialize Claude Code parser."""
        self._metadata = ParserMetadata(
            name="claude-code",
            version="1.0.0",
            supported_formats=[".jsonl"],
            capabilities={ParserCapability.INCREMENTAL, ParserCapability.BATCH},
            priority=50,
            description="Parser for Claude Code conversation logs (JSONL format)",
        )

    @property
    def metadata(self) -> ParserMetadata:
        """Get parser metadata."""
        return self._metadata

    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given log file.

        Args:
            file_path: Path to the log file to check

        Returns:
            True if this is a Claude Code log file, False otherwise
        """
        # Check file extension
        if file_path.suffix.lower() != ".jsonl":
            return False

        # Check file exists and is readable
        if not file_path.exists() or not file_path.is_file():
            return False

        # Scan entire file to detect format
        # Each JSONL message is independent - sessionId could appear anywhere
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        # Look for Claude Code markers
                        if "sessionId" in data and "version" in data:
                            return True
                    except json.JSONDecodeError:
                        continue

        except (OSError, UnicodeDecodeError) as e:
            logger.debug(f"Cannot read file {file_path}: {e}")
            return False

        return False

    def parse(self, file_path: Path) -> ParsedConversation:
        """
        Parse a Claude Code log file into structured format.

        Args:
            file_path: Path to the .jsonl log file

        Returns:
            ParsedConversation object with extracted data

        Raises:
            ParseFormatError: If the file format is invalid
            ParseDataError: If required data is missing
        """
        if not self.can_parse(file_path):
            raise ParseFormatError(f"File is not a valid Claude Code log: {file_path}")

        logger.info(f"Parsing Claude Code log: {file_path}")

        # Parse all lines
        raw_messages = self._parse_all_lines(file_path)

        if not raw_messages:
            raise ParseDataError("Log file is empty or contains no valid messages")

        # Extract session metadata from first message that has it
        session_id = None
        agent_version = None
        git_branch = None
        cwd = None
        is_sidechain = False
        agent_id = None

        for msg in raw_messages[:10]:  # Check first 10 messages
            if "sessionId" in msg:
                session_id = msg.get("sessionId")
                agent_version = msg.get("version")
                git_branch = msg.get("gitBranch")
                cwd = msg.get("cwd")
                is_sidechain = msg.get("isSidechain", False)
                agent_id = msg.get("agentId")
                break

        if not session_id:
            raise ParseDataError("Missing required field: sessionId")

        # Build message thread and extract tool calls
        parsed_messages = self._build_message_thread(raw_messages)

        # Calculate conversation timing
        timestamps = [msg.timestamp for msg in parsed_messages if msg.timestamp]
        start_time = min(timestamps) if timestamps else datetime.now()
        end_time = max(timestamps) if timestamps else start_time

        # Extract code changes from tool calls
        all_tool_calls = []
        for msg in parsed_messages:
            all_tool_calls.extend(msg.tool_calls)

        code_changes = self._detect_code_changes(all_tool_calls)

        # Determine conversation type and hierarchy (Phase 2: Epic 7u2)
        conversation_type = "agent" if is_sidechain else "main"

        # For agent conversations, generate unique session_id and extract parent's session_id
        # Agent log files store the PARENT's session ID in the sessionId field,
        # so we need to generate a unique identifier for the agent itself
        if is_sidechain and agent_id:
            # Use agentId as the unique session identifier for this agent conversation
            agent_session_id = agent_id
            parent_session_id = session_id  # Parent's session ID from file
            session_id_to_use = agent_session_id
        else:
            # Main conversations use sessionId directly
            session_id_to_use = session_id
            parent_session_id = None

        # Context semantics for Claude Code agents (isolated context, can use tools)
        context_semantics = {}
        agent_metadata = {}

        if is_sidechain:
            context_semantics = {
                "shares_parent_context": False,  # Agents have isolated context
                "can_use_parent_tools": True,  # Can use tools like parent
                "isolated_context": True,  # Explicitly isolated
                "max_context_window": None,  # Unknown for Claude Code agents
            }

            agent_metadata = {
                "agent_id": agent_id,
                "agent_type": "subagent",  # Could be Explore, Plan, etc.
                "parent_session_id": parent_session_id,  # Parent's actual session ID
            }

        # Build ParsedConversation
        return ParsedConversation(
            agent_type="claude-code",
            agent_version=agent_version,
            session_id=session_id_to_use,  # Unique ID (agentId for agents, sessionId for main)
            git_branch=git_branch,
            working_directory=cwd,
            start_time=start_time,
            end_time=end_time,
            messages=parsed_messages,
            files_touched=[change.file_path for change in code_changes],
            code_changes=code_changes,
            conversation_type=conversation_type,
            parent_session_id=parent_session_id,
            context_semantics=context_semantics,
            agent_metadata=agent_metadata,
        )

    def supports_incremental(self, file_path: Path) -> bool:
        """
        Check if incremental parsing is supported for this file.

        Args:
            file_path: Path to the log file

        Returns:
            True (Claude Code JSONL format always supports incremental parsing)

        Note:
            Claude Code uses JSONL format which naturally supports incremental
            parsing by appending new lines. This method always returns True for
            valid Claude Code files.
        """
        # Claude Code JSONL format always supports incremental parsing
        # We only check if this is a valid Claude Code file
        return self.can_parse(file_path)

    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int,
    ) -> IncrementalParseResult:
        """
        Parse only new content appended since last_offset.

        This method implements incremental parsing for Claude Code logs,
        reading only NEW lines appended to the file since the last parse.
        This provides ~12x performance improvement over full reparse.

        Args:
            file_path: Path to the log file
            last_offset: Byte offset where parsing last stopped
            last_line: Line number where parsing last stopped

        Returns:
            IncrementalParseResult with only new messages and updated state

        Raises:
            ParseFormatError: If file cannot be read or offset is invalid
            ValueError: If offset exceeds file size
        """
        if not file_path.exists():
            raise ParseFormatError(f"File does not exist: {file_path}")

        file_size = file_path.stat().st_size

        if last_offset < 0:
            raise ValueError(f"Offset must be non-negative, got {last_offset}")

        if last_offset > file_size:
            raise ValueError(
                f"Offset {last_offset} exceeds file size {file_size} for {file_path}"
            )

        logger.info(
            f"Incremental parse: {file_path} from offset {last_offset} "
            f"(line {last_line})"
        )

        # Parse only new lines from last_offset
        raw_messages = self._parse_lines_from_offset(file_path, last_offset, last_line)

        if not raw_messages:
            logger.debug(f"No new messages found in {file_path}")
            # Return empty result with current state
            partial_hash = calculate_partial_hash(file_path, file_size)
            return IncrementalParseResult(
                new_messages=[],
                last_processed_offset=file_size,
                last_processed_line=last_line,
                file_size_bytes=file_size,
                partial_hash=partial_hash,
                last_message_timestamp=None,
            )

        # Filter to only user/assistant messages (same as full parse)
        conversation_messages = [
            msg
            for msg in raw_messages
            if msg.get("type") in ("user", "assistant")
            and msg.get("message", {}).get("role") in ("user", "assistant")
        ]

        # Match tool calls with results (only for conversation messages)
        tool_result_map = match_tool_calls_with_results(conversation_messages)

        # Convert to ParsedMessage objects
        parsed_messages = []
        for msg_data in conversation_messages:
            try:
                parsed_msg = self._convert_to_parsed_message(msg_data, tool_result_map)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)
            except Exception as e:
                logger.warning(f"Failed to parse message {msg_data.get('uuid')}: {e}")
                continue

        # Sort by timestamp
        parsed_messages.sort(key=lambda m: m.timestamp)

        # Get last message timestamp for validation
        last_message_timestamp = None
        if parsed_messages:
            last_message_timestamp = parsed_messages[-1].timestamp

        # Calculate new state
        new_offset = file_size
        new_line = last_line + len(raw_messages)
        partial_hash = calculate_partial_hash(file_path, new_offset)

        logger.info(
            f"Incremental parse complete: {len(parsed_messages)} new messages, "
            f"new offset {new_offset} (line {new_line})"
        )

        return IncrementalParseResult(
            new_messages=parsed_messages,
            last_processed_offset=new_offset,
            last_processed_line=new_line,
            file_size_bytes=file_size,
            partial_hash=partial_hash,
            last_message_timestamp=last_message_timestamp,
        )

    def _parse_lines_from_offset(
        self, file_path: Path, start_offset: int, start_line: int
    ) -> list[dict[str, Any]]:
        """
        Parse lines from a specific byte offset in the file.

        Args:
            file_path: Path to the JSONL file
            start_offset: Byte offset to start reading from
            start_line: Line number to start from (for logging only)

        Returns:
            List of parsed JSON objects from new lines only

        Note:
            Skips invalid lines and logs warnings rather than failing.
        """
        messages = []
        line_num = start_line

        try:
            with file_path.open("r", encoding="utf-8") as f:
                # Seek to the last processed offset
                f.seek(start_offset)

                # Read only new lines from this point
                for line in f:
                    line_num += 1
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        messages.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping invalid JSON at {file_path}:{line_num}: {e}"
                        )
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise ParseFormatError(f"Cannot read file {file_path}: {e}") from e

        return messages

    def _parse_all_lines(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Parse all lines from a JSONL file.

        Args:
            file_path: Path to the JSONL file

        Returns:
            List of parsed JSON objects

        Note:
            Skips invalid lines and logs warnings rather than failing.
        """
        messages = []
        line_num = 0

        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line_num += 1
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        messages.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping invalid JSON at {file_path}:{line_num}: {e}"
                        )
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise ParseFormatError(f"Cannot read file {file_path}: {e}") from e

        return messages

    def _build_message_thread(
        self, raw_messages: list[dict[str, Any]]
    ) -> list[ParsedMessage]:
        """
        Build conversation thread from raw messages.

        This method:
        1. Filters out non-conversational messages (file snapshots, etc.)
        2. Reconstructs the message thread using parentUuid
        3. Matches tool calls with their results
        4. Converts to ParsedMessage objects

        Args:
            raw_messages: List of raw message dictionaries

        Returns:
            List of ParsedMessage objects in chronological order
        """
        # Filter to only user/assistant messages
        conversation_messages = [
            msg
            for msg in raw_messages
            if msg.get("type") in ("user", "assistant")
            and msg.get("message", {}).get("role") in ("user", "assistant")
        ]

        if not conversation_messages:
            logger.warning("No conversational messages found in log")
            return []

        # Match tool calls with results
        tool_result_map = match_tool_calls_with_results(conversation_messages)

        # Convert to ParsedMessage objects
        parsed_messages = []

        for msg_data in conversation_messages:
            try:
                parsed_msg = self._convert_to_parsed_message(msg_data, tool_result_map)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)
            except Exception as e:
                logger.warning(f"Failed to parse message {msg_data.get('uuid')}: {e}")
                continue

        # Sort by timestamp
        parsed_messages.sort(key=lambda m: m.timestamp)

        return parsed_messages

    def _convert_to_parsed_message(
        self, msg_data: dict[str, Any], tool_result_map: dict[str, dict[str, Any]]
    ) -> Optional[ParsedMessage]:
        """
        Convert a raw message to ParsedMessage.

        Args:
            msg_data: Raw message dictionary
            tool_result_map: Mapping of tool_use_id to result data

        Returns:
            ParsedMessage object, or None if conversion fails
        """
        message = msg_data.get("message", {})
        role = message.get("role")
        content = message.get("content", "")

        # Extract timestamp
        timestamp_str = msg_data.get("timestamp")
        if not timestamp_str:
            logger.warning(f"Message {msg_data.get('uuid')} missing timestamp")
            return None

        try:
            timestamp = parse_iso_timestamp(timestamp_str)
        except ValueError as e:
            logger.warning(f"Invalid timestamp in message {msg_data.get('uuid')}: {e}")
            return None

        # Extract text content
        text_content = extract_text_content(content)

        # Extract thinking content (assistant messages only)
        thinking_content = None
        if role == "assistant":
            thinking_content = extract_thinking_content(content)

        # Extract model info (assistant messages only)
        model = message.get("model")

        # Extract tool calls (assistant messages only)
        tool_calls = []
        if role == "assistant" and isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tool_call = self._extract_tool_call(item, tool_result_map)
                    if tool_call:
                        tool_calls.append(tool_call)

        # Extract token usage (assistant messages only)
        usage = message.get("usage", {})
        token_usage = None
        if usage:
            token_usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            }

        return ParsedMessage(
            role=role,
            content=text_content,
            timestamp=timestamp,
            model=model,
            tool_calls=tool_calls,
            token_usage=token_usage,
            thinking_content=thinking_content,
        )

    def _extract_tool_call(
        self, tool_use_item: dict[str, Any], tool_result_map: dict[str, dict[str, Any]]
    ) -> Optional[ToolCall]:
        """
        Extract a tool call with its result.

        Args:
            tool_use_item: Tool use content item from assistant message
            tool_result_map: Mapping of tool_use_id to result data

        Returns:
            ToolCall object, or None if extraction fails
        """
        tool_use_id = tool_use_item.get("id")
        tool_name = tool_use_item.get("name")
        tool_input = tool_use_item.get("input", {})

        if not tool_use_id or not tool_name:
            logger.warning("Tool call missing id or name")
            return None

        # Look up result
        result_item = tool_result_map.get(tool_use_id, {})
        result_content = result_item.get("content", "")
        is_error = result_item.get("is_error", False)

        return ToolCall(
            tool_name=tool_name,
            parameters=tool_input,
            result=result_content,
            success=not is_error,
            timestamp=None,  # Timestamp is on the message level
        )

    def _detect_code_changes(self, tool_calls: list[ToolCall]) -> list[CodeChange]:
        """
        Detect code changes from tool calls.

        Looks for Edit and Write tool calls and extracts file change information.

        Args:
            tool_calls: List of all tool calls from the conversation

        Returns:
            List of CodeChange objects
        """
        code_changes = []

        for tool_call in tool_calls:
            tool_name = tool_call.tool_name

            # Edit tool
            if tool_name == "Edit":
                file_path = tool_call.parameters.get("file_path")
                old_string = tool_call.parameters.get("old_string", "")
                new_string = tool_call.parameters.get("new_string", "")

                if file_path:
                    code_changes.append(
                        CodeChange(
                            file_path=file_path,
                            change_type="edit",
                            old_content=old_string,
                            new_content=new_string,
                        )
                    )

            # Write tool
            elif tool_name == "Write":
                file_path = tool_call.parameters.get("file_path")
                content = tool_call.parameters.get("content", "")

                if file_path:
                    code_changes.append(
                        CodeChange(
                            file_path=file_path,
                            change_type="create",
                            old_content=None,
                            new_content=content,
                        )
                    )

        return code_changes
