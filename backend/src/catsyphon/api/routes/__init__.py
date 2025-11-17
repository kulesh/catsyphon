"""
API routes for CatSyphon.
"""

from catsyphon.api.routes import (
    conversations,
    ingestion,
    metadata,
    setup,
    stats,
    upload,
    watch,
)

__all__ = ["conversations", "ingestion", "metadata", "setup", "stats", "upload", "watch"]
