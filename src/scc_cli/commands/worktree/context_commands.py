"""Context commands for work context management."""

from __future__ import annotations

import typer

from ... import contexts
from ...cli_common import console, handle_errors
from ...confirm import Confirm
from ...panels import create_info_panel, create_success_panel


@handle_errors
def context_clear_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Clear all recent work contexts from cache.

    Use this command when the Recent Contexts list shows stale or
    incorrect entries that you want to reset.

    Examples:
        scc context clear           # With confirmation prompt
        scc context clear --yes     # Skip confirmation
    """
    cache_path = contexts._get_contexts_path()

    # Show current count
    current_count = len(contexts.load_recent_contexts())
    if current_count == 0:
        console.print(
            create_info_panel(
                "No Contexts",
                "No work contexts to clear.",
                "Contexts are created when you run: scc start <workspace>",
            )
        )
        return

    # Confirm unless --yes (improved what/why/next confirmation)
    if not yes:
        console.print(
            f"[yellow]This will remove {current_count} context(s) from {cache_path}[/yellow]"
        )
        if not Confirm.ask("Continue?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    # Clear and report
    cleared = contexts.clear_contexts()

    console.print(
        create_success_panel(
            "Contexts Cleared",
            {
                "Removed": f"{cleared} work context(s)",
                "Cache file": str(cache_path),
            },
        )
    )
    console.print("[dim]Run 'scc start' to repopulate.[/dim]")
