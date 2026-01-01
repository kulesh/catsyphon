"""AI Advisor module for automation opportunity detection.

This module analyzes conversations to identify patterns that could be
automated as slash commands, MCP servers, or sub-agents.
"""

from catsyphon.advisor.detector import SlashCommandDetector
from catsyphon.advisor.mcp_detector import MCPDetector
from catsyphon.advisor.models import (
    MCP_CATEGORIES,
    MCPDetectionResult,
    MCPRecommendation,
    SlashCommandRecommendation,
)

__all__ = [
    "MCPDetector",
    "MCPDetectionResult",
    "MCPRecommendation",
    "MCP_CATEGORIES",
    "SlashCommandDetector",
    "SlashCommandRecommendation",
]
