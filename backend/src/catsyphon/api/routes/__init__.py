"""
API routes for CatSyphon.
"""

from catsyphon.api.routes import (
    conversations,
    ingestion,
    metadata,
    stats,
    upload,
    watch,
)

__all__ = ["conversations", "ingestion", "metadata", "stats", "upload", "watch"]
