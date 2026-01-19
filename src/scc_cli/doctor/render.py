"""Orchestration and rendering functions for the doctor module.

This module contains:
- build_doctor_json_data(): JSON serialization for CLI output
- render_doctor_results(): Rich terminal UI rendering
- render_doctor_compact(): Compact inline status display
- render_quick_status(): Single-line pass/fail indicator
- quick_check(): Fast prerequisite validation
- is_first_run(): First-run detection
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scc_cli import __version__
from scc_cli.core.enums import SeverityLevel

from .core import run_doctor
from .types import DoctorResult

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
        elif check.severity == SeverityLevel.WARNING:
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
        failed = [
            c.name for c in result.checks if not c.passed and c.severity == SeverityLevel.ERROR
        ]
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
