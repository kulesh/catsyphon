"""Rule-based conversation tagger for deterministic tags."""

import logging
import re
from typing import Optional

from catsyphon.models.parsed import ConversationTags, ParsedConversation

logger = logging.getLogger(__name__)


# Error patterns to detect problems
ERROR_PATTERNS = [
    r"\berror\b",
    r"\bexception\b",
    r"\bfailed\b",
    r"\bfailure\b",
    r"\btraceback\b",
    r"\bwarning\b",
    r"⚠️",
    r"❌",
    r"\[error\]",
    r"\[warning\]",
]

# Tool patterns (from Claude Code, Copilot, Cursor, etc.)
TOOL_PATTERNS = {
    "bash": r"\b(bash|shell|terminal|command)\b",
    "read": r"\b(read|cat|view|open)\s+file",
    "write": r"\b(write|create|save)\s+file",
    "edit": r"\b(edit|modify|update|change)\s+file",
    "grep": r"\b(grep|search|find)\b",
    "glob": r"\b(glob|pattern|match)\b",
    "test": r"\b(test|pytest|unittest|vitest)\b",
    "git": r"\b(git|commit|push|pull|branch)\b",
    "npm": r"\b(npm|yarn|pnpm)\b",
    "docker": r"\b(docker|container)\b",
}


class RuleTagger:
    """Tagger that extracts deterministic tags using pattern matching.

    This tagger is fast, free, and always accurate for detecting:
    - Error presence
    - Tool usage
    - Iteration count
    """

    def tag_conversation(self, parsed: ParsedConversation) -> ConversationTags:
        """Extract rule-based tags from conversation.

        Args:
            parsed: The parsed conversation to analyze

        Returns:
            ConversationTags with rule-extracted metadata
        """
        # Detect errors
        has_errors = self._detect_errors(parsed)

        # Extract tool usage
        tools_used = self._extract_tools(parsed)

        # Count iterations (default to 1, would need epoch info from database)
        iterations = 1

        # Extract patterns (common phrases/issues)
        patterns = self._extract_patterns(parsed)

        return ConversationTags(
            has_errors=has_errors,
            tools_used=tools_used,
            iterations=iterations,
            patterns=patterns,
        )

    def tag_from_canonical(
        self,
        canonical,
        metadata: Optional[dict] = None,
    ) -> ConversationTags:
        """Extract rule-based tags from canonical conversation.

        This is the preferred method as it uses pre-extracted metadata
        from the canonical representation instead of text searching.

        Args:
            canonical: CanonicalConversation object
            metadata: Optional additional metadata

        Returns:
            ConversationTags with rule-extracted metadata
        """
        # Extract directly from canonical metadata
        has_errors = canonical.has_errors
        tools_used = canonical.tools_used or []

        # Use epoch count as iterations proxy
        iterations = canonical.epoch_count

        # Derive patterns from canonical metadata
        patterns = self._derive_patterns_from_canonical(canonical)

        logger.debug(
            f"Extracted rule tags from canonical: "
            f"errors={has_errors}, tools={tools_used}, patterns={patterns}"
        )

        return ConversationTags(
            has_errors=has_errors,
            tools_used=tools_used,
            iterations=iterations,
            patterns=patterns,
        )

    def _detect_errors(self, parsed: ParsedConversation) -> bool:
        """Detect if conversation contains errors or warnings.

        Args:
            parsed: The parsed conversation

        Returns:
            True if errors detected, False otherwise
        """
        # Check messages for error patterns
        combined_text = " ".join((msg.content or "").lower() for msg in parsed.messages)

        for pattern in ERROR_PATTERNS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                logger.debug(f"Error pattern matched: {pattern}")
                return True

        return False

    def _extract_tools(self, parsed: ParsedConversation) -> list[str]:
        """Extract list of tools used in conversation.

        Args:
            parsed: The parsed conversation

        Returns:
            List of tool names detected
        """
        tools = set()
        combined_text = " ".join((msg.content or "").lower() for msg in parsed.messages)

        for tool_name, pattern in TOOL_PATTERNS.items():
            if re.search(pattern, combined_text, re.IGNORECASE):
                tools.add(tool_name)
                logger.debug(f"Tool detected: {tool_name}")

        return sorted(tools)

    def _extract_patterns(self, parsed: ParsedConversation) -> list[str]:
        """Extract common patterns or themes from conversation.

        Args:
            parsed: The parsed conversation

        Returns:
            List of detected patterns
        """
        patterns = []

        # Check for common conversation patterns
        combined_text = " ".join((msg.content or "").lower() for msg in parsed.messages)

        # Long conversation pattern
        if len(parsed.messages) > 50:
            patterns.append("long_conversation")

        # Quick resolution pattern
        if len(parsed.messages) <= 5:
            patterns.append("quick_resolution")

        # Type checking pattern
        if re.search(r"\b(mypy|type\s+error|type\s+checking)\b", combined_text):
            patterns.append("type_checking")

        # Testing pattern
        if re.search(r"\b(test|pytest|unittest|coverage)\b", combined_text):
            patterns.append("testing")

        # Debugging pattern
        if re.search(r"\b(debug|debugger|breakpoint|print)\b", combined_text):
            patterns.append("debugging")

        # Dependency pattern
        if re.search(r"\b(dependency|install|package|requirements)\b", combined_text):
            patterns.append("dependency_management")

        # Refactoring pattern
        if re.search(r"\b(refactor|rename|restructure|reorganize)\b", combined_text):
            patterns.append("refactoring")

        return patterns

    def _derive_patterns_from_canonical(self, canonical) -> list[str]:
        """Derive patterns from canonical conversation metadata.

        This is more efficient than text searching as it uses
        pre-extracted metadata and structured information.

        Args:
            canonical: CanonicalConversation object

        Returns:
            List of detected patterns
        """
        patterns = []

        # Length-based patterns
        if canonical.message_count > 50:
            patterns.append("long_conversation")
        elif canonical.message_count <= 5:
            patterns.append("quick_resolution")

        # Tool-based patterns
        tools_used = set(canonical.tools_used or [])

        if any(t in tools_used for t in ["test", "pytest", "vitest"]):
            patterns.append("testing")

        if any(t in tools_used for t in ["git", "commit", "push"]):
            patterns.append("git_operations")

        if any(t in tools_used for t in ["npm", "yarn", "pnpm"]):
            patterns.append("dependency_management")

        if any(t in tools_used for t in ["docker", "container"]):
            patterns.append("containerization")

        # Use narrative for specific pattern detection (more efficient than full text)
        narrative_lower = canonical.narrative.lower()

        if re.search(r"\b(mypy|type\s+error|type\s+checking)\b", narrative_lower):
            patterns.append("type_checking")

        if re.search(r"\b(debug|debugger|breakpoint)\b", narrative_lower):
            patterns.append("debugging")

        if re.search(r"\b(refactor|rename|restructure|reorganize)\b", narrative_lower):
            patterns.append("refactoring")

        # Error-based patterns
        if canonical.has_errors:
            patterns.append("error_handling")

        # Child conversation patterns (agent delegation)
        if canonical.children:
            patterns.append("agent_delegation")

        return patterns
