#!/usr/bin/env python3
"""
Backfill conversation.developer_id from working_directory paths.

This script updates existing conversations to set the developer_id field
by extracting the username from the working_directory path.
"""

from catsyphon.db.connection import db_session
from catsyphon.db.repositories import DeveloperRepository, WorkspaceRepository
from catsyphon.models.db import Conversation
from catsyphon.pipeline.ingestion import _extract_username_from_path
from sqlalchemy import select


def main():
    """Backfill developer_id from working_directory paths."""
    with db_session() as db:
        # Get default workspace
        workspace_repo = WorkspaceRepository(db)
        workspaces = workspace_repo.get_all(limit=1)
        if not workspaces:
            print("No workspace found")
            return
        workspace_id = workspaces[0].id

        # Get developer repo
        dev_repo = DeveloperRepository(db)

        # Get all conversations without developer_id
        conversations = (
            db.execute(
                select(Conversation).where(Conversation.developer_id.is_(None))
            )
            .scalars()
            .all()
        )

        print(f"Found {len(conversations)} conversations without developer_id")

        updated_count = 0
        skipped_count = 0

        for conv in conversations:
            # Try to extract username from project's directory_path
            username = None
            if conv.project and conv.project.directory_path:
                username = _extract_username_from_path(conv.project.directory_path)

            if username:
                # Get or create developer
                developer = dev_repo.get_or_create_by_username(username, workspace_id)
                conv.developer_id = developer.id
                updated_count += 1
                print(f"  {conv.id}: '{username}' (from {conv.project.directory_path})")
            else:
                skipped_count += 1

        # Commit changes
        db.commit()

        print(f"\nResults:")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped (no username in path): {skipped_count}")
        print(f"  Total: {len(conversations)}")


if __name__ == "__main__":
    main()
