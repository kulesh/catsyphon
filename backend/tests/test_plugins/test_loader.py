"""Tests for plugin discovery and loading."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from catsyphon.parsers.metadata import ParserCapability, ParserMetadata
from catsyphon.plugins.loader import PluginLoadError, PluginLoader
from catsyphon.plugins.manifest import PluginManifest, PluginMetadata as PluginMetadataSchema


class DummyParser:
    """Dummy parser for testing."""

    def __init__(self):
        self._metadata = ParserMetadata(
            name="dummy",
            version="1.0.0",
            supported_formats=[".test"],
            capabilities={ParserCapability.BATCH},
            priority=50,
            description="Dummy parser for testing",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path):
        return str(file_path).endswith(".test")

    def parse(self, file_path):
        return MagicMock()


@pytest.fixture
def plugin_dir(tmp_path):
    """Create a temporary plugin directory with test plugins."""
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()

    # Create first test plugin
    plugin1 = plugins_root / "test-parser-1"
    plugin1.mkdir()

    manifest1 = {
        "name": "test-parser-1",
        "version": "1.0.0",
        "description": "First test parser for unit testing",
        "parser_class": "test_parser_1.DummyParser",
        "supported_formats": [".test1"],
    }

    with open(plugin1 / "catsyphon.json", "w") as f:
        json.dump(manifest1, f)

    # Create parser module
    parser_code = '''
class DummyParser:
    def __init__(self):
        from catsyphon.parsers.metadata import ParserMetadata, ParserCapability
        self._metadata = ParserMetadata(
            name="test-parser-1",
            version="1.0.0",
            supported_formats=[".test1"],
            capabilities={ParserCapability.BATCH},
            priority=50,
            description="First test parser",
        )

    @property
    def metadata(self):
        return self._metadata

    def can_parse(self, file_path):
        return str(file_path).endswith(".test1")

    def parse(self, file_path):
        from unittest.mock import MagicMock
        return MagicMock()
'''

    with open(plugin1 / "test_parser_1.py", "w") as f:
        f.write(parser_code)

    # Create second test plugin
    plugin2 = plugins_root / "test-parser-2"
    plugin2.mkdir()

    manifest2 = {
        "name": "test-parser-2",
        "version": "2.0.0",
        "description": "Second test parser for unit testing",
        "parser_class": "test_parser_2.DummyParser",
        "supported_formats": [".test2"],
    }

    with open(plugin2 / "catsyphon.json", "w") as f:
        json.dump(manifest2, f)

    parser_code_2 = parser_code.replace("test-parser-1", "test-parser-2").replace(
        ".test1", ".test2"
    )

    with open(plugin2 / "test_parser_2.py", "w") as f:
        f.write(parser_code_2)

    # Create plugin without manifest (should be ignored)
    plugin_no_manifest = plugins_root / "no-manifest"
    plugin_no_manifest.mkdir()

    return plugins_root


class TestPluginLoader:
    """Test PluginLoader functionality."""

    def test_init_default(self):
        """Test default initialization."""
        loader = PluginLoader()

        assert loader.enable_entry_points is True
        assert loader.enable_directories is True
        assert len(loader.plugin_dirs) == 2  # Default dirs
        assert loader.plugin_count == 0  # Not discovered yet

    def test_init_custom_dirs(self, tmp_path):
        """Test initialization with custom directories."""
        custom_dir = tmp_path / "custom"
        loader = PluginLoader(plugin_dirs=[custom_dir])

        # Should include both default + custom dirs
        assert len(loader.plugin_dirs) > 2
        assert custom_dir in loader.plugin_dirs

    def test_init_disabled_discovery(self):
        """Test disabling discovery methods."""
        loader = PluginLoader(
            enable_entry_points=False,
            enable_directories=False,
        )

        assert loader.enable_entry_points is False
        assert loader.enable_directories is False

    def test_discover_directories(self, plugin_dir):
        """Test discovering plugins from directories."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,  # Only test directory discovery
        )

        manifests = loader.discover_plugins()

        assert len(manifests) == 2
        assert loader.plugin_count == 2

        # Check plugin names
        names = [m.name for m in manifests]
        assert "test-parser-1" in names
        assert "test-parser-2" in names

        # Verify manifests are directory-based
        for manifest in manifests:
            assert manifest.is_directory_plugin()
            assert not manifest.is_entry_point_plugin()

    def test_discover_ignores_non_plugins(self, plugin_dir):
        """Test that discovery ignores directories without manifests."""
        # plugin_dir has a "no-manifest" directory without catsyphon.json
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        manifests = loader.discover_plugins()

        # Should only find the 2 valid plugins
        assert len(manifests) == 2

    def test_discover_invalid_manifest(self, tmp_path):
        """Test handling of invalid manifest files."""
        plugins_root = tmp_path / "plugins"
        plugins_root.mkdir()

        # Create plugin with invalid JSON
        plugin = plugins_root / "invalid"
        plugin.mkdir()

        with open(plugin / "catsyphon.json", "w") as f:
            f.write("{ invalid json")

        loader = PluginLoader(
            plugin_dirs=[plugins_root],
            enable_entry_points=False,
        )

        # Should not raise, just skip invalid plugin
        manifests = loader.discover_plugins()
        assert len(manifests) == 0

    def test_list_plugins(self, plugin_dir):
        """Test listing discovered plugin names."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        loader.discover_plugins()

        names = loader.list_plugins()
        assert len(names) == 2
        assert "test-parser-1" in names
        assert "test-parser-2" in names

    def test_get_manifest(self, plugin_dir):
        """Test retrieving specific plugin manifest."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        loader.discover_plugins()

        manifest = loader.get_manifest("test-parser-1")
        assert manifest is not None
        assert manifest.name == "test-parser-1"
        assert manifest.version == "1.0.0"

        # Non-existent plugin
        assert loader.get_manifest("non-existent") is None

    def test_load_plugin(self, plugin_dir):
        """Test loading a specific plugin."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        loader.discover_plugins()

        # Load plugin
        parser = loader.load_plugin("test-parser-1")

        assert parser is not None
        assert hasattr(parser, "can_parse")
        assert hasattr(parser, "parse")
        assert hasattr(parser, "metadata")

    def test_load_plugin_caching(self, plugin_dir):
        """Test that loading the same plugin returns cached instance."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        loader.discover_plugins()

        # Load twice
        parser1 = loader.load_plugin("test-parser-1")
        parser2 = loader.load_plugin("test-parser-1")

        # Should be same instance
        assert parser1 is parser2

    def test_load_plugin_not_discovered(self):
        """Test loading plugin without discovery raises error."""
        loader = PluginLoader(enable_directories=False, enable_entry_points=False)

        with pytest.raises(PluginLoadError, match="not found"):
            loader.load_plugin("non-existent")

    def test_load_all_plugins(self, plugin_dir):
        """Test loading all discovered plugins."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        loader.discover_plugins()

        parsers = loader.load_all_plugins()

        assert len(parsers) == 2

    def test_discover_entry_points(self):
        """Test discovering plugins from entry points."""
        # Mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "test-entry-point"

        # Mock metadata function
        def get_metadata():
            return PluginMetadataSchema(
                name="test-ep-parser",
                version="1.0.0",
                description="Entry point parser for testing",
                parser_class="test_ep.Parser",
                supported_formats=[".ep"],
            )

        mock_ep.load.return_value = get_metadata

        # Python 3.10+ returns SelectableGroups, 3.9 returns dict
        with patch("importlib.metadata.entry_points") as mock_entry_points:
            # Return list directly for Python 3.10+ API (group parameter)
            mock_entry_points.return_value = [mock_ep]

            loader = PluginLoader(enable_directories=False)
            manifests = loader.discover_plugins()

            assert len(manifests) == 1
            assert manifests[0].name == "test-ep-parser"
            assert manifests[0].is_entry_point_plugin()

    def test_entry_point_precedence(self, plugin_dir):
        """Test that entry points take precedence over directory plugins."""
        # Create directory plugin
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
        )

        # Mock entry point with same name as directory plugin
        mock_ep = MagicMock()
        mock_ep.name = "test-entry-point"

        def get_metadata():
            return PluginMetadataSchema(
                name="test-parser-1",  # Same name as directory plugin
                version="999.0.0",  # Different version
                description="Entry point takes precedence over directory",
                parser_class="ep.Parser",
                supported_formats=[".ep"],
            )

        mock_ep.load.return_value = get_metadata

        with patch("importlib.metadata.entry_points") as mock_entry_points:
            mock_entry_points.return_value = [mock_ep]

            manifests = loader.discover_plugins()

            # Should have both parsers, but test-parser-1 from entry point
            manifest = loader.get_manifest("test-parser-1")
            assert manifest is not None
            assert manifest.version == "999.0.0"  # Entry point version
            assert manifest.is_entry_point_plugin()

    def test_discover_caches_results(self, plugin_dir):
        """Test that discover_plugins() can be called multiple times."""
        loader = PluginLoader(
            plugin_dirs=[plugin_dir],
            enable_entry_points=False,
        )

        # First discovery
        manifests1 = loader.discover_plugins()
        count1 = loader.plugin_count

        # Second discovery should refresh
        manifests2 = loader.discover_plugins()
        count2 = loader.plugin_count

        assert count1 == count2
        assert len(manifests1) == len(manifests2)

    def test_nonexistent_plugin_dir(self, tmp_path):
        """Test that nonexistent plugin directories are handled gracefully."""
        nonexistent = tmp_path / "does-not-exist"

        loader = PluginLoader(
            plugin_dirs=[nonexistent],
            enable_entry_points=False,
        )

        # Should not raise
        manifests = loader.discover_plugins()
        assert len(manifests) == 0
