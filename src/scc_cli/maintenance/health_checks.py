from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from scc_cli import config, contexts, sessions
from scc_cli.stores.exception_store import RepoStore, UserStore

from .types import MaintenancePreview, PathInfo, RiskTier


def _get_size(path: Path) -> int:
    """Get size of file or directory in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
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
        if readable:
            return "r-"
        return "--"
    except OSError:
        return "--"


def get_paths() -> list[PathInfo]:
    """Get all SCC-related paths with their status.

    Returns XDG-aware paths with exists/size/permissions info.
    """
    paths: list[PathInfo] = []

    paths.append(
        PathInfo(
            name="Config",
            path=config.CONFIG_FILE,
            exists=config.CONFIG_FILE.exists(),
            size_bytes=_get_size(config.CONFIG_FILE),
            permissions=_get_permissions(config.CONFIG_FILE),
        )
    )

    paths.append(
        PathInfo(
            name="Sessions",
            path=config.SESSIONS_FILE,
            exists=config.SESSIONS_FILE.exists(),
            size_bytes=_get_size(config.SESSIONS_FILE),
            permissions=_get_permissions(config.SESSIONS_FILE),
        )
    )

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

    paths.append(
        PathInfo(
            name="Cache",
            path=config.CACHE_DIR,
            exists=config.CACHE_DIR.exists(),
            size_bytes=_get_size(config.CACHE_DIR),
            permissions=_get_permissions(config.CACHE_DIR),
        )
    )

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
    return sum(path.size_bytes for path in get_paths())


def preview_operation(action_id: str, **kwargs: Any) -> MaintenancePreview:
    """Get preview of what an operation would do.

    Used for --plan flag and [P]review button.
    Fast, compute-only, no side effects.
    """
    from .tasks import get_task

    task = get_task(action_id)
    if task is None:
        raise ValueError(f"Unknown action: {action_id}")

    risk_tier = task.risk_tier
    description = task.description

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
    elif action_id in ("prune_sessions", "delete_all_sessions"):
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
        scope = kwargs.get("scope", "all")
        repo_root = kwargs.get("repo_root")
        repo_root_path = Path(repo_root) if repo_root else None
        stores: list[UserStore | RepoStore] = []
        if scope in ("all", "user"):
            stores.append(UserStore())
        if scope in ("all", "repo") and repo_root_path:
            stores.append(RepoStore(repo_root_path))

        for store in stores:
            paths.append(store.path)
            try:
                item_count += len(store.read().exceptions)
            except Exception:
                pass
            bytes_estimate += _get_size(store.path)
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
