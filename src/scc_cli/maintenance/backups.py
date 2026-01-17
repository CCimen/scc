from __future__ import annotations

import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _create_backup(path: Path) -> Path | None:
    """Create a timestamped backup of a file.

    Backups are created atomically with 0600 permissions.

    Args:
        path: File to backup

    Returns:
        Path to backup file, or None if file doesn't exist
    """
    if not path.exists():
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_suffix(f".bak-{timestamp}{path.suffix}")

    # Atomic copy with temp file
    backup_dir = path.parent
    with tempfile.NamedTemporaryFile(mode="wb", dir=backup_dir, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            shutil.copy2(path, tmp_path)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            tmp_path.rename(backup_path)
            return backup_path
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
