"""Session commands for Claude Code session management."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any

import typer
from rich.prompt import Confirm

from ... import config, sessions
from ...cli_common import console, handle_errors, render_responsive_table
from ...core.exit_codes import EXIT_CANCELLED
from ...json_command import json_command
from ...kinds import Kind
from ...maintenance import prune_sessions as maintenance_prune_sessions
from ...output_mode import is_json_mode
from ...panels import create_warning_panel
from ...presentation.json.sessions_json import build_session_list_data
from ...ui.picker import TeamSwitchRequested, pick_session


def _format_last_used(last_used: str | None) -> str:
    if not last_used:
        return "-"
    try:
        dt = datetime.fromisoformat(last_used)
    except ValueError:
        return last_used
    return sessions.format_relative_time(dt)


@json_command(Kind.SESSION_LIST)
@handle_errors
def sessions_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    team: str | None = typer.Option(
        None,
        "-t",
        "--team",
        "-p",
        "--profile",
        help="Filter by team/profile used on this machine",
    ),
    all_teams: bool = typer.Option(
        False, "--all", help="Show sessions for all teams (ignore active team)"
    ),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """List recent Claude Code sessions."""
    cfg = config.load_user_config()
    active_team = cfg.get("selected_profile")
    standalone_mode = config.is_standalone_mode()

    # Resolve effective filter
    filter_team: str | None
    if all_teams:
        filter_team = "__all__"
    elif team:
        filter_team = team
    elif standalone_mode:
        filter_team = None
    elif active_team:
        filter_team = active_team
    else:
        filter_team = "__all__"
        if not is_json_mode():
            console.print(
                "[dim]No active team selected — showing all sessions. "
                "Use 'scc team switch' or --team to filter.[/dim]"
            )

    include_all = filter_team == "__all__"
    recent = sessions.list_recent(
        limit=limit,
        team=None if include_all else filter_team,
        include_all=include_all,
    )

    session_dicts = [
        {
            "name": session.name,
            "workspace": session.workspace,
            "team": session.team,
            "last_used": session.last_used,
            "container_name": session.container_name,
            "branch": session.branch,
        }
        for session in recent
    ]
    data = build_session_list_data(session_dicts, team=None if include_all else filter_team)

    if is_json_mode():
        return data

    # Interactive picker mode
    if select and recent:
        try:
            selected = pick_session(
                recent,
                title="Select Session",
                subtitle=f"{len(recent)} recent sessions",
            )
            if selected:
                console.print(f"[green]Selected session:[/green] {selected.name}")
                console.print(f"[dim]Workspace: {selected.workspace}[/dim]")
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        return data

    if not recent:
        hint = "Start a session with: scc start <workspace>"
        if filter_team not in ("__all__", None):
            hint = "Use --all to show all teams or start a new session"
        console.print(
            create_warning_panel(
                "No Sessions",
                "No recent sessions found.",
                hint,
            )
        )
        return data

    # Build rows for responsive table
    rows = []
    for session in recent:
        # Shorten workspace path if needed
        ws = session.workspace or "-"
        if len(ws) > 40:
            ws = "..." + ws[-37:]
        rows.append(
            [
                session.name,
                ws,
                _format_last_used(session.last_used),
                session.team or "-",
            ]
        )

    title = "Recent Sessions"
    if filter_team not in ("__all__", None):
        title = f"Recent Sessions ({filter_team})"
    elif filter_team is None and standalone_mode:
        title = "Recent Sessions (standalone)"

    render_responsive_table(
        title=title,
        columns=[
            ("Session", "cyan"),
            ("Workspace", "white"),
        ],
        rows=rows,
        wide_columns=[
            ("Last Used", "yellow"),
            ("Team", "green"),
        ],
    )

    return data


@handle_errors
def session_list_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    team: str | None = typer.Option(
        None, "-t", "--team", "-p", "--profile", help="Filter by team/profile"
    ),
    all_teams: bool = typer.Option(
        False, "--all", help="Show sessions for all teams (ignore active team)"
    ),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """List recent Claude Code sessions.

    Alias for 'scc sessions'. Provides symmetric command structure.

    Examples:
        scc session list
        scc session list -n 20
        scc session list --select
    """
    # Delegate to sessions_cmd to avoid duplication
    sessions_cmd(
        limit=limit,
        team=team,
        all_teams=all_teams,
        select=select,
        json_output=json_output,
        pretty=pretty,
    )


def _parse_duration(duration: str) -> int:
    """Parse a duration string like '30d', '12h', '1w' to days.

    Supported formats:
        - Xd: X days
        - Xh: X hours (converted to days, rounded down)
        - Xw: X weeks (converted to days)

    Returns:
        Number of days.

    Raises:
        ValueError: If duration format is invalid.
    """
    match = re.match(r"^(\d+)([dhw])$", duration.lower())
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration}'. Use format like '30d', '12h', or '1w'."
        )

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return value
    elif unit == "h":
        return max(1, value // 24)  # At least 1 day
    elif unit == "w":
        return value * 7
    else:
        raise ValueError(f"Unknown duration unit: {unit}")


@handle_errors
def session_prune_cmd(
    older_than: Annotated[
        str,
        typer.Option(
            "--older-than",
            help="Prune sessions older than this (e.g., 30d, 12h, 1w). Default: 30d.",
        ),
    ] = "30d",
    keep: Annotated[
        int,
        typer.Option(
            "--keep",
            help="Keep at least this many recent sessions per team. Default: 20.",
        ),
    ] = 20,
    team: Annotated[
        str | None,
        typer.Option(
            "--team", "-t", "--profile", "-p", help="Only prune sessions for this team/profile."
        ),
    ] = None,
    all_teams: Annotated[
        bool,
        typer.Option("--all", help="Prune sessions across all teams."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Preview what would be pruned."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Prune old sessions while keeping recent ones.

    By default, removes sessions older than 30 days while keeping
    at least 20 recent sessions per team.

    Examples:
        scc session prune                    # Safe prune with defaults
        scc session prune --older-than 7d    # More aggressive
        scc session prune --keep 50          # Keep more history
        scc session prune --dry-run          # Preview only
        scc session prune --all --yes        # Prune all teams, no prompt
    """
    # Parse the duration
    try:
        older_than_days = _parse_duration(older_than)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Determine team filter
    prune_team: str | None = None
    if team:
        prune_team = team
    elif not all_teams:
        # Use active team if not --all
        cfg = config.load_user_config()
        active_team = cfg.get("selected_profile")
        if active_team:
            prune_team = active_team

    # Show what we're about to do
    scope = f"team '{prune_team}'" if prune_team else "all teams"
    console.print(
        f"\nPrune sessions older than {older_than_days} days (keeping newest {keep}) for {scope}"
    )

    # Get preview first
    result = maintenance_prune_sessions(
        older_than_days=older_than_days,
        keep_n=keep,
        team=prune_team,
        dry_run=True,
    )

    if result.removed_count == 0:
        console.print("[green]✓[/green] No sessions to prune")
        return

    console.print(f"  Sessions to remove: {result.removed_count}")

    if dry_run:
        console.print("  [dim](dry run - no changes made)[/dim]")
        return

    # Confirm if not --yes
    if not yes:
        if not Confirm.ask("Proceed?"):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(EXIT_CANCELLED)

    # Execute the prune
    result = maintenance_prune_sessions(
        older_than_days=older_than_days,
        keep_n=keep,
        team=prune_team,
        dry_run=False,
    )

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
        if result.bytes_freed > 0:
            console.print(f"  Freed: {result.bytes_freed_human}")
    else:
        console.print(f"[red]✗[/red] {result.message}")
        raise typer.Exit(1)
