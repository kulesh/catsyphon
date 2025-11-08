"""
CatSyphon FastAPI Application.

Main API application for querying conversation data and insights.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from catsyphon.api.routes import conversations, metadata, stats, upload
from catsyphon.startup import run_all_startup_checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Runs startup checks before the application starts serving requests.
    Ensures critical dependencies (database, migrations) are available.
    """
    # Startup: Run all dependency checks
    run_all_startup_checks()

    yield

    # Shutdown: Cleanup if needed (currently none)


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
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
