"""
Canonical representation API routes.

Endpoints for generating and retrieving canonical conversation representations.
"""

import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    CanonicalConfig,
    CanonicalMetadata,
    CanonicalNarrativeResponse,
    CanonicalResponse,
    RegenerateCanonicalRequest,
)
from catsyphon.canonicalization import CanonicalType, Canonicalizer
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import CanonicalRepository, ConversationRepository

router = APIRouter()


@router.get("/{conversation_id}/canonical", response_model=CanonicalResponse)
def get_canonical(
    conversation_id: UUID,
    canonical_type: str = Query(
        default="tagging",
        description="Type of canonical representation (tagging, insights, export)"
    ),
    sampling_strategy: str = Query(
        default="semantic",
        description="Sampling strategy (semantic, epoch, chronological)"
    ),
    force_regenerate: bool = Query(
        default=False,
        description="Force regeneration even if cached version exists"
    ),
    session: Session = Depends(get_db),
) -> CanonicalResponse:
    """
    Get canonical representation of a conversation.

    This endpoint returns a canonical representation of the conversation optimized
    for the specified analysis type. Canonical representations are:

    - **Intelligently sampled**: Priority-based sampling (errors > tools > thinking)
    - **Hierarchical**: Includes child conversations (agents, MCP, skills)
    - **Cached**: Database-backed caching with smart invalidation
    - **Play-format**: Theatrical narrative structure for better LLM comprehension

    **Canonical Types:**
    - `tagging`: Optimized for metadata extraction (8K tokens)
    - `insights`: Optimized for analytics and insights (12K tokens)
    - `export`: Full representation for export (20K tokens)

    **Cache Invalidation:**
    Canonical representations are automatically regenerated when:
    - Version mismatch (algorithm updated)
    - Token growth exceeds threshold (>2K new tokens)
    - Force regeneration requested

    Args:
        conversation_id: UUID of the conversation
        canonical_type: Type of canonical (tagging, insights, export)
        sampling_strategy: Sampling strategy (semantic, epoch, chronological)
        force_regenerate: Force regeneration even if cached
        session: Database session

    Returns:
        CanonicalResponse with narrative and metadata

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 400: Invalid canonical type or sampling strategy
    """
    # Validate canonical type
    try:
        canonical_type_enum = CanonicalType[canonical_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid canonical_type. Must be one of: tagging, insights, export"
        )

    # Validate sampling strategy
    valid_strategies = ["semantic", "epoch", "chronological"]
    if sampling_strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sampling_strategy. Must be one of: {', '.join(valid_strategies)}"
        )

    # Get conversation
    conversation_repo = ConversationRepository(session)
    conversation = conversation_repo.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )

    # Get or generate canonical
    try:
        canonical_repo = CanonicalRepository(session)
        canonicalizer = Canonicalizer(
            canonical_type=canonical_type_enum,
            sampling_strategy=sampling_strategy
        )

        # Force regeneration if requested
        if force_regenerate:
            canonical_repo.invalidate(conversation_id=conversation_id)

        canonical = canonical_repo.get_or_generate(
            conversation=conversation,
            canonical_type=canonical_type_enum,
            canonicalizer=canonicalizer,
            regeneration_threshold_tokens=2000,
            children=conversation.children if hasattr(conversation, 'children') else [],
        )

        # Build response
        # CanonicalConversation dataclass has direct attributes, not nested metadata
        return CanonicalResponse(
            id=uuid.uuid4(),  # Generate new ID for API response (canonical doesn't have one)
            conversation_id=uuid.UUID(canonical.conversation_id),
            version=canonical.canonical_version,
            canonical_type=canonical_type,
            narrative=canonical.narrative,
            token_count=canonical.token_count,
            metadata=CanonicalMetadata(
                tools_used=canonical.tools_used,
                files_touched=canonical.files_touched,
                errors_encountered=[],  # Not stored in CanonicalConversation
                has_errors=canonical.has_errors,
            ),
            config=CanonicalConfig(
                canonical_type=canonical_type,
                max_tokens=canonical.config.token_budget if canonical.config else 0,
                sampling_strategy=sampling_strategy,
            ),
            source_message_count=canonical.message_count,
            source_token_estimate=canonical.message_count * 100,  # Estimate
            generated_at=canonical.generated_at,
        )
    except Exception as e:
        # Log the error and return a 500 with useful info
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating canonical for conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate canonical representation: {str(e)}"
        )


