"""
Watch configuration API routes.

Endpoints for managing watch directory configurations.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from catsyphon.api.schemas import (
    WatchConfigurationCreate,
    WatchConfigurationResponse,
    WatchConfigurationUpdate,
)
from catsyphon.daemon_manager import DaemonManager
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import WatchConfigurationRepository, WorkspaceRepository

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_default_workspace_id(session: Session) -> Optional[UUID]:
    """
    Get default workspace ID for API operations.

    This is a temporary helper until proper authentication is implemented.
    Returns the first workspace in the database, or None if no workspaces exist.

    Returns:
        UUID of the first workspace, or None if no workspaces exist
    """
    workspace_repo = WorkspaceRepository(session)
    workspaces = workspace_repo.get_all(limit=1)

    if not workspaces:
        return None

    return workspaces[0].id


@router.get("/watch/configs", response_model=list[WatchConfigurationResponse])
async def list_watch_configs(
    active_only: bool = False,
    session: Session = Depends(get_db),
) -> list[WatchConfigurationResponse]:
    """
    List all watch configurations.

    Args:
        active_only: If true, only return active configurations

    Returns:
        List of watch configurations
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        return []

    if active_only:
        configs = repo.get_all_active(workspace_id)
    else:
        configs = repo.get_all()

    return [WatchConfigurationResponse.model_validate(c) for c in configs]


@router.get("/watch/configs/{config_id}", response_model=WatchConfigurationResponse)
async def get_watch_config(
    config_id: UUID,
    session: Session = Depends(get_db),
) -> WatchConfigurationResponse:
    """
    Get a specific watch configuration by ID.

    Args:
        config_id: Configuration UUID

    Returns:
        Watch configuration

    Raises:
        HTTPException: 404 if configuration not found
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    config = repo.get(config_id)

    if not config or config.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    return WatchConfigurationResponse.model_validate(config)


@router.post(
    "/watch/configs", response_model=WatchConfigurationResponse, status_code=201
)
async def create_watch_config(
    config: WatchConfigurationCreate,
    session: Session = Depends(get_db),
) -> WatchConfigurationResponse:
    """
    Create a new watch configuration.

    Args:
        config: Watch configuration data

    Returns:
        Created watch configuration

    Raises:
        HTTPException: 400 if directory already exists
        HTTPException: 500 if no workspace exists
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(
            status_code=500,
            detail="No workspace found. Please create a workspace first."
        )

    # Check if directory already exists in this workspace
    existing = repo.get_by_directory(config.directory, workspace_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Watch configuration already exists for directory: "
                f"{config.directory}"
            ),
        )

    # Create new configuration
    new_config = repo.create(
        workspace_id=workspace_id,
        directory=config.directory,
        project_id=config.project_id,
        developer_id=config.developer_id,
        enable_tagging=config.enable_tagging,
        extra_config=config.extra_config,
        created_by=config.created_by,
        is_active=False,  # Start as inactive
        stats={},
    )

    session.commit()

    return WatchConfigurationResponse.model_validate(new_config)


@router.put("/watch/configs/{config_id}", response_model=WatchConfigurationResponse)
async def update_watch_config(
    config_id: UUID,
    config: WatchConfigurationUpdate,
    session: Session = Depends(get_db),
) -> WatchConfigurationResponse:
    """
    Update a watch configuration.

    Args:
        config_id: Configuration UUID
        config: Updated configuration data

    Returns:
        Updated watch configuration

    Raises:
        HTTPException: 404 if configuration not found
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Verify config exists and belongs to workspace
    existing = repo.get(config_id)
    if not existing or existing.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Build update dict (only include non-None values)
    update_data = {k: v for k, v in config.model_dump().items() if v is not None}

    updated_config = repo.update(config_id, **update_data)

    if not updated_config:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    session.commit()

    return WatchConfigurationResponse.model_validate(updated_config)


@router.delete("/watch/configs/{config_id}", status_code=204)
async def delete_watch_config(
    config_id: UUID,
    session: Session = Depends(get_db),
) -> None:
    """
    Delete a watch configuration.

    Args:
        config_id: Configuration UUID

    Raises:
        HTTPException: 404 if configuration not found
        HTTPException: 400 if configuration is active
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    config = repo.get(config_id)
    if not config or config.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    if config.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an active watch configuration. Stop it first.",
        )

    repo.delete(config_id)
    session.commit()


