"""Background worker for scanning supplemental data sources."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from catsyphon.db.connection import db_session
from catsyphon.models.db import Workspace

logger = logging.getLogger(__name__)


class ArtifactScanner:
    """Single-threaded background scanner for non-conversation data sources.

    Follows the same lifecycle pattern as ``TaggingWorker``.
    """

    def __init__(self, scan_interval: float = 300.0, data_dirs: Optional[list[str]] = None):
        self.scan_interval = scan_interval
        self.data_dirs = data_dirs or ["/data/claude", "/data/codex"]
        self._stop_event = threading.Event()
        self._running = False
        self.scan_count = 0
        self.last_scan_at: Optional[float] = None
        self.sources_scanned = 0
        self.sources_with_errors = 0

    @property
    def running(self) -> bool:
        return self._running

    def run(self) -> None:
        """Main loop — scan all sources, sleep, repeat."""
        self._running = True
        logger.info(
            "Artifact scanner started (interval=%ds, data_dirs=%s)",
            self.scan_interval,
            self.data_dirs,
        )
        while not self._stop_event.is_set():
            self._run_all_scanners()
            self._stop_event.wait(timeout=self.scan_interval)
        self._running = False
        logger.info("Artifact scanner stopped")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()

    def trigger_scan(self) -> None:
        """Wake the scanner immediately (used by POST /artifacts/scan)."""
        self._stop_event.set()  # breaks current wait
        # Reset so the loop continues
        self._stop_event = threading.Event()

    def _run_all_scanners(self) -> None:
        from catsyphon.scanner.sources import SCANNER_REGISTRY

        scanned = 0
        errors = 0

        try:
            with db_session() as session:
                workspaces = (
                    session.query(Workspace)
                    .filter(Workspace.is_active.is_(True))
                    .all()
                )

                for ws in workspaces:
                    for scanner_fn in SCANNER_REGISTRY:
                        try:
                            scanner_fn(session, ws.id, self.data_dirs)
                            scanned += 1
                        except Exception:
                            errors += 1
                            logger.warning(
                                "Scanner %s failed for workspace %s",
                                scanner_fn.__name__,
                                ws.id,
                                exc_info=True,
                            )
                session.commit()
        except Exception:
            logger.error("Artifact scanner cycle failed", exc_info=True)

        self.scan_count += 1
        self.last_scan_at = time.time()
        self.sources_scanned = scanned
        self.sources_with_errors = errors

        if scanned > 0:
            logger.info(
                "Artifact scan #%d complete: %d sources scanned, %d errors",
                self.scan_count,
                scanned,
                errors,
            )


# ── Module-level singleton (mirrors tagging worker pattern) ─────────

_scanner: Optional[ArtifactScanner] = None
_thread: Optional[threading.Thread] = None


def start_scanner(
    scan_interval: Optional[float] = None,
    data_dirs: Optional[list[str]] = None,
) -> None:
    global _scanner, _thread
    if _thread is not None and _thread.is_alive():
        logger.warning("Artifact scanner already running")
        return

    from catsyphon.config import settings

    interval = scan_interval or getattr(settings, "scanner_interval_seconds", 300)
    dirs = data_dirs or getattr(settings, "scanner_data_dirs", "/data/claude,/data/codex").split(",")

    _scanner = ArtifactScanner(scan_interval=float(interval), data_dirs=dirs)
    _thread = threading.Thread(target=_scanner.run, name="artifact-scanner", daemon=True)
    _thread.start()


def stop_scanner(timeout: float = 10.0) -> None:
    global _scanner, _thread
    if _scanner is not None:
        _scanner.stop(timeout=timeout)
    if _thread is not None:
        _thread.join(timeout=timeout)
    _scanner = None
    _thread = None


def get_scanner_stats() -> dict:
    if _scanner is None:
        return {"scanner_running": False}
    return {
        "scanner_running": _scanner.running,
        "last_scan_at": _scanner.last_scan_at,
        "scan_count": _scanner.scan_count,
        "sources_scanned": _scanner.sources_scanned,
        "sources_with_errors": _scanner.sources_with_errors,
    }


def get_scanner() -> Optional[ArtifactScanner]:
    return _scanner
