"""
CatSyphon FastAPI Application.

Main API application for querying conversation data and insights.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from catsyphon.api.routes import (
    benchmarks,
    canonical,
    collectors,
    conversations,
    digests,
    ingestion,
    insights,
    metadata,
    otel,
    patterns,
    plans,
    projects,
    recaps,
    recommendations,
    setup,
    stats,
    upload,
    watch,
)
from catsyphon.config import settings
from catsyphon.daemon_manager import DaemonManager
from catsyphon.logging_config import setup_logging
from catsyphon.startup import run_all_startup_checks
from catsyphon.tagging import start_worker as start_tagging_worker
from catsyphon.tagging import stop_worker as stop_tagging_worker

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

    # Start tagging worker for async tagging job processing
    start_tagging_worker()
    logger.info("✓ Tagging worker started")

    # Defer loading active configs until server is ready to handle requests.
    # This prevents deadlock when watch configs with use_api=True try to
    # fetch credentials from localhost during startup.
    #
    # We poll the /health endpoint instead of using a fixed delay because:
    # 1. Fixed delays are timing-dependent and may fail on slow systems
    # 2. Health polling actively confirms the server is ready
    # 3. Combined with exponential backoff retry in fetch_builtin_credentials(),
    #    this provides robust startup handling
    import threading

    def deferred_load_configs() -> None:
        import time

        import requests

        # Poll health endpoint until server is ready
        max_attempts = 30  # 30 * 0.5s = 15s max wait
        for attempt in range(max_attempts):
            try:
                response = requests.get("http://localhost:8000/health", timeout=1)
                if response.ok:
                    logger.info("Server ready, loading watch configurations...")
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)
        else:
            logger.error("Server not ready after 15s, skipping config loading")
            return

        # Auto-bootstrap org, workspace, and watch configs if configured
        if settings.auto_setup:
            try:
                from catsyphon.bootstrap import auto_bootstrap

                auto_bootstrap()
            except Exception as e:
                logger.error(f"Auto-bootstrap failed: {e}", exc_info=True)

        # Load configs (with retry in fetch_builtin_credentials for robustness)
        try:
            daemon_manager.load_active_configs()
            logger.info("✓ Active watch configurations loaded")
        except Exception as e:
            logger.error(f"Failed to load active configs: {e}", exc_info=True)

    config_thread = threading.Thread(target=deferred_load_configs, daemon=True)
    config_thread.start()

    logger.info("Application startup complete")

    yield

    # Shutdown: Stop all daemons and cleanup
    logger.info("Application shutdown initiated...")

    # Stop tagging worker
    try:
        stop_tagging_worker(timeout=10)
        logger.info("✓ Tagging worker shutdown complete")
    except Exception as e:
        logger.error(f"Error stopping tagging worker: {e}", exc_info=True)

    # Stop daemon manager
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


app.include_router(collectors.router)  # /collectors/* endpoints
app.include_router(benchmarks.router)  # /benchmarks/* endpoints
app.include_router(
    conversations.router, prefix="/conversations", tags=["conversations"]
)
app.include_router(recaps.router, prefix="/conversations", tags=["recaps"])
app.include_router(digests.router)
app.include_router(patterns.router)
app.include_router(canonical.router, prefix="/conversations", tags=["canonical"])
app.include_router(insights.router, prefix="/conversations", tags=["insights"])
app.include_router(metadata.router, prefix="", tags=["metadata"])
app.include_router(plans.router, prefix="/plans", tags=["plans"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(watch.router, prefix="", tags=["watch"])
app.include_router(ingestion.router, prefix="", tags=["ingestion"])
app.include_router(recommendations.router, prefix="", tags=["recommendations"])
app.include_router(setup.router)
app.include_router(otel.router)
