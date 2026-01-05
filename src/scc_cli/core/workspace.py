"""Workspace resolution domain types.

This module contains pure data types for workspace resolution results.
These types are used by the services layer to communicate resolution outcomes.

Key concepts:
- WR (workspace_root): The stable identity for sessions (git root or .scc.yaml parent)
- ED (entry_dir): Where the user invoked from (preserved for container cwd)
- MR (mount_root): Host path to mount into the container (may expand for worktrees)
- CW (container_workdir): The working directory inside the container (mirrored host path)

All paths in ResolverResult are absolute and resolved (symlinks expanded).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolverResult:
    """Complete workspace resolution output.

    All paths are absolute and resolved (symlinks expanded via resolve()).

    Attributes:
        workspace_root: WR - stable identity for sessions (git root or .scc.yaml parent)
        entry_dir: ED - where user invoked from
        mount_root: MR - host path mounted into container
        container_workdir: CW - mirrored host absolute path inside container
        is_auto_detected: True if found via git/.scc.yaml (not explicit --workspace)
        is_suspicious: Whether WR is in a suspicious location (home, /tmp, etc.)
        is_mount_expanded: Whether MR was expanded for worktree gitdir access
        reason: Debug explanation of how resolution was performed
    """

    workspace_root: Path  # WR - stable identity for sessions
    entry_dir: Path  # ED - where user invoked from
    mount_root: Path  # MR - host path mounted into container
    container_workdir: str  # CW - mirrored host absolute path
    is_auto_detected: bool  # True if found via git/.scc.yaml
    is_suspicious: bool  # Whether WR is in a suspicious location
    is_mount_expanded: bool = False  # Whether MR was expanded for worktree
    reason: str = ""  # Debug explanation

    def is_auto_eligible(self) -> bool:
        """Whether this result is eligible for auto-launch.

        Auto-launch requires:
        1. Workspace was auto-detected (not from explicit --workspace arg)
        2. Workspace is not in a suspicious location (home, /tmp, system dirs)

        Returns:
            True if workspace can be auto-launched without user confirmation.
        """
        return self.is_auto_detected and not self.is_suspicious
