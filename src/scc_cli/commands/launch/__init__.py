"""
Launch package - commands for starting agents in Docker sandboxes.

This package contains the decomposed launch functionality:
- render.py: Pure output/display functions (no business logic)
- flow.py: Start command logic and interactive flows
- app.py: Thin CLI wrapper for Typer registration
"""

from .app import launch_app, start
from .flow import interactive_start, run_start_wizard_flow
from .render import (
    build_dry_run_data,
    show_dry_run_panel,
    show_launch_panel,
    warn_if_non_worktree,
)
from .team_settings import _configure_team_settings
from .workspace import (
    prepare_workspace,
    resolve_mount_and_branch,
    resolve_workspace_team,
    validate_and_resolve_workspace,
)

__all__ = [
    # Main entry points
    "start",
    "launch_app",
    "interactive_start",
    "run_start_wizard_flow",
    # Private helpers (exposed for orchestrator)
    "_configure_team_settings",
    # Workspace functions
    "validate_and_resolve_workspace",
    "prepare_workspace",
    "resolve_workspace_team",
    "resolve_mount_and_branch",
    # Render functions
    "build_dry_run_data",
    "show_dry_run_panel",
    "show_launch_panel",
    "warn_if_non_worktree",
]
