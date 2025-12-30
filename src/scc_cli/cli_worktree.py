"""
CLI Worktree and Session Commands.

Commands for managing git worktrees, sessions, and containers.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer
from rich.prompt import Confirm
from rich.status import Status

from . import config, contexts, deps, docker, git, sessions
from .cli_common import console, handle_errors, render_responsive_table
from .cli_helpers import ConfirmItems, confirm_action
from .constants import WORKTREE_BRANCH_PREFIX
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .json_command import json_command
from .kinds import Kind
from .output_mode import is_json_mode
from .panels import create_info_panel, create_success_panel, create_warning_panel
from .theme import Indicators, Spinners
from .ui.gate import InteractivityContext
from .ui.picker import TeamSwitchRequested, pick_containers, pick_session, pick_worktree

# ─────────────────────────────────────────────────────────────────────────────
# Worktree App
# ─────────────────────────────────────────────────────────────────────────────

worktree_app = typer.Typer(
    name="worktree",
    help="Manage git worktrees for parallel development.",
    no_args_is_help=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pure Functions
# ─────────────────────────────────────────────────────────────────────────────


def build_worktree_list_data(
    worktrees: list[dict[str, Any]],
    workspace: str,
) -> dict[str, Any]:
    """Build worktree list data for JSON output.

    Args:
        worktrees: List of worktree dictionaries from git.list_worktrees()
        workspace: Path to the workspace

    Returns:
        Dictionary with worktrees, count, and workspace
    """
    return {
        "worktrees": worktrees,
        "count": len(worktrees),
        "workspace": workspace,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Worktree Commands
# ─────────────────────────────────────────────────────────────────────────────


@worktree_app.command("create")
@handle_errors
def worktree_create_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name for the worktree/feature"),
    base_branch: str | None = typer.Option(
        None, "-b", "--base", help="Base branch (default: current)"
    ),
    start_claude: bool = typer.Option(
        True, "--start/--no-start", help="Start Claude after creating"
    ),
    install_deps: bool = typer.Option(
        False, "--install-deps", help="Install dependencies after creating worktree"
    ),
) -> None:
    """Create a new worktree for parallel development."""
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    if not git.is_git_repo(workspace_path):
        raise NotAGitRepoError(path=str(workspace_path))

    worktree_path = git.create_worktree(workspace_path, name, base_branch)

    console.print(
        create_success_panel(
            "Worktree Created",
            {
                "Path": str(worktree_path),
                "Branch": f"{WORKTREE_BRANCH_PREFIX}{name}",
                "Base": base_branch or "current branch",
            },
        )
    )

    # Install dependencies if requested
    if install_deps:
        with Status(
            "[cyan]Installing dependencies...[/cyan]", console=console, spinner=Spinners.SETUP
        ):
            success = deps.auto_install_dependencies(worktree_path)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Dependencies installed[/green]")
        else:
            console.print("[yellow]⚠ Could not detect package manager or install failed[/yellow]")

    if start_claude:
        console.print()
        if Confirm.ask("[cyan]Start Claude Code in this worktree?[/cyan]", default=True):
            docker.check_docker_available()
            docker_cmd, _ = docker.get_or_create_container(
                workspace=worktree_path,
                branch=f"{WORKTREE_BRANCH_PREFIX}{name}",
            )
            # Load org config for safety-net policy injection
            org_config = config.load_cached_org_config()
            docker.run(docker_cmd, org_config=org_config)


@worktree_app.command("list")
@json_command(Kind.WORKTREE_LIST)
@handle_errors
def worktree_list_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Interactive mode: select a worktree to work with"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """List all worktrees for a repository.

    With -i/--interactive, select a worktree and print its path
    (useful for piping: cd $(scc worktree list -i))
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    worktree_list = git.list_worktrees(workspace_path)

    # Convert WorktreeInfo dataclasses to dicts for JSON serialization
    worktree_dicts = [asdict(wt) for wt in worktree_list]
    data = build_worktree_list_data(worktree_dicts, str(workspace_path))

    if is_json_mode():
        return data

    if not worktree_list:
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No worktrees found for this repository.",
                "Create one with: scc worktree create <repo> <name>",
            )
        )
        return

    # Interactive mode: use worktree picker
    if interactive:
        try:
            selected = pick_worktree(
                worktree_list,
                title="Select Worktree",
                subtitle=f"{len(worktree_list)} worktrees in {workspace_path.name}",
            )
            if selected:
                # Print just the path for scripting: cd $(scc worktree list -i)
                print(selected.path)
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        return

    # Use the beautiful worktree rendering from git.py
    git.render_worktrees(worktree_list, console)

    return data


