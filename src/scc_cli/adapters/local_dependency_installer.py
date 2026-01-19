"""Local dependency installer adapter."""

from __future__ import annotations

from pathlib import Path

from scc_cli import deps
from scc_cli.ports.dependency_installer import DependencyInstaller, DependencyInstallResult


class LocalDependencyInstaller(DependencyInstaller):
    """Install dependencies using local package managers."""

    def install(self, workspace: Path) -> DependencyInstallResult:
        """Install dependencies for a workspace.

        Args:
            workspace: Workspace directory to inspect and install dependencies.

        Returns:
            Result describing whether installation was attempted and succeeded.
        """
        package_manager = deps.detect_package_manager(workspace)
        if package_manager is None:
            return DependencyInstallResult(attempted=False, success=False)

        success = deps.install_dependencies(workspace, package_manager, strict=False)
        return DependencyInstallResult(
            attempted=True,
            success=success,
            package_manager=package_manager,
        )
