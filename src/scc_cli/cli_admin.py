"""
CLI Admin Commands.

Commands for system administration: doctor, update, statusline, and stats.
"""

import importlib.resources
import json
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.status import Status
from rich.table import Table

from . import config, docker, doctor, stats
from .cli_common import console, handle_errors
from .panels import create_info_panel, create_success_panel, create_warning_panel

# ─────────────────────────────────────────────────────────────────────────────
# Admin App
# ─────────────────────────────────────────────────────────────────────────────

admin_app = typer.Typer(
    name="admin",
    help="System administration commands.",
    no_args_is_help=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Doctor Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def doctor_cmd(
    workspace: str | None = typer.Argument(None, help="Optional workspace to check"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick status only"),
) -> None:
    """Check prerequisites and system health."""
    workspace_path = Path(workspace).expanduser().resolve() if workspace else None

    with Status("[cyan]Running health checks...[/cyan]", console=console, spinner="dots"):
        result = doctor.run_doctor(workspace_path)

    if quick:
        doctor.render_quick_status(console, result)
    else:
        doctor.render_doctor_results(console, result)

    # Return proper exit code
    if not result.all_ok:
        raise typer.Exit(3)  # Prerequisites failed


# ─────────────────────────────────────────────────────────────────────────────
# Update Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def update_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force check even if recently checked"),
) -> None:
    """Check for updates to scc-cli CLI and organization config."""
    from . import update as update_module

    cfg = config.load_config()

    with Status("[cyan]Checking for updates...[/cyan]", console=console, spinner="dots"):
        result = update_module.check_all_updates(cfg, force=force)

    # Render detailed update status panel
    update_module.render_update_status_panel(console, result)


# ─────────────────────────────────────────────────────────────────────────────
# Statusline Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def statusline_cmd(
    install: bool = typer.Option(
        False, "--install", "-i", help="Install the SCC status line script"
    ),
    uninstall: bool = typer.Option(
        False, "--uninstall", help="Remove the status line configuration"
    ),
    show: bool = typer.Option(False, "--show", "-s", help="Show current status line config"),
) -> None:
    """Configure Claude Code status line to show git worktree info.

    The status line displays: Model | Git branch/worktree | Context usage | Cost

    Examples:
        scc statusline --install    # Install the SCC status line
        scc statusline --show       # Show current configuration
        scc statusline --uninstall  # Remove status line config
    """
    claude_dir = Path.home() / ".claude"  # noqa: F841

    if show:
        # Show current configuration from Docker sandbox volume
        with Status(
            "[cyan]Reading Docker sandbox settings...[/cyan]",
            console=console,
            spinner="dots",
        ):
            settings = docker.get_sandbox_settings()

        if settings and "statusLine" in settings:
            console.print(
                create_info_panel(
                    "Status Line Configuration (Docker Sandbox)",
                    f"Script: {settings['statusLine'].get('command', 'Not set')}",
                    "Run 'scc statusline --uninstall' to remove",
                )
            )
        elif settings:
            console.print(
                create_info_panel(
                    "No Status Line",
                    "Status line is not configured in Docker sandbox.",
                    "Run 'scc statusline --install' to set it up",
                )
            )
        else:
            console.print(
                create_info_panel(
                    "No Configuration",
                    "Docker sandbox settings.json does not exist yet.",
                    "Run 'scc statusline --install' to create it",
                )
            )
        return

    if uninstall:
        # Remove status line configuration from Docker sandbox
        with Status(
            "[cyan]Removing statusline from Docker sandbox...[/cyan]",
            console=console,
            spinner="dots",
        ):
            # Get existing settings
            existing_settings = docker.get_sandbox_settings()

            if existing_settings and "statusLine" in existing_settings:
                del existing_settings["statusLine"]
                # Write updated settings back
                docker.inject_file_to_sandbox_volume(
                    "settings.json", json.dumps(existing_settings, indent=2)
                )
                console.print(
                    create_success_panel(
                        "Status Line Removed (Docker Sandbox)",
                        {"Settings": "Updated"},
                    )
                )
            else:
                console.print(
                    create_info_panel(
                        "Nothing to Remove",
                        "Status line was not configured in Docker sandbox.",
                    )
                )
        return

    if install:
        # SCC philosophy: Everything stays in Docker sandbox, not on host
        # Inject statusline script and settings into Docker sandbox volume

        # Get the status line script from package resources
        try:
            template_files = importlib.resources.files("scc_cli.templates")
            script_content = (template_files / "statusline.sh").read_text()
        except (FileNotFoundError, TypeError):
            # Fallback: read from relative path during development
            dev_path = Path(__file__).parent / "templates" / "statusline.sh"
            if dev_path.exists():
                script_content = dev_path.read_text()
            else:
                console.print(
                    create_warning_panel(
                        "Template Not Found",
                        "Could not find statusline.sh template.",
                    )
                )
                raise typer.Exit(1)

        with Status(
            "[cyan]Injecting statusline into Docker sandbox...[/cyan]",
            console=console,
            spinner="dots",
        ):
            # Inject script into Docker volume (will be at /mnt/claude-data/scc-statusline.sh)
            script_ok = docker.inject_file_to_sandbox_volume("scc-statusline.sh", script_content)

            # Get existing settings from Docker volume (if any)
            existing_settings = docker.get_sandbox_settings() or {}

            # Add statusline config (path inside container)
            existing_settings["statusLine"] = {
                "type": "command",
                "command": "/mnt/claude-data/scc-statusline.sh",
                "padding": 0,
            }

            # Inject settings into Docker volume
            settings_ok = docker.inject_file_to_sandbox_volume(
                "settings.json", json.dumps(existing_settings, indent=2)
            )

        if script_ok and settings_ok:
            console.print(
                create_success_panel(
                    "Status Line Installed (Docker Sandbox)",
                    {
                        "Script": "/mnt/claude-data/scc-statusline.sh",
                        "Settings": "/mnt/claude-data/settings.json",
                    },
                )
            )
            console.print()
            console.print(
                "[dim]The status line shows: "
                "[bold]Model[/bold] | [cyan]🌿 branch[/cyan] or [magenta]⎇ worktree[/magenta]:branch | "
                "[green]Ctx %[/green] | [yellow]$cost[/yellow][/dim]"
            )
            console.print("[dim]Restart Claude Code sandbox to see the changes.[/dim]")
        else:
            console.print(
                create_warning_panel(
                    "Installation Failed",
                    "Could not inject statusline into Docker sandbox volume.",
                    "Ensure Docker Desktop is running",
                )
            )
            raise typer.Exit(1)
        return

    # No flags - show help
    console.print(
        create_info_panel(
            "Status Line",
            "Configure a custom status line for Claude Code.",
            "Use --install to set up, --show to view, --uninstall to remove",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stats Sub-App
# ─────────────────────────────────────────────────────────────────────────────

stats_app = typer.Typer(
    name="stats",
    help="View and export usage statistics.",
    no_args_is_help=False,
)


@stats_app.callback(invoke_without_command=True)
@handle_errors
def stats_cmd(
    ctx: typer.Context,
    days: int | None = typer.Option(None, "--days", "-d", help="Filter to last N days"),
) -> None:
    """View your usage statistics.

    Shows session counts, duration, and per-project breakdown.

    Examples:
        scc stats                 # Show all-time stats
        scc stats --days 7        # Show last 7 days
        scc stats export --json   # Export as JSON
    """
    # If a subcommand was invoked, don't run the default
    if ctx.invoked_subcommand is not None:
        return

    report = stats.get_stats(days=days)

    # Handle empty stats
    if report.total_sessions == 0:
        console.print(
            create_info_panel(
                "Usage Statistics",
                "No sessions recorded yet.",
                "Run 'scc start' to begin tracking usage",
            )
        )
        return

    # Build summary panel
    duration_hours = report.total_duration_minutes // 60
    duration_mins = report.total_duration_minutes % 60

    summary_lines = [
        f"Total sessions: {report.total_sessions}",
        f"Total duration: {duration_hours}h {duration_mins}m",
    ]
    if report.incomplete_sessions > 0:
        summary_lines.append(f"Incomplete sessions: {report.incomplete_sessions}")

    period_str = ""
    if days is not None:
        period_str = f"Last {days} days"
    else:
        period_str = "All time"

    console.print(
        create_info_panel(
            f"Usage Statistics ({period_str})",
            "\n".join(summary_lines),
        )
    )

    # Show per-project breakdown if available
    if report.by_project:
        console.print()
        table = Table(title="Per-Project Breakdown", box=box.SIMPLE)
        table.add_column("Project", style="cyan")
        table.add_column("Sessions", justify="right")
        table.add_column("Duration", justify="right")

        for project, data in report.by_project.items():
            proj_hours = data["duration_minutes"] // 60
            proj_mins = data["duration_minutes"] % 60
            table.add_row(
                project,
                str(data["sessions"]),
                f"{proj_hours}h {proj_mins}m",
            )

        console.print(table)


@stats_app.command(name="export")
@handle_errors
def stats_export_cmd(
    json_format: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Export raw events"),
    days: int | None = typer.Option(None, "--days", "-d", help="Filter to last N days"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export statistics as JSON.

    Examples:
        scc stats export --json              # Export aggregated stats
        scc stats export --raw               # Export raw event data
        scc stats export --json -o stats.json  # Export to file
    """
    import json as json_module

    if raw:
        # Export raw events
        events = stats.read_usage_events()
        result = json_module.dumps(events, indent=2)
    else:
        # Export aggregated stats
        report = stats.get_stats(days=days)
        result = json_module.dumps(report.to_dict(), indent=2)

    if output:
        output.write_text(result)
        console.print(
            create_success_panel(
                "Stats Exported",
                {"Output file": str(output)},
            )
        )
    else:
        # Print to stdout
        print(result)


@stats_app.command(name="aggregate")
@handle_errors
def stats_aggregate_cmd(
    files: list[Path] = typer.Argument(
        None, help="Stats JSON files to aggregate (supports glob patterns)"
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Aggregate multiple stats files.

    Useful for team leads to combine exported stats from team members.

    Examples:
        scc stats aggregate stats1.json stats2.json
        scc stats aggregate stats-*.json --output team-stats.json
    """
    import glob
    import json as json_module

    if not files:
        console.print("[red]Error: No input files provided[/red]")
        raise typer.Exit(1)

    # Expand glob patterns
    expanded_files: list[Path] = []
    for file_pattern in files:
        pattern_str = str(file_pattern)
        if "*" in pattern_str or "?" in pattern_str:
            matched = glob.glob(pattern_str)
            if matched:
                expanded_files.extend(Path(m) for m in matched)
            else:
                console.print(f"[yellow]Warning: No files matched pattern '{pattern_str}'[/yellow]")
        else:
            expanded_files.append(file_pattern)

    if not expanded_files:
        console.print("[red]Error: No files found to aggregate[/red]")
        raise typer.Exit(1)

    # Read and aggregate
    aggregated: dict[str, Any] = {
        "total_sessions": 0,
        "total_duration_minutes": 0,
        "incomplete_sessions": 0,
        "by_project": {},
        "files_aggregated": [],
    }

    for file_path in expanded_files:
        if not file_path.exists():
            console.print(f"[red]Error: File not found: {file_path}[/red]")
            raise typer.Exit(1)

        try:
            data = json_module.loads(file_path.read_text())
        except json_module.JSONDecodeError:
            console.print(f"[red]Error: Invalid JSON in file: {file_path}[/red]")
            raise typer.Exit(1)

        # Aggregate totals
        aggregated["total_sessions"] += data.get("total_sessions", 0)
        aggregated["total_duration_minutes"] += data.get("total_duration_minutes", 0)
        aggregated["incomplete_sessions"] += data.get("incomplete_sessions", 0)
        aggregated["files_aggregated"].append(str(file_path))

        # Merge by_project
        for project, proj_data in data.get("by_project", {}).items():
            if project not in aggregated["by_project"]:
                aggregated["by_project"][project] = {"sessions": 0, "duration_minutes": 0}
            aggregated["by_project"][project]["sessions"] += proj_data.get("sessions", 0)
            aggregated["by_project"][project]["duration_minutes"] += proj_data.get(
                "duration_minutes", 0
            )

    result = json_module.dumps(aggregated, indent=2)

    if output:
        output.write_text(result)
        console.print(
            create_success_panel(
                "Stats Aggregated",
                {
                    "Files processed": str(len(expanded_files)),
                    "Total sessions": str(aggregated["total_sessions"]),
                    "Output file": str(output),
                },
            )
        )
    else:
        print(result)
