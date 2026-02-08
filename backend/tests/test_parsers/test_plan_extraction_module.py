"""Unit tests for the plan_extraction module (standalone functions)."""

import pytest

from catsyphon.models.parsed import ParsedMessage, PlanInfo, ToolCall
from catsyphon.parsers.plan_extraction import (
    PLAN_FILE_PATTERN,
    PLAN_MODE_ENTRY_PATTERN,
    detect_plan_mode_entry,
    extract_plan_operations,
    is_plan_file_path,
)


class TestIsPlanFilePath:
    """Test the is_plan_file_path standalone function."""

    def test_standard_plan_path(self):
        assert is_plan_file_path("/Users/test/.claude/plans/my-plan.md")

    def test_tilde_plan_path(self):
        assert is_plan_file_path("~/.claude/plans/my-plan.md")

    def test_home_user_path(self):
        assert is_plan_file_path("/home/user/.claude/plans/feature-plan.md")

    def test_windows_path_normalization(self):
        assert is_plan_file_path("C:\\Users\\test\\.claude\\plans\\my-plan.md")

    def test_plan_path_with_hyphens(self):
        assert is_plan_file_path(
            "/Users/test/.claude/plans/frolicking-hugging-swing.md"
        )

    def test_plan_path_with_numbers(self):
        assert is_plan_file_path("/Users/test/.claude/plans/plan-with-numbers-123.md")

    def test_non_plan_path(self):
        assert not is_plan_file_path("/Users/test/project/src/main.py")

    def test_claude_config_not_plan(self):
        assert not is_plan_file_path("/Users/test/.claude/config.json")

    def test_plans_directory_not_plan(self):
        assert not is_plan_file_path("/Users/test/.claude/plans/")

    def test_empty_path(self):
        assert not is_plan_file_path("")

    def test_none_input(self):
        assert not is_plan_file_path(None)


class TestDetectPlanModeEntry:
    """Test the detect_plan_mode_entry standalone function."""

    def test_detects_new_plan(self):
        content = """<system-reminder>
Plan mode is active. The user indicated that they do not want you to execute yet.

## Plan File Info:
No plan file exists yet. You should create your plan at /Users/test/.claude/plans/test-plan.md using the Write tool.
</system-reminder>"""
        result = detect_plan_mode_entry(content)
        assert result == "/Users/test/.claude/plans/test-plan.md"

    def test_detects_existing_plan(self):
        content = """<system-reminder>
Plan mode is active. The user indicated that they do not want you to execute yet.

## Plan File Info:
A plan file already exists at /Users/kulesh/.claude/plans/existing-plan.md.
</system-reminder>"""
        result = detect_plan_mode_entry(content)
        assert result == "/Users/kulesh/.claude/plans/existing-plan.md"

    def test_no_plan_mode(self):
        assert detect_plan_mode_entry("Hello, how are you?") is None

    def test_empty_content(self):
        assert detect_plan_mode_entry("") is None

    def test_none_content(self):
        assert detect_plan_mode_entry(None) is None

    def test_partial_match_no_path(self):
        content = "<system-reminder>\nPlan mode is active.\n</system-reminder>"
        assert detect_plan_mode_entry(content) is None


