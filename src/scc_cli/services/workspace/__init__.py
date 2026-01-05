"""Workspace resolution services.

This package provides workspace detection and resolution for the launch command.

Exports:
    resolve_launch_context: Main entry point for workspace resolution
    is_suspicious_directory: Check if a path is inappropriate as workspace
    get_suspicious_reason: Get human-readable reason for suspicious status
    ResolverResult: Complete workspace resolution result (from core)

Example usage:
    from scc_cli.services.workspace import resolve_launch_context

    result = resolve_launch_context(Path.cwd(), workspace_arg=None)
    if result is None:
        # No workspace detected - need wizard or explicit path
        ...
    elif not result.is_auto_eligible():
        # Suspicious location - need confirmation
        ...
    else:
        # Good to auto-launch
        ...
"""

from scc_cli.core.workspace import ResolverResult

from .resolver import resolve_launch_context
from .suspicious import get_suspicious_reason, is_suspicious_directory

__all__ = [
    "ResolverResult",
    "get_suspicious_reason",
    "is_suspicious_directory",
    "resolve_launch_context",
]
