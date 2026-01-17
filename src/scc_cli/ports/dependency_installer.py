"""Dependency installer port definition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DependencyInstallResult:
    """Outcome of a dependency installation attempt.

    Invariants:
        - `attempted` is False when no package manager was detected.
        - `success` is meaningful only when `attempted` is True.

    Args:
        attempted: Whether an installation was attempted.
        success: Whether the installation succeeded.
        package_manager: Detected package manager name when available.
    """

    attempted: bool
    success: bool
    package_manager: str | None = None


class DependencyInstaller(Protocol):
    """Abstract dependency installation operations.

    Invariants:
        - Installation attempts are best-effort and never prompt for input.
        - Results are returned to the caller for rendering decisions.

    Args:
        workspace: Path to the workspace where dependencies should be installed.
    """

    def install(self, workspace: Path) -> DependencyInstallResult:
        """Install dependencies for a workspace.

        Args:
            workspace: Workspace directory to inspect and install dependencies.

        Returns:
            Result describing whether installation was attempted and succeeded.
        """
        ...
