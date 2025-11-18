"""
Conversation repository.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload, selectinload

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Conversation


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation model."""

    def __init__(self, session: Session):
        super().__init__(Conversation, session)

    def get_with_relations(
        self, id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Optional[Conversation]:
        """
        Get conversation with all related data loaded within a workspace.

        Args:
            id: Conversation UUID
            workspace_id: Workspace UUID

        Returns:
            Conversation with relations or None
        """
        return (
            self.session.query(Conversation)
            .options(
                joinedload(Conversation.project),
                joinedload(Conversation.developer),
                joinedload(Conversation.epochs),
                joinedload(Conversation.messages),
                joinedload(Conversation.children),  # Phase 2: Epic 7u2
                joinedload(Conversation.parent_conversation),  # Phase 2: Epic 7u2
            )
            .filter(Conversation.id == id, Conversation.workspace_id == workspace_id)
            .first()
        )

    def get_by_session_id(
        self, session_id: str, workspace_id: uuid.UUID
    ) -> Optional[Conversation]:
        """
        Get conversation by session_id from extra_data (metadata) JSONB field within a workspace.

        Args:
            session_id: Session ID to search for
            workspace_id: Workspace UUID

        Returns:
            Conversation with matching session_id or None
        """
        return (
            self.session.query(Conversation)
            .filter(
                Conversation.extra_data["session_id"].as_string() == session_id,
                Conversation.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_project(
        self,
        project_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by project within a workspace.

        Args:
            project_id: Project UUID
            workspace_id: Workspace UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(
                Conversation.project_id == project_id,
                Conversation.workspace_id == workspace_id,
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_developer(
        self,
        developer_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by developer within a workspace.

        Args:
            developer_id: Developer UUID
            workspace_id: Workspace UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(
                Conversation.developer_id == developer_id,
                Conversation.workspace_id == workspace_id,
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_agent_type(
        self,
        agent_type: str,
        workspace_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by agent type within a workspace.

        Args:
            agent_type: Agent type (e.g., 'claude-code')
            workspace_id: Workspace UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(
                Conversation.agent_type == agent_type,
                Conversation.workspace_id == workspace_id,
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations within date range for a workspace.

        Args:
            start_date: Start datetime
            end_date: End datetime
            workspace_id: Workspace UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(
                Conversation.start_time >= start_date,
                Conversation.start_time <= end_date,
                Conversation.workspace_id == workspace_id,
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_status(self, status: str, workspace_id: uuid.UUID) -> int:
        """
        Count conversations by status within a workspace.

        Args:
            status: Conversation status
            workspace_id: Workspace UUID

        Returns:
            Count of conversations
        """
        return (
            self.session.query(Conversation)
            .filter(
                Conversation.status == status,
                Conversation.workspace_id == workspace_id,
            )
            .count()
        )

    def get_recent(
        self, workspace_id: uuid.UUID, limit: int = 10
    ) -> List[Conversation]:
        """
        Get most recent conversations for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of results

        Returns:
            List of recent conversations
        """
        return (
            self.session.query(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.start_time.desc())
            .limit(limit)
            .all()
        )

    def get_by_filters(
        self,
        workspace_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        collector_id: Optional[uuid.UUID] = None,
        load_relations: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by multiple filters within a workspace.

        Args:
            workspace_id: Workspace UUID (required)
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            collector_id: Filter by collector
            load_relations: Whether to load related objects
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations matching filters
        """
        query = self.session.query(Conversation).filter(
            Conversation.workspace_id == workspace_id
        )

        # Add filters
        if project_id:
            query = query.filter(Conversation.project_id == project_id)
        if developer_id:
            query = query.filter(Conversation.developer_id == developer_id)
        if agent_type:
            query = query.filter(Conversation.agent_type == agent_type)
        if status:
            query = query.filter(Conversation.status == status)
        if success is not None:
            query = query.filter(Conversation.success == success)
        if start_date:
            query = query.filter(Conversation.start_time >= start_date)
        if end_date:
            query = query.filter(Conversation.start_time <= end_date)
        if collector_id:
            query = query.filter(Conversation.collector_id == collector_id)

        # Load relations if requested
        if load_relations:
            query = query.options(
                joinedload(Conversation.project),
                joinedload(Conversation.developer),
                joinedload(Conversation.epochs),
                joinedload(Conversation.messages),
                joinedload(Conversation.files_touched),
                joinedload(Conversation.conversation_tags),
            )

        # Order, offset, limit
        query = query.order_by(Conversation.start_time.desc()).offset(offset)
        if limit:
            query = query.limit(limit)

        return query.all()

    def count_by_filters(
        self,
        workspace_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        collector_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Count conversations by multiple filters within a workspace.

        Args:
            workspace_id: Workspace UUID (required)
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            collector_id: Filter by collector

        Returns:
            Count of conversations matching filters
        """
        query = self.session.query(Conversation).filter(
            Conversation.workspace_id == workspace_id
        )

        # Add filters (same as get_by_filters)
        if project_id:
            query = query.filter(Conversation.project_id == project_id)
        if developer_id:
            query = query.filter(Conversation.developer_id == developer_id)
        if agent_type:
            query = query.filter(Conversation.agent_type == agent_type)
        if status:
            query = query.filter(Conversation.status == status)
        if success is not None:
            query = query.filter(Conversation.success == success)
        if start_date:
            query = query.filter(Conversation.start_time >= start_date)
        if end_date:
            query = query.filter(Conversation.start_time <= end_date)
        if collector_id:
            query = query.filter(Conversation.collector_id == collector_id)

        return query.count()

    def get_with_counts(
        self,
        workspace_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        collector_id: Optional[uuid.UUID] = None,
        order_by: str = "start_time",
        order_dir: str = "desc",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Tuple[Conversation, int, int, int]]:
        """
        Get conversations with denormalized counts for a workspace.

        Returns list of (conversation, message_count, epoch_count,
        files_count) tuples using denormalized count columns for performance.

        Args:
            workspace_id: Workspace UUID (required)
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type (partial match)
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            collector_id: Filter by collector
            order_by: Column to order by
            order_dir: Order direction ('asc' or 'desc')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of (Conversation, message_count, epoch_count, files_count) tuples
        """
        # Use denormalized count columns - no expensive joins needed!
        query = (
            self.session.query(
                Conversation,
                Conversation.message_count,
                Conversation.epoch_count,
                Conversation.files_count,
            )
            .filter(Conversation.workspace_id == workspace_id)
            .options(
                selectinload(Conversation.project), selectinload(Conversation.developer)
            )
        )

        # Apply filters (same as get_by_filters)
        if project_id:
            query = query.filter(Conversation.project_id == project_id)
        if developer_id:
            query = query.filter(Conversation.developer_id == developer_id)
        if agent_type:
            query = query.filter(Conversation.agent_type.ilike(f"%{agent_type}%"))
        if status:
            query = query.filter(Conversation.status == status)
        if success is not None:
            query = query.filter(Conversation.success == success)
        if start_date:
            query = query.filter(Conversation.start_time >= start_date)
        if end_date:
            query = query.filter(Conversation.start_time <= end_date)
        if collector_id:
            query = query.filter(Conversation.collector_id == collector_id)

        # Ordering
        order_col = getattr(Conversation, order_by, Conversation.start_time)
        query = query.order_by(
            order_col.desc() if order_dir == "desc" else order_col.asc()
        )

        # Pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        return query.all()

    def get_by_workspace(
        self, workspace_id: uuid.UUID, limit: Optional[int] = None, offset: int = 0
    ) -> List[Conversation]:
        """
        Get all conversations for a workspace.

        Args:
            workspace_id: Workspace UUID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_workspace(self, workspace_id: uuid.UUID) -> int:
        """
        Count conversations in a workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            Number of conversations
        """
        return (
            self.session.query(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .count()
        )

    def get_by_collector(
        self,
        collector_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by collector within a workspace.

        Args:
            collector_id: Collector UUID
            workspace_id: Workspace UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(
                Conversation.collector_id == collector_id,
                Conversation.workspace_id == workspace_id,
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()
