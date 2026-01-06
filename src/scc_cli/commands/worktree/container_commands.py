"""Container commands for Docker sandbox management."""

from __future__ import annotations

from typing import Any

import typer
from rich.status import Status

from ... import docker
from ...cli_common import console, handle_errors, render_responsive_table
from ...cli_helpers import ConfirmItems, confirm_action
from ...panels import create_info_panel, create_success_panel, create_warning_panel
from ...theme import Indicators, Spinners
from ...ui.gate import InteractivityContext
from ...ui.picker import TeamSwitchRequested, pick_containers
from ._helpers import is_container_stopped


def _list_interactive(containers: list[docker.ContainerInfo]) -> None:
    """Run interactive container list with action keys.

    Allows user to navigate containers and press action keys:
    - s: Stop the selected container
    - r: Resume the selected container
    - Enter: Show container details

    Args:
        containers: List of ContainerInfo objects.
    """
    from ...ui.formatters import format_container
    from ...ui.list_screen import ListMode, ListScreen

    # Convert to list items
    items = [format_container(c) for c in containers]

    # Define action handlers
    def stop_container_action(item: Any) -> None:
        """Stop the selected container."""
        container = item.value
        with Status(f"[cyan]Stopping {container.name}...[/cyan]", console=console):
            success = docker.stop_container(container.id)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Stopped: {container.name}[/green]")
        else:
            console.print(f"[red]{Indicators.get('FAIL')} Failed to stop: {container.name}[/red]")

    def resume_container_action(item: Any) -> None:
        """Resume the selected container."""
        container = item.value
        with Status(f"[cyan]Resuming {container.name}...[/cyan]", console=console):
            success = docker.resume_container(container.id)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Resumed: {container.name}[/green]")
        else:
            console.print(f"[red]{Indicators.get('FAIL')} Failed to resume: {container.name}[/red]")

    # Create screen with action handlers
    screen = ListScreen(
        items,
        title="Containers",
        mode=ListMode.ACTIONABLE,
        custom_actions={
            "s": stop_container_action,
            "r": resume_container_action,
        },
    )

    # Run the screen (actions execute via callbacks, returns None)
    screen.run()

    console.print("[dim]Actions: s=stop, r=resume, q=quit[/dim]")


@handle_errors
def list_cmd(
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Interactive mode: select container and take action"
    ),
) -> None:
    """List all SCC-managed Docker containers.

    With -i/--interactive, enter actionable mode where you can select a container
    and press action keys:
    - s: Stop the container
    - r: Resume the container
    - Enter: Select and show details
    """
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner=Spinners.DOCKER):
        containers = docker.list_scc_containers()

    if not containers:
        console.print(
            create_warning_panel(
                "No Containers",
                "No SCC-managed containers found.",
                "Use: scc sessions (recent sessions) or scc start <workspace>",
            )
        )
        return

    # Interactive mode: use ACTIONABLE list screen
    if interactive:
        _list_interactive(containers)
        return

    # Build rows for table display
    rows = []
    for c in containers:
        # Color status based on state
        status = c.status
        if "Up" in status:
            status = f"[green]{status}[/green]"
        elif "Exited" in status:
            status = f"[yellow]{status}[/yellow]"

        ws = c.workspace or "-"
        if ws != "-" and len(ws) > 35:
            ws = "..." + ws[-32:]

        rows.append([c.name, status, ws, c.profile or "-", c.branch or "-"])

    render_responsive_table(
        title="SCC Containers",
        columns=[
            ("Container", "cyan"),
            ("Status", "white"),
        ],
        rows=rows,
        wide_columns=[
            ("Workspace", "dim"),
            ("Profile", "yellow"),
            ("Branch", "green"),
        ],
    )

    console.print("[dim]Resume with: docker start -ai <container_name>[/dim]")
    console.print("[dim]Or use: scc list -i for interactive mode[/dim]")


