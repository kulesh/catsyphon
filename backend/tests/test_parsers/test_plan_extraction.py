"""Tests for plan extraction from Claude Code logs."""

from pathlib import Path

import pytest

from catsyphon.parsers.claude_code import ClaudeCodeParser


class TestPlanModeDetection:
    """Test plan mode entry detection from system-reminder tags."""

    def test_detect_plan_mode_entry(self):
        """Test detecting plan mode from system-reminder content."""
        parser = ClaudeCodeParser()
        content = """<system-reminder>
Plan mode is active. The user indicated that they do not want you to execute yet.

## Plan File Info:
No plan file exists yet. You should create your plan at /Users/test/.claude/plans/my-plan.md using the Write tool.
</system-reminder>"""

        result = parser._detect_plan_mode_entry(content)
        assert result == "/Users/test/.claude/plans/my-plan.md"

    def test_detect_plan_mode_existing_plan(self):
        """Test detecting plan mode when plan file already exists."""
        parser = ClaudeCodeParser()
        content = """<system-reminder>
Plan mode is active. The user indicated that they do not want you to execute yet.

## Plan File Info:
A plan file already exists at /Users/kulesh/.claude/plans/existing-plan.md.
</system-reminder>"""

        # This pattern should still find the path
        result = parser._detect_plan_mode_entry(content)
        assert result == "/Users/kulesh/.claude/plans/existing-plan.md"

    def test_no_plan_mode_regular_message(self):
        """Test that regular messages don't trigger plan mode detection."""
        parser = ClaudeCodeParser()
        result = parser._detect_plan_mode_entry("Hello, can you help me with code?")
        assert result is None

    def test_no_plan_mode_empty_content(self):
        """Test handling of empty content."""
        parser = ClaudeCodeParser()
        assert parser._detect_plan_mode_entry("") is None
        assert parser._detect_plan_mode_entry(None) is None


class TestPlanFilePathDetection:
    """Test plan file path identification."""

    def test_standard_plan_path(self):
        """Test standard plan file paths are detected."""
        parser = ClaudeCodeParser()
        assert parser._is_plan_file_path("/Users/test/.claude/plans/my-plan.md")
        assert parser._is_plan_file_path("~/.claude/plans/my-plan.md")
        assert parser._is_plan_file_path("/home/user/.claude/plans/feature-plan.md")

    def test_plan_path_with_special_chars(self):
        """Test plan paths with special characters."""
        parser = ClaudeCodeParser()
        assert parser._is_plan_file_path(
            "/Users/test/.claude/plans/frolicking-hugging-swing.md"
        )
        assert parser._is_plan_file_path(
            "/Users/test/.claude/plans/plan-with-numbers-123.md"
        )

    def test_non_plan_paths(self):
        """Test that non-plan paths are not detected."""
        parser = ClaudeCodeParser()
        assert not parser._is_plan_file_path("/Users/test/project/README.md")
        assert not parser._is_plan_file_path("/Users/test/.claude/config.json")
        assert not parser._is_plan_file_path("/Users/test/.claude/plans/")
        assert not parser._is_plan_file_path("")
        assert not parser._is_plan_file_path(None)

    def test_windows_path_normalization(self):
        """Test that Windows-style paths are normalized."""
        parser = ClaudeCodeParser()
        # Windows paths should be normalized to forward slashes
        assert parser._is_plan_file_path("C:\\Users\\test\\.claude\\plans\\plan.md")


