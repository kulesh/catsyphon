"""
Repository layer for database operations.

Provides a clean API for CRUD operations on database models.
"""

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.db.repositories.collector import CollectorRepository
from catsyphon.db.repositories.collector_session import CollectorSessionRepository
from catsyphon.db.repositories.conversation import ConversationRepository
from catsyphon.db.repositories.developer import DeveloperRepository
from catsyphon.db.repositories.epoch import EpochRepository
from catsyphon.db.repositories.ingestion_job import IngestionJobRepository
from catsyphon.db.repositories.insights import InsightsRepository
from catsyphon.db.repositories.message import MessageRepository
from catsyphon.db.repositories.organization import OrganizationRepository
from catsyphon.db.repositories.project import ProjectRepository
from catsyphon.db.repositories.raw_log import RawLogRepository
from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.db.repositories.workspace import WorkspaceRepository

__all__ = [
    "BaseRepository",
    "CanonicalRepository",
    "CollectorRepository",
    "CollectorSessionRepository",
    "ConversationRepository",
    "DeveloperRepository",
    "EpochRepository",
    "IngestionJobRepository",
    "InsightsRepository",
    "MessageRepository",
    "OrganizationRepository",
    "ProjectRepository",
    "RawLogRepository",
    "WatchConfigurationRepository",
    "WorkspaceRepository",
]
