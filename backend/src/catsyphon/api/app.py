"""
CatSyphon FastAPI Application.

Main API application for querying conversation data and insights.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from catsyphon.api.routes import (
    conversations,
    ingestion,
    metadata,
    projects,
    setup,
    stats,
    upload,
    watch,
)
from catsyphon.daemon_manager import DaemonManager
from catsyphon.logging_config import setup_logging
from catsyphon.startup import run_all_startup_checks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Runs startup checks before the application starts serving requests.
    Ensures critical dependencies (database, migrations) are available.
    Initializes and manages watch daemons.
    """
    # Initialize logging first
    setup_logging(context="api")

    # Startup: Run all dependency checks
    logger.info("Running startup checks...")
    run_all_startup_checks()
    logger.info("✓ Startup checks passed")

    # Initialize DaemonManager
    logger.info("Initializing DaemonManager...")
    daemon_manager = DaemonManager(stats_sync_interval=30)
    app.state.daemon_manager = daemon_manager

    # Start background threads
    daemon_manager.start()
    logger.info("✓ DaemonManager started")

    # Load and start active watch configurations
    try:
        daemon_manager.load_active_configs()
        logger.info("✓ Active watch configurations loaded")
    except Exception as e:
        logger.error(f"Failed to load active configs: {e}", exc_info=True)

    logger.info("Application startup complete")

    yield

    # Shutdown: Stop all daemons and cleanup
    logger.info("Application shutdown initiated...")
    try:
        daemon_manager.shutdown(timeout=10)
        logger.info("✓ DaemonManager shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

    logger.info("Application shutdown complete")


app = FastAPI(
    lifespan=lifespan,
    title="CatSyphon API",
    description="API for analyzing coding agent conversation logs",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - API health check."""
    return {
        "status": "ok",
        "message": "CatSyphon API is running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    from catsyphon.db.connection import check_connection

    db_status = "healthy" if check_connection() else "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
    }


@app.get("/ready")
async def ready() -> dict:
    """
    Readiness probe endpoint for Kubernetes/load balancers.

    Returns 200 OK if ready to serve requests, 503 Service Unavailable otherwise.
    Includes startup metrics and current health status.
    """
    from fastapi import Response, status

    from catsyphon.startup import check_readiness

    is_ready, details = check_readiness()

    if not is_ready:
        return Response(
            content=details,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return details


app.include_router(
    conversations.router, prefix="/conversations", tags=["conversations"]
)
app.include_router(metadata.router, prefix="", tags=["metadata"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(watch.router, prefix="", tags=["watch"])
app.include_router(ingestion.router, prefix="", tags=["ingestion"])
app.include_router(setup.router)
