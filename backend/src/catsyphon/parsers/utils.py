"""
Utility functions for parsing conversation logs.

This module provides common utilities used by various parsers, including
timestamp parsing, thread reconstruction, and tool call matching.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dateutil import parser as date_parser


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string to a datetime object.

    Args:
        timestamp_str: ISO 8601 formatted timestamp (e.g., "2025-10-16T19:12:28.024Z")

    Returns:
        Parsed datetime object (timezone-aware)

    Raises:
        ValueError: If the timestamp string is invalid
    """
    try:
        return date_parser.isoparse(timestamp_str)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


def build_message_tree(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Build a tree structure from messages using parentUuid relationships.

    Args:
        messages: List of message dictionaries with 'uuid' and 'parentUuid' fields

    Returns:
        Dictionary mapping message UUID to message data with 'children' field added

    Note:
        This function preserves the original message order and builds a tree
        structure that can be traversed to reconstruct conversation flow.
    """
    # Create lookup by UUID
    message_map = {msg["uuid"]: {**msg, "children": []} for msg in messages}

    # Build parent-child relationships
    for msg in messages:
        parent_uuid = msg.get("parentUuid")
        if parent_uuid and parent_uuid in message_map:
            message_map[parent_uuid]["children"].append(msg["uuid"])

    return message_map


def match_tool_calls_with_results(
    messages: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Match tool invocations with their results.

    Tool calls appear in assistant messages as 'tool_use' content items.
    Results appear in subsequent user messages as 'tool_result' content items.
    This function creates a mapping from tool_use_id to the result.

    Args:
        messages: List of message dictionaries

    Returns:
        Dictionary mapping tool_use_id to tool result data

    Example:
        >>> messages = [
        ...     {"message": {"content": [{"type": "tool_use", "id": "t1", ...}]}},
        ...     {"message": {"content": [
        ...         {"type": "tool_result", "tool_use_id": "t1", ...}
        ...     ]}}
        ... ]
        >>> results = match_tool_calls_with_results(messages)
        >>> results["t1"]  # Returns the tool result
    """
    tool_results: dict[str, dict[str, Any]] = {}

    for msg in messages:
        message_data = msg.get("message", {})
        content = message_data.get("content", [])

        # Handle both string and array content formats
        if isinstance(content, str):
            continue

        # Look for tool results
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                tool_use_id = item.get("tool_use_id")
                if tool_use_id:
                    tool_results[tool_use_id] = item

    return tool_results


def extract_text_content(content: Any) -> str:
    """
    Extract text content from a message's content field.

    Content can be:
    - A string (simple message)
    - An array of content items (structured message)

    Args:
        content: The message content (string or array)

    Returns:
        Extracted text content, or empty string if none found
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "\n".join(text_parts)

    return ""


def extract_thinking_content(content: Any) -> Optional[str]:
    """
    Extract thinking content from a message's content field.

    Thinking blocks are Claude's extended thinking feature that shows
    internal reasoning before responding. They appear as type: "thinking"
    content blocks in assistant messages.

    Args:
        content: The message content (string or array)

    Returns:
        Extracted thinking content, or None if none found

    Example:
        >>> content = [
        ...     {"type": "thinking", "thinking": "Let me analyze this..."},
        ...     {"type": "text", "text": "Here's my answer"}
        ... ]
        >>> extract_thinking_content(content)
        "Let me analyze this..."
    """
    if not isinstance(content, list):
        return None

    thinking_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "thinking":
            thinking_text = item.get("thinking", "")
            if thinking_text:
                thinking_parts.append(thinking_text)

    return "\n\n".join(thinking_parts) if thinking_parts else None


def safe_get_nested(
    data: dict[str, Any], *keys: str, default: Any = None
) -> Optional[Any]:
    """
    Safely get a nested dictionary value.

    Args:
        data: The dictionary to search
        *keys: Sequence of keys to traverse
        default: Default value if path doesn't exist

    Returns:
        The value at the nested path, or default if not found

    Example:
        >>> data = {"message": {"content": [{"type": "text"}]}}
        >>> safe_get_nested(data, "message", "content", 0, "type")
        'text'
        >>> safe_get_nested(data, "message", "missing", "key", default="N/A")
        'N/A'
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, list) and isinstance(key, int):
            try:
                current = current[key]
            except (IndexError, TypeError):
                return default
        else:
            return default

        if current is None:
            return default

    return current


def is_conversational_log(file_path: Path, max_lines: int = 5) -> bool:
    """
    Quick pre-check to identify conversational logs vs metadata-only files.

    Checks first N lines for Claude Code conversation markers (sessionId + version).
    This is a lightweight filter to skip obviously non-conversational files before
    attempting full parse.

    Metadata-only files typically contain only 'summary' and 'file-history-snapshot'
    message types without sessionId/version fields. These are auxiliary files created
    by Claude Code for tracking state and are not meant to be parsed as conversations.

    Args:
        file_path: Path to .jsonl file to check
        max_lines: Number of lines to check (default: 5, enough to detect markers)

    Returns:
        True if file appears to be a conversational log (has sessionId + version)
        False if file appears to be metadata-only (no conversation markers found)

    Example:
        >>> path = Path("session-123.jsonl")
        >>> is_conversational_log(path)
        True
        >>> metadata_path = Path("metadata-only.jsonl")
        >>> is_conversational_log(metadata_path)
        False

    Note:
        This is a heuristic check. The full parser still validates files completely.
        Files that pass this pre-check may still be rejected by the parser if they
        have deeper validation issues.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                # Stop after checking max_lines
                if i >= max_lines:
                    return False  # First N lines don't have markers

                # Skip empty lines
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    # Look for Claude Code conversation markers
                    if "sessionId" in data and "version" in data:
                        return True  # Conversational log detected
                except json.JSONDecodeError:
                    # Malformed JSON line, continue checking
                    continue

    except (OSError, UnicodeDecodeError):
        # File can't be read - let parser handle it
        return False

    # No markers found in first N lines = likely metadata-only file
    return False
