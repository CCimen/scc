"""Environment health checks for doctor module.

Checks for Git, Docker, WSL2, and workspace path requirements.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..types import CheckResult


def check_git() -> CheckResult:
    """Check if Git is installed and accessible."""
    from ... import git as git_module

    if not git_module.check_git_installed():
        return CheckResult(
            name="Git",
            passed=False,
            message="Git is not installed or not in PATH",
            fix_hint="Install Git from https://git-scm.com/downloads",
            fix_url="https://git-scm.com/downloads",
            severity="error",
        )

    version = git_module.get_git_version()
    return CheckResult(
        name="Git",
        passed=True,
        message="Git is installed and accessible",
        version=version,
    )


def check_docker() -> CheckResult:
    """Check if Docker is installed and running."""
    from ... import docker as docker_module

    version = docker_module.get_docker_version()

    if version is None:
        return CheckResult(
            name="Docker",
            passed=False,
            message="Docker is not installed or not running",
            fix_hint="Install Docker Desktop from https://docker.com/products/docker-desktop",
            fix_url="https://docker.com/products/docker-desktop",
            severity="error",
        )

    return CheckResult(
        name="Docker",
        passed=True,
        message="Docker CLI is installed and accessible",
        version=version,
    )


def check_docker_desktop() -> CheckResult:
    """Check Docker Desktop version (sandbox requires 4.50+)."""
    from ... import docker as docker_module

    desktop_version = docker_module.get_docker_desktop_version()
    if desktop_version is None:
        return CheckResult(
            name="Docker Desktop",
            passed=False,
            message="Docker Desktop CLI not detected",
            fix_hint=("Install or update Docker Desktop 4.50+ and ensure its CLI is first in PATH"),
            fix_url="https://docker.com/products/docker-desktop",
            severity="warning",
        )

    current = docker_module._parse_version(desktop_version)
    required = docker_module._parse_version(docker_module.MIN_DOCKER_VERSION)

    if current < required:
        return CheckResult(
            name="Docker Desktop",
            passed=False,
            message=(
                f"Docker Desktop {'.'.join(map(str, current))} is below minimum "
                f"{docker_module.MIN_DOCKER_VERSION}"
            ),
            version=desktop_version,
            fix_hint="Update Docker Desktop to 4.50+",
            fix_url="https://docker.com/products/docker-desktop",
            severity="error",
        )

    return CheckResult(
        name="Docker Desktop",
        passed=True,
        message="Docker Desktop meets sandbox requirements",
        version=desktop_version,
    )


def check_docker_sandbox() -> CheckResult:
    """Check if Docker sandbox feature is available."""
    from ... import docker as docker_module

    if not docker_module.check_docker_sandbox():
        return CheckResult(
            name="Docker Sandbox",
            passed=False,
            message="Docker sandbox feature is not available",
            fix_hint=(
                f"Requires Docker Desktop {docker_module.MIN_DOCKER_VERSION}+ with sandbox enabled. "
                "Run 'docker sandbox --help' and verify Docker Desktop is first in PATH"
            ),
            fix_url="https://docs.docker.com/desktop/features/sandbox/",
            severity="error",
        )

    return CheckResult(
        name="Docker Sandbox",
        passed=True,
        message="Docker sandbox feature is available",
    )


def check_docker_running() -> CheckResult:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return CheckResult(
                name="Docker Daemon",
                passed=True,
                message="Docker daemon is running",
            )
        else:
            return CheckResult(
                name="Docker Daemon",
                passed=False,
                message="Docker daemon is not running",
                fix_hint="Start Docker Desktop or run 'sudo systemctl start docker'",
                severity="error",
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return CheckResult(
            name="Docker Daemon",
            passed=False,
            message="Could not connect to Docker daemon",
            fix_hint="Ensure Docker Desktop is running",
            severity="error",
        )


def check_wsl2() -> tuple[CheckResult, bool]:
    """Check WSL2 environment and return (result, is_wsl2)."""
    from ... import platform as platform_module

    is_wsl2 = platform_module.is_wsl2()

    if is_wsl2:
        return (
            CheckResult(
                name="WSL2 Environment",
                passed=True,
                message="Running in WSL2 (recommended for Windows)",
                severity="info",
            ),
            True,
        )

    return (
        CheckResult(
            name="WSL2 Environment",
            passed=True,
            message="Not running in WSL2",
            severity="info",
        ),
        False,
    )


def check_workspace_path(workspace: Path | None = None) -> CheckResult:
    """Check if workspace path is optimal (not on Windows mount in WSL2)."""
    from ... import platform as platform_module

    if workspace is None:
        return CheckResult(
            name="Workspace Path",
            passed=True,
            message="No workspace specified",
            severity="info",
        )

    if platform_module.is_wsl2() and platform_module.is_windows_mount_path(workspace):
        return CheckResult(
            name="Workspace Path",
            passed=False,
            message=f"Workspace is on Windows filesystem: {workspace}",
            fix_hint="Move project to ~/projects inside WSL for better performance",
            severity="warning",
        )

    return CheckResult(
        name="Workspace Path",
        passed=True,
        message=f"Workspace path is optimal: {workspace}",
    )
