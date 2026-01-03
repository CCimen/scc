"""
Launch package - commands for starting Claude Code in Docker sandboxes.

This package contains the decomposed launch functionality:
- render.py: Pure output/display functions (no business logic)
- app.py: Main command logic and orchestration
- (more modules to be added as extraction continues)

Public API re-exports for backward compatibility.
"""

from .app import (
    _configure_team_settings,
    _sync_marketplace_settings,
    interactive_start,
    launch_app,
    run_start_wizard_flow,
    start,
)
from .render import (
    build_dry_run_data,
    show_dry_run_panel,
    show_launch_panel,
    warn_if_non_worktree,
)
from .sandbox import extract_container_name, launch_sandbox
from .workspace import (
    prepare_workspace,
    resolve_mount_and_branch,
    resolve_workspace_team,
    validate_and_resolve_workspace,
)

# Backward compatibility aliases for orchestrator imports
_validate_and_resolve_workspace = validate_and_resolve_workspace
_prepare_workspace = prepare_workspace
_resolve_workspace_team = resolve_workspace_team
_resolve_mount_and_branch = resolve_mount_and_branch
_launch_sandbox = launch_sandbox
_extract_container_name = extract_container_name
_warn_if_non_worktree = warn_if_non_worktree

__all__ = [
    # Main entry points
    "start",
    "launch_app",
    "interactive_start",
    "run_start_wizard_flow",
    # Private helpers (exposed for orchestrator)
    "_configure_team_settings",
    "_sync_marketplace_settings",
    # Sandbox functions
    "launch_sandbox",
    "extract_container_name",
    "_launch_sandbox",
    "_extract_container_name",
    # Workspace functions (new public API)
    "validate_and_resolve_workspace",
    "prepare_workspace",
    "resolve_workspace_team",
    "resolve_mount_and_branch",
    # Backward compatibility aliases
    "_validate_and_resolve_workspace",
    "_prepare_workspace",
    "_resolve_workspace_team",
    "_resolve_mount_and_branch",
    # Render functions
    "build_dry_run_data",
    "show_dry_run_panel",
    "show_launch_panel",
    "warn_if_non_worktree",
    "_warn_if_non_worktree",
]