@handle_errors
def stop_cmd(
    container: str = typer.Argument(
        None,
        help="Container name or ID to stop (omit for interactive picker)",
    ),
    all_containers: bool = typer.Option(
        False, "--all", "-a", help="Stop all running Claude Code sandboxes"
    ),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Use multi-select picker to choose containers"
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip confirmation prompt when stopping multiple containers"
    ),
) -> None:
    """Stop running Docker sandbox(es).

    Examples:
        scc stop                         # Interactive picker if multiple running
        scc stop -i                      # Force interactive multi-select picker
        scc stop claude-sandbox-2025...  # Stop specific container
        scc stop --all                   # Stop all (explicit)
        scc stop --yes                   # Stop all without confirmation
    """
    with Status("[cyan]Fetching sandboxes...[/cyan]", console=console, spinner=Spinners.DOCKER):
        # List Docker Desktop sandbox containers (image: docker/sandbox-templates:claude-code)
        running = docker.list_running_sandboxes()

    if not running:
        console.print(
            create_info_panel(
                "No Running Sandboxes",
                "No Claude Code sandboxes are currently running.",
                "Start one with: scc -w /path/to/project",
            )
        )
        return

    # If specific container requested
    if container and not all_containers:
        # Find matching container
        match = None
        for c in running:
            if c.name == container or c.id.startswith(container):
                match = c
                break

        if not match:
            console.print(
                create_warning_panel(
                    "Container Not Found",
                    f"No running container matches: {container}",
                    "Run 'scc list' to see available containers",
                )
            )
            raise typer.Exit(1)

        # Stop the specific container
        with Status(f"[cyan]Stopping {match.name}...[/cyan]", console=console):
            success = docker.stop_container(match.id)

        if success:
            console.print(create_success_panel("Container Stopped", {"Name": match.name}))
        else:
            console.print(
                create_warning_panel(
                    "Stop Failed",
                    f"Could not stop container: {match.name}",
                )
            )
            raise typer.Exit(1)
        return

    # Determine which containers to stop
    to_stop = running

    # Interactive picker mode: when -i flag OR multiple containers without --all/--yes
    ctx = InteractivityContext.create(json_mode=False, no_interactive=False)
    use_picker = interactive or (len(running) > 1 and not all_containers and not yes)

    if use_picker and ctx.allows_prompt():
        # Use multi-select picker
        try:
            selected = pick_containers(
                running,
                title="Stop Containers",
                subtitle=f"{len(running)} running",
            )
            if not selected:
                console.print("[dim]No containers selected.[/dim]")
                return
            to_stop = selected
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
            return
    elif len(running) > 1 and not yes:
        # Fallback to confirmation prompt (non-TTY or --all without --yes)
        try:
            confirm_action(
                yes=yes,
                prompt=f"Stop {len(running)} running container(s)?",
                items=ConfirmItems(
                    title=f"Found {len(running)} running container(s):",
                    items=[c.name for c in running],
                ),
            )
        except typer.Abort:
            console.print("[dim]Aborted.[/dim]")
            return

    console.print(f"[cyan]Stopping {len(to_stop)} container(s)...[/cyan]")

    stopped = []
    failed = []
    for c in to_stop:
        with Status(f"[cyan]Stopping {c.name}...[/cyan]", console=console):
            if docker.stop_container(c.id):
                stopped.append(c.name)
            else:
                failed.append(c.name)

    if stopped:
        console.print(
            create_success_panel(
                "Containers Stopped",
                {"Stopped": str(len(stopped)), "Names": ", ".join(stopped)},
            )
        )

    if failed:
        console.print(
            create_warning_panel(
                "Some Failed",
                f"Could not stop: {', '.join(failed)}",
            )
        )


@handle_errors
def prune_cmd(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt (for scripts/CI)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only show what would be removed, don't prompt"
    ),
) -> None:
    """Remove stopped SCC containers.

    Shows stopped containers and prompts for confirmation before removing.
    Use --yes/-y to skip confirmation (for scripts/CI).
    Use --dry-run to only preview without prompting.

    Only removes STOPPED containers. Running containers are never affected.

    Examples:
        scc prune              # Show containers, prompt to remove
        scc prune --yes        # Remove without prompting (CI/scripts)
        scc prune --dry-run    # Only show what would be removed
    """
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner=Spinners.DOCKER):
        # Use _list_all_sandbox_containers to find ALL sandbox containers (by image)
        # This matches how stop_cmd uses list_running_sandboxes (also by image)
        # Containers created by Docker Desktop directly don't have SCC labels
        all_containers = docker._list_all_sandbox_containers()

    # Filter to only stopped containers
    stopped = [c for c in all_containers if is_container_stopped(c.status)]

    if not stopped:
        console.print(
            create_info_panel(
                "Nothing to Prune",
                "No stopped SCC containers found.",
                "Run 'scc stop' first to stop running containers, then prune.",
            )
        )
        return

    # Handle dry-run mode separately - show what would be removed
    if dry_run:
        console.print(f"[bold]Would remove {len(stopped)} stopped container(s):[/bold]")
        for c in stopped:
            console.print(f"  [dim]•[/dim] {c.name}")
        console.print("[dim]Dry run complete. No containers removed.[/dim]")
        return

    # Use centralized confirmation helper for actual removal
    # This handles: --yes, JSON mode, non-interactive mode
    try:
        confirm_action(
            yes=yes,
            dry_run=False,
            prompt=f"Remove {len(stopped)} stopped container(s)?",
            items=ConfirmItems(
                title=f"Found {len(stopped)} stopped container(s):",
                items=[c.name for c in stopped],
            ),
        )
    except typer.Abort:
        console.print("[dim]Aborted.[/dim]")
        return

    # Actually remove containers
    console.print(f"[cyan]Removing {len(stopped)} stopped container(s)...[/cyan]")

    removed = []
    failed = []
    for c in stopped:
        with Status(f"[cyan]Removing {c.name}...[/cyan]", console=console):
            if docker.remove_container(c.name):
                removed.append(c.name)
            else:
                failed.append(c.name)

    if removed:
        console.print(
            create_success_panel(
                "Containers Removed",
                {"Removed": str(len(removed)), "Names": ", ".join(removed)},
            )
        )

    if failed:
        console.print(
            create_warning_panel(
                "Some Failed",
                f"Could not remove: {', '.join(failed)}",
            )
        )
        raise typer.Exit(1)


@handle_errors
def container_list_cmd() -> None:
    """List all SCC-managed Docker containers.

    Alias for 'scc list'. Provides symmetric command structure.

    Examples:
        scc container list
    """
    # Delegate to list_cmd to avoid duplication and ensure consistent behavior
    list_cmd(interactive=False)
