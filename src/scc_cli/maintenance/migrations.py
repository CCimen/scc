from __future__ import annotations

from pathlib import Path
from typing import Literal

from scc_cli import config
from scc_cli.stores.exception_store import RepoStore, UserStore

from .backups import _create_backup
from .cache_cleanup import clear_cache, clear_contexts, prune_containers
from .repair_sessions import delete_all_sessions
from .types import ResetResult, RiskTier


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

    stores_to_reset: list[tuple[str, UserStore | RepoStore]] = []
    if scope in ("all", "user"):
        stores_to_reset.append(("user", user_store))
    if scope in ("all", "repo") and repo_store:
        stores_to_reset.append(("repo", repo_store))

    for _store_name, store in stores_to_reset:
        result.paths.append(store.path)
        if store.path.exists():
            result.removed_count += len(store.read().exceptions)
            result.bytes_freed += store.path.stat().st_size if store.path.exists() else 0

    if result.removed_count == 0:
        result.message = "No exceptions to reset"
        return result

    if dry_run:
        result.message = f"Would reset {result.removed_count} exceptions"
        return result

    if create_backup:
        for _store_name, store in stores_to_reset:
            if store.path.exists():
                backup = _create_backup(store.path)
                if backup and result.backup_path is None:
                    result.backup_path = backup

    try:
        for _store_name, store in stores_to_reset:
            store.reset()
        result.message = f"Reset {result.removed_count} exceptions"
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to reset exceptions: {exc}"

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

    result.bytes_freed = config.CONFIG_FILE.stat().st_size

    if dry_run:
        result.message = "Would reset configuration"
        return result

    if create_backup:
        result.backup_path = _create_backup(config.CONFIG_FILE)

    try:
        config.CONFIG_FILE.unlink()
        result.message = "Configuration reset"
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to reset config: {exc}"

    return result


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
                break
        except Exception as exc:
            results.append(
                ResetResult(
                    success=False,
                    action_id=op_name,
                    risk_tier=RiskTier.FACTORY_RESET,
                    error=str(exc),
                    message=f"Failed: {exc}",
                )
            )
            if not continue_on_error:
                break

    return results
