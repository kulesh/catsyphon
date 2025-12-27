"""
Tests for AuthContext dependency.

Validates workspace isolation and multi-tenancy security.
"""

import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context, require_auth_context
from catsyphon.db.repositories import OrganizationRepository, WorkspaceRepository
from catsyphon.models.db import Organization, Workspace


class TestAuthContext:
    """Unit tests for AuthContext dataclass."""

    def test_auth_context_creation(self):
        """AuthContext should store workspace and organization IDs."""
        workspace_id = uuid.uuid4()
        org_id = uuid.uuid4()

        ctx = AuthContext(workspace_id=workspace_id, organization_id=org_id)

        assert ctx.workspace_id == workspace_id
        assert ctx.organization_id == org_id
        assert ctx.user_id is None

    def test_auth_context_with_user_id(self):
        """AuthContext should optionally accept user_id for future auth."""
        workspace_id = uuid.uuid4()
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        ctx = AuthContext(
            workspace_id=workspace_id,
            organization_id=org_id,
            user_id=user_id,
        )

        assert ctx.user_id == user_id


class TestGetAuthContext:
    """Integration tests for get_auth_context dependency."""

    @pytest.fixture
    def org_and_workspace(self, db_session: Session):
        """Create test organization and workspace with unique names."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        # Use unique slugs to avoid conflicts with autouse fixtures
        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(name=f"Auth Test Org {unique_id}", slug=f"auth-test-org-{unique_id}")
        workspace = ws_repo.create(
            name=f"Auth Test Workspace {unique_id}",
            slug=f"auth-test-workspace-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace

    @pytest.fixture
    def inactive_workspace(self, db_session: Session, org_and_workspace):
        """Create an inactive workspace."""
        org, _ = org_and_workspace
        ws_repo = WorkspaceRepository(db_session)

        unique_id = str(uuid.uuid4())[:8]
        workspace = ws_repo.create(
            name=f"Inactive Workspace {unique_id}",
            slug=f"inactive-workspace-{unique_id}",
            organization_id=org.id,
            is_active=False,
        )
        db_session.commit()
        return workspace

    def test_valid_workspace_header(self, db_session: Session, org_and_workspace):
        """get_auth_context should accept valid X-Workspace-Id header."""
        _, workspace = org_and_workspace

        ctx = get_auth_context(
            x_workspace_id=str(workspace.id),
            session=db_session,
        )

        assert ctx.workspace_id == workspace.id
        assert ctx.organization_id == workspace.organization_id

    def test_fallback_to_first_workspace(self, db_session: Session, org_and_workspace):
        """get_auth_context should fall back to first workspace if no header."""
        _, workspace = org_and_workspace

        ctx = get_auth_context(x_workspace_id=None, session=db_session)

        # Should get the first workspace
        assert ctx.workspace_id is not None
        assert ctx.organization_id is not None

    def test_invalid_workspace_id_format(self, db_session: Session, org_and_workspace):
        """get_auth_context should reject invalid UUID format."""
        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(x_workspace_id="not-a-uuid", session=db_session)

        assert exc_info.value.status_code == 400
        assert "Invalid workspace ID format" in exc_info.value.detail

    def test_nonexistent_workspace(self, db_session: Session, org_and_workspace):
        """get_auth_context should reject non-existent workspace IDs."""
        fake_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(x_workspace_id=str(fake_id), session=db_session)

        assert exc_info.value.status_code == 401
        assert "Invalid workspace ID" in exc_info.value.detail

    def test_inactive_workspace_rejected(
        self, db_session: Session, inactive_workspace: Workspace
    ):
        """get_auth_context should reject inactive workspaces."""
        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(
                x_workspace_id=str(inactive_workspace.id),
                session=db_session,
            )

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()

    def test_no_workspaces_available(self, db_session: Session):
        """get_auth_context should 401 if no workspaces exist and no header."""
        # Clear all workspaces first
        db_session.query(Workspace).delete()
        db_session.query(Organization).delete()
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_auth_context(x_workspace_id=None, session=db_session)

        assert exc_info.value.status_code == 401
        assert "No workspace available" in exc_info.value.detail


class TestRequireAuthContext:
    """Tests for require_auth_context (strict mode)."""

    @pytest.fixture
    def org_and_workspace(self, db_session: Session):
        """Create test organization and workspace with unique names."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        # Use unique slugs to avoid conflicts with autouse fixtures
        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(name=f"Require Auth Test Org {unique_id}", slug=f"require-auth-org-{unique_id}")
        workspace = ws_repo.create(
            name=f"Require Auth Test Workspace {unique_id}",
            slug=f"require-auth-ws-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace

    def test_valid_workspace_header(self, db_session: Session, org_and_workspace):
        """require_auth_context should accept valid X-Workspace-Id header."""
        _, workspace = org_and_workspace

        ctx = require_auth_context(
            x_workspace_id=str(workspace.id),
            session=db_session,
        )

        assert ctx.workspace_id == workspace.id

    def test_missing_header_raises_error(self, db_session: Session):
        """require_auth_context should require the header (no fallback)."""
        # Note: In actual FastAPI usage, missing required header returns 422
        # We test the function directly here which would receive the value
        with pytest.raises(HTTPException) as exc_info:
            require_auth_context(x_workspace_id="", session=db_session)

        # Empty string is invalid UUID format
        assert exc_info.value.status_code == 400


class TestAuthContextAPIIntegration:
    """End-to-end API tests for auth context."""

    @pytest.fixture
    def app_with_auth_endpoint(self, db_session: Session):
        """Create a test app with an endpoint using auth context."""
        from fastapi import Depends

        app = FastAPI()

        @app.get("/test-auth")
        def test_auth(auth: AuthContext = Depends(get_auth_context)):
            return {
                "workspace_id": str(auth.workspace_id),
                "organization_id": str(auth.organization_id),
            }

        return app

    @pytest.fixture
    def test_client(self, app_with_auth_endpoint):
        """Create test client."""
        return TestClient(app_with_auth_endpoint, raise_server_exceptions=False)

    @pytest.fixture
    def setup_test_data(self, db_session: Session):
        """Create test organization and workspace for API tests with unique names."""
        org_repo = OrganizationRepository(db_session)
        ws_repo = WorkspaceRepository(db_session)

        # Use unique slugs to avoid conflicts with autouse fixtures
        unique_id = str(uuid.uuid4())[:8]
        org = org_repo.create(name=f"API Test Org {unique_id}", slug=f"api-test-org-{unique_id}")
        workspace = ws_repo.create(
            name=f"API Test Workspace {unique_id}",
            slug=f"api-test-workspace-{unique_id}",
            organization_id=org.id,
        )
        db_session.commit()

        return org, workspace
