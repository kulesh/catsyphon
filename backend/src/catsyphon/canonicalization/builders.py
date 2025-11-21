"""Builders for converting conversations to narrative formats."""

import logging
from datetime import datetime
from typing import Optional

from catsyphon.canonicalization.models import CanonicalConfig, CanonicalConversation
from catsyphon.canonicalization.samplers import SampledMessage
from catsyphon.models.db import Conversation, FileTouched

logger = logging.getLogger(__name__)


class PlayFormatBuilder:
    """Build theatrical 'play' format narrative from conversation.

    Creates a chronological narrative with:
    - Act/Scene structure (epochs and message clusters)
    - Character labels (USER, ASSISTANT, AGENT, SYSTEM)
    - Stage directions (tool calls, code changes, thinking)
    - Hierarchical asides (agent delegations)
    """

    def __init__(self, config: CanonicalConfig):
        """Initialize builder.

        Args:
            config: Canonicalization configuration
        """
        self.config = config

    def build(
        self,
        conversation: Conversation,
        sampled_messages: list[SampledMessage],
        files_touched: list[FileTouched],
        children: Optional[list[CanonicalConversation]] = None,
    ) -> str:
        """Build play format narrative.

        Args:
            conversation: Main conversation
            sampled_messages: Sampled and prioritized messages
            files_touched: Files touched during conversation
            children: Child conversations (agents, MCP, etc.)

        Returns:
            Play format narrative as string
        """
        lines: list[str] = []

        # Header
        lines.append(self._build_header(conversation, files_touched))
        lines.append("")

        # Messages
        current_epoch_id = None
        for i, sm in enumerate(sampled_messages):
            msg = sm.message

            # Epoch transition
            if msg.epoch_id != current_epoch_id:
                if current_epoch_id is not None:
                    lines.append("")  # Blank line between epochs
                epoch_num = self._get_epoch_sequence(msg.epoch_id, conversation)
                lines.append(f"--- EPOCH {epoch_num} ---")
                lines.append("")
                current_epoch_id = msg.epoch_id

            # Message
            lines.extend(self._build_message(msg, sm.reason))

            # Check if there's a child conversation spawned after this message
            if children:
                for child in children:
                    # Simple heuristic: if child start time is close to this message
                    if self._child_spawned_after(msg, child):
                        lines.append("")
                        lines.extend(self._build_child_narrative(child))
                        lines.append("")

            lines.append("")  # Blank line after each message

        # Summary
        lines.append(self._build_summary(conversation, sampled_messages))

        return "\n".join(lines)

    def _build_header(
        self, conversation: Conversation, files_touched: list[FileTouched]
    ) -> str:
        """Build conversation header."""
        duration = None
        if conversation.start_time and conversation.end_time:
            delta = conversation.end_time - conversation.start_time
            duration = int(delta.total_seconds() / 60)  # minutes

        status_str = conversation.status.upper()
        if conversation.success is not None:
            status_str += " (SUCCESS)" if conversation.success else " (FAILED)"

        header = f"""=== CONVERSATION: {conversation.id} ===
Agent: {conversation.agent_type}"""

        if conversation.agent_version:
            header += f" v{conversation.agent_version}"

        header += f"""
Type: {conversation.conversation_type}
Started: {conversation.start_time.strftime('%Y-%m-%d %H:%M:%S')}"""

        if conversation.end_time:
            header += f"""
Ended: {conversation.end_time.strftime('%Y-%m-%d %H:%M:%S')}"""

        if duration:
            header += f"""
Duration: {duration} minutes"""

        header += f"""
Status: {status_str}
Messages: {conversation.message_count} | Epochs: {conversation.epoch_count} | Files: {len(files_touched)}"""

        return header

    def _build_message(self, msg: any, reason: str) -> list[str]:
        """Build message lines."""
        lines: list[str] = []

        # Timestamp and role
        time_str = msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else "??:??:??"
        role_str = msg.role.upper()

        # Content (truncated if needed)
        content = msg.content or "(no content)"
        if len(content) > self.config.max_message_chars:
            content = content[: self.config.max_message_chars] + "..."

        lines.append(f"[{time_str}] {role_str}: {content}")

        # Sampling reason (for debugging)
        if reason and reason != "normal":
            lines.append(f"  [PRIORITY: {reason}]")

        # Tool calls
        if msg.tool_calls and self.config.include_tool_details:
            tools_str = ", ".join(
                tc.get("tool_name", "unknown") for tc in msg.tool_calls
            )
            lines.append(f"  [TOOLS: {tools_str}]")

            # Tool details (truncated)
            for tc in msg.tool_calls:
                params = tc.get("parameters", {})
                if params and len(str(params)) > self.config.max_tool_param_chars:
                    param_str = str(params)[: self.config.max_tool_param_chars] + "..."
                else:
                    param_str = str(params)

                success_str = "✓" if tc.get("success", True) else "✗"
                lines.append(f"    {success_str} {tc.get('tool_name', 'unknown')}: {param_str}")

        # Code changes
        if msg.code_changes and self.config.include_code_changes:
            for cc in msg.code_changes:
                file_path = cc.get("file_path", "unknown")
                change_type = cc.get("change_type", "unknown")
                lines_added = cc.get("lines_added", 0)
                lines_deleted = cc.get("lines_deleted", 0)

                change_str = f"{file_path} - {change_type}"
                if lines_added or lines_deleted:
                    change_str += f" (+{lines_added}/-{lines_deleted})"

                lines.append(f"  [CODE: {change_str}]")

        # Thinking content
        if msg.thinking_content and self.config.include_thinking:
            thinking = msg.thinking_content
            if len(thinking) > self.config.max_thinking_chars:
                thinking = thinking[: self.config.max_thinking_chars] + "..."

            lines.append(f"  [THINKING: {thinking}]")

        return lines

    def _build_child_narrative(self, child: CanonicalConversation) -> list[str]:
        """Build narrative for child conversation (agent, MCP, etc.)."""
        lines: list[str] = []

        duration = None
        if child.duration_seconds:
            duration = int(child.duration_seconds / 60)  # minutes

        lines.append(f"┌─ AGENT DELEGATION: {child.conversation_id} ─┐")
        lines.append(f"│ Type: {child.conversation_type}")
        lines.append(f"│ Messages: {child.message_count} | Duration: {duration} min" if duration else f"│ Messages: {child.message_count}")
        lines.append(f"│ Tools: {', '.join(child.tools_used[:5])}" if child.tools_used else "│ Tools: None")
        lines.append(f"│ Files: {len(child.files_touched)}")
        lines.append("│")

        # Include child narrative (indented)
        for line in child.narrative.split("\n"):
            if line.strip():
                lines.append(f"│   {line}")

        lines.append("└────────────────────────────────────────┘")

        return lines

    def _build_summary(
        self, conversation: Conversation, sampled_messages: list[SampledMessage]
    ) -> str:
        """Build conversation summary."""
        # Extract tags
        tags = conversation.tags or {}

        summary = """=== SUMMARY ==="""

        if tags.get("outcome"):
            summary += f"""
Outcome: {tags.get('outcome').upper()}"""

        if tags.get("intent"):
            summary += f"""
Intent: {tags.get('intent')}"""

        if tags.get("sentiment"):
            score = tags.get("sentiment_score", 0.0)
            summary += f"""
Sentiment: {tags.get('sentiment')} ({score:.1f})"""

        if tags.get("problems"):
            problems = tags.get("problems", [])[:3]  # Top 3
            summary += f"""
Problems: {', '.join(problems)}"""

        if tags.get("features"):
            features = tags.get("features", [])[:3]  # Top 3
            summary += f"""
Features: {', '.join(features)}"""

        if tags.get("tools_used"):
            tools = tags.get("tools_used", [])
            summary += f"""
Tools Used: {', '.join(tools)}"""

        # Sampling stats
        total_messages = conversation.message_count
        sampled_count = len(sampled_messages)
        summary += f"""

Sampling: {sampled_count}/{total_messages} messages included"""

        return summary

    def _get_epoch_sequence(self, epoch_id: any, conversation: Conversation) -> int:
        """Get epoch sequence number."""
        for epoch in conversation.epochs:
            if epoch.id == epoch_id:
                return epoch.sequence
        return 0

    def _child_spawned_after(
        self, msg: any, child: CanonicalConversation
    ) -> bool:
        """Check if child was spawned after this message.

        Simple heuristic: child start time within 1 minute of message timestamp.
        """
        if not msg.timestamp or not child.start_time:
            return False

        delta = abs((child.start_time - msg.timestamp).total_seconds())
        return delta < 60  # Within 1 minute


