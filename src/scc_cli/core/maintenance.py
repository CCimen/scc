"""Backward-compatible facade for maintenance operations."""

from __future__ import annotations

from scc_cli.maintenance import (
    MaintenanceLock,
    MaintenanceLockError,
    MaintenancePreview,
    PathInfo,
    ResetResult,
    RiskTier,
    cleanup_expired_exceptions,
    clear_cache,
    clear_contexts,
    delete_all_sessions,
    factory_reset,
    get_paths,
    get_total_size,
    preview_operation,
    prune_containers,
    prune_sessions,
    reset_config,
    reset_exceptions,
)

__all__ = [
    "MaintenanceLock",
    "MaintenanceLockError",
    "MaintenancePreview",
    "PathInfo",
    "ResetResult",
    "RiskTier",
    "cleanup_expired_exceptions",
    "clear_cache",
    "clear_contexts",
    "delete_all_sessions",
    "factory_reset",
    "get_paths",
    "get_total_size",
    "preview_operation",
    "prune_containers",
    "prune_sessions",
    "reset_config",
    "reset_exceptions",
]
