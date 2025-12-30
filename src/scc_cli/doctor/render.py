"""Orchestration and rendering functions for the doctor module.

This module contains:
- run_doctor(): Main orchestrator that runs all health checks
- build_doctor_json_data(): JSON serialization for CLI output
- render_doctor_results(): Rich terminal UI rendering
- render_doctor_compact(): Compact inline status display
- render_quick_status(): Single-line pass/fail indicator
- quick_check(): Fast prerequisite validation
- is_first_run(): First-run detection
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scc_cli import __version__

from .checks import (
    check_config_directory,
    check_docker,
    check_docker_running,
    check_docker_sandbox,
    check_git,
    check_user_config_valid,
    check_workspace_path,
    check_wsl2,
)
from .types import DoctorResult

# ═══════════════════════════════════════════════════════════════════════════════
# JSON Serialization
# ═══════════════════════════════════════════════════════════════════════════════


def build_doctor_json_data(result: DoctorResult) -> dict[str, Any]:
    """Build JSON-serializable data from DoctorResult.

    Args:
        result: The DoctorResult to convert.

    Returns:
        Dictionary suitable for JSON envelope data field.
    """
    checks_data = []
    for check in result.checks:
        check_dict: dict[str, Any] = {
            "name": check.name,
            "passed": check.passed,
            "message": check.message,
            "severity": check.severity,
        }
        if check.version:
            check_dict["version"] = check.version
        if check.fix_hint:
            check_dict["fix_hint"] = check.fix_hint
        if check.fix_url:
            check_dict["fix_url"] = check.fix_url
        if check.fix_commands:
            check_dict["fix_commands"] = check.fix_commands
        if check.code_frame:
            check_dict["code_frame"] = check.code_frame
        checks_data.append(check_dict)

    # Calculate summary stats
    total = len(result.checks)
    passed = sum(1 for c in result.checks if c.passed)
    errors = sum(1 for c in result.checks if not c.passed and c.severity == "error")
    warnings = sum(1 for c in result.checks if not c.passed and c.severity == "warning")

    return {
        "checks": checks_data,
        "summary": {
            "total": total,
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "all_ok": result.all_ok,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main Doctor Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════


def run_doctor(workspace: Path | None = None) -> DoctorResult:
    """Run all health checks and return comprehensive results.

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

    # User config JSON validation check
    user_config_check = check_user_config_valid()
    result.checks.append(user_config_check)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Rich Terminal UI Rendering
# ═══════════════════════════════════════════════════════════════════════════════


def render_doctor_results(console: Console, result: DoctorResult) -> None:
    """Render doctor results with beautiful Rich formatting.

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
    version_suffix = f" (scc-cli v{__version__})"
    title_text = (
        f"System Health Check{version_suffix}"
        if result.all_ok
        else f"System Health Check - Issues Found{version_suffix}"
    )

    panel = Panel(
        table,
        title=f"[{title_style}]{title_text}[/{title_style}]",
        border_style="green" if result.all_ok else "red",
        padding=(1, 1),
    )

    console.print(panel)

    # Display code frames for any checks with syntax errors (beautiful error display)
    code_frame_checks = [c for c in result.checks if c.code_frame and not c.passed]
    for check in code_frame_checks:
        if check.code_frame is not None:  # Type guard for mypy
            console.print()
            # Create a panel for the code frame with Rich styling
            code_panel = Panel(
                check.code_frame,
                title=f"[bold red]⚠️  JSON Syntax Error: {check.name}[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
            console.print(code_panel)

    # Summary line
    if result.all_ok:
        console.print()
        console.print(
            "  [bold green]All prerequisites met![/bold green] [dim]Ready to run Claude Code.[/dim]"
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

        # Next Steps section with fix_commands
        checks_with_commands = [c for c in result.checks if not c.passed and c.fix_commands]
        if checks_with_commands:
            console.print()
            console.print("  [bold cyan]Next Steps[/bold cyan]")
            console.print("  [dim]────────────────────────────────────────────────────[/dim]")
            console.print()

            for check in checks_with_commands:
                console.print(f"  [bold white]{check.name}:[/bold white]")
                if check.fix_hint:
                    console.print(f"    [dim]{check.fix_hint}[/dim]")
                if check.fix_commands:
                    for i, cmd in enumerate(check.fix_commands, 1):
                        console.print(f"    [cyan]{i}.[/cyan] [white]{cmd}[/white]")
                console.print()

    console.print()


def render_doctor_compact(console: Console, result: DoctorResult) -> None:
    """Render compact doctor results for inline display.

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
    """Render a single-line status for quick checks.

    Returns immediately with pass/fail indicator.
    """
    if result.all_ok:
        console.print("[green]  All systems operational[/green]")
    else:
        failed = [c.name for c in result.checks if not c.passed and c.severity == "error"]
        console.print(f"[red]  Issues detected:[/red] {', '.join(failed)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Check Utilities
# ═══════════════════════════════════════════════════════════════════════════════


def quick_check() -> bool:
    """Perform a quick prerequisite check.

    Returns True if all critical prerequisites are met.
    Used for fast startup validation.
    """
    result = run_doctor()
    return result.all_ok


def is_first_run() -> bool:
    """Check if this is the first run of scc.

    Returns True if config directory doesn't exist or is empty.
    """
    from scc_cli import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        return True

    # Check if config file exists
    config_file = config.CONFIG_FILE
    return not config_file.exists()