@worktree_app.command("remove")
@handle_errors
def worktree_remove_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name of the worktree to remove"),
    force: bool = typer.Option(
        False, "-f", "--force", help="Force removal even with uncommitted changes"
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip all confirmation prompts"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be removed without removing"
    ),
) -> None:
    """Remove a worktree.

    By default, prompts for confirmation if there are uncommitted changes and
    asks whether to delete the associated branch.

    Use --yes to skip prompts (auto-confirms all actions).
    Use --dry-run to preview what would be removed.
    Use --force to remove even with uncommitted changes (still prompts unless --yes).
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # cleanup_worktree handles all output including success panels
    git.cleanup_worktree(workspace_path, name, force, console, skip_confirm=yes, dry_run=dry_run)


# ─────────────────────────────────────────────────────────────────────────────
# Session Commands
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# Container Commands
# ─────────────────────────────────────────────────────────────────────────────


def _list_interactive(containers: list[docker.ContainerInfo]) -> None:
    """Run interactive container list with action keys.

    Allows user to navigate containers and press action keys:
    - s: Stop the selected container
    - r: Resume the selected container
    - Enter: Show container details

    Args:
        containers: List of ContainerInfo objects.
    """
    from .ui.formatters import format_container
    from .ui.list_screen import ListMode, ListScreen

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
                "Start a session with: scc start <workspace>",
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


# ─────────────────────────────────────────────────────────────────────────────
# Prune Command
# ─────────────────────────────────────────────────────────────────────────────


def _is_container_stopped(status: str) -> bool:
    """Check if a container status indicates it's stopped (not running).

    Docker status strings:
    - "Up 2 hours" / "Up 30 seconds" / "Up 2 hours (healthy)" = running
    - "Exited (0) 2 hours ago" / "Exited (137) 5 seconds ago" = stopped
    - "Created" = created but never started (stopped)
    - "Dead" = dead container (stopped)
    """
    status_lower = status.lower()
    # Running containers have status starting with "up"
    if status_lower.startswith("up"):
        return False
    # Everything else is stopped: Exited, Created, Dead, etc.
    return True


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
    stopped = [c for c in all_containers if _is_container_stopped(c.status)]

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


# ─────────────────────────────────────────────────────────────────────────────
# Symmetric Alias Apps (Phase 8)
# ─────────────────────────────────────────────────────────────────────────────

session_app = typer.Typer(
    name="session",
    help="Session management commands.",
    no_args_is_help=True,
)

container_app = typer.Typer(
    name="container",
    help="Container management commands.",
    no_args_is_help=True,
)


@session_app.command("list")
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
    # Delegate to existing sessions logic
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


@container_app.command("list")
@handle_errors
def container_list_cmd() -> None:
    """List all SCC-managed Docker containers.

    Alias for 'scc list'. Provides symmetric command structure.

    Examples:
        scc container list
    """
    # Delegate to existing list logic
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner=Spinners.DOCKER):
        containers = docker.list_scc_containers()

    if not containers:
        console.print(
            create_warning_panel(
                "No Containers",
                "No SCC-managed containers found.",
                "Start a session with: scc start <workspace>",
            )
        )
        return

    # Build rows
    rows = []
    for c in containers:
        # Color status based on state
        status = c.status
        if status == "running":
            status = f"[green]{status}[/green]"
        elif status == "exited":
            status = f"[yellow]{status}[/yellow]"

        rows.append([c.name, status, c.workspace or "-", c.profile or "-", c.branch or "-"])

    render_responsive_table(
        title="SCC Containers",
        columns=[
            ("Name", "cyan"),
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


# ─────────────────────────────────────────────────────────────────────────────
# Context App (Work Context Management)
# ─────────────────────────────────────────────────────────────────────────────

context_app = typer.Typer(
    name="context",
    help="Work context management commands.",
    no_args_is_help=True,
)


@context_app.command("clear")
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
