"""
Insights API routes.

Endpoints for generating and retrieving canonical-powered insights.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.schemas import InsightsResponse
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository
from catsyphon.insights import InsightsGenerator

router = APIRouter()


@router.get("/{conversation_id}/insights", response_model=InsightsResponse)
def get_conversation_insights(
    conversation_id: UUID,
    force_regenerate: bool = Query(
        default=False,
        description="Force regeneration even if cached insights exist"
    ),
    session: Session = Depends(get_db),
) -> InsightsResponse:
    """
    Get comprehensive insights for a conversation using canonical representation.

    This endpoint generates deep insights about developer-AI collaboration by:
    1. Getting the canonical representation (intelligently sampled narrative)
    2. Analyzing the narrative with LLM for qualitative insights
    3. Extracting quantitative metrics from canonical metadata
    4. Combining both for a comprehensive view

    **Insights Generated:**
    - **Workflow patterns**: Observable patterns (e.g., "iterative-refinement", "error-driven")
    - **Productivity indicators**: Signals of productivity (e.g., "high-tool-diversity")
    - **Collaboration quality**: How well human and agent worked together (1-10)
    - **Key moments**: Critical turning points in the conversation
    - **Learning opportunities**: Areas for improvement
    - **Agent effectiveness**: How helpful the agent was (1-10)
    - **Scope clarity**: How well-defined the goal was (1-10)
    - **Technical debt**: Signs of debt being created or addressed
    - **Testing behavior**: Observations about testing practices
    - **Quantitative metrics**: Message count, tools used, files touched, etc.

    **Caching:**
    Canonical representations are cached, making subsequent insight requests fast.
    Use `force_regenerate=true` to bypass cache.

    Args:
        conversation_id: UUID of the conversation
        force_regenerate: Force regeneration of canonical and insights
        session: Database session

    Returns:
        InsightsResponse with qualitative and quantitative insights

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 500: Insights generation failed
    """
    # Get conversation
    conversation_repo = ConversationRepository(session)
    conversation = conversation_repo.get_by_id(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )

    # Force regeneration if requested
    if force_regenerate:
        from catsyphon.db.repositories.canonical import CanonicalRepository
        canonical_repo = CanonicalRepository(session)
        canonical_repo.invalidate(
            conversation_id=conversation_id,
            canonical_type="insights",
        )

    # Generate insights
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured. Insights generation requires AI analysis."
        )

    insights_generator = InsightsGenerator(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        max_tokens=1000,
    )

    children = conversation.children if hasattr(conversation, 'children') else []
    insights = insights_generator.generate_insights(
        conversation=conversation,
        session=session,
        children=children,
    )

    return InsightsResponse(
        conversation_id=conversation_id,
        **insights
    )


@router.get("/batch-insights", response_model=dict[str, Any])
def get_batch_insights(
    project_id: UUID = Query(..., description="Project ID to analyze"),
    limit: int = Query(default=10, le=100, description="Number of recent conversations"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get aggregated insights for multiple conversations in a project.

    This endpoint analyzes recent conversations and provides:
    - Common workflow patterns across the project
    - Average collaboration quality
    - Frequent learning opportunities
    - Tool effectiveness patterns
    - Overall productivity trends

    Args:
        project_id: UUID of the project
        limit: Number of recent conversations to analyze (max 100)
        session: Database session

    Returns:
        Dictionary with aggregated insights

    Raises:
        HTTPException 404: Project not found
    """
    # Get recent conversations for project
    conversation_repo = ConversationRepository(session)
    conversations = conversation_repo.get_by_project(project_id, limit=limit)

    if not conversations:
        raise HTTPException(
            status_code=404,
            detail=f"No conversations found for project {project_id}"
        )

    # Generate insights for each conversation
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured"
        )

    insights_generator = InsightsGenerator(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
    )

    all_insights = []
    for conv in conversations:
        children = conv.children if hasattr(conv, 'children') else []
        insights = insights_generator.generate_insights(
            conversation=conv,
            session=session,
            children=children,
        )
        all_insights.append(insights)

    # Aggregate insights
    aggregated = _aggregate_insights(all_insights)

    return {
        "project_id": str(project_id),
        "conversations_analyzed": len(all_insights),
        "aggregated_insights": aggregated,
    }


def _aggregate_insights(insights_list: list[dict]) -> dict[str, Any]:
    """Aggregate insights from multiple conversations.

    Args:
        insights_list: List of insights dictionaries

    Returns:
        Aggregated insights
    """
    if not insights_list:
        return {}

    # Aggregate workflow patterns
    all_patterns = []
    for insight in insights_list:
        patterns = insight.get("workflow_patterns", [])
        all_patterns.extend(patterns)

    # Count pattern frequency
    pattern_counts: dict[str, int] = {}
    for pattern in all_patterns:
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    # Sort by frequency
    top_patterns = sorted(
        pattern_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    # Average scores
    avg_collaboration = sum(
        i.get("collaboration_quality", 5) for i in insights_list
    ) / len(insights_list)

    avg_effectiveness = sum(
        i.get("agent_effectiveness", 5) for i in insights_list
    ) / len(insights_list)

    avg_scope_clarity = sum(
        i.get("scope_clarity", 5) for i in insights_list
    ) / len(insights_list)

    # Collect learning opportunities
    all_opportunities = []
    for insight in insights_list:
        opportunities = insight.get("learning_opportunities", [])
        all_opportunities.extend(opportunities)

    opportunity_counts: dict[str, int] = {}
    for opp in all_opportunities:
        opportunity_counts[opp] = opportunity_counts.get(opp, 0) + 1

    top_opportunities = sorted(
        opportunity_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return {
        "top_workflow_patterns": [
            {"pattern": p, "frequency": c} for p, c in top_patterns
        ],
        "average_collaboration_quality": round(avg_collaboration, 2),
        "average_agent_effectiveness": round(avg_effectiveness, 2),
        "average_scope_clarity": round(avg_scope_clarity, 2),
        "common_learning_opportunities": [
            {"opportunity": o, "frequency": c} for o, c in top_opportunities
        ],
    }
