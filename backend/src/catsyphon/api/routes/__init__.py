"""
API routes for CatSyphon.
"""

from catsyphon.api.routes import (
    canonical,
    conversations,
    ingestion,
    insights,
    metadata,
    projects,
    setup,
    stats,
    upload,
    watch,
)

__all__ = ["canonical", "conversations", "ingestion", "insights", "metadata", "projects", "setup", "stats", "upload", "watch"]
