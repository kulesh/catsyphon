"""
Plugin manifest schema and validation.

Defines the structure of plugin metadata files (catsyphon.json) that describe
parser plugins. Manifests are validated using Pydantic for type safety.
"""

import logging
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class PluginMetadata(BaseModel):
    """
    Metadata about a parser plugin.

    This is typically stored in a catsyphon.json file alongside the plugin code.
    """

    name: str = Field(
        ...,
        description="Unique plugin name (lowercase, alphanumeric, hyphens only)",
        pattern=r"^[a-z0-9-]+$",
    )

    version: str = Field(
        ...,
        description="Semantic version (e.g., '1.0.0')",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    description: str = Field(
        ...,
        description="Human-readable description of the plugin",
        min_length=10,
        max_length=500,
    )

    parser_class: str = Field(
        ...,
        description="Fully qualified class name (e.g., 'my_plugin.parser.MyParser')",
    )

    supported_formats: List[str] = Field(
        ...,
        description="File extensions this parser supports (e.g., ['.jsonl', '.json'])",
        min_length=1,
    )

    author: Optional[str] = Field(
        None,
        description="Plugin author name or organization",
    )

    homepage: Optional[str] = Field(
        None,
        description="URL to plugin documentation or repository",
    )

    license: Optional[str] = Field(
        None,
        description="License identifier (e.g., 'MIT', 'Apache-2.0')",
    )

    requires_python: Optional[str] = Field(
        None,
        description="Minimum Python version required (e.g., '>=3.11')",
    )

    dependencies: List[str] = Field(
        default_factory=list,
        description="Python package dependencies (e.g., ['requests>=2.28.0'])",
    )

    @field_validator("supported_formats")
    @classmethod
    def validate_formats(cls, formats: List[str]) -> List[str]:
        """Ensure all formats start with a dot and are lowercase."""
        validated = []
        for fmt in formats:
            if not fmt.startswith("."):
                fmt = f".{fmt}"
            validated.append(fmt.lower())
        return validated

    @field_validator("parser_class")
    @classmethod
    def validate_parser_class(cls, value: str) -> str:
        """Ensure parser_class has at least module.Class structure."""
        parts = value.split(".")
        if len(parts) < 2:
            raise ValueError(
                f"parser_class must be fully qualified (e.g., 'module.Class'), got: {value}"
            )
        return value


class PluginManifest(BaseModel):
    """
    Complete plugin manifest including metadata and discovery info.

    This extends PluginMetadata with runtime information about where
    the plugin was discovered and how to load it.
    """

    metadata: PluginMetadata = Field(
        ...,
        description="Core plugin metadata from catsyphon.json",
    )

    plugin_dir: Optional[Path] = Field(
        None,
        description="Directory containing the plugin (for directory-based plugins)",
    )

    entry_point: Optional[str] = Field(
        None,
        description="Entry point name (for package-based plugins)",
    )

    @property
    def name(self) -> str:
        """Convenience accessor for plugin name."""
        return self.metadata.name

    @property
    def version(self) -> str:
        """Convenience accessor for plugin version."""
        return self.metadata.version

    def is_directory_plugin(self) -> bool:
        """Check if this plugin was loaded from a directory."""
        return self.plugin_dir is not None

    def is_entry_point_plugin(self) -> bool:
        """Check if this plugin was loaded from an entry point."""
        return self.entry_point is not None

    @classmethod
    def from_file(cls, manifest_path: Path, plugin_dir: Path) -> "PluginManifest":
        """
        Load a plugin manifest from a catsyphon.json file.

        Args:
            manifest_path: Path to the catsyphon.json file
            plugin_dir: Directory containing the plugin

        Returns:
            PluginManifest instance

        Raises:
            ValueError: If the manifest file is invalid
            FileNotFoundError: If the manifest file doesn't exist
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        try:
            import json

            with open(manifest_path) as f:
                data = json.load(f)

            metadata = PluginMetadata(**data)
            return cls(
                metadata=metadata,
                plugin_dir=plugin_dir,
                entry_point=None,
            )

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest {manifest_path}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse manifest {manifest_path}: {e}")

    @classmethod
    def from_entry_point(
        cls,
        entry_point_name: str,
        metadata: PluginMetadata,
    ) -> "PluginManifest":
        """
        Create a plugin manifest from an entry point.

        Args:
            entry_point_name: Name of the entry point
            metadata: Plugin metadata

        Returns:
            PluginManifest instance
        """
        return cls(
            metadata=metadata,
            plugin_dir=None,
            entry_point=entry_point_name,
        )
