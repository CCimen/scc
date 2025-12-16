"""
System health checks and prerequisite validation.

The doctor module provides comprehensive health checks for all
prerequisites needed to run Claude Code in Docker sandboxes.

Philosophy: "Fast feedback, clear guidance"
- Check all prerequisites quickly
- Provide clear pass/fail indicators
- Offer actionable fix suggestions
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    message: str
    version: Optional[str] = None
    fix_hint: Optional[str] = None
    fix_url: Optional[str] = None
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class DoctorResult:
    """Complete health check results."""

    git_ok: bool = False
    git_version: Optional[str] = None
    docker_ok: bool = False
    docker_version: Optional[str] = None
    sandbox_ok: bool = False
    wsl2_detected: bool = False
    windows_path_warning: bool = False
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """Check if all critical prerequisites pass."""
        return self.git_ok and self.docker_ok and self.sandbox_ok

    @property
    def error_count(self) -> int:
        """Count of failed critical checks."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warnings."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")


# ═══════════════════════════════════════════════════════════════════════════════
# Health Checks
# ═══════════════════════════════════════════════════════════════════════════════


def check_git() -> CheckResult:
    """Check if Git is installed and accessible."""
    from . import git as git_module

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
    from . import docker as docker_module

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

    # Parse and check minimum version
    current = docker_module._parse_version(version)
    required = docker_module._parse_version(docker_module.MIN_DOCKER_VERSION)

    if current < required:
        return CheckResult(
            name="Docker",
            passed=False,
            message=f"Docker version {'.'.join(map(str, current))} is below minimum {docker_module.MIN_DOCKER_VERSION}",
            version=version,
            fix_hint="Update Docker Desktop to the latest version",
            fix_url="https://docker.com/products/docker-desktop",
            severity="error",
        )

    return CheckResult(
        name="Docker",
        passed=True,
        message="Docker is installed and meets version requirements",
        version=version,
    )


