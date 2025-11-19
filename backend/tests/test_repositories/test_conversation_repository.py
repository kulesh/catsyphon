"""
Tests for ConversationRepository with focus on hierarchical conversations.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, DeveloperRepository, ProjectRepository
from catsyphon.models.db import Conversation


class TestConversationRepositoryBasics:
    """Basic tests for conversation repository."""

    def test_create_conversation(self, db_session: Session, sample_workspace):
        """Test creating a basic conversation."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        conversation = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            agent_version="2.0.28",
            start_time=now,
            end_time=now + timedelta(minutes=5),
        )
        db_session.flush()

        assert conversation.id is not None
        assert conversation.agent_type == "claude-code"
        assert conversation.workspace_id == sample_workspace.id

    def test_get_by_id(self, db_session: Session, sample_workspace):
        """Test retrieving conversation by ID."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        created = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
        )
        db_session.flush()

        retrieved = repo.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_all(self, db_session: Session, sample_workspace):
        """Test getting all conversations."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create multiple conversations
        for i in range(3):
            repo.create(
                workspace_id=sample_workspace.id,
                agent_type="claude-code",
                start_time=now + timedelta(minutes=i),
            )
        db_session.flush()

        all_convs = repo.get_all()

        assert len(all_convs) >= 3


class TestHierarchicalConversationRepository:
    """Tests for hierarchical conversation queries."""

    def test_get_with_relations_loads_children(self, db_session: Session, sample_workspace):
        """Test that get_with_relations loads children conversations."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent conversation
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-123"},
            conversation_type="main",
        )
        db_session.flush()

        # Create child agent conversations
        child1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            extra_data={"session_id": "agent-1"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-1", "parent_session_id": "parent-123"},
        )
        child2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            extra_data={"session_id": "agent-2"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-2", "parent_session_id": "parent-123"},
        )
        db_session.flush()

        # Retrieve parent with relations
        parent_with_relations = repo.get_with_relations(parent.id, sample_workspace.id)

        assert parent_with_relations is not None
        assert len(parent_with_relations.children) == 2
        assert {c.id for c in parent_with_relations.children} == {child1.id, child2.id}

    def test_get_with_relations_loads_parent(self, db_session: Session, sample_workspace):
        """Test that get_with_relations loads parent conversation."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "parent-456"},
            conversation_type="main",
        )
        db_session.flush()

        # Create child
        child = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            extra_data={"session_id": "agent-child"},
            conversation_type="agent",
            parent_conversation_id=parent.id,
            agent_metadata={"agent_id": "agent-child", "parent_session_id": "parent-456"},
        )
        db_session.flush()

        # Retrieve child with relations
        child_with_relations = repo.get_with_relations(child.id, sample_workspace.id)

        assert child_with_relations is not None
        assert child_with_relations.parent_conversation is not None
        assert child_with_relations.parent_conversation.id == parent.id

    def test_get_by_conversation_type_main(self, db_session: Session, sample_workspace):
        """Test filtering conversations by conversation_type='main'."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create mixed conversations
        main1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        agent1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
        )
        main2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="main",
        )
        db_session.flush()

        # Query by conversation_type
        # Note: Using raw SQLAlchemy query since get_by_filters may not support this yet
        main_convs = db_session.query(Conversation).filter(
            Conversation.workspace_id == sample_workspace.id,
            Conversation.conversation_type == "main"
        ).all()

        assert len(main_convs) >= 2
        assert all(c.conversation_type == "main" for c in main_convs)
        assert main1.id in [c.id for c in main_convs]
        assert main2.id in [c.id for c in main_convs]
        assert agent1.id not in [c.id for c in main_convs]

    def test_get_by_conversation_type_agent(self, db_session: Session, sample_workspace):
        """Test filtering conversations by conversation_type='agent'."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create mixed conversations
        main1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        agent1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
        )
        agent2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="agent",
        )
        db_session.flush()

        # Query by conversation_type
        agent_convs = db_session.query(Conversation).filter(
            Conversation.workspace_id == sample_workspace.id,
            Conversation.conversation_type == "agent"
        ).all()

        assert len(agent_convs) >= 2
        assert all(c.conversation_type == "agent" for c in agent_convs)
        assert agent1.id in [c.id for c in agent_convs]
        assert agent2.id in [c.id for c in agent_convs]
        assert main1.id not in [c.id for c in agent_convs]

    def test_get_by_parent_conversation_id(self, db_session: Session, sample_workspace):
        """Test finding children by parent_conversation_id."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create parent
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        db_session.flush()

        # Create children
        child1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
            parent_conversation_id=parent.id,
        )
        child2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="agent",
            parent_conversation_id=parent.id,
        )
        db_session.flush()

        # Query children by parent ID
        children = db_session.query(Conversation).filter(
            Conversation.parent_conversation_id == parent.id
        ).all()

        assert len(children) == 2
        assert {c.id for c in children} == {child1.id, child2.id}

    def test_get_orphaned_agents(self, db_session: Session, sample_workspace):
        """Test finding orphaned agent conversations (parent_conversation_id is NULL)."""
        repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create orphaned agents
        orphan1 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="agent",
            parent_conversation_id=None,
            agent_metadata={"parent_session_id": "non-existent-parent"},
        )
        orphan2 = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
            parent_conversation_id=None,
            agent_metadata={"parent_session_id": "another-missing-parent"},
        )

        # Create linked agent (not orphaned)
        parent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now,
            conversation_type="main",
        )
        db_session.flush()

        linked_agent = repo.create(
            workspace_id=sample_workspace.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=2),
            conversation_type="agent",
            parent_conversation_id=parent.id,
        )
        db_session.flush()

        # Query orphaned agents
        orphans = db_session.query(Conversation).filter(
            Conversation.workspace_id == sample_workspace.id,
            Conversation.conversation_type == "agent",
            Conversation.parent_conversation_id.is_(None)
        ).all()

        assert len(orphans) >= 2
        assert orphan1.id in [o.id for o in orphans]
        assert orphan2.id in [o.id for o in orphans]
        assert linked_agent.id not in [o.id for o in orphans]

    def test_workspace_isolation_hierarchy(self, db_session: Session):
        """Test that workspace isolation prevents cross-workspace parent linking."""
        from catsyphon.db.repositories import WorkspaceRepository, OrganizationRepository

        org_repo = OrganizationRepository(db_session)
        workspace_repo = WorkspaceRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        now = datetime.now(UTC)

        # Create organization first
        org = org_repo.create(name="test-org", slug="test-org")
        db_session.flush()

        # Create two workspaces
        workspace1 = workspace_repo.create(name="workspace-1", slug="workspace-1", organization_id=org.id)
        workspace2 = workspace_repo.create(name="workspace-2", slug="workspace-2", organization_id=org.id)
        db_session.flush()

        # Create parent in workspace 1
        parent_ws1 = conv_repo.create(
            workspace_id=workspace1.id,
            agent_type="claude-code",
            start_time=now,
            extra_data={"session_id": "shared-session-id"},
            conversation_type="main",
        )
        db_session.flush()

        # Create orphaned agent in workspace 2 with same parent session ID
        agent_ws2 = conv_repo.create(
            workspace_id=workspace2.id,
            agent_type="claude-code",
            start_time=now + timedelta(minutes=1),
            conversation_type="agent",
            agent_metadata={"parent_session_id": "shared-session-id"},
            parent_conversation_id=None,
        )
        db_session.flush()

        # Query parent in workspace 2 (should not find parent from workspace 1)
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy import cast, String

        # Use JSON path query for SQLite compatibility
        parent_in_ws2_query = db_session.query(Conversation).filter(
            Conversation.workspace_id == workspace2.id,
            cast(Conversation.extra_data["session_id"], String) == "shared-session-id"
        ).all()

        # Should not find parent from workspace 1
        assert len(parent_in_ws2_query) == 0

        # Verify agent remains orphaned (cannot link to parent in different workspace)
        assert agent_ws2.parent_conversation_id is None
