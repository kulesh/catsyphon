"""
Plugin discovery and loading system.

Provides hybrid plugin discovery from both:
1. Entry points (setuptools-based packages)
2. Local directories (~/.catsyphon/plugins/, .catsyphon/parsers/)

Entry points take precedence when multiple plugins have the same name.
"""

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from catsyphon.parsers.base import ConversationParser
from catsyphon.plugins.manifest import PluginManifest, PluginMetadata

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""

    pass


class PluginLoader:
    """
    Discovers and loads parser plugins from multiple sources.

    The loader supports two discovery mechanisms:
    1. Entry points: Plugins installed as Python packages
    2. Directory scanning: Plugins in local directories

    Entry points take precedence when both sources provide the same plugin name.
    """

    # Entry point group name for CatSyphon parsers
    ENTRY_POINT_GROUP = "catsyphon.parsers"

    # Default plugin directories to scan
    DEFAULT_PLUGIN_DIRS = [
        Path.home() / ".catsyphon" / "plugins",
        Path(".catsyphon") / "parsers",
    ]

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        enable_entry_points: bool = True,
        enable_directories: bool = True,
    ) -> None:
        """
        Initialize the plugin loader.

        Args:
            plugin_dirs: Additional directories to scan for plugins
                        (combined with DEFAULT_PLUGIN_DIRS)
            enable_entry_points: Whether to discover entry point plugins
            enable_directories: Whether to discover directory plugins
        """
        self.enable_entry_points = enable_entry_points
        self.enable_directories = enable_directories

        # Combine default dirs with user-provided dirs
        self.plugin_dirs: List[Path] = list(self.DEFAULT_PLUGIN_DIRS)
        if plugin_dirs:
            self.plugin_dirs.extend(plugin_dirs)

        # Cache of discovered manifests (name -> manifest)
        self._manifests: Dict[str, PluginManifest] = {}

        # Cache of loaded parser instances (name -> parser)
        self._parsers: Dict[str, ConversationParser] = {}

    def discover_plugins(self) -> List[PluginManifest]:
        """
        Discover all available plugins from entry points and directories.

        Returns:
            List of discovered plugin manifests

        Note:
            Results are cached. Call this method again to refresh discovery.
        """
        self._manifests.clear()

        # Discover from entry points (if enabled)
        if self.enable_entry_points:
            self._discover_entry_points()

        # Discover from directories (if enabled)
        if self.enable_directories:
            self._discover_directories()

        logger.info(f"Discovered {len(self._manifests)} plugin(s)")
        return list(self._manifests.values())

    def _discover_entry_points(self) -> None:
        """
        Discover plugins from setuptools entry points.

        Entry points are declared in pyproject.toml like:
        [project.entry-points."catsyphon.parsers"]
        cursor = "catsyphon_cursor:get_metadata"
        """
        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points

                # Python 3.10+ API
                eps = entry_points(group=self.ENTRY_POINT_GROUP)
            else:
                from importlib.metadata import entry_points

                # Python 3.9 compatibility
                eps = entry_points().get(self.ENTRY_POINT_GROUP, [])

            for ep in eps:
                try:
                    # Load the entry point (should return PluginMetadata)
                    metadata_fn = ep.load()
                    metadata = metadata_fn()

                    if not isinstance(metadata, PluginMetadata):
                        logger.warning(
                            f"Entry point {ep.name} returned invalid type: "
                            f"{type(metadata).__name__} (expected PluginMetadata)"
                        )
                        continue

                    # Create manifest from entry point
                    manifest = PluginManifest.from_entry_point(ep.name, metadata)

                    # Store manifest (entry points take precedence)
                    self._manifests[metadata.name] = manifest

                    logger.debug(
                        f"Discovered entry point plugin: {metadata.name} v{metadata.version}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to load entry point {ep.name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Entry point discovery failed: {e}")

    def _discover_directories(self) -> None:
        """
        Discover plugins from local directories.

        Each plugin directory should contain:
        - catsyphon.json (manifest)
        - Python module with parser implementation
        """
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                logger.debug(f"Plugin directory does not exist: {plugin_dir}")
                continue

            if not plugin_dir.is_dir():
                logger.warning(f"Plugin path is not a directory: {plugin_dir}")
                continue

            # Scan for plugin subdirectories
            for subdir in plugin_dir.iterdir():
                if not subdir.is_dir():
                    continue

                manifest_path = subdir / "catsyphon.json"
                if not manifest_path.exists():
                    # Not a plugin directory
                    continue

                try:
                    # Load manifest from file
                    manifest = PluginManifest.from_file(manifest_path, subdir)

                    # Only add if not already discovered via entry point
                    if manifest.name not in self._manifests:
                        self._manifests[manifest.name] = manifest
                        logger.debug(
                            f"Discovered directory plugin: {manifest.name} "
                            f"v{manifest.version} at {subdir}"
                        )
                    else:
                        logger.debug(
                            f"Skipping directory plugin {manifest.name} "
                            f"(entry point takes precedence)"
                        )

                except Exception as e:
                    logger.warning(f"Failed to load manifest from {manifest_path}: {e}")
                    continue

    def load_plugin(self, name: str) -> ConversationParser:
        """
        Load a specific plugin by name.

        Args:
            name: Plugin name to load

        Returns:
            Parser instance

        Raises:
            PluginLoadError: If plugin not found or fails to load

        Note:
            Results are cached. Calling this method multiple times with the
            same name returns the same instance.
        """
        # Check cache
        if name in self._parsers:
            return self._parsers[name]

        # Find manifest
        if name not in self._manifests:
            raise PluginLoadError(
                f"Plugin '{name}' not found. Call discover_plugins() first."
            )

        manifest = self._manifests[name]

        try:
            # Load parser class
            parser = self._load_parser_class(manifest)

            # Cache and return
            self._parsers[name] = parser
            logger.info(f"Loaded plugin: {name} v{manifest.version}")
            return parser

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin '{name}': {e}") from e

    def _load_parser_class(self, manifest: PluginManifest) -> ConversationParser:
        """
        Load the parser class from a manifest.

        Args:
            manifest: Plugin manifest

        Returns:
            Instantiated parser

        Raises:
            PluginLoadError: If class cannot be loaded or instantiated
        """
        class_path = manifest.metadata.parser_class
        module_name, class_name = class_path.rsplit(".", 1)

        # Handle directory-based plugins
        if manifest.is_directory_plugin():
            assert manifest.plugin_dir is not None

            # Add plugin directory to sys.path temporarily
            plugin_dir_str = str(manifest.plugin_dir)
            if plugin_dir_str not in sys.path:
                sys.path.insert(0, plugin_dir_str)

            try:
                # Import module
                module = importlib.import_module(module_name)

                # Get parser class
                if not hasattr(module, class_name):
                    raise PluginLoadError(
                        f"Module {module_name} has no class {class_name}"
                    )

                parser_class = getattr(module, class_name)

                # Instantiate parser
                parser = parser_class()

                # Verify it implements ConversationParser protocol
                if not hasattr(parser, "can_parse") or not hasattr(parser, "parse"):
                    raise PluginLoadError(
                        f"{class_path} does not implement ConversationParser protocol"
                    )

                return parser

            except Exception as e:
                raise PluginLoadError(f"Failed to load {class_path}: {e}") from e

        # Handle entry point plugins
        else:
            try:
                # Import module (should be installed via pip)
                module = importlib.import_module(module_name)

                # Get parser class
                if not hasattr(module, class_name):
                    raise PluginLoadError(
                        f"Module {module_name} has no class {class_name}"
                    )

                parser_class = getattr(module, class_name)

                # Instantiate parser
                parser = parser_class()

                # Verify it implements ConversationParser protocol
                if not hasattr(parser, "can_parse") or not hasattr(parser, "parse"):
                    raise PluginLoadError(
                        f"{class_path} does not implement ConversationParser protocol"
                    )

                return parser

            except Exception as e:
                raise PluginLoadError(f"Failed to load {class_path}: {e}") from e

    def load_all_plugins(self) -> List[ConversationParser]:
        """
        Load all discovered plugins.

        Returns:
            List of loaded parser instances

        Note:
            Plugins that fail to load are logged but not included in results.
        """
        parsers = []

        for name in self._manifests.keys():
            try:
                parser = self.load_plugin(name)
                parsers.append(parser)
            except PluginLoadError as e:
                logger.error(f"Failed to load plugin {name}: {e}")
                continue

        return parsers

    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """
        Get the manifest for a specific plugin.

        Args:
            name: Plugin name

        Returns:
            Plugin manifest or None if not found
        """
        return self._manifests.get(name)

    def list_plugins(self) -> List[str]:
        """
        Get names of all discovered plugins.

        Returns:
            List of plugin names
        """
        return list(self._manifests.keys())

    @property
    def plugin_count(self) -> int:
        """Get count of discovered plugins."""
        return len(self._manifests)
