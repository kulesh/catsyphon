"""
Shared parser result types.

Provides structured metadata for downstream ingestion to improve
observability without changing the core ParsedConversation model.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

from catsyphon.models.parsed import ParsedConversation


class ParseIssueSeverity(Enum):
    """Severity level for parse issues."""

    WARNING = "warning"  # Non-fatal: some data skipped but file processed
    ERROR = "error"  # Fatal: file could not be processed


@dataclass
class ParseIssue:
    """
    Structured parse issue for tracking warnings and errors.

    Attributes:
        severity: WARNING (non-fatal) or ERROR (fatal)
        message: Human-readable description
        line_number: Optional line number where issue occurred
        field: Optional field name that had the issue
        context: Optional additional context (e.g., raw line content)
    """

    severity: ParseIssueSeverity
    message: str
    line_number: Optional[int] = None
    field: Optional[str] = None
    context: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.line_number is not None:
            result["line_number"] = self.line_number
        if self.field:
            result["field"] = self.field
        if self.context:
            result["context"] = self.context[:100]  # Truncate for storage
        return result


@dataclass
class ParseResult:
    """
    Structured parse output with metadata for observability.

    Attributes:
        conversation: ParsedConversation produced by the parser.
        parser_name: Identifier for the parser (e.g., "claude-code").
        parser_version: Version string from the parser metadata.
        parse_method: Parsing method used ("full", "incremental").
        change_type: Optional change detection result ("append", "rewrite", etc).
        metrics: Numeric or string metrics emitted by the parser.
        warnings: Human-readable parse warnings collected during detection/parse.
        issues: Structured list of ParseIssue objects for detailed tracking.
    """

    conversation: ParsedConversation
    parser_name: str
    parser_version: Optional[str]
    parse_method: str = "full"
    change_type: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)  # Legacy: string warnings
    issues: List[ParseIssue] = field(default_factory=list)  # New: structured issues

    def add_warning(
        self,
        message: str,
        line_number: Optional[int] = None,
        field: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add a warning (non-fatal issue)."""
        self.issues.append(
            ParseIssue(
                severity=ParseIssueSeverity.WARNING,
                message=message,
                line_number=line_number,
                field=field,
                context=context,
            )
        )
        # Also add to legacy warnings list for backwards compatibility
        self.warnings.append(message)

    def add_error(
        self,
        message: str,
        line_number: Optional[int] = None,
        field: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add an error (fatal issue)."""
        self.issues.append(
            ParseIssue(
                severity=ParseIssueSeverity.ERROR,
                message=message,
                line_number=line_number,
                field=field,
                context=context,
            )
        )

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == ParseIssueSeverity.WARNING)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == ParseIssueSeverity.ERROR)

    @property
    def has_issues(self) -> bool:
        """Whether any issues were recorded."""
        return len(self.issues) > 0

    def issues_to_dict(self) -> dict[str, Any]:
        """Convert issues to dictionary for IngestionJob.metrics storage."""
        return {
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "issues": [i.to_dict() for i in self.issues[:50]],  # Limit stored issues
        }


@dataclass
class ProbeResult:
    """
    Lightweight capability probe result for parser selection.

    Attributes:
        can_parse: Whether the parser believes it can parse the file.
        confidence: 0.0-1.0 confidence score for selection ordering.
        reasons: Human-readable hints for observability/debugging.
    """

    can_parse: bool
    confidence: float = 0.5
    reasons: List[str] = field(default_factory=list)