class TestExtractPlanOperations:
    """Test the extract_plan_operations standalone function."""

    def test_empty_messages(self):
        assert extract_plan_operations([]) == []

    def test_no_plan_messages(self):
        msg = ParsedMessage(
            role="user",
            content="Hello, help me with coding",
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        assert extract_plan_operations([msg]) == []

    def test_plan_mode_entry_creates_plan_info(self):
        user_msg = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/new-plan.md\n"
                "</system-reminder>\nHelp me plan"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg])
        assert len(plans) == 1
        assert plans[0].plan_file_path == "/Users/test/.claude/plans/new-plan.md"
        assert plans[0].entry_message_index == 0

    def test_write_to_plan_file(self):
        user_msg = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/write-test.md\n"
                "</system-reminder>\nPlan this"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        assistant_msg = ParsedMessage(
            role="assistant",
            content="Writing plan file.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/write-test.md",
                        "content": "# My Plan\n\n## Steps\n1. Do the thing",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg, assistant_msg])
        assert len(plans) == 1
        plan = plans[0]
        assert plan.initial_content == "# My Plan\n\n## Steps\n1. Do the thing"
        assert plan.final_content == plan.initial_content
        assert len(plan.operations) == 1
        assert plan.operations[0].operation_type == "create"

    def test_edit_to_plan_file_increments_iteration(self):
        user_msg = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/edit-test.md\n"
                "</system-reminder>\nPlan"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        write_msg = ParsedMessage(
            role="assistant",
            content="Creating plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/edit-test.md",
                        "content": "# Plan\n\n## Step 1\nOld step",
                    },
                )
            ],
            code_changes=[],
        )
        edit_msg = ParsedMessage(
            role="assistant",
            content="Updating plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Edit",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/edit-test.md",
                        "old_string": "Old step",
                        "new_string": "New step",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg, write_msg, edit_msg])
        assert len(plans) == 1
        plan = plans[0]
        assert plan.iteration_count == 2  # starts at 1, incremented on edit
        assert plan.final_content == "# Plan\n\n## Step 1\nNew step"
        assert len(plan.operations) == 2
        assert plan.operations[1].operation_type == "edit"

    def test_exit_plan_mode_sets_approved(self):
        user_msg = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/approve-test.md\n"
                "</system-reminder>\nPlan"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        write_msg = ParsedMessage(
            role="assistant",
            content="Writing plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/approve-test.md",
                        "content": "# Plan",
                    },
                )
            ],
            code_changes=[],
        )
        exit_msg = ParsedMessage(
            role="assistant",
            content="Exiting plan mode.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="ExitPlanMode",
                    parameters={},
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg, write_msg, exit_msg])
        assert len(plans) == 1
        assert plans[0].status == "approved"
        assert plans[0].exit_message_index == 2

    def test_plan_without_exit_stays_active(self):
        user_msg = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/active-test.md\n"
                "</system-reminder>\nPlan"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        write_msg = ParsedMessage(
            role="assistant",
            content="Writing plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/active-test.md",
                        "content": "# Plan",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg, write_msg])
        assert len(plans) == 1
        assert plans[0].status == "active"
        assert plans[0].exit_message_index is None

    def test_read_plan_file_creates_referenced_plan(self):
        assistant_msg = ParsedMessage(
            role="assistant",
            content="Let me read the plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Read",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/read-test.md",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([assistant_msg])
        assert len(plans) == 1
        assert plans[0].status == "referenced"
        assert plans[0].plan_file_path == "/Users/test/.claude/plans/read-test.md"

    def test_multiple_plans_tracked_separately(self):
        user_msg_a = ParsedMessage(
            role="user",
            content=(
                "<system-reminder>\n"
                "Plan mode is active.\n"
                "create your plan at /Users/test/.claude/plans/plan-a.md\n"
                "</system-reminder>\nPlan A"
            ),
            timestamp=None,
            tool_calls=[],
            code_changes=[],
        )
        write_a = ParsedMessage(
            role="assistant",
            content="Writing plan A.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/plan-a.md",
                        "content": "# Plan A",
                    },
                )
            ],
            code_changes=[],
        )
        write_b = ParsedMessage(
            role="assistant",
            content="Writing plan B.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/plan-b.md",
                        "content": "# Plan B",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([user_msg_a, write_a, write_b])
        assert len(plans) == 2
        plan_paths = {p.plan_file_path for p in plans}
        assert "/Users/test/.claude/plans/plan-a.md" in plan_paths
        assert "/Users/test/.claude/plans/plan-b.md" in plan_paths

    def test_write_to_plan_without_mode_entry(self):
        """A write to a plan file without prior plan mode entry should still be tracked."""
        assistant_msg = ParsedMessage(
            role="assistant",
            content="Writing plan.",
            timestamp=None,
            tool_calls=[
                ToolCall(
                    tool_name="Write",
                    parameters={
                        "file_path": "/Users/test/.claude/plans/no-entry.md",
                        "content": "# Surprise Plan",
                    },
                )
            ],
            code_changes=[],
        )
        plans = extract_plan_operations([assistant_msg])
        assert len(plans) == 1
        assert plans[0].initial_content == "# Surprise Plan"


class TestPatternConstants:
    """Test that the regex constants are properly exported and functional."""

    def test_plan_file_pattern_matches(self):
        assert PLAN_FILE_PATTERN.search(".claude/plans/test.md")
        assert not PLAN_FILE_PATTERN.search(".claude/config.json")

    def test_plan_mode_entry_pattern_matches(self):
        text = (
            "<system-reminder>\n"
            "Plan mode is active.\n"
            "create your plan at /tmp/test.md"
        )
        match = PLAN_MODE_ENTRY_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "/tmp/test.md"
