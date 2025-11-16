"""Tests for plugin manifest schema and validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from catsyphon.plugins.manifest import PluginManifest, PluginMetadata


class TestPluginMetadata:
    """Test PluginMetadata validation."""

    def test_valid_metadata(self):
        """Test creating valid metadata."""
        metadata = PluginMetadata(
            name="cursor-parser",
            version="1.0.0",
            description="Parser for Cursor IDE conversation logs",
            parser_class="cursor_parser.parser.CursorParser",
            supported_formats=[".db", ".sqlite"],
        )

        assert metadata.name == "cursor-parser"
        assert metadata.version == "1.0.0"
        assert metadata.supported_formats == [".db", ".sqlite"]

    def test_name_validation(self):
        """Test plugin name validation (lowercase, alphanumeric, hyphens)."""
        # Valid names
        PluginMetadata(
            name="cursor-parser",
            version="1.0.0",
            description="Valid parser name",
            parser_class="module.Class",
            supported_formats=[".json"],
        )

        PluginMetadata(
            name="my-parser-123",
            version="1.0.0",
            description="Valid parser name",
            parser_class="module.Class",
            supported_formats=[".json"],
        )

        # Invalid: uppercase
        with pytest.raises(ValidationError, match="String should match pattern"):
            PluginMetadata(
                name="CursorParser",
                version="1.0.0",
                description="Invalid uppercase",
                parser_class="module.Class",
                supported_formats=[".json"],
            )

        # Invalid: underscores
        with pytest.raises(ValidationError, match="String should match pattern"):
            PluginMetadata(
                name="cursor_parser",
                version="1.0.0",
                description="Invalid underscore",
                parser_class="module.Class",
                supported_formats=[".json"],
            )

    def test_version_validation(self):
        """Test semantic version validation."""
        # Valid versions
        PluginMetadata(
            name="test",
            version="1.0.0",
            description="Valid version",
            parser_class="module.Class",
            supported_formats=[".json"],
        )

        PluginMetadata(
            name="test",
            version="12.34.56",
            description="Valid version",
            parser_class="module.Class",
            supported_formats=[".json"],
        )

        # Invalid: not semantic version
        with pytest.raises(ValidationError, match="String should match pattern"):
            PluginMetadata(
                name="test",
                version="1.0",
                description="Invalid version",
                parser_class="module.Class",
                supported_formats=[".json"],
            )

        with pytest.raises(ValidationError, match="String should match pattern"):
            PluginMetadata(
                name="test",
                version="v1.0.0",
                description="Invalid version with v prefix",
                parser_class="module.Class",
                supported_formats=[".json"],
            )

    def test_description_length(self):
        """Test description length constraints."""
        # Too short
        with pytest.raises(
            ValidationError, match="String should have at least 10 characters"
        ):
            PluginMetadata(
                name="test",
                version="1.0.0",
                description="Short",
                parser_class="module.Class",
                supported_formats=[".json"],
            )

        # Too long
        with pytest.raises(
            ValidationError, match="String should have at most 500 characters"
        ):
            PluginMetadata(
                name="test",
                version="1.0.0",
                description="x" * 501,
                parser_class="module.Class",
                supported_formats=[".json"],
            )

    def test_parser_class_validation(self):
        """Test parser class path validation."""
        # Valid: fully qualified
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Valid class path",
            parser_class="my_package.parser.MyParser",
            supported_formats=[".json"],
        )
        assert metadata.parser_class == "my_package.parser.MyParser"

        # Valid: minimum module.Class structure
        metadata2 = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Valid class path",
            parser_class="module.Class",
            supported_formats=[".json"],
        )
        assert metadata2.parser_class == "module.Class"

    def test_supported_formats_validation(self):
        """Test format normalization (adds dots, lowercases)."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test format normalization",
            parser_class="module.Class",
            supported_formats=["json", ".JSONL", "DB"],
        )

        # Should normalize to lowercase with dots
        assert metadata.supported_formats == [".json", ".jsonl", ".db"]

    def test_optional_fields(self):
        """Test optional metadata fields."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test optional fields",
            parser_class="module.Class",
            supported_formats=[".json"],
            author="John Doe",
            homepage="https://github.com/johndoe/parser",
            license="MIT",
            requires_python=">=3.11",
            dependencies=["requests>=2.28.0", "pydantic>=2.0"],
        )

        assert metadata.author == "John Doe"
        assert metadata.homepage == "https://github.com/johndoe/parser"
        assert metadata.license == "MIT"
        assert metadata.requires_python == ">=3.11"
        assert len(metadata.dependencies) == 2


class TestPluginManifest:
    """Test PluginManifest functionality."""

    def test_manifest_properties(self):
        """Test convenience properties."""
        metadata = PluginMetadata(
            name="cursor",
            version="1.0.0",
            description="Cursor parser",
            parser_class="cursor.Parser",
            supported_formats=[".db"],
        )

        manifest = PluginManifest(metadata=metadata, plugin_dir=Path("/path/to/plugin"))

        assert manifest.name == "cursor"
        assert manifest.version == "1.0.0"

    def test_is_directory_plugin(self):
        """Test directory plugin detection."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test parser",
            parser_class="test.Parser",
            supported_formats=[".json"],
        )

        # Directory plugin
        manifest_dir = PluginManifest(
            metadata=metadata, plugin_dir=Path("/path/to/plugin")
        )
        assert manifest_dir.is_directory_plugin()
        assert not manifest_dir.is_entry_point_plugin()

        # Entry point plugin
        manifest_ep = PluginManifest(metadata=metadata, entry_point="test")
        assert manifest_ep.is_entry_point_plugin()
        assert not manifest_ep.is_directory_plugin()

    def test_from_file(self, tmp_path):
        """Test loading manifest from JSON file."""
        # Create manifest file
        manifest_data = {
            "name": "cursor-parser",
            "version": "1.0.0",
            "description": "Parser for Cursor IDE conversation logs",
            "parser_class": "cursor_parser.parser.CursorParser",
            "supported_formats": [".db", ".sqlite"],
            "author": "John Doe",
        }

        manifest_path = tmp_path / "catsyphon.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        # Load manifest
        manifest = PluginManifest.from_file(manifest_path, tmp_path)

        assert manifest.name == "cursor-parser"
        assert manifest.version == "1.0.0"
        assert manifest.plugin_dir == tmp_path
        assert manifest.is_directory_plugin()
        assert manifest.metadata.author == "John Doe"

    def test_from_file_not_found(self, tmp_path):
        """Test error handling for missing manifest file."""
        manifest_path = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError, match="Manifest file not found"):
            PluginManifest.from_file(manifest_path, tmp_path)

    def test_from_file_invalid_json(self, tmp_path):
        """Test error handling for invalid JSON."""
        manifest_path = tmp_path / "invalid.json"
        with open(manifest_path, "w") as f:
            f.write("{ invalid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            PluginManifest.from_file(manifest_path, tmp_path)

    def test_from_file_validation_error(self, tmp_path):
        """Test error handling for validation errors."""
        # Create invalid manifest (missing required fields)
        manifest_data = {
            "name": "test",
            "version": "1.0.0",
            # Missing description, parser_class, supported_formats
        }

        manifest_path = tmp_path / "invalid.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        with pytest.raises(ValueError, match="Failed to parse manifest"):
            PluginManifest.from_file(manifest_path, tmp_path)

    def test_from_entry_point(self):
        """Test creating manifest from entry point."""
        metadata = PluginMetadata(
            name="cursor",
            version="1.0.0",
            description="Cursor parser",
            parser_class="cursor.Parser",
            supported_formats=[".db"],
        )

        manifest = PluginManifest.from_entry_point("cursor-parser", metadata)

        assert manifest.name == "cursor"
        assert manifest.version == "1.0.0"
        assert manifest.entry_point == "cursor-parser"
        assert manifest.is_entry_point_plugin()
        assert not manifest.is_directory_plugin()
