from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from scc_cli import config
from scc_cli.utils.locks import file_lock, lock_path

LOCK_FILE_NAME = "maintenance.lock"


def _get_lock_path() -> Path:
    """Get path to maintenance lock file."""
    return config.CONFIG_DIR / LOCK_FILE_NAME


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except OSError:
        return False


def _get_lock_info(lock_file: Path) -> tuple[int | None, bool]:
    """Get lock file info: (PID, is_stale).

    Returns:
        Tuple of (PID from lock file, whether the lock appears stale)
    """
    try:
        if not lock_file.exists():
            return None, False
        content = lock_file.read_text().strip()
        if not content:
            return None, False
        pid = int(content)
        is_stale = not _is_process_running(pid)
        return pid, is_stale
    except (ValueError, OSError):
        return None, False


class MaintenanceLockError(Exception):
    """Raised when maintenance is already running in another process."""

    def __init__(self, message: str, is_stale: bool = False, pid: int | None = None):
        super().__init__(message)
        self.is_stale = is_stale
        self.pid = pid


class MaintenanceLock:
    """Context manager for maintenance lock.

    Prevents concurrent maintenance operations from CLI and TUI.
    Detects stale locks from crashed processes.

    Usage:
        with MaintenanceLock():
            # perform maintenance
    """

    def __init__(self, force: bool = False) -> None:
        self._lock_path = _get_lock_path()
        self._lock_file: Any = None
        self._force = force

    def __enter__(self) -> MaintenanceLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Use the existing file_lock utility
        lock_file = lock_path("maintenance")

        # Check for stale lock before attempting to acquire
        pid, is_stale = _get_lock_info(lock_file)

        # If force is set and lock is stale, remove the lock file
        if self._force and is_stale and lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass

        try:
            self._lock_file = file_lock(lock_file)
            self._lock_file.__enter__()
        except Exception:
            # Re-check stale status for error message
            pid, is_stale = _get_lock_info(lock_file)

            if is_stale:
                raise MaintenanceLockError(
                    f"Lock file exists from PID {pid} which is no longer running.\n"
                    "The lock appears stale. Use 'scc reset --force-unlock' to recover.",
                    is_stale=True,
                    pid=pid,
                )
            raise MaintenanceLockError(
                "Maintenance already running in another process. Close other SCC sessions first.",
                is_stale=False,
                pid=pid,
            )
        return self

    def __exit__(self, *args: Any) -> None:
        if self._lock_file:
            self._lock_file.__exit__(*args)
