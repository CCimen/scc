"""Maintenance operations and task registry."""

from __future__ import annotations

from .cache_cleanup import (
    cleanup_expired_exceptions,
    clear_cache,
    clear_contexts,
    prune_containers,
)
from .health_checks import get_paths, get_total_size, preview_operation
from .lock import MaintenanceLock, MaintenanceLockError
from .migrations import factory_reset, reset_config, reset_exceptions
from .repair_sessions import delete_all_sessions, prune_sessions
from .tasks import (
    MaintenanceTask,
    MaintenanceTaskContext,
    get_task,
    list_tasks,
    run_task,
)
from .types import MaintenancePreview, PathInfo, ResetResult, RiskTier

__all__ = [
    "RiskTier",
    "PathInfo",
    "ResetResult",
    "MaintenancePreview",
    "MaintenanceLock",
    "MaintenanceLockError",
    "clear_cache",
    "cleanup_expired_exceptions",
    "clear_contexts",
    "prune_containers",
    "prune_sessions",
    "reset_exceptions",
    "delete_all_sessions",
    "reset_config",
    "factory_reset",
    "get_paths",
    "get_total_size",
    "preview_operation",
    "MaintenanceTask",
    "MaintenanceTaskContext",
    "list_tasks",
    "get_task",
    "run_task",
]
