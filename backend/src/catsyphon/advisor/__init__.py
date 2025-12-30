"""AI Advisor module for automation opportunity detection.

This module analyzes conversations to identify patterns that could be
automated as slash commands, MCP servers, or sub-agents.
"""

from catsyphon.advisor.detector import SlashCommandDetector
from catsyphon.advisor.models import SlashCommandRecommendation

__all__ = [
    "SlashCommandDetector",
    "SlashCommandRecommendation",
]
