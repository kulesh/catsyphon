"""Pydantic models for advisor recommendations."""

from typing import Any, Optional

from pydantic import BaseModel, Field

# MCP Categories Registry - detection signals for external tool integrations
MCP_CATEGORIES: dict[str, dict[str, Any]] = {
    "browser-automation": {
        "signals": [
            r"open.*browser",
            r"click.*button",
            r"fill.*form",
            r"screenshot",
            r"selenium",
            r"playwright",
            r"puppeteer",
            r"UI test",
            r"e2e test",
            r"end-to-end",
            r"visual regression",
            r"scrape.*page",
            r"web.*automation",
        ],
        "mcps": ["playwright-mcp", "puppeteer-mcp", "browser-mcp"],
        "use_cases": [
            "Browser automation",
            "UI/E2E testing",
            "Web scraping",
            "Visual regression testing",
        ],
    },
    "database": {
        "signals": [
            r"SELECT\s+",
            r"INSERT\s+INTO",
            r"UPDATE\s+.*SET",
            r"DELETE\s+FROM",
            r"CREATE\s+TABLE",
            r"ALTER\s+TABLE",
            r"check.*table",
            r"query.*database",
            r"postgres",
            r"mysql",
            r"sqlite",
            r"mongodb",
            r"redis",
            r"run.*sql",
            r"database.*migration",
        ],
        "mcps": ["postgres-mcp", "mysql-mcp", "sqlite-mcp", "mongodb-mcp", "redis-mcp"],
        "use_cases": [
            "Direct database queries",
            "Schema inspection",
            "Data exploration",
            "Migration management",
        ],
    },
    "api-integration": {
        "signals": [
            r"curl\s+",
            r"fetch.*api",
            r"REST.*endpoint",
            r"GraphQL",
            r"HTTP\s+request",
            r"API.*call",
            r"webhook",
            r"oauth",
            r"bearer.*token",
            r"api.*key",
        ],
        "mcps": ["http-mcp", "graphql-mcp", "postman-mcp"],
        "use_cases": [
            "API testing",
            "Third-party integrations",
            "Webhook management",
        ],
    },
    "cloud-services": {
        "signals": [
            r"aws\s+",
            r"s3\s+",
            r"ec2\s+",
            r"lambda\s+",
            r"gcp\s+",
            r"azure\s+",
            r"kubernetes",
            r"kubectl",
            r"docker",
            r"terraform",
            r"cloudformation",
            r"deploy.*cloud",
            r"infrastructure",
        ],
        "mcps": [
            "aws-mcp",
            "gcp-mcp",
            "azure-mcp",
            "kubernetes-mcp",
            "docker-mcp",
        ],
        "use_cases": [
            "Cloud resource management",
            "Container orchestration",
            "Infrastructure as code",
            "Deployment automation",
        ],
    },
    "github-integration": {
        "signals": [
            r"create.*PR",
            r"pull.*request",
            r"list.*issues",
            r"github.*api",
            r"gh\s+",
            r"git.*actions",
            r"workflow.*run",
            r"merge.*request",
            r"code.*review",
        ],
        "mcps": ["github-mcp", "gitlab-mcp"],
        "use_cases": [
            "PR management",
            "Issue tracking",
            "CI/CD workflows",
            "Code review automation",
        ],
    },
    "file-system": {
        "signals": [
            r"read.*file",
            r"write.*file",
            r"upload.*file",
            r"download.*file",
            r"sync.*files",
            r"google.*drive",
            r"dropbox",
            r"s3.*bucket",
            r"file.*watch",
        ],
        "mcps": ["filesystem-mcp", "gdrive-mcp", "dropbox-mcp", "s3-mcp"],
        "use_cases": [
            "File synchronization",
            "Cloud storage access",
            "File watching and automation",
        ],
    },
    "messaging": {
        "signals": [
            r"slack.*message",
            r"send.*notification",
            r"discord.*bot",
            r"teams.*message",
            r"email.*send",
            r"notify.*team",
            r"post.*channel",
        ],
        "mcps": ["slack-mcp", "discord-mcp", "teams-mcp", "email-mcp"],
        "use_cases": [
            "Team notifications",
            "Status updates",
            "Alert management",
        ],
    },
    "observability": {
        "signals": [
            r"check.*logs",
            r"error.*logs",
            r"monitoring",
            r"datadog",
            r"grafana",
            r"prometheus",
            r"sentry",
            r"cloudwatch",
            r"metrics",
            r"traces",
        ],
        "mcps": ["datadog-mcp", "grafana-mcp", "cloudwatch-mcp", "sentry-mcp"],
        "use_cases": [
            "Log analysis",
            "Metrics exploration",
            "Error tracking",
            "Performance monitoring",
        ],
    },
}


class SlashCommandRecommendation(BaseModel):
    """A recommendation to create a slash command from detected patterns."""

    command_name: str = Field(
        description="Suggested slash command name (e.g., 'format-code')"
    )
    title: str = Field(description="Human-readable title for the recommendation")
    description: str = Field(
        description="Detailed description of what the command would do"
    )
    trigger_phrases: list[str] = Field(
        default_factory=list,
        description="Example phrases that would trigger this command",
    )
    template: Optional[str] = Field(
        default=None, description="Suggested template for the command implementation"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    priority: int = Field(
        default=2, ge=0, le=4, description="Priority level (0=critical, 4=low)"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting evidence (message indices, quotes)",
    )


class DetectionResult(BaseModel):
    """Result from running the slash command detector."""

    recommendations: list[SlashCommandRecommendation] = Field(
        default_factory=list, description="List of detected slash command opportunities"
    )
    conversation_id: Optional[str] = Field(
        default=None, description="ID of the analyzed conversation"
    )
    tokens_analyzed: int = Field(
        default=0, description="Number of tokens in the analyzed narrative"
    )
    detection_model: str = Field(
        default="gpt-4o-mini", description="Model used for detection"
    )


class MCPRecommendation(BaseModel):
    """A recommendation to install an MCP server for external tool integration."""

    category: str = Field(
        description="MCP category (browser-automation, database, api-integration, etc.)"
    )
    suggested_mcps: list[str] = Field(
        default_factory=list, description="List of suggested MCP servers to install"
    )
    use_cases: list[str] = Field(
        default_factory=list, description="Use cases this MCP would enable"
    )
    title: str = Field(description="Human-readable title for the recommendation")
    description: str = Field(
        description="Detailed description of why this MCP would help"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    friction_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How much friction was detected without this MCP (0.0 to 1.0)",
    )
    priority: int = Field(
        default=2, ge=0, le=4, description="Priority level (0=critical, 4=low)"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting evidence (matched signals, quotes, workarounds)",
    )


class MCPDetectionResult(BaseModel):
    """Result from running the MCP detector."""

    recommendations: list[MCPRecommendation] = Field(
        default_factory=list, description="List of detected MCP server opportunities"
    )
    conversation_id: Optional[str] = Field(
        default=None, description="ID of the analyzed conversation"
    )
    tokens_analyzed: int = Field(
        default=0, description="Number of tokens in the analyzed narrative"
    )
    detection_model: str = Field(
        default="gpt-4o-mini", description="Model used for detection"
    )
    categories_detected: list[str] = Field(
        default_factory=list, description="Categories that were detected via signals"
    )