class JSONBuilder:
    """Build structured JSON representation."""

    def __init__(self, config: CanonicalConfig):
        """Initialize builder.

        Args:
            config: Canonicalization configuration
        """
        self.config = config

    def build(
        self,
        conversation: Conversation,
        sampled_messages: list[SampledMessage],
        files_touched: list[FileTouched],
        children: Optional[list[CanonicalConversation]] = None,
    ) -> dict:
        """Build JSON representation.

        Args:
            conversation: Main conversation
            sampled_messages: Sampled and prioritized messages
            files_touched: Files touched during conversation
            children: Child conversations

        Returns:
            Dictionary suitable for JSON serialization
        """
        return {
            "conversation_id": str(conversation.id),
            "session_id": conversation.extra_data.get("session_id"),
            "agent_type": conversation.agent_type,
            "agent_version": conversation.agent_version,
            "conversation_type": conversation.conversation_type,
            "start_time": conversation.start_time.isoformat(),
            "end_time": conversation.end_time.isoformat() if conversation.end_time else None,
            "duration_seconds": (
                int((conversation.end_time - conversation.start_time).total_seconds())
                if conversation.end_time and conversation.start_time
                else None
            ),
            "status": conversation.status,
            "success": conversation.success,
            "message_count": conversation.message_count,
            "epoch_count": conversation.epoch_count,
            "files_count": len(files_touched),
            "tags": conversation.tags,
            "messages": [
                {
                    "role": sm.message.role,
                    "content": sm.message.content,
                    "timestamp": sm.message.timestamp.isoformat() if sm.message.timestamp else None,
                    "tool_calls": sm.message.tool_calls if self.config.include_tool_details else [],
                    "code_changes": sm.message.code_changes if self.config.include_code_changes else [],
                    "thinking": sm.message.thinking_content if self.config.include_thinking else None,
                    "priority": sm.priority,
                    "reason": sm.reason,
                }
                for sm in sampled_messages
            ],
            "files_touched": [
                {"file_path": f.file_path, "change_type": f.change_type}
                for f in files_touched
            ],
            "children": [child.to_dict() for child in (children or [])],
        }
