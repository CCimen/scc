"""Org status command for showing organization configuration status."""

from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from ...cli_common import console, handle_errors
from ...config import load_user_config
from ...core.constants import CLI_VERSION
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...remote import load_from_cache
from ._builders import build_status_data


@handle_errors
def org_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Show current organization configuration status.

    Displays connection mode (standalone or organization), cache freshness,
    version compatibility, and selected profile.

    Examples:
        scc org status
        scc org status --json
        scc org status --pretty
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load configuration data
    user_config = load_user_config()
    org_config, cache_meta = load_from_cache()

    # Build status data
    status_data = build_status_data(user_config, org_config, cache_meta)

    # JSON output mode
    if json_output:
        with json_output_mode():
            envelope = build_envelope(Kind.ORG_STATUS, data=status_data)
            print_json(envelope)
            raise typer.Exit(0)

    # Human-readable output
    _render_status_human(status_data)
    raise typer.Exit(0)


def _render_status_human(status: dict[str, Any]) -> None:
    """Render status data as human-readable Rich output.

    Args:
        status: Status data from build_status_data
    """
    # Mode header
    mode = status["mode"]
    if mode == "standalone":
        console.print("\n[bold cyan]Organization Status[/bold cyan]")
        console.print("  Mode: [yellow]Standalone[/yellow] (no organization configured)")
        console.print("\n  [dim]Tip: Run 'scc setup' to connect to an organization[/dim]\n")
        return

    # Organization mode
    console.print("\n[bold cyan]Organization Status[/bold cyan]")

    # Create a table for organization info
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")

    # Organization info
    org = status.get("organization", {})
    if org:
        org_name = org.get("name") or "[not fetched]"
        table.add_row("Organization", f"[bold]{org_name}[/bold]")
        table.add_row("Source URL", org.get("source_url", "[not configured]"))

    # Selected profile
    profile = status.get("selected_profile")
    if profile:
        table.add_row("Selected Profile", f"[green]{profile}[/green]")
    else:
        table.add_row("Selected Profile", "[yellow]None[/yellow]")

    # Available profiles
    available = status.get("available_profiles", [])
    if available:
        table.add_row("Available Profiles", ", ".join(available))

    console.print(table)

    # Cache status
    cache = status.get("cache")
    if cache:
        console.print("\n[bold]Cache Status[/bold]")
        cache_table = Table(show_header=False, box=None, padding=(0, 2))
        cache_table.add_column("Key", style="dim")
        cache_table.add_column("Value")

        if cache.get("valid"):
            cache_table.add_row("Status", "[green]+ Fresh[/green]")
        else:
            cache_table.add_row("Status", "[yellow]! Expired[/yellow]")

        if cache.get("fetched_at"):
            cache_table.add_row("Fetched At", cache["fetched_at"])
        if cache.get("expires_at"):
            cache_table.add_row("Expires At", cache["expires_at"])

        console.print(cache_table)
    else:
        console.print("\n[yellow]Cache:[/yellow] Not fetched yet")
        console.print(
            "  [dim]Run 'scc start' or 'scc doctor' to fetch the organization config[/dim]"
        )

    # Version compatibility
    compat = status.get("version_compatibility")
    if compat:
        console.print("\n[bold]Version Compatibility[/bold]")
        compat_table = Table(show_header=False, box=None, padding=(0, 2))
        compat_table.add_column("Key", style="dim")
        compat_table.add_column("Value")

        if compat.get("compatible"):
            compat_table.add_row("Status", "[green]+ Compatible[/green]")
        else:
            if compat.get("blocking_error"):
                compat_table.add_row("Status", "[red]x Incompatible[/red]")
                compat_table.add_row("Error", f"[red]{compat['blocking_error']}[/red]")
            else:
                compat_table.add_row("Status", "[yellow]! Warnings[/yellow]")

        if compat.get("schema_version"):
            compat_table.add_row("Schema Version", compat["schema_version"])
        if compat.get("min_cli_version"):
            compat_table.add_row("Min CLI Version", compat["min_cli_version"])
        compat_table.add_row("Current CLI", compat.get("current_cli_version", CLI_VERSION))

        # Show warnings if any
        warnings = compat.get("warnings", [])
        for warning in warnings:
            console.print(f"  [yellow]! {warning}[/yellow]")

        console.print(compat_table)

    console.print()  # Final newline
