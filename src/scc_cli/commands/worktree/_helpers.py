"""Pure helper functions for worktree commands.

This module contains pure, side-effect-free functions extracted from the
worktree command module. These functions are ideal for unit testing without
mocks and serve as building blocks for the higher-level command logic.

Functions:
    build_worktree_list_data: JSON mapping helper for worktree list output.
    is_container_stopped: Check if a Docker container status indicates stopped.
"""

from __future__ import annotations

from ...presentation.json.worktree_json import build_worktree_list_data

__all__ = ["build_worktree_list_data", "is_container_stopped"]


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