@router.post(
    "/watch/configs/{config_id}/start", response_model=WatchConfigurationResponse
)
async def start_watching(
    config_id: UUID,
    request: Request,
    session: Session = Depends(get_db),
) -> WatchConfigurationResponse:
    """
    Activate a watch configuration and start the daemon.

    Args:
        config_id: Configuration UUID
        request: FastAPI request (for accessing app state)
        session: Database session

    Returns:
        Updated watch configuration

    Raises:
        HTTPException: 404 if configuration not found
        HTTPException: 400 if daemon fails to start
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Get configuration
    config = repo.get(config_id)
    if not config or config.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Check if already active
    if config.is_active:
        raise HTTPException(
            status_code=400,
            detail="Watch configuration is already active",
        )

    # Mark as active in database
    updated_config = repo.activate(config_id)
    session.commit()

    # Get DaemonManager from app state
    daemon_manager: DaemonManager = request.app.state.daemon_manager

    # Start the daemon
    try:
        daemon_manager.start_daemon(updated_config)
        logger.info(f"Started daemon for config {config_id}")
    except Exception as e:
        logger.error(f"Failed to start daemon for config {config_id}: {e}", exc_info=True)

        # Rollback - mark as inactive
        try:
            repo.deactivate(config_id)
            session.commit()
        except Exception:
            pass

        raise HTTPException(
            status_code=400,
            detail=f"Failed to start daemon: {str(e)}",
        )

    return WatchConfigurationResponse.model_validate(updated_config)


@router.post(
    "/watch/configs/{config_id}/stop", response_model=WatchConfigurationResponse
)
async def stop_watching(
    config_id: UUID,
    request: Request,
    session: Session = Depends(get_db),
) -> WatchConfigurationResponse:
    """
    Deactivate a watch configuration and stop the daemon.

    Args:
        config_id: Configuration UUID
        request: FastAPI request (for accessing app state)
        session: Database session

    Returns:
        Updated watch configuration

    Raises:
        HTTPException: 404 if configuration not found
        HTTPException: 400 if daemon not running
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = _get_default_workspace_id(session)

    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Get configuration
    config = repo.get(config_id)
    if not config or config.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    # Check if active
    if not config.is_active:
        raise HTTPException(
            status_code=400,
            detail="Watch configuration is not active",
        )

    # Get DaemonManager from app state
    daemon_manager: DaemonManager = request.app.state.daemon_manager

    # Stop the daemon
    try:
        daemon_manager.stop_daemon(config_id, save_stats=True)
        logger.info(f"Stopped daemon for config {config_id}")
    except Exception as e:
        logger.error(f"Failed to stop daemon for config {config_id}: {e}", exc_info=True)
        # Continue anyway - mark as inactive in DB

    # Mark as inactive in database
    updated_config = repo.deactivate(config_id)
    session.commit()

    return WatchConfigurationResponse.model_validate(updated_config)


@router.get("/watch/status")
async def get_watch_status(
    request: Request,
    session: Session = Depends(get_db),
) -> dict:
    """
    Get overall watch daemon status.

    Returns:
        Dictionary with watch status information including runtime daemon status
    """
    repo = WatchConfigurationRepository(session)

    active_configs = repo.get_all_active()
    inactive_configs = repo.get_all_inactive()

    # Get DaemonManager from app state
    daemon_manager: DaemonManager = request.app.state.daemon_manager

    # Get runtime status
    daemon_status = daemon_manager.get_all_status()

    return {
        "total_configs": repo.count(),
        "active_count": len(active_configs),
        "inactive_count": len(inactive_configs),
        "running_daemons": daemon_status["running_daemons"],
        "total_daemons": daemon_status["total_daemons"],
        "active_configs": [
            WatchConfigurationResponse.model_validate(c) for c in active_configs
        ],
    }


@router.get("/watch/daemon/status")
async def get_all_daemon_status(
    request: Request,
) -> dict:
    """
    Get detailed runtime status for all daemons.

    Returns:
        Dictionary with detailed daemon status, stats, and health
    """
    daemon_manager: DaemonManager = request.app.state.daemon_manager
    return daemon_manager.get_all_status()


@router.get("/watch/daemon/status/{config_id}")
async def get_daemon_status(
    config_id: UUID,
    request: Request,
) -> dict:
    """
    Get detailed runtime status for a specific daemon.

    Args:
        config_id: Watch configuration ID

    Returns:
        Daemon status dictionary

    Raises:
        HTTPException: 404 if daemon not running
    """
    daemon_manager: DaemonManager = request.app.state.daemon_manager
    status = daemon_manager.get_daemon_status(config_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail="No daemon running for this configuration",
        )

    return status