def check_docker_sandbox() -> CheckResult:
    """Check if Docker sandbox feature is available."""
    from . import docker as docker_module

    if not docker_module.check_docker_sandbox():
        return CheckResult(
            name="Docker Sandbox",
            passed=False,
            message="Docker sandbox feature is not available",
            fix_hint=f"Requires Docker Desktop {docker_module.MIN_DOCKER_VERSION}+ with sandbox feature enabled",
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
    import subprocess

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


def check_wsl2() -> Tuple[CheckResult, bool]:
    """Check WSL2 environment and return (result, is_wsl2)."""
    from . import platform as platform_module

    is_wsl2 = platform_module.is_wsl2()

    if is_wsl2:
        return CheckResult(
            name="WSL2 Environment",
            passed=True,
            message="Running in WSL2 (recommended for Windows)",
            severity="info",
        ), True

    return CheckResult(
        name="WSL2 Environment",
        passed=True,
        message="Not running in WSL2",
        severity="info",
    ), False


def check_workspace_path(workspace: Optional[Path] = None) -> CheckResult:
    """Check if workspace path is optimal (not on Windows mount in WSL2)."""
    from . import platform as platform_module

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


def check_config_directory() -> CheckResult:
    """Check if configuration directory exists and is writable."""
    from . import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            return CheckResult(
                name="Config Directory",
                passed=True,
                message=f"Created config directory: {config_dir}",
            )
        except PermissionError:
            return CheckResult(
                name="Config Directory",
                passed=False,
                message=f"Cannot create config directory: {config_dir}",
                fix_hint="Check permissions on parent directory",
                severity="error",
            )

    # Check if writable
    test_file = config_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return CheckResult(
            name="Config Directory",
            passed=True,
            message=f"Config directory is writable: {config_dir}",
        )
    except (PermissionError, OSError):
        return CheckResult(
            name="Config Directory",
            passed=False,
            message=f"Config directory is not writable: {config_dir}",
            fix_hint=f"Check permissions: chmod 755 {config_dir}",
            severity="error",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Main Doctor Function
# ═══════════════════════════════════════════════════════════════════════════════


def run_doctor(workspace: Optional[Path] = None) -> DoctorResult:
    """
    Run all health checks and return comprehensive results.

    Args:
        workspace: Optional workspace path to check for optimization

    Returns:
        DoctorResult with all check results
    """
    result = DoctorResult()

    # Git check
    git_check = check_git()
    result.checks.append(git_check)
    result.git_ok = git_check.passed
    result.git_version = git_check.version

    # Docker check
    docker_check = check_docker()
    result.checks.append(docker_check)
    result.docker_ok = docker_check.passed
    result.docker_version = docker_check.version

    # Docker daemon check (only if Docker is installed)
    if result.docker_ok:
        daemon_check = check_docker_running()
        result.checks.append(daemon_check)
        if not daemon_check.passed:
            result.docker_ok = False

    # Docker sandbox check (only if Docker is OK)
    if result.docker_ok:
        sandbox_check = check_docker_sandbox()
        result.checks.append(sandbox_check)
        result.sandbox_ok = sandbox_check.passed
    else:
        result.sandbox_ok = False

    # WSL2 check
    wsl2_check, is_wsl2 = check_wsl2()
    result.checks.append(wsl2_check)
    result.wsl2_detected = is_wsl2

    # Workspace path check (if WSL2 and workspace provided)
    if workspace:
        path_check = check_workspace_path(workspace)
        result.checks.append(path_check)
        result.windows_path_warning = not path_check.passed and path_check.severity == "warning"

    # Config directory check
    config_check = check_config_directory()
    result.checks.append(config_check)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Beautiful Rich UI Rendering
# ═══════════════════════════════════════════════════════════════════════════════


def render_doctor_results(console: Console, result: DoctorResult) -> None:
    """
    Render doctor results with beautiful Rich formatting.

    Uses consistent styling with the rest of the CLI:
    - Cyan for info/brand
    - Green for success
    - Yellow for warnings
    - Red for errors
    """
    # Header
    console.print()

    # Build results table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Status", width=8, justify="center")
    table.add_column("Check", min_width=20)
    table.add_column("Details", min_width=30)

    for check in result.checks:
        # Status icon with color
        if check.passed:
            status = Text("  ", style="bold green")
        elif check.severity == "warning":
            status = Text("  ", style="bold yellow")
        else:
            status = Text("  ", style="bold red")

        # Check name
        name = Text(check.name, style="white")

        # Details with version and message
        details = Text()
        if check.version:
            details.append(f"{check.version}\n", style="cyan")
        details.append(check.message, style="dim" if check.passed else "white")

        if not check.passed and check.fix_hint:
            details.append(f"\n{check.fix_hint}", style="yellow")

        table.add_row(status, name, details)

    # Wrap table in panel
    title_style = "bold green" if result.all_ok else "bold red"
    title_text = "System Health Check" if result.all_ok else "System Health Check - Issues Found"

    panel = Panel(
        table,
        title=f"[{title_style}]{title_text}[/{title_style}]",
        border_style="green" if result.all_ok else "red",
        padding=(1, 1),
    )

    console.print(panel)

    # Summary line
    if result.all_ok:
        console.print()
        console.print(
            "  [bold green]All prerequisites met![/bold green] "
            "[dim]Ready to run Claude Code.[/dim]"
        )
    else:
        console.print()
        summary_parts = []
        if result.error_count > 0:
            summary_parts.append(f"[bold red]{result.error_count} error(s)[/bold red]")
        if result.warning_count > 0:
            summary_parts.append(f"[bold yellow]{result.warning_count} warning(s)[/bold yellow]")

        console.print(f"  Found {' and '.join(summary_parts)}. ", end="")
        console.print("[dim]Fix the issues above to continue.[/dim]")

    console.print()


def render_doctor_compact(console: Console, result: DoctorResult) -> None:
    """
    Render compact doctor results for inline display.

    Used during startup to show quick status.
    """
    checks = []

    # Git
    if result.git_ok:
        checks.append("[green]Git[/green]")
    else:
        checks.append("[red]Git[/red]")

    # Docker
    if result.docker_ok:
        checks.append("[green]Docker[/green]")
    else:
        checks.append("[red]Docker[/red]")

    # Sandbox
    if result.sandbox_ok:
        checks.append("[green]Sandbox[/green]")
    else:
        checks.append("[red]Sandbox[/red]")

    console.print(f"  [dim]Prerequisites:[/dim] {' | '.join(checks)}")


def render_quick_status(console: Console, result: DoctorResult) -> None:
    """
    Render a single-line status for quick checks.

    Returns immediately with pass/fail indicator.
    """
    if result.all_ok:
        console.print("[green]  All systems operational[/green]")
    else:
        failed = [c.name for c in result.checks if not c.passed and c.severity == "error"]
        console.print(f"[red]  Issues detected:[/red] {', '.join(failed)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Check Functions
# ═══════════════════════════════════════════════════════════════════════════════


def quick_check() -> bool:
    """
    Perform a quick prerequisite check.

    Returns True if all critical prerequisites are met.
    Used for fast startup validation.
    """
    result = run_doctor()
    return result.all_ok


def is_first_run() -> bool:
    """
    Check if this is the first run of scc.

    Returns True if config directory doesn't exist or is empty.
    """
    from . import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        return True

    # Check if config file exists
    config_file = config.CONFIG_FILE
    return not config_file.exists()
