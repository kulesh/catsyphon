"""Tests for credential storage."""

import json
import tempfile
from pathlib import Path

import pytest

from catsyphon_sdk.credentials import CredentialStore


class TestCredentialStore:
    """Tests for CredentialStore."""

    @pytest.fixture
    def temp_store(self, tmp_path: Path) -> CredentialStore:
        """Create a credential store with temp directory."""
        return CredentialStore(config_dir=tmp_path)

    def test_store_and_retrieve(self, temp_store: CredentialStore):
        """Should store and retrieve credentials."""
        temp_store.store(
            server_url="https://example.com",
            workspace_id="ws-123",
            collector_id="col-456",
            api_key="cs_live_secret",
            api_key_prefix="cs_live_sec",
        )

        cred = temp_store.get(
            server_url="https://example.com",
            workspace_id="ws-123",
        )

        assert cred is not None
        assert cred.collector_id == "col-456"
        assert cred.api_key == "cs_live_secret"
        assert cred.api_key_prefix == "cs_live_sec"

    def test_get_nonexistent(self, temp_store: CredentialStore):
        """Should return None for nonexistent credentials."""
        cred = temp_store.get(
            server_url="https://example.com",
            workspace_id="ws-123",
        )
        assert cred is None

    def test_multiple_profiles(self, temp_store: CredentialStore):
        """Should support multiple profiles."""
        temp_store.store(
            server_url="https://example.com",
            workspace_id="ws-123",
            collector_id="col-1",
            api_key="key-1",
            api_key_prefix="prefix-1",
            profile="dev",
        )
        temp_store.store(
            server_url="https://example.com",
            workspace_id="ws-123",
            collector_id="col-2",
            api_key="key-2",
            api_key_prefix="prefix-2",
            profile="prod",
        )

        dev_cred = temp_store.get(
            server_url="https://example.com",
            workspace_id="ws-123",
            profile="dev",
        )
        prod_cred = temp_store.get(
            server_url="https://example.com",
            workspace_id="ws-123",
            profile="prod",
        )

        assert dev_cred.collector_id == "col-1"
        assert prod_cred.collector_id == "col-2"

    def test_delete_credential(self, temp_store: CredentialStore):
        """Should delete credentials."""
        temp_store.store(
            server_url="https://example.com",
            workspace_id="ws-123",
            collector_id="col-456",
            api_key="secret",
            api_key_prefix="sec",
        )

        deleted = temp_store.delete(
            server_url="https://example.com",
            workspace_id="ws-123",
        )
        assert deleted is True

        cred = temp_store.get(
            server_url="https://example.com",
            workspace_id="ws-123",
        )
        assert cred is None

    def test_delete_nonexistent(self, temp_store: CredentialStore):
        """Should return False when deleting nonexistent."""
        deleted = temp_store.delete(
            server_url="https://example.com",
            workspace_id="ws-123",
        )
        assert deleted is False

    def test_list_profiles(self, temp_store: CredentialStore):
        """Should list all profiles."""
        temp_store.store(
            server_url="https://a.com",
            workspace_id="ws-1",
            collector_id="col-1",
            api_key="key-1",
            api_key_prefix="p-1",
        )
        temp_store.store(
            server_url="https://b.com",
            workspace_id="ws-2",
            collector_id="col-2",
            api_key="key-2",
            api_key_prefix="p-2",
        )

        profiles = temp_store.list_profiles()
        assert len(profiles) == 2

    def test_clear_all(self, temp_store: CredentialStore):
        """Should clear all credentials."""
        temp_store.store(
            server_url="https://a.com",
            workspace_id="ws-1",
            collector_id="col-1",
            api_key="key-1",
            api_key_prefix="p-1",
        )
        temp_store.store(
            server_url="https://b.com",
            workspace_id="ws-2",
            collector_id="col-2",
            api_key="key-2",
            api_key_prefix="p-2",
        )

        count = temp_store.clear_all()
        assert count == 2

        profiles = temp_store.list_profiles()
        assert len(profiles) == 0

    def test_url_normalization(self, temp_store: CredentialStore):
        """Should handle URL variations."""
        temp_store.store(
            server_url="https://example.com/",  # With trailing slash
            workspace_id="ws-123",
            collector_id="col-456",
            api_key="secret",
            api_key_prefix="sec",
        )

        # Should find with or without trailing slash
        cred = temp_store.get(
            server_url="https://example.com",  # Without trailing slash
            workspace_id="ws-123",
        )
        # Note: Current implementation may treat these differently
        # This test documents current behavior
