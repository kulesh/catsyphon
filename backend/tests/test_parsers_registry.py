from pathlib import Path
from datetime import datetime, UTC

from catsyphon.models.parsed import ParsedConversation
from catsyphon.parsers.metadata import ParserMetadata
from catsyphon.parsers.registry import ParserRegistry


class _DummyParserLow:
    def __init__(self) -> None:
        self.metadata = ParserMetadata(
            name="low",
            version="0.1.0",
            supported_formats=[".jsonl"],
            priority=10,
        )

    def can_parse(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path) -> ParsedConversation:
        return ParsedConversation(
            agent_type="low",
            agent_version=None,
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[],
            metadata={},
        )


class _DummyParserHigh:
    def __init__(self) -> None:
        self.metadata = ParserMetadata(
            name="high",
            version="0.2.0",
            supported_formats=[".jsonl"],
            priority=90,
        )

    def can_parse(self, file_path: Path) -> bool:
        return True

    def parse(self, file_path: Path) -> ParsedConversation:
        return ParsedConversation(
            agent_type="high",
            agent_version=None,
            start_time=datetime.now(UTC),
            end_time=None,
            messages=[],
            metadata={},
        )


def test_registry_prefers_higher_priority_and_injects_parser_metadata(tmp_path):
    registry = ParserRegistry()
    registry.register(_DummyParserLow())
    registry.register(_DummyParserHigh())

    # Create minimal JSONL file
    file_path = tmp_path / "sample.jsonl"
    file_path.write_text("{}\n")

    parsed = registry.parse(file_path)

    assert parsed.agent_type == "high"
    assert parsed.metadata.get("parser", {}).get("name") == "high"
