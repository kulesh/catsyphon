"""
Recommendations API routes.

Endpoints for automation recommendation detection and management.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    DetectionRequest,
    DetectionResponse,
    RecommendationEvidence,
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationSummaryStats,
    RecommendationUpdate,
    SuggestedImplementation,
)
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import ConversationRepository, RecommendationRepository

logger = logging.getLogger(__name__)

router = APIRouter()


def _db_to_response(rec) -> RecommendationResponse:
    """Convert database model to response schema."""
    evidence = rec.evidence or {}
    impl = rec.suggested_implementation or {}

    # Build evidence with both slash command and MCP fields
    evidence_obj = RecommendationEvidence(
        quotes=evidence.get("quotes", []),
        pattern_count=evidence.get("pattern_count", 0),
        matched_signals=evidence.get("matched_signals", []),
        workarounds_detected=evidence.get("workarounds_detected", []),
        friction_indicators=evidence.get("friction_indicators", []),
    )

    # Build suggested implementation with both slash command and MCP fields
    impl_obj = SuggestedImplementation(
        command_name=impl.get("command_name"),
        trigger_phrases=impl.get("trigger_phrases", []),
        template=impl.get("template"),
        category=impl.get("category"),
        suggested_mcps=impl.get("suggested_mcps", []),
        use_cases=impl.get("use_cases", []),
        friction_score=impl.get("friction_score"),
    ) if impl else None

    return RecommendationResponse(
        id=rec.id,
        conversation_id=rec.conversation_id,
        recommendation_type=rec.recommendation_type,
        title=rec.title,
        description=rec.description,
        confidence=rec.confidence,
        priority=rec.priority,
        evidence=evidence_obj,
        suggested_implementation=impl_obj,
        status=rec.status,
        user_feedback=rec.user_feedback,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.get(
    "/conversations/{conversation_id}/recommendations",
    response_model=RecommendationListResponse,
)
def get_conversation_recommendations(
    conversation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    status: str = Query(default=None, description="Filter by status"),
    recommendation_type: str = Query(default=None, description="Filter by type"),
    session: Session = Depends(get_db),
) -> RecommendationListResponse:
    """
    Get automation recommendations for a conversation.

    Returns all detected slash command opportunities for the given conversation,
    ordered by confidence (highest first).

    Args:
        conversation_id: UUID of the conversation
        status: Optional filter by status (pending, accepted, dismissed, implemented)
        recommendation_type: Optional filter by type (slash_command, mcp_server)
        session: Database session

    Returns:
        RecommendationListResponse with list of recommendations

    Raises:
        HTTPException 404: Conversation not found

    Requires X-Workspace-Id header.
    """
    # Verify conversation exists
    conversation_repo = ConversationRepository(session)
    workspace_id = auth.workspace_id

    conversation = conversation_repo.get_with_relations(conversation_id, workspace_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id} not found"
        )

    # Get recommendations
    rec_repo = RecommendationRepository(session)
    recommendations = rec_repo.get_by_conversation(
        conversation_id=conversation_id,
        status=status,
        recommendation_type=recommendation_type,
    )

    return RecommendationListResponse(
        items=[_db_to_response(r) for r in recommendations],
        total=len(recommendations),
        conversation_id=conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/recommendations/detect",
    response_model=DetectionResponse,
)
def detect_recommendations(
    conversation_id: UUID,
    request: DetectionRequest = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> DetectionResponse:
    """
    Trigger automation recommendation detection for a conversation.

    Analyzes the conversation using LLM to detect patterns that could become
    slash commands. Results are saved to the database.

    Args:
        conversation_id: UUID of the conversation to analyze
        request: Optional request body with force_regenerate flag
        session: Database session

    Returns:
        DetectionResponse with detected recommendations

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 500: Detection failed or OpenAI not configured

    Requires X-Workspace-Id header.
    """
    if request is None:
        request = DetectionRequest()

    # Verify conversation exists
    conversation_repo = ConversationRepository(session)
    workspace_id = auth.workspace_id

    conversation = conversation_repo.get_with_relations(conversation_id, workspace_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id} not found"
        )

    # Check for existing recommendations (unless force_regenerate)
    if not request.force_regenerate:
        rec_repo = RecommendationRepository(session)
        existing = rec_repo.get_by_conversation(conversation_id)
        if existing:
            logger.info(
                "Returning %s existing recommendations for %s",
                len(existing),
                conversation_id,
            )
            return DetectionResponse(
                conversation_id=conversation_id,
                recommendations_count=len(existing),
                tokens_analyzed=0,  # Not re-analyzed
                detection_model="cached",
                recommendations=[_db_to_response(r) for r in existing],
            )

    # Check OpenAI configuration
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "OpenAI API key not configured. Recommendation detection "
                "requires AI analysis."
            ),
        )

    # Run detection
    from catsyphon.advisor import SlashCommandDetector

    detector = SlashCommandDetector(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
    )

    children = conversation.children if hasattr(conversation, "children") else []
    result = detector.detect_sync(
        conversation=conversation,
        session=session,
        children=children,
        save_to_db=True,
    )

    session.commit()

    # Fetch saved recommendations for response
    rec_repo = RecommendationRepository(session)
    saved = rec_repo.get_by_conversation(conversation_id)

    return DetectionResponse(
        conversation_id=conversation_id,
        recommendations_count=len(result.recommendations),
        tokens_analyzed=result.tokens_analyzed,
        detection_model=result.detection_model,
        recommendations=[_db_to_response(r) for r in saved],
    )


@router.post(
    "/conversations/{conversation_id}/recommendations/detect-mcp",
    response_model=DetectionResponse,
)
def detect_mcp_recommendations(
    conversation_id: UUID,
    request: DetectionRequest = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> DetectionResponse:
    """
    Trigger MCP server opportunity detection for a conversation.

    Analyzes the conversation using rule-based signal matching and LLM analysis
    to detect needs for external tool integrations (MCP servers).
    Results are saved to the database.

    Args:
        conversation_id: UUID of the conversation to analyze
        request: Optional request body with force_regenerate flag
        session: Database session

    Returns:
        DetectionResponse with detected MCP recommendations

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 500: Detection failed or OpenAI not configured

    Requires X-Workspace-Id header.
    """
    if request is None:
        request = DetectionRequest()

    # Verify conversation exists
    conversation_repo = ConversationRepository(session)
    workspace_id = auth.workspace_id

    conversation = conversation_repo.get_with_relations(conversation_id, workspace_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id} not found"
        )

    # Check for existing MCP recommendations (unless force_regenerate)
    if not request.force_regenerate:
        rec_repo = RecommendationRepository(session)
        existing = rec_repo.get_by_conversation(
            conversation_id, recommendation_type="mcp_server"
        )
        if existing:
            logger.info(
                "Returning %s existing MCP recommendations for %s",
                len(existing),
                conversation_id,
            )
            return DetectionResponse(
                conversation_id=conversation_id,
                recommendations_count=len(existing),
                tokens_analyzed=0,  # Not re-analyzed
                detection_model="cached",
                recommendations=[_db_to_response(r) for r in existing],
            )

    # Check OpenAI configuration
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "OpenAI API key not configured. MCP detection "
                "requires AI analysis."
            ),
        )

    # Run MCP detection
    from catsyphon.advisor import MCPDetector

    detector = MCPDetector(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
    )

    children = conversation.children if hasattr(conversation, "children") else []
    result = detector.detect_sync(
        conversation=conversation,
        session=session,
        children=children,
        save_to_db=True,
    )

    session.commit()

    # Fetch saved MCP recommendations for response
    rec_repo = RecommendationRepository(session)
    saved = rec_repo.get_by_conversation(
        conversation_id, recommendation_type="mcp_server"
    )

    return DetectionResponse(
        conversation_id=conversation_id,
        recommendations_count=len(result.recommendations),
        tokens_analyzed=result.tokens_analyzed,
        detection_model=result.detection_model,
        recommendations=[_db_to_response(r) for r in saved],
    )


@router.patch(
    "/recommendations/{recommendation_id}",
    response_model=RecommendationResponse,
)
def update_recommendation(
    recommendation_id: UUID,
    update: RecommendationUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> RecommendationResponse:
    """
    Update a recommendation's status or feedback.

    Used to accept, dismiss, or mark a recommendation as implemented,
    optionally with user feedback.

    Args:
        recommendation_id: UUID of the recommendation
        update: Update payload with status and/or feedback
        session: Database session

    Returns:
        Updated RecommendationResponse

    Raises:
        HTTPException 400: Invalid status
        HTTPException 404: Recommendation not found

    Requires X-Workspace-Id header.
    """
    # Validate status if provided
    valid_statuses = {"pending", "accepted", "dismissed", "implemented"}
    if update.status and update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    rec_repo = RecommendationRepository(session)
    recommendation = rec_repo.get(recommendation_id)

    if not recommendation:
        raise HTTPException(
            status_code=404, detail=f"Recommendation {recommendation_id} not found"
        )

    # Update fields
    if update.status:
        recommendation = rec_repo.update_status(
            recommendation_id=recommendation_id,
            status=update.status,
            user_feedback=update.user_feedback,
        )
    elif update.user_feedback:
        recommendation.user_feedback = update.user_feedback
        session.flush()

    session.commit()

    return _db_to_response(recommendation)


@router.get("/recommendations/summary", response_model=RecommendationSummaryStats)
def get_recommendations_summary(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> RecommendationSummaryStats:
    """
    Get aggregate statistics for all recommendations.

    Provides summary stats across all conversations including counts by
    status, type, and average confidence.

    Args:
        session: Database session

    Returns:
        RecommendationSummaryStats with aggregate statistics

    Requires X-Workspace-Id header.
    """
    rec_repo = RecommendationRepository(session)
    stats = rec_repo.get_summary_stats()

    return RecommendationSummaryStats(
        total=stats["total"],
        by_status=stats["by_status"],
        by_type=stats["by_type"],
        average_confidence=stats["average_confidence"],
    )


@router.get("/recommendations/high-confidence", response_model=list[RecommendationResponse])
def get_high_confidence_recommendations(
    auth: AuthContext = Depends(get_auth_context),
    min_confidence: float = Query(default=0.7, ge=0.0, le=1.0),
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[RecommendationResponse]:
    """
    Get high-confidence pending recommendations across all conversations.

    Useful for surfacing the most actionable automation opportunities.

    Args:
        min_confidence: Minimum confidence threshold (default 0.7)
        limit: Maximum results to return (default 10, max 100)
        session: Database session

    Returns:
        List of high-confidence RecommendationResponse

    Requires X-Workspace-Id header.
    """
    rec_repo = RecommendationRepository(session)
    recommendations = rec_repo.get_high_confidence(
        min_confidence=min_confidence,
        limit=limit,
    )

    return [_db_to_response(r) for r in recommendations]
