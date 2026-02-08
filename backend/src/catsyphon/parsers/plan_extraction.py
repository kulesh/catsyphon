"""
Plan extraction from Claude Code conversation logs.

Extracts plan mode information including plan file creation, editing,
approval, and related agent sessions from parsed conversation messages.
"""

import logging
import re
from typing import Optional

from catsyphon.models.parsed import ParsedMessage, PlanInfo, PlanOperation

logger = logging.getLogger(__name__)

# Plan detection patterns
PLAN_FILE_PATTERN = re.compile(r"\.claude/plans/[^/]+\.md$")
PLAN_MODE_ENTRY_PATTERN = re.compile(
    r"<system-reminder>\s*Plan mode is active.*?"
    r"(?:create your plan at|already exists at|A plan file already exists at)\s+([\S]+\.md)",
    re.DOTALL | re.IGNORECASE,
)


def is_plan_file_path(file_path: str) -> bool:
    """
    Check if a file path is a Claude Code plan file.

    Args:
        file_path: The file path to check

    Returns:
        True if the path matches the plan file pattern (~/.claude/plans/*.md)
    """
    if not file_path:
        return False
    # Normalize path separators and handle home directory
    normalized = file_path.replace("\\", "/")
    return bool(PLAN_FILE_PATTERN.search(normalized))


def detect_plan_mode_entry(content: str) -> Optional[str]:
    """
    Detect plan mode entry from user message content.

    Looks for system-reminder tags indicating plan mode is active and
    extracts the plan file path.

    Args:
        content: The message content to check

    Returns:
        The plan file path if plan mode is active, None otherwise
    """
    if not content:
        return None
    match = PLAN_MODE_ENTRY_PATTERN.search(content)
    if match:
        return match.group(1)
    return None


def extract_plan_operations(
    parsed_messages: list[ParsedMessage],
) -> list[PlanInfo]:
    """
    Extract plan information from parsed messages.

    Tracks:
    - Plan mode entry/exit via system-reminder tags and ExitPlanMode tool
    - Write operations to plan files (initial content)
    - Edit operations to plan files (iterations)
    - Task tool calls with Plan subagent

    Args:
        parsed_messages: List of parsed messages from the conversation

    Returns:
        List of PlanInfo objects, one per unique plan file detected
    """
    plans_by_path: dict[str, PlanInfo] = {}
    current_plan_path: Optional[str] = None

    for msg_idx, msg in enumerate(parsed_messages):
        # Check for plan mode entry in user messages
        if msg.role == "user":
            detected_path = detect_plan_mode_entry(msg.content)
            if detected_path:
                current_plan_path = detected_path
                logger.debug(f"Plan mode entry detected: {detected_path}")

                # Initialize plan if not already tracked
                if current_plan_path not in plans_by_path:
                    plans_by_path[current_plan_path] = PlanInfo(
                        plan_file_path=current_plan_path,
                        entry_message_index=msg_idx,
                    )
                else:
                    # Update entry index for potential re-entry
                    plans_by_path[current_plan_path].entry_message_index = msg_idx

        # Check tool calls in assistant messages
        if msg.role == "assistant" and msg.tool_calls:
            for tool_call in msg.tool_calls:
                # ExitPlanMode detection
                if tool_call.tool_name == "ExitPlanMode":
                    # Find the plan to mark as approved
                    plan_to_approve = None
                    if current_plan_path and current_plan_path in plans_by_path:
                        plan_to_approve = plans_by_path[current_plan_path]
                    elif plans_by_path:
                        # Fallback: find plan with most recent operation
                        latest_plan = None
                        latest_msg_idx = -1
                        for plan in plans_by_path.values():
                            if plan.operations:
                                last_op_idx = plan.operations[-1].message_index
                                if last_op_idx > latest_msg_idx:
                                    latest_msg_idx = last_op_idx
                                    latest_plan = plan
                        plan_to_approve = latest_plan

                    if plan_to_approve:
                        plan_to_approve.exit_message_index = msg_idx
                        plan_to_approve.status = "approved"
                        logger.debug(
                            f"Plan approved via ExitPlanMode: "
                            f"{plan_to_approve.plan_file_path}"
                        )

                    current_plan_path = None
                    continue

                # Task tool with Plan subagent - track related agent
                if tool_call.tool_name == "Task":
                    subagent_type = tool_call.parameters.get("subagent_type", "")
                    if subagent_type.lower() == "plan":
                        if current_plan_path and current_plan_path in plans_by_path:
                            # Could extract agent_id from result if available
                            logger.debug(f"Plan agent spawned for: {current_plan_path}")

                # Read operations to plan files - track as referenced
                if tool_call.tool_name == "Read":
                    file_path = tool_call.parameters.get("file_path", "")
                    if is_plan_file_path(file_path):
                        # Initialize plan if this is a new path we haven't seen
                        if file_path not in plans_by_path:
                            plans_by_path[file_path] = PlanInfo(
                                plan_file_path=file_path,
                                status="referenced",
                            )
                            logger.debug(f"Plan file referenced (read): {file_path}")
                        continue

                # Write/Edit to plan files
                file_path = tool_call.parameters.get("file_path", "")
                if not is_plan_file_path(file_path):
                    continue

                # Initialize plan if this is a new path we haven't seen
                if file_path not in plans_by_path:
                    plans_by_path[file_path] = PlanInfo(plan_file_path=file_path)

                plan = plans_by_path[file_path]

                if tool_call.tool_name == "Write":
                    content = tool_call.parameters.get("content", "")
                    operation = PlanOperation(
                        operation_type="create",
                        file_path=file_path,
                        content=content,
                        timestamp=msg.timestamp,
                        message_index=msg_idx,
                    )
                    plan.operations.append(operation)

                    # Track initial and final content
                    if plan.initial_content is None:
                        plan.initial_content = content
                    plan.final_content = content
                    # Upgrade status from 'referenced' to 'active' if we're writing
                    if plan.status == "referenced":
                        plan.status = "active"
                    logger.debug(f"Plan file created: {file_path}")

                elif tool_call.tool_name == "Edit":
                    old_content = tool_call.parameters.get("old_string", "")
                    new_content = tool_call.parameters.get("new_string", "")
                    operation = PlanOperation(
                        operation_type="edit",
                        file_path=file_path,
                        old_content=old_content,
                        new_content=new_content,
                        timestamp=msg.timestamp,
                        message_index=msg_idx,
                    )
                    plan.operations.append(operation)
                    plan.iteration_count += 1

                    # Update final content with edit
                    if plan.final_content:
                        plan.final_content = plan.final_content.replace(
                            old_content, new_content
                        )
                    # Upgrade status from 'referenced' to 'active' if we're editing
                    if plan.status == "referenced":
                        plan.status = "active"
                    logger.debug(
                        f"Plan file edited: {file_path} "
                        f"(iteration {plan.iteration_count})"
                    )

    return list(plans_by_path.values())
