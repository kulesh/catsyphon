"""
Watch configuration API routes.

Endpoints for managing watch directory configurations.
"""

import logging
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import (
    PathValidationRequest,
    PathValidationResponse,
    SuggestedPath,
    WatchConfigurationCreate,
    WatchConfigurationResponse,
    WatchConfigurationUpdate,
)
from catsyphon.daemon_manager import DaemonManager
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import WatchConfigurationRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/watch/suggested-paths", response_model=list[SuggestedPath])
async def get_suggested_paths(
    auth: AuthContext = Depends(get_auth_context),
) -> list[SuggestedPath]:
    """
    Get suggested watch directory paths.

    Returns paths that exist on the system where Claude Code logs are commonly found.

    Requires X-Workspace-Id header.
    """
    suggestions = []
    home = Path.home()

    # AI coding assistant log locations (parent directories)
    candidates = [
        (home / ".claude", "Claude", "Claude Code logs", "projects"),
        (home / ".codex", "Codex", "Codex CLI logs", "sessions"),
        (home / ".opencode", "OpenCode", "OpenCode logs", "sessions"),
    ]

    for path, name, description, subdir in candidates:
        if path.exists() and path.is_dir():
            # Count projects/sessions in the expected subdirectory
            project_count = None
            projects_path = path / subdir
            if projects_path.exists() and projects_path.is_dir():
                try:
                    project_count = len(
                        [p for p in projects_path.iterdir() if p.is_dir()]
                    )
                except PermissionError:
                    pass

            suggestions.append(
                SuggestedPath(
                    path=str(path),
                    name=name,
                    description=description,
                    project_count=project_count,
                )
            )

    return suggestions


@router.post("/watch/validate-path", response_model=PathValidationResponse)
async def validate_path(
    request: PathValidationRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> PathValidationResponse:
    """
    Validate a directory path exists and is readable.

    Expands ~ to user home directory.

    Requires X-Workspace-Id header.
    """
    try:
        path = Path(request.path).expanduser().resolve()
    except Exception:
        return PathValidationResponse(
            valid=False,
            expanded_path=request.path,
            exists=False,
            is_directory=False,
            is_readable=False,
        )

    exists = path.exists()
    is_dir = path.is_dir() if exists else False
    is_readable = os.access(path, os.R_OK) if exists else False

    return PathValidationResponse(
        valid=exists and is_dir and is_readable,
        expanded_path=str(path),
        exists=exists,
        is_directory=is_dir,
        is_readable=is_readable,
    )


@router.get("/watch/configs", response_model=list[WatchConfigurationResponse])
async def list_watch_configs(
    auth: AuthContext = Depends(get_auth_context),
    active_only: bool = False,
    session: Session = Depends(get_db),
) -> list[WatchConfigurationResponse]:
    """
    List all watch configurations.

    Args:
        active_only: If true, only return active configurations

    Returns:
        List of watch configurations

    Requires X-Workspace-Id header.
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

    if active_only:
        configs = repo.get_all_active(workspace_id)
    else:
        configs = repo.get_by_workspace(workspace_id)

    return [WatchConfigurationResponse.model_validate(c) for c in configs]


@router.get("/watch/configs/{config_id}", response_model=WatchConfigurationResponse)
async def get_watch_config(
    config_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
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

    Requires X-Workspace-Id header.
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

    config = repo.get(config_id)

    if not config or config.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Watch configuration not found")

    return WatchConfigurationResponse.model_validate(config)


@router.post(
    "/watch/configs", response_model=WatchConfigurationResponse, status_code=201
)
async def create_watch_config(
    config: WatchConfigurationCreate,
    auth: AuthContext = Depends(get_auth_context),
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

    Requires X-Workspace-Id header.
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

    # Expand ~ to home directory and resolve path
    expanded_directory = str(Path(config.directory).expanduser().resolve())

    # Check if directory already exists in this workspace
    existing = repo.get_by_directory(expanded_directory, workspace_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Watch configuration already exists for directory: "
                f"{expanded_directory}"
            ),
        )

    # Create new configuration
    new_config = repo.create(
        workspace_id=workspace_id,
        directory=expanded_directory,
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
    auth: AuthContext = Depends(get_auth_context),
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

    Requires X-Workspace-Id header.
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

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
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> None:
    """
    Delete a watch configuration.

    Args:
        config_id: Configuration UUID

    Raises:
        HTTPException: 404 if configuration not found
        HTTPException: 400 if configuration is active

    Requires X-Workspace-Id header.
    """
    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

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
    auth: AuthContext = Depends(get_auth_context),
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

    Requires X-Workspace-Id header.
    """
    import asyncio

    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

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

    # Start the daemon in a thread pool to avoid blocking the event loop
    # This is important because start_daemon makes HTTP requests that need
    # to be handled by the same uvicorn instance
    try:
        await asyncio.to_thread(daemon_manager.start_daemon, updated_config)
        logger.info(f"Started daemon for config {config_id}")
    except Exception as e:
        logger.error(
            f"Failed to start daemon for config {config_id}: {e}", exc_info=True
        )

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
    auth: AuthContext = Depends(get_auth_context),
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

    Requires X-Workspace-Id header.
    """
    import asyncio

    repo = WatchConfigurationRepository(session)
    workspace_id = auth.workspace_id

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

    # Stop the daemon in a thread pool to avoid blocking the event loop
    try:
        await asyncio.to_thread(daemon_manager.stop_daemon, config_id, True)
        logger.info(f"Stopped daemon for config {config_id}")
    except Exception as e:
        logger.error(
            f"Failed to stop daemon for config {config_id}: {e}", exc_info=True
        )
        # Continue anyway - mark as inactive in DB

    # Mark as inactive in database
    updated_config = repo.deactivate(config_id)
    session.commit()

    return WatchConfigurationResponse.model_validate(updated_config)


@router.get("/watch/status")
async def get_watch_status(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> dict:
    """
    Get overall watch daemon status.

    Returns:
        Dictionary with watch status information including runtime daemon status

    Requires X-Workspace-Id header.
    """
    workspace_id = auth.workspace_id
    repo = WatchConfigurationRepository(session)

    active_configs = repo.get_all_active(workspace_id)
    inactive_configs = repo.get_all_inactive(workspace_id)

    # Get DaemonManager from app state
    daemon_manager: DaemonManager = request.app.state.daemon_manager

    # Get runtime status
    daemon_status = daemon_manager.get_all_status()

    return {
        "total_configs": repo.count_by_workspace(workspace_id),
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
