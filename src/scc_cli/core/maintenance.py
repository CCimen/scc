"""
Maintenance operations for SCC CLI.

Pure functions for reset and cleanup operations.
Both CLI (scc reset) and TUI (Settings screen) delegate to this module.

Key principles:
- Pure operations: no UI, no prompts, no console output
- Delegate to existing primitives where possible
- Return ResetResult with counts/bytes/paths for UI to display
- Atomic backups before destructive operations
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from .. import config, contexts, sessions
from ..stores.exception_store import RepoStore, UserStore
from ..utils.locks import file_lock, lock_path

# ═══════════════════════════════════════════════════════════════════════════════
# Risk Tiers
# ═══════════════════════════════════════════════════════════════════════════════


class RiskTier(Enum):
    """Risk level for maintenance operations.

    Tier 0: Safe - no confirmation needed
    Tier 1: Changes State - Y/N confirmation
    Tier 2: Destructive - Y/N + impact list
    Tier 3: Factory Reset - type-to-confirm
    """

    SAFE = 0
    CHANGES_STATE = 1
    DESTRUCTIVE = 2
    FACTORY_RESET = 3


# ═══════════════════════════════════════════════════════════════════════════════
# Result Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PathInfo:
    """Information about a configuration path.

    Attributes:
        name: Human-readable name (e.g., "Config", "Sessions")
        path: Absolute path to file or directory
        exists: Whether the path exists
        size_bytes: Size in bytes (0 if doesn't exist)
        permissions: Permission string ("rw", "r-", "--")
    """

    name: str
    path: Path
    exists: bool
    size_bytes: int
    permissions: str

    @property
    def size_human(self) -> str:
        """Human-readable size (e.g., '2.1 KB')."""
        if self.size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if self.size_bytes < 1024:
                return (
                    f"{self.size_bytes:.1f} {unit}"
                    if self.size_bytes >= 10
                    else f"{self.size_bytes} {unit}"
                )
            self.size_bytes = int(self.size_bytes / 1024)
        return f"{self.size_bytes:.1f} TB"


@dataclass
class ResetResult:
    """Result of a reset operation.

    All UI should render from these values, never hardcode paths.
    """

    success: bool
    action_id: str
    risk_tier: RiskTier
    paths: list[Path] = field(default_factory=list)
    removed_count: int = 0
    bytes_freed: int = 0
    backup_path: Path | None = None
    message: str = ""
    next_steps: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def bytes_freed_human(self) -> str:
        """Human-readable bytes freed."""
        if self.bytes_freed == 0:
            return "0 B"
        size: float = self.bytes_freed
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if size >= 10 else f"{int(size)} {unit}"
            size = size / 1024
        return f"{size:.1f} TB"


@dataclass
class MaintenancePreview:
    """Preview of what a maintenance operation would do.

    Used for --plan flag and [P]review button.
    """

    action_id: str
    risk_tier: RiskTier
    paths: list[Path]
    description: str
    item_count: int = 0
    bytes_estimate: int = 0
    backup_will_be_created: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Maintenance Lock
# ═══════════════════════════════════════════════════════════════════════════════


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
        lf = lock_path("maintenance")

        # Check for stale lock before attempting to acquire
        pid, is_stale = _get_lock_info(lf)

        # If force is set and lock is stale, remove the lock file
        if self._force and is_stale and lf.exists():
            try:
                lf.unlink()
            except OSError:
                pass

        try:
            self._lock_file = file_lock(lf)
            self._lock_file.__enter__()
        except Exception:
            # Re-check stale status for error message
            pid, is_stale = _get_lock_info(lf)

            if is_stale:
                raise MaintenanceLockError(
                    f"Lock file exists from PID {pid} which is no longer running.\n"
                    "The lock appears stale. Use 'scc reset --force-unlock' to recover.",
                    is_stale=True,
                    pid=pid,
                )
            else:
                raise MaintenanceLockError(
                    "Maintenance already running in another process. "
                    "Close other SCC sessions first.",
                    is_stale=False,
                    pid=pid,
                )
        return self

    def __exit__(self, *args: Any) -> None:
        if self._lock_file:
            self._lock_file.__exit__(*args)


# ═══════════════════════════════════════════════════════════════════════════════
# Path Discovery
# ═══════════════════════════════════════════════════════════════════════════════


def _get_size(path: Path) -> int:
    """Get size of file or directory in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    # Directory: sum all files recursively
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _get_permissions(path: Path) -> str:
    """Get permission string for path (rw, r-, --)."""
    if not path.exists():
        return "--"
    try:
        mode = path.stat().st_mode
        readable = bool(mode & stat.S_IRUSR)
        writable = bool(mode & stat.S_IWUSR)
        if readable and writable:
            return "rw"
        elif readable:
            return "r-"
        else:
            return "--"
    except OSError:
        return "--"


def get_paths() -> list[PathInfo]:
    """Get all SCC-related paths with their status.

    Returns XDG-aware paths with exists/size/permissions info.
    """
    paths = []

    # Config file
    paths.append(
        PathInfo(
            name="Config",
            path=config.CONFIG_FILE,
            exists=config.CONFIG_FILE.exists(),
            size_bytes=_get_size(config.CONFIG_FILE),
            permissions=_get_permissions(config.CONFIG_FILE),
        )
    )

    # Sessions file
    paths.append(
        PathInfo(
            name="Sessions",
            path=config.SESSIONS_FILE,
            exists=config.SESSIONS_FILE.exists(),
            size_bytes=_get_size(config.SESSIONS_FILE),
            permissions=_get_permissions(config.SESSIONS_FILE),
        )
    )

    # Exceptions file (user store)
    exceptions_path = config.CONFIG_DIR / "exceptions.json"
    paths.append(
        PathInfo(
            name="Exceptions",
            path=exceptions_path,
            exists=exceptions_path.exists(),
            size_bytes=_get_size(exceptions_path),
            permissions=_get_permissions(exceptions_path),
        )
    )

    # Cache directory
    paths.append(
        PathInfo(
            name="Cache",
            path=config.CACHE_DIR,
            exists=config.CACHE_DIR.exists(),
            size_bytes=_get_size(config.CACHE_DIR),
            permissions=_get_permissions(config.CACHE_DIR),
        )
    )

    # Contexts file (in cache)
    contexts_path = contexts._get_contexts_path()
    paths.append(
        PathInfo(
            name="Contexts",
            path=contexts_path,
            exists=contexts_path.exists(),
            size_bytes=_get_size(contexts_path),
            permissions=_get_permissions(contexts_path),
        )
    )

    return paths


def get_total_size() -> int:
    """Get total size of all SCC paths in bytes."""
    return sum(p.size_bytes for p in get_paths())


# ═══════════════════════════════════════════════════════════════════════════════
# Backup Operations
# ═══════════════════════════════════════════════════════════════════════════════


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
            # Copy content
            shutil.copy2(path, tmp_path)
            # Set restrictive permissions (0600)
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            # Atomic rename
            tmp_path.rename(backup_path)
            return backup_path
        except Exception:
            # Cleanup on failure
            tmp_path.unlink(missing_ok=True)
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# Clear Operations (Tier 0 - Safe)
# ═══════════════════════════════════════════════════════════════════════════════


def clear_cache(dry_run: bool = False) -> ResetResult:
    """Clear regenerable cache files.

    Risk: Tier 0 (Safe) - Files regenerate automatically on next use.
    """
    cache_dir = config.CACHE_DIR
    result = ResetResult(
        success=True,
        action_id="clear_cache",
        risk_tier=RiskTier.SAFE,
        paths=[cache_dir],
        message="Cache cleared",
    )

    if not cache_dir.exists():
        result.message = "No cache to clear"
        return result

    # Calculate size before clearing
    result.bytes_freed = _get_size(cache_dir)

    # Count files
    file_count = 0
    try:
        for item in cache_dir.rglob("*"):
            if item.is_file():
                file_count += 1
    except OSError:
        pass
    result.removed_count = file_count

    if dry_run:
        result.message = f"Would clear {file_count} cache files"
        return result

    # Actually clear
    try:
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        result.message = f"Cleared {file_count} cache files"
    except OSError as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to clear cache: {e}"

    return result


def cleanup_expired_exceptions(dry_run: bool = False) -> ResetResult:
    """Remove only expired exceptions.

    Risk: Tier 0 (Safe) - Only removes already-expired items.
    """
    result = ResetResult(
        success=True,
        action_id="cleanup_expired_exceptions",
        risk_tier=RiskTier.SAFE,
        message="Expired exceptions cleaned up",
    )

    user_store = UserStore()
    result.paths = [user_store.path]

    # Count expired before cleanup
    try:
        exception_file = user_store.read()
        expired_count = sum(1 for e in exception_file.exceptions if e.is_expired())
        result.removed_count = expired_count
    except Exception:
        result.removed_count = 0

    if dry_run:
        result.message = f"Would remove {result.removed_count} expired exceptions"
        return result

    if result.removed_count == 0:
        result.message = "No expired exceptions to clean up"
        return result

    try:
        # prune_expired removes expired exceptions
        user_store.prune_expired()
        result.message = f"Removed {result.removed_count} expired exceptions"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to cleanup: {e}"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Clear Operations (Tier 1 - Changes State)
# ═══════════════════════════════════════════════════════════════════════════════


def clear_contexts(dry_run: bool = False) -> ResetResult:
    """Clear recent work contexts.

    Risk: Tier 1 (Changes State) - Clears Quick Resume list.
    """
    result = ResetResult(
        success=True,
        action_id="clear_contexts",
        risk_tier=RiskTier.CHANGES_STATE,
        message="Contexts cleared",
        next_steps=["Your Quick Resume list is now empty. New contexts will appear as you work."],
    )

    contexts_path = contexts._get_contexts_path()
    result.paths = [contexts_path]

    # Get current count
    current_contexts = contexts.load_recent_contexts()
    result.removed_count = len(current_contexts)

    if result.removed_count == 0:
        result.message = "No contexts to clear"
        return result

    if dry_run:
        result.message = f"Would clear {result.removed_count} contexts"
        return result

    try:
        result.bytes_freed = _get_size(contexts_path)
        cleared = contexts.clear_contexts()
        result.removed_count = cleared
        result.message = f"Cleared {cleared} contexts"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to clear contexts: {e}"

    return result


def prune_containers(dry_run: bool = False) -> ResetResult:
    """Remove stopped Docker containers.

    Risk: Tier 1 (Changes State) - Only removes stopped containers.

    This delegates to the existing container pruning logic.
    """
    result = ResetResult(
        success=True,
        action_id="prune_containers",
        risk_tier=RiskTier.CHANGES_STATE,
        message="Containers pruned",
    )

    try:
        from .sandbox import docker  # type: ignore[import-untyped]

        # Get stopped containers
        all_containers = docker._list_all_sandbox_containers()
        stopped = [c for c in all_containers if c.get("status", "").lower() != "running"]
        result.removed_count = len(stopped)

        if result.removed_count == 0:
            result.message = "No stopped containers to prune"
            return result

        if dry_run:
            result.message = f"Would remove {result.removed_count} stopped containers"
            return result

        # Actually prune
        for container in stopped:
            container_id = container.get("id") or container.get("name")
            if container_id:
                try:
                    docker._remove_container(container_id)
                except Exception:
                    pass

        result.message = f"Removed {result.removed_count} stopped containers"

    except ImportError:
        result.message = "Docker not available"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to prune containers: {e}"

    return result


def prune_sessions(
    older_than_days: int = 30,
    keep_n: int = 20,
    team: str | None = None,
    dry_run: bool = False,
) -> ResetResult:
    """Prune old sessions while keeping recent ones.

    Risk: Tier 1 (Changes State) - Safe prune with defaults.

    Args:
        older_than_days: Remove sessions older than this (default: 30)
        keep_n: Keep at least this many recent sessions per team (default: 20)
        team: Only prune sessions for this team (None = all)
        dry_run: Preview only, don't actually delete
    """
    result = ResetResult(
        success=True,
        action_id="prune_sessions",
        risk_tier=RiskTier.CHANGES_STATE,
        paths=[config.SESSIONS_FILE],
        message=f"Pruned sessions older than {older_than_days}d (kept newest {keep_n} per team)",
    )

    try:
        from ..utils.locks import file_lock, lock_path

        lock_file = lock_path("sessions")
        with file_lock(lock_file):
            all_sessions = sessions._load_sessions()
            original_count = len(all_sessions)

            if original_count == 0:
                result.message = "No sessions to prune"
                return result

            # Calculate cutoff date
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

            # Group sessions by team
            by_team: dict[str | None, list[dict[str, Any]]] = {}
            for s in all_sessions:
                t = s.get("team")
                if team is not None and t != team:
                    # Keep sessions from other teams
                    by_team.setdefault(t, []).append(s)
                else:
                    by_team.setdefault(t, []).append(s)

            # For each team, keep newest keep_n, prune rest if older than cutoff
            kept_sessions = []
            for t, team_sessions in by_team.items():
                # Sort by last_used descending
                team_sessions.sort(key=lambda s: s.get("last_used", ""), reverse=True)

                # Always keep the newest keep_n
                kept = team_sessions[:keep_n]
                remaining = team_sessions[keep_n:]

                # From remaining, keep only if newer than cutoff
                for s in remaining:
                    last_used = s.get("last_used", "")
                    if last_used:
                        try:
                            dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
                            if dt > cutoff:
                                kept.append(s)
                        except (ValueError, TypeError):
                            pass

                kept_sessions.extend(kept)

            result.removed_count = original_count - len(kept_sessions)

            if result.removed_count == 0:
                result.message = "No sessions to prune"
                return result

            if dry_run:
                result.message = f"Would prune {result.removed_count} sessions older than {older_than_days}d (kept newest {keep_n} per team)"
                return result

            # Calculate bytes freed
            result.bytes_freed = _get_size(config.SESSIONS_FILE)

            # Save filtered sessions
            sessions._save_sessions(kept_sessions)

            # Recalculate bytes freed
            new_size = _get_size(config.SESSIONS_FILE)
            result.bytes_freed = result.bytes_freed - new_size

            result.message = f"Pruned {result.removed_count} sessions older than {older_than_days}d (kept newest {keep_n} per team)"

    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to prune sessions: {e}"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Reset Operations (Tier 2 - Destructive)
# ═══════════════════════════════════════════════════════════════════════════════


def reset_exceptions(
    scope: Literal["all", "user", "repo"] = "all",
    repo_root: Path | None = None,
    dry_run: bool = False,
    create_backup: bool = True,
) -> ResetResult:
    """Reset exception stores.

    Risk: Tier 2 (Destructive) - Removes policy exceptions.

    Args:
        scope: Which stores to reset ("all", "user", "repo")
        repo_root: Repo root for repo-scoped exceptions
        dry_run: Preview only
        create_backup: Create backup before deletion
    """
    result = ResetResult(
        success=True,
        action_id="reset_exceptions",
        risk_tier=RiskTier.DESTRUCTIVE,
        message="Exceptions reset",
    )

    user_store = UserStore()
    repo_store = RepoStore(repo_root) if repo_root else None

    # Determine which stores to reset
    stores_to_reset: list[tuple[str, Any]] = []
    if scope in ("all", "user"):
        stores_to_reset.append(("user", user_store))
    if scope in ("all", "repo") and repo_store:
        stores_to_reset.append(("repo", repo_store))

    for store_name, store in stores_to_reset:
        result.paths.append(store.path)
        if store.path.exists():
            result.removed_count += len(store.load())
            result.bytes_freed += _get_size(store.path)

    if result.removed_count == 0:
        result.message = "No exceptions to reset"
        return result

    if dry_run:
        result.message = f"Would reset {result.removed_count} exceptions"
        return result

    # Create backup if requested
    if create_backup:
        for store_name, store in stores_to_reset:
            if store.path.exists():
                backup = _create_backup(store.path)
                if backup and result.backup_path is None:
                    result.backup_path = backup

    # Reset stores
    try:
        for store_name, store in stores_to_reset:
            store.reset()
        result.message = f"Reset {result.removed_count} exceptions"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to reset exceptions: {e}"

    return result


def delete_all_sessions(
    dry_run: bool = False,
    create_backup: bool = True,
) -> ResetResult:
    """Delete entire sessions store.

    Risk: Tier 2 (Destructive) - Removes all session history.
    """
    result = ResetResult(
        success=True,
        action_id="delete_all_sessions",
        risk_tier=RiskTier.DESTRUCTIVE,
        paths=[config.SESSIONS_FILE],
        message="All sessions deleted",
        next_steps=["Your session history is now empty. New sessions will appear as you work."],
    )

    if not config.SESSIONS_FILE.exists():
        result.message = "No sessions to delete"
        return result

    # Count sessions
    try:
        all_sessions = sessions._load_sessions()
        result.removed_count = len(all_sessions)
    except Exception:
        result.removed_count = 0

    result.bytes_freed = _get_size(config.SESSIONS_FILE)

    if dry_run:
        result.message = f"Would delete {result.removed_count} sessions"
        return result

    # Create backup if requested
    if create_backup:
        result.backup_path = _create_backup(config.SESSIONS_FILE)

    try:
        sessions.clear_history()
        result.message = f"Deleted {result.removed_count} sessions"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to delete sessions: {e}"

    return result


def reset_config(
    dry_run: bool = False,
    create_backup: bool = True,
) -> ResetResult:
    """Reset user configuration to defaults.

    Risk: Tier 2 (Destructive) - Requires running setup again.
    """
    result = ResetResult(
        success=True,
        action_id="reset_config",
        risk_tier=RiskTier.DESTRUCTIVE,
        paths=[config.CONFIG_FILE],
        message="Configuration reset",
        next_steps=["Run 'scc setup' to reconfigure"],
    )

    if not config.CONFIG_FILE.exists():
        result.message = "No configuration to reset"
        return result

    result.bytes_freed = _get_size(config.CONFIG_FILE)

    if dry_run:
        result.message = "Would reset configuration"
        return result

    # Create backup if requested
    if create_backup:
        result.backup_path = _create_backup(config.CONFIG_FILE)

    try:
        config.CONFIG_FILE.unlink()
        result.message = "Configuration reset"
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.message = f"Failed to reset config: {e}"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Reset (Tier 3)
# ═══════════════════════════════════════════════════════════════════════════════


def factory_reset(
    dry_run: bool = False,
    create_backup: bool = True,
    continue_on_error: bool = False,
) -> list[ResetResult]:
    """Perform factory reset - remove all SCC data.

    Risk: Tier 3 (Factory Reset) - Complete clean slate.

    Order: Local files first (config, sessions, exceptions, contexts, cache),
    containers last. This ensures Docker failures don't block local cleanup.

    Args:
        dry_run: Preview only
        create_backup: Create backups for Tier 2 operations
        continue_on_error: Don't stop on first failure

    Returns:
        List of ResetResult for each operation
    """
    results: list[ResetResult] = []

    # Order: local files first, containers last
    operations = [
        ("reset_config", lambda: reset_config(dry_run=dry_run, create_backup=create_backup)),
        (
            "delete_all_sessions",
            lambda: delete_all_sessions(dry_run=dry_run, create_backup=create_backup),
        ),
        (
            "reset_exceptions",
            lambda: reset_exceptions(dry_run=dry_run, create_backup=create_backup),
        ),
        ("clear_contexts", lambda: clear_contexts(dry_run=dry_run)),
        ("clear_cache", lambda: clear_cache(dry_run=dry_run)),
        ("prune_containers", lambda: prune_containers(dry_run=dry_run)),
    ]

    for op_name, op_func in operations:
        try:
            result = op_func()
            results.append(result)

            if not result.success and not continue_on_error:
                # Stop on first failure
                break

        except Exception as e:
            results.append(
                ResetResult(
                    success=False,
                    action_id=op_name,
                    risk_tier=RiskTier.FACTORY_RESET,
                    error=str(e),
                    message=f"Failed: {e}",
                )
            )
            if not continue_on_error:
                break

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Preview / Plan Operations
# ═══════════════════════════════════════════════════════════════════════════════


def preview_operation(action_id: str, **kwargs: Any) -> MaintenancePreview:
    """Get preview of what an operation would do.

    Used for --plan flag and [P]review button.
    Fast, compute-only, no side effects.
    """
    action_map = {
        "clear_cache": (RiskTier.SAFE, "Clear regenerable cache files"),
        "cleanup_expired_exceptions": (RiskTier.SAFE, "Remove only expired exceptions"),
        "clear_contexts": (RiskTier.CHANGES_STATE, "Clear recent work contexts"),
        "prune_containers": (RiskTier.CHANGES_STATE, "Remove stopped Docker containers"),
        "prune_sessions": (RiskTier.CHANGES_STATE, "Prune old sessions (keeps recent)"),
        "reset_exceptions": (RiskTier.DESTRUCTIVE, "Clear all policy exceptions"),
        "delete_all_sessions": (RiskTier.DESTRUCTIVE, "Delete entire session history"),
        "reset_config": (RiskTier.DESTRUCTIVE, "Reset configuration (requires setup)"),
        "factory_reset": (RiskTier.FACTORY_RESET, "Remove all SCC data"),
    }

    if action_id not in action_map:
        raise ValueError(f"Unknown action: {action_id}")

    risk_tier, description = action_map[action_id]

    # Get paths affected
    paths: list[Path] = []
    item_count = 0
    bytes_estimate = 0

    if action_id == "clear_cache":
        paths = [config.CACHE_DIR]
        bytes_estimate = _get_size(config.CACHE_DIR)
    elif action_id == "clear_contexts":
        ctx_path = contexts._get_contexts_path()
        paths = [ctx_path]
        item_count = len(contexts.load_recent_contexts())
        bytes_estimate = _get_size(ctx_path)
    elif action_id == "prune_sessions" or action_id == "delete_all_sessions":
        paths = [config.SESSIONS_FILE]
        try:
            item_count = len(sessions._load_sessions())
        except Exception:
            item_count = 0
        bytes_estimate = _get_size(config.SESSIONS_FILE)
    elif action_id == "reset_config":
        paths = [config.CONFIG_FILE]
        bytes_estimate = _get_size(config.CONFIG_FILE)
    elif action_id == "reset_exceptions":
        user_store = UserStore()
        paths = [user_store.path]
        try:
            item_count = len(user_store.read().exceptions)
        except Exception:
            item_count = 0
        bytes_estimate = _get_size(user_store.path)
    elif action_id == "factory_reset":
        paths = [config.CONFIG_DIR, config.CACHE_DIR]
        bytes_estimate = get_total_size()

    backup_will_be_created = risk_tier == RiskTier.DESTRUCTIVE

    return MaintenancePreview(
        action_id=action_id,
        risk_tier=risk_tier,
        paths=paths,
        description=description,
        item_count=item_count,
        bytes_estimate=bytes_estimate,
        backup_will_be_created=backup_will_be_created,
        parameters=kwargs,
    )
