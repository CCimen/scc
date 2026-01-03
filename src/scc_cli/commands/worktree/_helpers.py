"""Pure helper functions for worktree commands.

This module contains pure, side-effect-free functions extracted from the
worktree command module. These functions are ideal for unit testing without
mocks and serve as building blocks for the higher-level command logic.

Functions:
    build_worktree_list_data: Build worktree list data for JSON output.
    is_container_stopped: Check if a Docker container status indicates stopped.
"""

from __future__ import annotations

from typing import Any


def build_worktree_list_data(
    worktrees: list[dict[str, Any]],
    workspace: str,
) -> dict[str, Any]:
    """Build worktree list data for JSON output.

    Args:
        worktrees: List of worktree dictionaries from git.list_worktrees()
        workspace: Path to the workspace

    Returns:
        Dictionary with worktrees, count, and workspace
    """
    return {
        "worktrees": worktrees,
        "count": len(worktrees),
        "workspace": workspace,
    }


def is_container_stopped(status: str) -> bool:
    """Check if a container status indicates it's stopped (not running).

    Docker status strings:
    - "Up 2 hours" / "Up 30 seconds" / "Up 2 hours (healthy)" = running
    - "Exited (0) 2 hours ago" / "Exited (137) 5 seconds ago" = stopped
    - "Created" = created but never started (stopped)
    - "Dead" = dead container (stopped)

    Args:
        status: The Docker container status string.

    Returns:
        True if the container is stopped, False if running.
    """
    status_lower = status.lower()
    # Running containers have status starting with "up"
    if status_lower.startswith("up"):
        return False
    # Everything else is stopped: Exited, Created, Dead, etc.
    return True
