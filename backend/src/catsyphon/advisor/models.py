"""Pydantic models for advisor recommendations."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SlashCommandRecommendation(BaseModel):
    """A recommendation to create a slash command from detected patterns."""

    command_name: str = Field(
        description="Suggested slash command name (e.g., 'format-code')"
    )
    title: str = Field(
        description="Human-readable title for the recommendation"
    )
    description: str = Field(
        description="Detailed description of what the command would do"
    )
    trigger_phrases: list[str] = Field(
        default_factory=list,
        description="Example phrases that would trigger this command"
    )
    template: Optional[str] = Field(
        default=None,
        description="Suggested template for the command implementation"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0)"
    )
    priority: int = Field(
        default=2,
        ge=0,
        le=4,
        description="Priority level (0=critical, 4=low)"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting evidence (message indices, quotes)"
    )


class DetectionResult(BaseModel):
    """Result from running the slash command detector."""

    recommendations: list[SlashCommandRecommendation] = Field(
        default_factory=list,
        description="List of detected slash command opportunities"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID of the analyzed conversation"
    )
    tokens_analyzed: int = Field(
        default=0,
        description="Number of tokens in the analyzed narrative"
    )
    detection_model: str = Field(
        default="gpt-4o-mini",
        description="Model used for detection"
    )
