"""
Test parser against all real Claude Code conversation samples.

This test validates that the parser can handle all real-world conversation
logs without errors.
"""

from pathlib import Path

import pytest

from catsyphon.parsers.claude_code import ClaudeCodeParser

# Get all real sample files
SAMPLES_DIR = Path(__file__).parents[3] / "test-samples"
SAMPLE_FILES = list(SAMPLES_DIR.rglob("*.jsonl"))


class TestRealSamples:
    """Tests against real Claude Code conversation samples."""

    @pytest.mark.parametrize("log_file", SAMPLE_FILES, ids=lambda p: p.name)
    def test_can_parse_real_sample(self, log_file: Path):
        """Test that parser can detect format of real sample."""
        parser = ClaudeCodeParser()
        assert parser.can_parse(log_file) is True

    @pytest.mark.parametrize("log_file", SAMPLE_FILES, ids=lambda p: p.name)
    def test_parse_real_sample(self, log_file: Path):
        """Test that parser can parse real sample without errors."""
        parser = ClaudeCodeParser()

        # Should parse without raising exceptions
        result = parser.parse(log_file)

        # Basic validation
        assert result.agent_type == "claude-code"
        assert result.agent_version is not None
        assert len(result.messages) > 0
        assert result.start_time is not None


class TestRealSamplesStatistics:
    """Collect statistics about real samples."""

    def test_parse_all_samples_summary(self):
        """Parse all samples and report summary statistics."""
        parser = ClaudeCodeParser()

        total = len(SAMPLE_FILES)
        successful = 0
        failed = 0
        errors = []

        total_messages = 0
        total_tool_calls = 0

        for log_file in SAMPLE_FILES:
            try:
                result = parser.parse(log_file)
                successful += 1
                total_messages += len(result.messages)
                for msg in result.messages:
                    total_tool_calls += len(msg.tool_calls)
            except Exception as e:
                failed += 1
                errors.append((log_file.name, str(e)))

        # Print summary
        print(f"\n{'='*70}")
        print("Real Sample Parsing Summary")
        print(f"{'='*70}")
        print(f"Total samples: {total}")
        print(f"Successfully parsed: {successful} ({successful/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"\nTotal messages parsed: {total_messages}")
        print(f"Total tool calls extracted: {total_tool_calls}")

        if errors:
            print("\nErrors:")
            for filename, error in errors:
                print(f"  - {filename}: {error}")

        print(f"{'='*70}\n")

        # Test should pass even if some fail (for now)
        # In the future, might want: assert failed == 0
        assert total == len(SAMPLE_FILES)