class TestPlanExtraction:
    """Test full plan extraction from conversation fixtures."""

    @pytest.fixture
    def plan_conversation_path(self):
        """Path to the plan conversation test fixture."""
        return Path(__file__).parent / "fixtures" / "plan_conversation.jsonl"

    def test_extract_plan_from_conversation(self, plan_conversation_path):
        """Test extracting plan data from a complete conversation."""
        parser = ClaudeCodeParser()
        result = parser.parse(plan_conversation_path)

        # Should have extracted 1 plan
        assert len(result.plans) == 1
        plan = result.plans[0]

        # Check plan file path
        assert plan.plan_file_path == "/Users/test/.claude/plans/test-plan-abcd1234.md"

        # Check status is approved (ExitPlanMode was called)
        assert plan.status == "approved"

        # Check iteration count (1 initial write + 1 edit = 2, but iteration_count
        # starts at 1 and increments on edits, so should be 2)
        assert plan.iteration_count == 2

        # Check initial content was captured
        assert plan.initial_content is not None
        assert "User Authentication Implementation Plan" in plan.initial_content
        assert "JWT tokens" in plan.initial_content

        # Check final content includes the edit
        assert plan.final_content is not None
        assert "Write unit and integration tests" in plan.final_content

        # Check operations were tracked
        assert len(plan.operations) == 2

        # First operation should be create
        assert plan.operations[0].operation_type == "create"
        assert plan.operations[0].content is not None

        # Second operation should be edit
        assert plan.operations[1].operation_type == "edit"
        assert plan.operations[1].old_content is not None
        assert plan.operations[1].new_content is not None

    def test_plan_entry_and_exit_indices(self, plan_conversation_path):
        """Test that entry and exit message indices are tracked."""
        parser = ClaudeCodeParser()
        result = parser.parse(plan_conversation_path)

        assert len(result.plans) == 1
        plan = result.plans[0]

        # Entry should be at message index 0 (first user message with system-reminder)
        assert plan.entry_message_index == 0

        # Exit should be at the message index where ExitPlanMode was called
        # This is in the assistant message at index 4 (0-indexed: user, assistant, user, assistant, user, assistant)
        # Actually the messages are: user(0), assistant(1), user(tool_result, skipped), assistant(2), user(3), assistant(4), etc
        # But tool_result messages are filtered, so we need to count actual conversational messages
        assert plan.exit_message_index is not None
        assert plan.exit_message_index > plan.entry_message_index


class TestPlanExtractionEdgeCases:
    """Test edge cases in plan extraction."""

    def test_conversation_without_plans(self, tmp_path):
        """Test parsing a conversation that has no plan operations."""
        # Create a simple conversation without any plan operations
        content = """{"sessionId":"no-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":"Hello, how are you?"},"uuid":"msg-1","timestamp":"2025-01-15T10:00:00.000Z","cwd":"/Users/test/project"}
{"sessionId":"no-plan-001","version":"2.0.28","type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I'm doing well! How can I help you today?"}]},"uuid":"msg-2","timestamp":"2025-01-15T10:00:01.000Z"}"""

        file_path = tmp_path / "no_plan.jsonl"
        file_path.write_text(content)

        parser = ClaudeCodeParser()
        result = parser.parse(file_path)

        # Should have no plans
        assert len(result.plans) == 0

    def test_plan_without_exit(self, tmp_path):
        """Test plan that was created but never exited (abandoned)."""
        content = """{"sessionId":"abandoned-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":"<system-reminder>\\nPlan mode is active.\\ncreate your plan at /Users/test/.claude/plans/abandoned.md\\n</system-reminder>\\nHelp me plan something"},"uuid":"msg-1","timestamp":"2025-01-15T10:00:00.000Z","cwd":"/Users/test/project"}
{"sessionId":"abandoned-plan-001","version":"2.0.28","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Write","input":{"file_path":"/Users/test/.claude/plans/abandoned.md","content":"# Abandoned Plan"}}]},"uuid":"msg-2","timestamp":"2025-01-15T10:00:01.000Z"}
{"sessionId":"abandoned-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":"File written"}]},"uuid":"msg-3","timestamp":"2025-01-15T10:00:02.000Z"}"""

        file_path = tmp_path / "abandoned_plan.jsonl"
        file_path.write_text(content)

        parser = ClaudeCodeParser()
        result = parser.parse(file_path)

        # Should have 1 plan with status "active" (not approved)
        assert len(result.plans) == 1
        assert result.plans[0].status == "active"
        assert result.plans[0].exit_message_index is None

    def test_multiple_plans_in_conversation(self, tmp_path):
        """Test conversation with multiple different plan files."""
        content = """{"sessionId":"multi-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":"<system-reminder>\\nPlan mode is active.\\ncreate your plan at /Users/test/.claude/plans/plan-a.md\\n</system-reminder>\\nPlan A"},"uuid":"msg-1","timestamp":"2025-01-15T10:00:00.000Z","cwd":"/Users/test/project"}
{"sessionId":"multi-plan-001","version":"2.0.28","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Write","input":{"file_path":"/Users/test/.claude/plans/plan-a.md","content":"# Plan A"}}]},"uuid":"msg-2","timestamp":"2025-01-15T10:00:01.000Z"}
{"sessionId":"multi-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":"File written"}]},"uuid":"msg-3","timestamp":"2025-01-15T10:00:02.000Z"}
{"sessionId":"multi-plan-001","version":"2.0.28","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"t2","name":"Write","input":{"file_path":"/Users/test/.claude/plans/plan-b.md","content":"# Plan B"}}]},"uuid":"msg-4","timestamp":"2025-01-15T10:00:03.000Z"}
{"sessionId":"multi-plan-001","version":"2.0.28","type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t2","content":"File written"}]},"uuid":"msg-5","timestamp":"2025-01-15T10:00:04.000Z"}"""

        file_path = tmp_path / "multi_plan.jsonl"
        file_path.write_text(content)

        parser = ClaudeCodeParser()
        result = parser.parse(file_path)

        # Should have 2 plans
        assert len(result.plans) == 2

        plan_paths = {p.plan_file_path for p in result.plans}
        assert "/Users/test/.claude/plans/plan-a.md" in plan_paths
        assert "/Users/test/.claude/plans/plan-b.md" in plan_paths


