"""Environment health checks for doctor module.

Checks for Git, Docker, WSL2, and workspace path requirements.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scc_cli.core.enums import SeverityLevel
from scc_cli.core.contracts import RuntimeInfo

from ..types import CheckResult


def _probe_runtime_info() -> RuntimeInfo | None:
    """Return the current runtime probe result when available.

    Doctor checks should report the effective runtime truthfully. When Docker
    Desktop sandbox support is unavailable but the probe selected the OCI
    backend, that is a healthy runtime path rather than an error.
    """
    try:
        from scc_cli.bootstrap import get_default_adapters

        adapters = get_default_adapters()
        probe = adapters.runtime_probe
        if probe is None:
            return None
        return probe.probe()
    except Exception:
        return None


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
            severity=SeverityLevel.ERROR,
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
            severity=SeverityLevel.ERROR,
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
            severity=SeverityLevel.WARNING,
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
            severity=SeverityLevel.ERROR,
        )

    return CheckResult(
        name="Docker Desktop",
        passed=True,
        message="Docker Desktop meets sandbox requirements",
        version=desktop_version,
    )


def check_docker_sandbox() -> CheckResult:
    """Check whether SCC has a valid sandbox backend.

    Docker Desktop sandbox support is one valid backend. If it is unavailable
    but the runtime probe selected plain OCI, the check should still pass.
    """
    from ... import docker as docker_module

    if docker_module.check_docker_sandbox():
        return CheckResult(
            name="Sandbox Backend",
            passed=True,
            message="Docker sandbox backend is available",
        )

    runtime_info = _probe_runtime_info()
    if runtime_info is not None and runtime_info.daemon_reachable:
        if runtime_info.preferred_backend == "oci":
            return CheckResult(
                name="Sandbox Backend",
                passed=True,
                message="Docker sandbox unavailable; SCC will use the OCI backend instead",
                version=runtime_info.version,
                severity=SeverityLevel.INFO,
            )

    return CheckResult(
        name="Sandbox Backend",
        passed=False,
        message="No usable sandbox backend is available",
        fix_hint=(
            f"Enable Docker sandbox with Docker Desktop {docker_module.MIN_DOCKER_VERSION}+ "
            "or use a reachable OCI-capable Docker daemon"
        ),
        fix_url="https://docs.docker.com/desktop/features/sandbox/",
        severity=SeverityLevel.ERROR,
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
                severity=SeverityLevel.ERROR,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return CheckResult(
            name="Docker Daemon",
            passed=False,
            message="Could not connect to Docker daemon",
            fix_hint="Ensure Docker Desktop is running",
            severity=SeverityLevel.ERROR,
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
                severity=SeverityLevel.INFO,
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


def check_runtime_backend() -> CheckResult:
    """Check the container runtime backend type and reachability."""
    try:
        from scc_cli.bootstrap import get_default_adapters

        adapters = get_default_adapters()
        probe = adapters.runtime_probe
        if probe is None:
            return CheckResult(
                name="Runtime Backend",
                passed=False,
                message="Runtime probe not available in current configuration",
                severity=SeverityLevel.WARNING,
            )
        info = probe.probe()
    except Exception as exc:
        return CheckResult(
            name="Runtime Backend",
            passed=False,
            message=f"Failed to probe runtime backend: {exc}",
            severity=SeverityLevel.WARNING,
        )

    if not info.daemon_reachable:
        backend_label = info.preferred_backend or "unavailable"
        return CheckResult(
            name="Runtime Backend",
            passed=False,
            message=f"Runtime backend: {backend_label} — daemon not reachable",
            fix_hint="Start Docker Desktop or the Docker daemon",
            severity=SeverityLevel.WARNING,
        )

    backend_label = info.preferred_backend or "unknown"
    version_str = info.version or "unknown"
    return CheckResult(
        name="Runtime Backend",
        passed=True,
        message=(
            f"Runtime backend: {backend_label} "
            f"({info.display_name}, version {version_str})"
        ),
        version=version_str,
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
            severity=SeverityLevel.WARNING,
        )

    return CheckResult(
        name="Workspace Path",
        passed=True,
        message=f"Workspace path is optimal: {workspace}",
    )
