"""
Authentication and authorization context for API endpoints.

Provides workspace isolation and multi-tenancy security through the AuthContext
dependency. All multi-tenant endpoints should use get_auth_context() to ensure
proper workspace scoping.

Phase 1 of Multi-Tenancy Security Fixes (catsyphon-p1-security).
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from catsyphon.db.connection import get_db
from catsyphon.db.repositories.workspace import WorkspaceRepository


@dataclass
class AuthContext:
    """
    Authentication context for API requests.

    Contains the workspace and organization context for the current request,
    ensuring all database operations are properly scoped.

    Attributes:
        workspace_id: UUID of the current workspace
        organization_id: UUID of the workspace's organization
        user_id: Optional UUID of authenticated user (reserved for future auth)

    Example:
        >>> @router.get("/conversations/{id}")
        >>> async def get_conversation(
        ...     id: UUID,
        ...     auth: AuthContext = Depends(get_auth_context),
        ...     session: Session = Depends(get_db),
        ... ):
        ...     repo = ConversationRepository(session)
        ...     conv = repo.get_by_workspace(id, auth.workspace_id)
        ...     if not conv:
        ...         raise HTTPException(404, "Not found")
        ...     return conv
    """

    workspace_id: UUID
    organization_id: UUID
    user_id: Optional[UUID] = None  # Reserved for future user authentication


def get_auth_context(
    x_workspace_id: Optional[str] = Header(
        None,
        description="Workspace UUID for multi-tenant isolation (required)",
        alias="X-Workspace-Id",
    ),
    session: Session = Depends(get_db),
) -> AuthContext:
    """
    FastAPI dependency to extract and validate workspace context from request.

    Extracts workspace_id from the X-Workspace-Id header. This header is required
    for multi-tenant workspace isolation.

    Args:
        x_workspace_id: Workspace UUID from X-Workspace-Id header
        session: Database session from dependency injection

    Returns:
        AuthContext with validated workspace and organization IDs

    Raises:
        HTTPException(401): If workspace header is missing or invalid
        HTTPException(400): If workspace ID format is invalid
    """
    workspace_repo = WorkspaceRepository(session)

    # Require workspace header - no fallback to default workspace
    if not x_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Workspace-Id header is required",
        )

    try:
        workspace_uuid = UUID(x_workspace_id)
        workspace = workspace_repo.get(workspace_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid workspace ID",
        )

    if not workspace.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace is inactive",
        )

    return AuthContext(
        workspace_id=workspace.id,
        organization_id=workspace.organization_id,
    )


def require_auth_context(
    x_workspace_id: str = Header(
        ...,
        description="Workspace UUID (required)",
        alias="X-Workspace-Id",
    ),
    session: Session = Depends(get_db),
) -> AuthContext:
    """
    Strict version of get_auth_context that requires explicit workspace header.

    Use this for endpoints that should never fall back to a default workspace,
    such as collector ingestion endpoints in Phase 2+.

    Args:
        x_workspace_id: Required workspace UUID from X-Workspace-Id header
        session: Database session from dependency injection

    Returns:
        AuthContext with validated workspace and organization IDs

    Raises:
        HTTPException(401): If workspace header is missing or invalid
    """
    workspace_repo = WorkspaceRepository(session)

    try:
        workspace_uuid = UUID(x_workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    workspace = workspace_repo.get(workspace_uuid)

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid workspace ID",
        )

    if not workspace.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace is inactive",
        )

    return AuthContext(
        workspace_id=workspace.id,
        organization_id=workspace.organization_id,
    )
