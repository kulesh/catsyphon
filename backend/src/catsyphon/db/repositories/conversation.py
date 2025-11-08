"""
Conversation repository.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from catsyphon.db.repositories.base import BaseRepository
from catsyphon.models.db import Conversation


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation model."""

    def __init__(self, session: Session):
        super().__init__(Conversation, session)

    def get_with_relations(self, id: uuid.UUID) -> Optional[Conversation]:
        """
        Get conversation with all related data loaded.

        Args:
            id: Conversation UUID

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
            )
            .filter(Conversation.id == id)
            .first()
        )

    def get_by_project(
        self,
        project_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by project.

        Args:
            project_id: Project UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(Conversation.project_id == project_id)
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_developer(
        self,
        developer_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by developer.

        Args:
            developer_id: Developer UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(Conversation.developer_id == developer_id)
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_agent_type(
        self,
        agent_type: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by agent type.

        Args:
            agent_type: Agent type (e.g., 'claude-code')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations
        """
        query = (
            self.session.query(Conversation)
            .filter(Conversation.agent_type == agent_type)
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
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations within date range.

        Args:
            start_date: Start datetime
            end_date: End datetime
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
            )
            .order_by(Conversation.start_time.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_by_status(self, status: str) -> int:
        """
        Count conversations by status.

        Args:
            status: Conversation status

        Returns:
            Count of conversations
        """
        return (
            self.session.query(Conversation)
            .filter(Conversation.status == status)
            .count()
        )

    def get_recent(self, limit: int = 10) -> List[Conversation]:
        """
        Get most recent conversations.

        Args:
            limit: Maximum number of results

        Returns:
            List of recent conversations
        """
        return (
            self.session.query(Conversation)
            .order_by(Conversation.start_time.desc())
            .limit(limit)
            .all()
        )

    def get_by_filters(
        self,
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        load_relations: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations by multiple filters.

        Args:
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            load_relations: Whether to load related objects
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of conversations matching filters
        """
        query = self.session.query(Conversation)

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
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count conversations by multiple filters.

        Args:
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)

        Returns:
            Count of conversations matching filters
        """
        query = self.session.query(Conversation)

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

        return query.count()

    def get_with_counts(
        self,
        project_id: Optional[uuid.UUID] = None,
        developer_id: Optional[uuid.UUID] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        order_by: str = "start_time",
        order_dir: str = "desc",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Tuple[Conversation, int, int, int]]:
        """
        Get conversations with counts computed in SQL.

        Returns list of (conversation, message_count, epoch_count, files_count) tuples.
        This is much more efficient than loading all messages/epochs/files just to count them.

        Args:
            project_id: Filter by project
            developer_id: Filter by developer
            agent_type: Filter by agent type (partial match)
            status: Filter by status
            success: Filter by success status
            start_date: Filter by start date (>=)
            end_date: Filter by end date (<=)
            order_by: Column to order by
            order_dir: Order direction ('asc' or 'desc')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of (Conversation, message_count, epoch_count, files_count) tuples
        """
        from catsyphon.models.db import Message, Epoch, FileTouched

        query = (
            self.session.query(
                Conversation,
                func.coalesce(func.count(Message.id.distinct()), 0).label('message_count'),
                func.coalesce(func.count(Epoch.id.distinct()), 0).label('epoch_count'),
                func.coalesce(func.count(FileTouched.id.distinct()), 0).label('files_count'),
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
            .outerjoin(Epoch, Conversation.id == Epoch.conversation_id)
            .outerjoin(FileTouched, Conversation.id == FileTouched.conversation_id)
            .options(
                joinedload(Conversation.project),
                joinedload(Conversation.developer)
            )
            .group_by(Conversation.id)
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

        # Ordering
        order_col = getattr(Conversation, order_by, Conversation.start_time)
        query = query.order_by(order_col.desc() if order_dir == "desc" else order_col.asc())

        # Pagination
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        return query.all()
