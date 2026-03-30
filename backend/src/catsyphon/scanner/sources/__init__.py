"""Scanner source registry — all artifact scanners."""

from __future__ import annotations

from catsyphon.scanner.sources.agent_metadata import scan_agent_metadata
from catsyphon.scanner.sources.codex_sqlite import scan_codex_sqlite
from catsyphon.scanner.sources.file_history import scan_file_history
from catsyphon.scanner.sources.global_history import scan_global_history
from catsyphon.scanner.sources.plugin_inventory import scan_plugin_inventory
from catsyphon.scanner.sources.project_memory import scan_project_memory
from catsyphon.scanner.sources.settings_config import scan_settings_config
from catsyphon.scanner.sources.shell_snapshots import scan_shell_snapshots
from catsyphon.scanner.sources.standalone_plans import scan_standalone_plans
from catsyphon.scanner.sources.token_analytics import scan_token_analytics

SCANNER_REGISTRY = [
    scan_token_analytics,
    scan_project_memory,
    scan_global_history,
    scan_codex_sqlite,
    scan_standalone_plans,
    scan_settings_config,
    scan_file_history,
    scan_agent_metadata,
    scan_shell_snapshots,
    scan_plugin_inventory,
]
