"""
Auto-bootstrap for zero-config startup.

When AUTO_SETUP=true, idempotently creates the organization, workspace, and
watch configurations specified by environment variables.  Safe to run on every
restart — existing records are reused, not duplicated.
"""

import logging
import os
import re

from catsyphon.config import settings
from catsyphon.db.connection import db_session
from catsyphon.db.repositories.organization import OrganizationRepository
from catsyphon.db.repositories.watch_config import WatchConfigurationRepository
from catsyphon.db.repositories.workspace import WorkspaceRepository

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a human name to a URL-friendly slug."""
    slug = re.sub(r"[\s_]+", "-", name.lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug.strip("-"))
    return slug or "default"


def auto_bootstrap() -> None:
    """
    Create org, workspace, and watch configs from AUTO_* env vars.

    Designed to run once per startup inside the deferred config loader thread.
    Every operation is idempotent: existing records are looked up by slug or
    directory before creating new ones.
    """
    if not settings.auto_setup:
        return

    org_name = settings.auto_org_name or os.environ.get("HOSTNAME", "local")
    workspace_name = settings.auto_workspace_name
    watch_dirs_raw = settings.auto_watch_dirs

    logger.info("Auto-bootstrap: setting up %s / %s", org_name, workspace_name)

    with db_session() as session:
        # ── Organization ─────────────────────────────────────────────
        org_repo = OrganizationRepository(session)
        org_slug = _slugify(org_name)
        org = org_repo.get_or_create_by_slug(org_slug, org_name)
        session.flush()  # ensure org.id is assigned
        logger.info("Auto-bootstrap: org '%s' (id=%s)", org.name, org.id)

        # ── Workspace ────────────────────────────────────────────────
        ws_repo = WorkspaceRepository(session)
        ws_slug = _slugify(workspace_name)
        workspace = ws_repo.get_or_create_by_slug(
            ws_slug, workspace_name, org.id
        )
        session.flush()
        logger.info(
            "Auto-bootstrap: workspace '%s' (id=%s)", workspace.name, workspace.id
        )

        # ── Watch configurations ─────────────────────────────────────
        if not watch_dirs_raw:
            logger.info("Auto-bootstrap: no watch directories specified")
            return

        watch_repo = WatchConfigurationRepository(session)
        dirs = [d.strip() for d in watch_dirs_raw.split(",") if d.strip()]

        created = 0
        reactivated = 0

        for directory in dirs:
            if not os.path.isdir(directory):
                logger.info(
                    "Auto-bootstrap: skipping %s (not mounted)", directory
                )
                continue

            existing = watch_repo.get_by_directory(directory, workspace.id)
            if existing:
                if not existing.is_active:
                    watch_repo.activate(existing.id)
                    reactivated += 1
                    logger.info(
                        "Auto-bootstrap: reactivated watch for %s", directory
                    )
                else:
                    logger.info(
                        "Auto-bootstrap: watch already active for %s", directory
                    )
            else:
                watch_repo.create(
                    workspace_id=workspace.id,
                    directory=directory,
                    is_active=True,
                )
                created += 1
                logger.info(
                    "Auto-bootstrap: created watch for %s", directory
                )

    logger.info(
        "Auto-bootstrap complete: %d created, %d reactivated",
        created,
        reactivated,
    )
