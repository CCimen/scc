"""Session commands for Claude Code session management."""

from __future__ import annotations

import typer

from ... import config, sessions
from ...cli_common import console, handle_errors, render_responsive_table
from ...panels import create_warning_panel
from ...ui.picker import TeamSwitchRequested, pick_session


@handle_errors
def sessions_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    team: str | None = typer.Option(None, "-t", "--team", help="Filter by team"),
    all_teams: bool = typer.Option(
        False, "--all", help="Show sessions for all teams (ignore active team)"
    ),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
) -> None:
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
        console.print(
            "[dim]No active team selected — showing all sessions. "
            "Use 'scc team switch' or --team to filter.[/dim]"
        )

    recent = sessions.list_recent(limit)
    if filter_team != "__all__":
        recent = [s for s in recent if s.get("team") == filter_team]

    # Interactive picker mode
    if select and recent:
        try:
            selected = pick_session(
                recent,
                title="Select Session",
                subtitle=f"{len(recent)} recent sessions",
            )
            if selected:
                console.print(f"[green]Selected session:[/green] {selected.get('name', '-')}")
                console.print(f"[dim]Workspace: {selected.get('workspace', '-')}[/dim]")
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        return

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
        return

    # Build rows for responsive table
    rows = []
    for s in recent:
        # Shorten workspace path if needed
        ws = s.get("workspace", "-")
        if len(ws) > 40:
            ws = "..." + ws[-37:]
        rows.append([s.get("name", "-"), ws, s.get("last_used", "-"), s.get("team", "-")])

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


@handle_errors
def session_list_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    team: str | None = typer.Option(None, "-t", "--team", help="Filter by team"),
    all_teams: bool = typer.Option(
        False, "--all", help="Show sessions for all teams (ignore active team)"
    ),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
) -> None:
    """List recent Claude Code sessions.

    Alias for 'scc sessions'. Provides symmetric command structure.

    Examples:
        scc session list
        scc session list -n 20
        scc session list --select
    """
    # Delegate to sessions_cmd to avoid duplication
    sessions_cmd(limit=limit, team=team, all_teams=all_teams, select=select)
