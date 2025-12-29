"""
File-based credential storage for CatSyphon SDK.

Stores collector credentials in ~/.catsyphon/credentials.json with
secure file permissions. Supports multiple server/workspace profiles.
"""

import json
import logging
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default credential directory follows XDG spec
DEFAULT_CATSYPHON_DIR = Path.home() / ".catsyphon"
CREDENTIALS_FILE = "credentials.json"


@dataclass
class StoredCredential:
    """A stored collector credential."""

    server_url: str
    workspace_id: str
    collector_id: str
    api_key: str
    api_key_prefix: str
    created_at: str
    profile: str = "default"


class CredentialStore:
    """
    File-based credential storage.

    Stores credentials in ~/.catsyphon/credentials.json with secure permissions.
    Supports multiple profiles for different server/workspace combinations.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the credential store.

        Args:
            config_dir: Directory for credentials file (default: ~/.catsyphon)
        """
        self.config_dir = config_dir or DEFAULT_CATSYPHON_DIR
        self.credentials_file = self.config_dir / CREDENTIALS_FILE

    def _ensure_config_dir(self) -> None:
        """Create config directory with secure permissions if needed."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, mode=0o700)
            logger.debug(f"Created credentials directory: {self.config_dir}")

    def _secure_file_permissions(self) -> None:
        """Ensure credentials file has secure permissions (600)."""
        if self.credentials_file.exists():
            # Set permissions to owner read/write only
            os.chmod(self.credentials_file, stat.S_IRUSR | stat.S_IWUSR)

    def _load_credentials(self) -> dict[str, dict]:
        """Load all credentials from file."""
        if not self.credentials_file.exists():
            return {}

        try:
            with open(self.credentials_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load credentials: {e}")
            return {}

    def _save_credentials(self, credentials: dict[str, dict]) -> None:
        """Save all credentials to file."""
        self._ensure_config_dir()

        with open(self.credentials_file, "w") as f:
            json.dump(credentials, f, indent=2)

        self._secure_file_permissions()

    @staticmethod
    def _make_profile_key(server_url: str, workspace_id: str, profile: str) -> str:
        """Generate a unique key for a server/workspace/profile combination."""
        # Normalize server URL
        parsed = urlparse(server_url)
        host = parsed.netloc or parsed.path
        return f"{profile}:{host}:{workspace_id}"

    def store(
        self,
        server_url: str,
        workspace_id: str,
        collector_id: str,
        api_key: str,
        api_key_prefix: str,
        profile: str = "default",
    ) -> None:
        """
        Store a collector credential.

        Args:
            server_url: CatSyphon server URL
            workspace_id: Workspace UUID
            collector_id: Collector UUID
            api_key: API key (will be stored securely)
            api_key_prefix: API key prefix for identification
            profile: Profile name for this credential
        """
        credentials = self._load_credentials()

        key = self._make_profile_key(server_url, workspace_id, profile)
        credentials[key] = {
            "server_url": server_url,
            "workspace_id": workspace_id,
            "collector_id": collector_id,
            "api_key": api_key,
            "api_key_prefix": api_key_prefix,
            "profile": profile,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._save_credentials(credentials)
        logger.info(f"Stored credentials for profile '{profile}' ({api_key_prefix}...)")

    def get(
        self,
        server_url: str,
        workspace_id: str,
        profile: str = "default",
    ) -> Optional[StoredCredential]:
        """
        Retrieve a stored credential.

        Args:
            server_url: CatSyphon server URL
            workspace_id: Workspace UUID
            profile: Profile name

        Returns:
            StoredCredential if found, None otherwise
        """
        credentials = self._load_credentials()
        key = self._make_profile_key(server_url, workspace_id, profile)

        if key not in credentials:
            return None

        cred = credentials[key]
        return StoredCredential(
            server_url=cred["server_url"],
            workspace_id=cred["workspace_id"],
            collector_id=cred["collector_id"],
            api_key=cred["api_key"],
            api_key_prefix=cred["api_key_prefix"],
            profile=cred.get("profile", "default"),
            created_at=cred.get("created_at", ""),
        )

    def delete(
        self,
        server_url: str,
        workspace_id: str,
        profile: str = "default",
    ) -> bool:
        """
        Delete a stored credential.

        Args:
            server_url: CatSyphon server URL
            workspace_id: Workspace UUID
            profile: Profile name

        Returns:
            True if deleted, False if not found
        """
        credentials = self._load_credentials()
        key = self._make_profile_key(server_url, workspace_id, profile)

        if key not in credentials:
            return False

        del credentials[key]
        self._save_credentials(credentials)
        logger.info(f"Deleted credentials for profile '{profile}'")
        return True

    def list_profiles(self) -> list[StoredCredential]:
        """
        List all stored credential profiles.

        Returns:
            List of stored credentials
        """
        credentials = self._load_credentials()
        return [
            StoredCredential(
                server_url=cred["server_url"],
                workspace_id=cred["workspace_id"],
                collector_id=cred["collector_id"],
                api_key=cred["api_key"],
                api_key_prefix=cred["api_key_prefix"],
                profile=cred.get("profile", "default"),
                created_at=cred.get("created_at", ""),
            )
            for cred in credentials.values()
        ]

    def clear_all(self) -> int:
        """
        Clear all stored credentials.

        Returns:
            Number of credentials deleted
        """
        credentials = self._load_credentials()
        count = len(credentials)

        if count > 0:
            self._save_credentials({})
            logger.info(f"Cleared {count} stored credential(s)")

        return count
