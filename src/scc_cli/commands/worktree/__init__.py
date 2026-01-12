"""
Worktree package - commands for git worktrees, sessions, and containers.

This package contains the decomposed worktree functionality:
- app.py: Typer app definitions and command wiring
- worktree_commands.py: Git worktree management commands
- container_commands.py: Docker container management commands
- session_commands.py: Session management commands
- context_commands.py: Work context management commands
- _helpers.py: Pure helper functions

Public API re-exports for backward compatibility.
"""

# Re-export pure helpers for testing
from ._helpers import build_worktree_list_data, is_container_stopped
from .app import (
    container_app,
    context_app,
    session_app,
    worktree_app,
)
from .container_commands import (
    container_list_cmd,
    list_cmd,
    prune_cmd,
    stop_cmd,
)
from .context_commands import context_clear_cmd
from .session_commands import session_list_cmd, session_prune_cmd, sessions_cmd
from .worktree_commands import (
    worktree_create_cmd,
    worktree_enter_cmd,
    worktree_list_cmd,
    worktree_prune_cmd,
    worktree_remove_cmd,
    worktree_select_cmd,
    worktree_switch_cmd,
)

# Backward compatibility alias (original name had underscore prefix)
_is_container_stopped = is_container_stopped

__all__ = [
    # Typer apps
    "worktree_app",
    "session_app",
    "container_app",
    "context_app",
    # Worktree commands
    "worktree_create_cmd",
    "worktree_list_cmd",
    "worktree_switch_cmd",
    "worktree_select_cmd",
    "worktree_enter_cmd",
    "worktree_remove_cmd",
    "worktree_prune_cmd",
    # Container commands
    "list_cmd",
    "stop_cmd",
    "prune_cmd",
    "container_list_cmd",
    # Session commands
    "sessions_cmd",
    "session_list_cmd",
    "session_prune_cmd",
    # Context commands
    "context_clear_cmd",
    # Pure helpers
    "build_worktree_list_data",
    "is_container_stopped",
    "_is_container_stopped",
]
