from __future__ import annotations

import shutil

from scc_cli import config, contexts
from scc_cli.stores.exception_store import UserStore

from .health_checks import _get_size
from .types import ResetResult, RiskTier


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

    result.bytes_freed = _get_size(cache_dir)

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

    try:
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        result.message = f"Cleared {file_count} cache files"
    except OSError as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to clear cache: {exc}"

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

    try:
        exception_file = user_store.read()
        expired_count = sum(1 for exception in exception_file.exceptions if exception.is_expired())
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
        user_store.prune_expired()
        result.message = f"Removed {result.removed_count} expired exceptions"
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to cleanup: {exc}"

    return result


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
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to clear contexts: {exc}"

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
        from scc_cli import docker

        all_containers = docker._list_all_sandbox_containers()
        stopped = [
            container for container in all_containers if container.status.lower() != "running"
        ]
        result.removed_count = len(stopped)

        if result.removed_count == 0:
            result.message = "No stopped containers to prune"
            return result

        if dry_run:
            result.message = f"Would remove {result.removed_count} stopped containers"
            return result

        for container in stopped:
            container_id = container.id or container.name
            if container_id:
                try:
                    docker.remove_container(container_id)
                except Exception:
                    pass

        result.message = f"Removed {result.removed_count} stopped containers"

    except ImportError:
        result.message = "Docker not available"
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to prune containers: {exc}"

    return result