@router.get("/{conversation_id}/canonical/narrative", response_model=CanonicalNarrativeResponse)
def get_canonical_narrative(
    conversation_id: UUID,
    canonical_type: str = Query(
        default="tagging",
        description="Type of canonical representation"
    ),
    sampling_strategy: str = Query(
        default="semantic",
        description="Sampling strategy (semantic, epoch, chronological)"
    ),
    session: Session = Depends(get_db),
) -> CanonicalNarrativeResponse:
    """
    Get just the narrative text from canonical representation.

    This is a lightweight endpoint that returns only the narrative without
    full metadata. Useful for displaying conversation summaries or feeding
    directly to LLMs for analysis.

    Args:
        conversation_id: UUID of the conversation
        canonical_type: Type of canonical (tagging, insights, export)
        sampling_strategy: Sampling strategy (semantic, epoch, chronological)
        session: Database session

    Returns:
        CanonicalNarrativeResponse with narrative text

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 400: Invalid canonical type or sampling strategy
    """
    # Validate canonical type
    try:
        canonical_type_enum = CanonicalType[canonical_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid canonical_type. Must be one of: tagging, insights, export"
        )

    # Validate sampling strategy
    valid_strategies = ["semantic", "epoch", "chronological"]
    if sampling_strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sampling_strategy. Must be one of: {', '.join(valid_strategies)}"
        )

    # Get conversation
    conversation_repo = ConversationRepository(session)
    conversation = conversation_repo.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )

    # Get or generate canonical
    canonical_repo = CanonicalRepository(session)
    canonicalizer = Canonicalizer(
        canonical_type=canonical_type_enum,
        sampling_strategy=sampling_strategy
    )

    canonical = canonical_repo.get_or_generate(
        conversation=conversation,
        canonical_type=canonical_type_enum,  # Fixed: use enum, not string
        canonicalizer=canonicalizer,
        children=conversation.children if hasattr(conversation, 'children') else [],
    )

    return CanonicalNarrativeResponse(
        narrative=canonical.narrative,
        token_count=canonical.token_count,
        canonical_type=canonical_type,  # Use the string parameter
        version=canonical.canonical_version,  # Fixed: correct attribute name
    )


@router.post("/{conversation_id}/canonical/regenerate", response_model=CanonicalResponse)
def regenerate_canonical(
    conversation_id: UUID,
    request: RegenerateCanonicalRequest,
    session: Session = Depends(get_db),
) -> CanonicalResponse:
    """
    Force regeneration of canonical representation.

    This endpoint invalidates any cached canonical representation and generates
    a fresh one. Useful when:
    - Conversation has been updated
    - Testing new canonicalization algorithms
    - Debugging canonical representation issues

    Args:
        conversation_id: UUID of the conversation
        request: Request with canonical type and sampling strategy to regenerate
        session: Database session

    Returns:
        CanonicalResponse with freshly generated canonical

    Raises:
        HTTPException 404: Conversation not found
        HTTPException 400: Invalid canonical type or sampling strategy
    """
    # Validate canonical type
    try:
        canonical_type_enum = CanonicalType[request.canonical_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid canonical_type. Must be one of: tagging, insights, export"
        )

    # Validate sampling strategy
    valid_strategies = ["semantic", "epoch", "chronological"]
    if request.sampling_strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sampling_strategy. Must be one of: {', '.join(valid_strategies)}"
        )

    # Get conversation
    conversation_repo = ConversationRepository(session)
    conversation = conversation_repo.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )

    # Invalidate cache
    canonical_repo = CanonicalRepository(session)
    canonical_repo.invalidate(
        conversation_id=conversation_id,
        canonical_type=request.canonical_type,
    )

    # Generate fresh canonical
    canonicalizer = Canonicalizer(
        canonical_type=canonical_type_enum,
        sampling_strategy=request.sampling_strategy
    )
    canonical = canonical_repo.get_or_generate(
        conversation=conversation,
        canonical_type=canonical_type_enum,  # Fixed: use enum, not string
        canonicalizer=canonicalizer,
        children=conversation.children if hasattr(conversation, 'children') else [],
    )

    # Build response
    # CanonicalConversation dataclass has direct attributes, not nested metadata
    return CanonicalResponse(
        id=uuid.uuid4(),  # Generate new ID for API response
        conversation_id=uuid.UUID(canonical.conversation_id),
        version=canonical.canonical_version,
        canonical_type=request.canonical_type,
        narrative=canonical.narrative,
        token_count=canonical.token_count,
        metadata=CanonicalMetadata(
            tools_used=canonical.tools_used,
            files_touched=canonical.files_touched,
            errors_encountered=[],  # Not stored in CanonicalConversation
            has_errors=canonical.has_errors,
        ),
        config=CanonicalConfig(
            canonical_type=request.canonical_type,
            max_tokens=canonical.config.token_budget if canonical.config else 0,
            sampling_strategy=request.sampling_strategy,
        ),
        source_message_count=canonical.message_count,
        source_token_estimate=canonical.message_count * 100,  # Estimate
        generated_at=canonical.generated_at,
    )


@router.delete("/{conversation_id}/canonical")
def delete_canonical(
    conversation_id: UUID,
    canonical_type: Optional[str] = Query(
        default=None,
        description="Specific canonical type to delete, or all if not specified"
    ),
    session: Session = Depends(get_db),
) -> dict:
    """
    Delete cached canonical representation(s).

    This endpoint removes cached canonical representations from the database.
    If canonical_type is specified, only that type is deleted. Otherwise,
    all canonical representations for the conversation are removed.

    Args:
        conversation_id: UUID of the conversation
        canonical_type: Optional specific type to delete
        session: Database session

    Returns:
        dict with deletion count

    Raises:
        HTTPException 404: Conversation not found
    """
    # Verify conversation exists
    conversation_repo = ConversationRepository(session)
    conversation = conversation_repo.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )

    # Delete canonical(s)
    canonical_repo = CanonicalRepository(session)
    deleted_count = canonical_repo.invalidate(
        conversation_id=conversation_id,
        canonical_type=canonical_type,
    )

    return {
        "conversation_id": str(conversation_id),
        "canonical_type": canonical_type or "all",
        "deleted_count": deleted_count,
    }
