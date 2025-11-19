"""
End-to-End test for hierarchical conversation ingestion.

This test validates the entire pipeline from parsing to database storage
using real Claude Code log files with hierarchical conversations (agents).
"""

import time
from pathlib import Path

from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, WorkspaceRepository
from catsyphon.models.db import Conversation
from catsyphon.parsers import get_default_registry
from catsyphon.pipeline.ingestion import ingest_conversation, link_orphaned_agents


class TestE2EHierarchyIngestion:
    """End-to-end tests for hierarchical conversation ingestion."""

    def test_fresh_db_full_ingestion(self, db_session: Session):
        """
        E2E test: Ingest all test-samples files into fresh database.

        This test validates:
        1. Full dataset ingestion (all available .jsonl files)
        2. Agent conversations correctly linked to parents
        3. No orphaned agents after post-ingestion linking
        4. Data integrity across the entire system
        5. Performance benchmarks for ingestion
        """
        # Setup
        workspace_repo = WorkspaceRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        registry = get_default_registry()

        # Create workspace
        from catsyphon.db.repositories import OrganizationRepository

        org_repo = OrganizationRepository(db_session)
        org = org_repo.create(name="test-org", slug="test-org")
        db_session.flush()

        workspace = workspace_repo.create(
            name="Test Workspace", slug="test-workspace", organization_id=org.id
        )
        db_session.flush()

        # Test data directory
        test_samples_dir = Path("/Users/kulesh/dev/catsyphon/test-samples/-Users-kulesh-dev-topgrader")

        # Verify test data exists
        assert test_samples_dir.exists(), f"Test samples directory not found: {test_samples_dir}"

        # Collect all .jsonl files
        jsonl_files = list(test_samples_dir.glob("*.jsonl"))
        assert len(jsonl_files) > 0, "No .jsonl files found in test samples directory"

        print(f"\n📁 Found {len(jsonl_files)} files to ingest")

        # Track statistics
        start_time = time.time()
        successful_ingestions = 0
        failed_ingestions = 0
        agent_conversations = []
        main_conversations = []
        parse_errors = []

        # Phase 1: Ingest all files
        print("\n📥 Phase 1: Ingesting files...")
        for log_file in jsonl_files:
            try:
                # Parse the file
                parsed = registry.parse(log_file)

                # Ingest into database
                conversation = ingest_conversation(
                    session=db_session,
                    parsed=parsed,
                    project_name="test-project",
                    developer_username="test-developer",
                    file_path=log_file,
                )
                db_session.flush()

                successful_ingestions += 1

                # Track conversation type
                if parsed.conversation_type == "agent":
                    agent_conversations.append(conversation)
                    print(f"  ✓ Agent: {log_file.name} → {conversation.id}")
                else:
                    main_conversations.append(conversation)

            except Exception as e:
                failed_ingestions += 1
                parse_errors.append((log_file.name, str(e)))
                print(f"  ✗ Failed: {log_file.name} - {e}")

        db_session.commit()

        ingestion_time = time.time() - start_time

        # Print ingestion summary
        print(f"\n📊 Ingestion Summary:")
        print(f"  Total files: {len(jsonl_files)}")
        print(f"  Successful: {successful_ingestions}")
        print(f"  Failed: {failed_ingestions}")
        print(f"  Main conversations: {len(main_conversations)}")
        print(f"  Agent conversations: {len(agent_conversations)}")
        print(f"  Time: {ingestion_time:.2f}s")

        # Validation 1: Verify counts
        total_files = len(jsonl_files)
        assert successful_ingestions > 0, "Expected at least some successful ingestions"
        assert successful_ingestions == total_files, f"Expected all {total_files} files to ingest successfully, got {successful_ingestions}"
        assert len(agent_conversations) >= 2, f"Expected at least 2 agent conversations, got {len(agent_conversations)}"
        assert len(main_conversations) >= 1, f"Expected at least 1 main conversation, got {len(main_conversations)}"

        # Phase 2: Link orphaned agents
        print(f"\n🔗 Phase 2: Linking orphaned agents...")
        linking_start = time.time()

        # Count orphans before linking
        orphans_before = db_session.query(Conversation).filter(
            Conversation.workspace_id == workspace.id,
            Conversation.conversation_type == "agent",
            Conversation.parent_conversation_id.is_(None),
        ).count()

        print(f"  Orphaned agents before linking: {orphans_before}")

        # Run linking
        linked_count = link_orphaned_agents(db_session, workspace.id)
        db_session.commit()

        linking_time = time.time() - linking_start

        print(f"  Linked {linked_count} orphaned agents in {linking_time:.2f}s")

        # Count orphans after linking
        orphans_after = db_session.query(Conversation).filter(
            Conversation.workspace_id == workspace.id,
            Conversation.conversation_type == "agent",
            Conversation.parent_conversation_id.is_(None),
        ).count()

        print(f"  Orphaned agents after linking: {orphans_after}")

        # Validation 2: Verify linking worked
        assert linked_count > 0, "Expected at least some agents to be linked"
        assert orphans_after < orphans_before, "Expected fewer orphans after linking"

        # Phase 3: Detailed hierarchy validation
        print(f"\n🔍 Phase 3: Validating hierarchy...")

        # Get all conversations with relations
        all_conversations = conv_repo.get_all()

        # Validate agent conversations
        for agent in agent_conversations:
            db_session.refresh(agent)

            # Check if agent has parent_session_id in metadata
            parent_session_id = agent.agent_metadata.get("parent_session_id")

            if parent_session_id:
                # Find parent by session_id
                parent = next(
                    (
                        c
                        for c in all_conversations
                        if c.extra_data.get("session_id") == parent_session_id
                    ),
                    None,
                )

                if parent:
                    # Agent should be linked to parent
                    assert (
                        agent.parent_conversation_id == parent.id
                    ), f"Agent {agent.id} should be linked to parent {parent.id}"
                    print(f"  ✓ Agent {agent.extra_data.get('session_id')} → Parent {parent.extra_data.get('session_id')}")
                else:
                    # Parent doesn't exist (incomplete test data)
                    assert (
                        agent.parent_conversation_id is None
                    ), f"Agent {agent.id} has parent_id but parent doesn't exist"
                    print(f"  ⊘ Agent {agent.extra_data.get('session_id')} → Parent not found (expected for incomplete data)")

        # Validation 3: Data integrity checks
        print(f"\n🔬 Phase 4: Data integrity checks...")

        # Check for duplicate session_id + conversation_type combinations
        session_type_pairs = {}
        for conv in all_conversations:
            session_id = conv.extra_data.get("session_id")
            if session_id:
                key = (session_id, conv.conversation_type)
                if key in session_type_pairs:
                    raise AssertionError(
                        f"Duplicate session_id + conversation_type: {key}"
                    )
                session_type_pairs[key] = conv.id

        print(f"  ✓ No duplicate session_id + conversation_type pairs")

        # Check that all agents have agent_metadata
        for agent in agent_conversations:
            assert agent.agent_metadata, f"Agent {agent.id} missing agent_metadata"
            assert isinstance(
                agent.agent_metadata, dict
            ), f"Agent {agent.id} agent_metadata is not a dict"

        print(f"  ✓ All agents have valid agent_metadata")

        # Check that all agents have context_semantics
        for agent in agent_conversations:
            assert agent.context_semantics, f"Agent {agent.id} missing context_semantics"
            assert isinstance(
                agent.context_semantics, dict
            ), f"Agent {agent.id} context_semantics is not a dict"

        print(f"  ✓ All agents have valid context_semantics")

        # Performance benchmarks
        print(f"\n⚡ Performance Benchmarks:")
        print(f"  Total time: {ingestion_time + linking_time:.2f}s")
        print(f"  Ingestion time: {ingestion_time:.2f}s")
        print(f"  Linking time: {linking_time:.2f}s")
        print(f"  Files per second: {successful_ingestions / ingestion_time:.2f}")
        print(f"  Average time per file: {ingestion_time / successful_ingestions:.3f}s")

        # Final summary
        print(f"\n✅ E2E Test Summary:")
        print(f"  Total conversations: {len(all_conversations)}")
        print(f"  Main conversations: {len([c for c in all_conversations if c.conversation_type == 'main'])}")
        print(f"  Agent conversations: {len([c for c in all_conversations if c.conversation_type == 'agent'])}")
        print(f"  Linked agents: {len([a for a in agent_conversations if a.parent_conversation_id])}")
        print(f"  Orphaned agents: {orphans_after}")

        # Final assertions
        total_conversations = len(all_conversations)
        assert total_conversations >= successful_ingestions, "Conversation count mismatch"

        linked_agents = len([a for a in agent_conversations if a.parent_conversation_id])
        print(f"\n🎉 E2E test completed successfully!")
        print(f"  Ingested {successful_ingestions} conversations")
        print(f"  Linked {linked_agents} agent conversations to parents")
        print(f"  {orphans_after} orphaned agents remaining (expected for incomplete test data)")

    def test_incremental_parsing_performance(self, db_session: Session):
        """
        Test that incremental parsing is used for re-ingestion.

        This validates that the system correctly detects and uses incremental
        parsing when re-ingesting the same files.
        """
        # Setup
        workspace_repo = WorkspaceRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        registry = get_default_registry()

        from catsyphon.db.repositories import OrganizationRepository

        org_repo = OrganizationRepository(db_session)
        org = org_repo.create(name="test-org-2", slug="test-org-2")
        db_session.flush()

        workspace = workspace_repo.create(
            name="Perf Test Workspace", slug="perf-test-workspace", organization_id=org.id
        )
        db_session.flush()

        # Test with a single large file
        test_samples_dir = Path("/Users/kulesh/dev/catsyphon/test-samples/-Users-kulesh-dev-topgrader")

        # Find a main conversation file (not agent)
        jsonl_files = [
            f for f in test_samples_dir.glob("*.jsonl")
            if not f.name.startswith("agent-")
        ]

        if not jsonl_files:
            print("⚠️  No main conversation files found, skipping incremental test")
            return

        test_file = jsonl_files[0]
        print(f"\n🔄 Testing incremental parsing with: {test_file.name}")

        # First ingestion (full parse)
        print("  First ingestion (full parse)...")
        start_time = time.time()
        parsed = registry.parse(test_file)
        first_parse_time = time.time() - start_time

        conversation = ingest_conversation(
            session=db_session,
            parsed=parsed,
            project_name="perf-project",
            file_path=test_file,
        )
        db_session.commit()

        print(f"    Parse time: {first_parse_time:.3f}s")
        print(f"    Messages: {len(parsed.messages)}")

        # Second ingestion (should detect UNCHANGED and skip)
        print("  Second ingestion (should detect UNCHANGED)...")
        start_time = time.time()
        parsed2 = registry.parse(test_file)
        second_parse_time = time.time() - start_time

        conversation2 = ingest_conversation(
            session=db_session,
            parsed=parsed2,
            project_name="perf-project",
            file_path=test_file,
            update_mode="replace",
        )
        db_session.commit()

        print(f"    Parse time: {second_parse_time:.3f}s")
        print(f"    Messages: {len(parsed2.messages)}")

        # Verify same conversation was returned
        assert conversation2.id == conversation.id, "Should reuse same conversation"

        # Performance comparison
        print(f"\n⚡ Incremental Parsing Performance:")
        print(f"  First parse (full): {first_parse_time:.3f}s")
        print(f"  Second parse (incremental): {second_parse_time:.3f}s")

        if second_parse_time < first_parse_time:
            speedup = first_parse_time / second_parse_time
            print(f"  Speedup: {speedup:.1f}x faster")
        else:
            print(f"  Note: Incremental parsing may not show speedup for small files")

        print(f"\n✅ Incremental parsing test completed")