class TestPlanDataSerialization:
    """Test plan data serialization to dict for JSONB storage."""

    def test_plan_info_to_dict(self, tmp_path):
        """Test that PlanInfo.to_dict() produces valid JSONB-ready dict."""
        content = """{"sessionId":"serialize-001","version":"2.0.28","type":"user","message":{"role":"user","content":"<system-reminder>\\nPlan mode is active.\\ncreate your plan at /Users/test/.claude/plans/serialize-test.md\\n</system-reminder>\\nTest"},"uuid":"msg-1","timestamp":"2025-01-15T10:00:00.000Z","cwd":"/Users/test/project"}
{"sessionId":"serialize-001","version":"2.0.28","type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Write","input":{"file_path":"/Users/test/.claude/plans/serialize-test.md","content":"# Test Plan"}}]},"uuid":"msg-2","timestamp":"2025-01-15T10:00:01.000Z"}
{"sessionId":"serialize-001","version":"2.0.28","type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":"File written"}]},"uuid":"msg-3","timestamp":"2025-01-15T10:00:02.000Z"}"""

        file_path = tmp_path / "serialize.jsonl"
        file_path.write_text(content)

        parser = ClaudeCodeParser()
        result = parser.parse(file_path)

        assert len(result.plans) == 1
        plan_dict = result.plans[0].to_dict()

        # Check structure
        assert "plan_file_path" in plan_dict
        assert "initial_content" in plan_dict
        assert "final_content" in plan_dict
        assert "status" in plan_dict
        assert "iteration_count" in plan_dict
        assert "operations" in plan_dict
        assert "entry_message_index" in plan_dict
        assert "exit_message_index" in plan_dict
        assert "related_agent_session_ids" in plan_dict

        # Check operations are also serialized
        assert isinstance(plan_dict["operations"], list)
        if plan_dict["operations"]:
            op = plan_dict["operations"][0]
            assert "operation_type" in op
            assert "file_path" in op
            assert "timestamp" in op  # Should be ISO string or None
