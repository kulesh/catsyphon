"""
Setup and onboarding API endpoints.

Provides endpoints for initial system setup, organization and workspace management.
"""

import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    OrganizationCreate,
    OrganizationResponse,
    SetupStatusResponse,
    WorkspaceCreate,
    WorkspaceResponse,
)
from catsyphon.db.connection import get_db
from catsyphon.db.repositories.organization import OrganizationRepository
from catsyphon.db.repositories.workspace import WorkspaceRepository

router = APIRouter(prefix="/setup", tags=["setup"])


def _generate_slug(name: str) -> str:
    """
    Generate a URL-friendly slug from a name.

    Args:
        name: The name to convert to a slug

    Returns:
        URL-friendly slug (lowercase, hyphens instead of spaces)

    Examples:
        "ACME Corporation" -> "acme-corporation"
        "My  Company!!!" -> "my-company"
    """
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove any characters that aren't alphanumeric or hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    return slug or "default"


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    session: Session = Depends(get_db),
) -> SetupStatusResponse:
    """
    Check if the system needs onboarding.

    Returns setup status including whether onboarding is needed
    (i.e., no workspace exists yet).

    This endpoint is used by the frontend to decide whether to
    redirect to the setup wizard on first visit.
    """
    workspace_repo = WorkspaceRepository(session)
    org_repo = OrganizationRepository(session)

    workspaces = workspace_repo.get_all(limit=1)
    orgs = org_repo.get_all(limit=1)

    return SetupStatusResponse(
        needs_onboarding=len(workspaces) == 0,
        organization_count=len(orgs),
        workspace_count=len(workspaces),
    )


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    org_data: OrganizationCreate,
    session: Session = Depends(get_db),
) -> OrganizationResponse:
    """
    Create a new organization.

    Organizations are the top-level entity that contain workspaces.
    Typically represents a company, team, or personal account.

    If slug is not provided, it will be auto-generated from the name.
    """
    org_repo = OrganizationRepository(session)

    # Generate slug if not provided
    slug = org_data.slug or _generate_slug(org_data.name)

    # Check if slug already exists
    existing = org_repo.get_by_slug(slug)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with slug '{slug}' already exists. Please choose a different name or slug.",
        )

    # Create organization
    org = org_repo.create(name=org_data.name, slug=slug)
    session.commit()

    return OrganizationResponse.model_validate(org)


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    session: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    """
    List all organizations.

    Returns all active organizations in the system.
    """
    org_repo = OrganizationRepository(session)
    orgs = org_repo.get_active()

    return [OrganizationResponse.model_validate(org) for org in orgs]


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    session: Session = Depends(get_db),
) -> OrganizationResponse:
    """
    Get a single organization by ID.
    """
    org_repo = OrganizationRepository(session)
    org = org_repo.get(org_id)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrganizationResponse.model_validate(org)


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    session: Session = Depends(get_db),
) -> WorkspaceResponse:
    """
    Create a new workspace.

    Workspaces help organize conversations by project, team, or environment.
    All workspaces must belong to an organization.

    If slug is not provided, it will be auto-generated from the name.
    """
    workspace_repo = WorkspaceRepository(session)
    org_repo = OrganizationRepository(session)

    # Verify organization exists
    org = org_repo.get(workspace_data.organization_id)
    if not org:
        raise HTTPException(
            status_code=404,
            detail=f"Organization with ID '{workspace_data.organization_id}' not found",
        )

    # Generate slug if not provided
    slug = workspace_data.slug or _generate_slug(workspace_data.name)

    # Check if slug already exists
    existing = workspace_repo.get_by_slug(slug)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Workspace with slug '{slug}' already exists. Please choose a different name or slug.",
        )

    # Create workspace
    workspace = workspace_repo.create(
        organization_id=workspace_data.organization_id,
        name=workspace_data.name,
        slug=slug,
    )
    session.commit()

    return WorkspaceResponse.model_validate(workspace)


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(
    organization_id: Optional[UUID] = None,
    session: Session = Depends(get_db),
) -> list[WorkspaceResponse]:
    """
    List all workspaces.

    Optionally filter by organization_id.
    """
    workspace_repo = WorkspaceRepository(session)

    if organization_id:
        workspaces = workspace_repo.get_by_organization(organization_id)
    else:
        workspaces = workspace_repo.get_all()

    return [WorkspaceResponse.model_validate(ws) for ws in workspaces]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    session: Session = Depends(get_db),
) -> WorkspaceResponse:
    """
    Get a single workspace by ID.
    """
    workspace_repo = WorkspaceRepository(session)
    workspace = workspace_repo.get(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return WorkspaceResponse.model_validate(workspace)
