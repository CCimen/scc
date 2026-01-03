"""Session commands for Claude Code session management."""

from __future__ import annotations

import typer

from ... import sessions
from ...cli_common import console, handle_errors, render_responsive_table
from ...panels import create_warning_panel
from ...ui.picker import TeamSwitchRequested, pick_session


@handle_errors
def sessions_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
) -> None:
    """List recent Claude Code sessions."""
    recent = sessions.list_recent(limit)

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
        console.print(
            create_warning_panel(
                "No Sessions",
                "No recent sessions found.",
                "Start a session with: scc start <workspace>",
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

    render_responsive_table(
        title="Recent Sessions",
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
    sessions_cmd(limit=limit, select=select)
