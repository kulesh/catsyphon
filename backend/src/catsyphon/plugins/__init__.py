"""
Plugin system for extensible parser support.

This package provides infrastructure for discovering, loading, and managing
parser plugins. Plugins can be distributed as Python packages or placed in
local directories for development.
"""

from catsyphon.plugins.loader import PluginLoader
from catsyphon.plugins.manifest import PluginManifest, PluginMetadata

__all__ = [
    "PluginLoader",
    "PluginManifest",
    "PluginMetadata",
]
