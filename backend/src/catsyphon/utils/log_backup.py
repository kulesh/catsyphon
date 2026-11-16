"""Log file backup utilities.

Copies source log files to a backup directory before processing,
guarding against Claude Code's cleanupPeriodDays and auto-update
file deletions.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_log_file(
    file_path: Path,
    watch_directory: Path,
    backup_dir: Path,
) -> Path | None:
    """Copy a log file to the backup directory, mirroring source structure.

    Args:
        file_path: Absolute path to the log file.
        watch_directory: The watched root directory.
        backup_dir: Root of the backup tree.

    Returns:
        The backup path on success, None on failure.
    """
    try:
        relative = file_path.relative_to(watch_directory.resolve())
    except ValueError:
        relative = Path(file_path.name)

    dest = backup_dir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(str(file_path), str(dest))
        logger.debug("Backed up %s → %s", file_path.name, dest)
        return dest
    except Exception as e:
        logger.warning("Failed to backup %s: %s", file_path.name, e)
        return None
