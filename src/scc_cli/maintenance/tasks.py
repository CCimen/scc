from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from .cache_cleanup import (
    cleanup_expired_exceptions,
    clear_cache,
    clear_contexts,
    prune_containers,
)
from .migrations import factory_reset, reset_config, reset_exceptions
from .repair_sessions import delete_all_sessions, prune_sessions
from .types import MaintenancePreview, ResetResult, RiskTier

MaintenanceTaskResult: TypeAlias = ResetResult | list[ResetResult]
PreconditionResult: TypeAlias = tuple[bool, str | None]
Precondition: TypeAlias = Callable[["MaintenanceTaskContext"], PreconditionResult]


@dataclass(frozen=True)
class MaintenanceTaskContext:
    """Parameters for running maintenance tasks."""

    dry_run: bool = False
    create_backup: bool = True
    continue_on_error: bool = False
    exception_scope: Literal["all", "user", "repo"] = "all"
    repo_root: Path | None = None
    older_than_days: int = 30
    keep_n: int = 20
    team: str | None = None


@dataclass(frozen=True)
class MaintenanceTask:
    """Maintenance task descriptor used for registry lookups."""

    id: str
    label: str
    description: str
    risk_tier: RiskTier
    run: Callable[[MaintenanceTaskContext], MaintenanceTaskResult]
    preview: Callable[[MaintenanceTaskContext], MaintenancePreview] | None = None
    preconditions: tuple[Precondition, ...] = ()


TASKS: tuple[MaintenanceTask, ...] = (
    MaintenanceTask(
        id="clear_cache",
        label="Clear cache",
        description="Clear regenerable cache files",
        risk_tier=RiskTier.SAFE,
        run=lambda ctx: clear_cache(dry_run=ctx.dry_run),
    ),
    MaintenanceTask(
        id="cleanup_expired_exceptions",
        label="Cleanup expired exceptions",
        description="Remove only expired exceptions",
        risk_tier=RiskTier.SAFE,
        run=lambda ctx: cleanup_expired_exceptions(dry_run=ctx.dry_run),
    ),
    MaintenanceTask(
        id="clear_contexts",
        label="Clear contexts",
        description="Clear recent work contexts",
        risk_tier=RiskTier.CHANGES_STATE,
        run=lambda ctx: clear_contexts(dry_run=ctx.dry_run),
    ),
    MaintenanceTask(
        id="prune_containers",
        label="Prune containers",
        description="Remove stopped Docker containers",
        risk_tier=RiskTier.CHANGES_STATE,
        run=lambda ctx: prune_containers(dry_run=ctx.dry_run),
    ),
    MaintenanceTask(
        id="prune_sessions",
        label="Prune sessions (30d, keep 20)",
        description="Prune old sessions (keeps recent)",
        risk_tier=RiskTier.CHANGES_STATE,
        run=lambda ctx: prune_sessions(
            older_than_days=ctx.older_than_days,
            keep_n=ctx.keep_n,
            team=ctx.team,
            dry_run=ctx.dry_run,
        ),
    ),
    MaintenanceTask(
        id="reset_exceptions",
        label="Reset all exceptions",
        description="Clear all policy exceptions",
        risk_tier=RiskTier.DESTRUCTIVE,
        run=lambda ctx: reset_exceptions(
            scope=ctx.exception_scope,
            repo_root=ctx.repo_root,
            dry_run=ctx.dry_run,
            create_backup=ctx.create_backup,
        ),
    ),
    MaintenanceTask(
        id="delete_all_sessions",
        label="Delete all sessions",
        description="Delete entire session history",
        risk_tier=RiskTier.DESTRUCTIVE,
        run=lambda ctx: delete_all_sessions(
            dry_run=ctx.dry_run,
            create_backup=ctx.create_backup,
        ),
    ),
    MaintenanceTask(
        id="reset_config",
        label="Reset configuration",
        description="Reset configuration (requires setup)",
        risk_tier=RiskTier.DESTRUCTIVE,
        run=lambda ctx: reset_config(
            dry_run=ctx.dry_run,
            create_backup=ctx.create_backup,
        ),
    ),
    MaintenanceTask(
        id="factory_reset",
        label="Factory reset (everything)",
        description="Remove all SCC data",
        risk_tier=RiskTier.FACTORY_RESET,
        run=lambda ctx: factory_reset(
            dry_run=ctx.dry_run,
            create_backup=ctx.create_backup,
            continue_on_error=ctx.continue_on_error,
        ),
    ),
)

_TASK_REGISTRY = {task.id: task for task in TASKS}


def list_tasks() -> tuple[MaintenanceTask, ...]:
    """Return all registered maintenance tasks in display order."""
    return TASKS


def get_task(action_id: str) -> MaintenanceTask | None:
    """Return a maintenance task by id."""
    return _TASK_REGISTRY.get(action_id)


def run_task(action_id: str, context: MaintenanceTaskContext) -> MaintenanceTaskResult:
    """Run a maintenance task by id."""
    task = get_task(action_id)
    if task is None:
        raise ValueError(f"Unknown maintenance task: {action_id}")
    return task.run(context)
