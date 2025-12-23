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

from . import deps, docker, git, sessions, ui
from .cli_common import console, handle_errors, render_responsive_table
from .constants import WORKTREE_BRANCH_PREFIX
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import json_output_mode, print_json, set_pretty_mode
from .panels import create_info_panel, create_success_panel, create_warning_panel

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
        with Status("[cyan]Installing dependencies...[/cyan]", console=console, spinner="dots"):
            success = deps.auto_install_dependencies(worktree_path)
        if success:
            console.print("[green]✓ Dependencies installed[/green]")
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
            docker.run(docker_cmd)


@worktree_app.command("list")
@handle_errors
def worktree_list_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """List all worktrees for a repository."""
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    worktree_list = git.list_worktrees(workspace_path)

    # JSON output mode
    if json_output:
        with json_output_mode():
            # Convert WorktreeInfo dataclasses to dicts for JSON serialization
            worktree_dicts = [asdict(wt) for wt in worktree_list]
            data = build_worktree_list_data(worktree_dicts, str(workspace_path))
            envelope = build_envelope(Kind.WORKTREE_LIST, data=data)
            print_json(envelope)
            raise typer.Exit(0)

    if not worktree_list:
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No worktrees found for this repository.",
                "Create one with: scc worktree create <repo> <name>",
            )
        )
        return

    # Use the beautiful worktree rendering from git.py
    git.render_worktrees(worktree_list, console)


@worktree_app.command("remove")
@handle_errors
def worktree_remove_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name of the worktree to remove"),
    force: bool = typer.Option(False, "-f", "--force", help="Force removal"),
) -> None:
    """Remove a worktree."""
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    result = git.cleanup_worktree(workspace_path, name, force, console)

    if result:
        console.print(
            create_success_panel(
                "Worktree Removed",
                {
                    "Name": name,
                    "Status": "Successfully removed",
                },
            )
        )


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
        selected = ui.select_session(console, recent)
        if selected:
            console.print(f"[green]Selected session:[/green] {selected.get('name', '-')}")
            console.print(f"[dim]Workspace: {selected.get('workspace', '-')}[/dim]")
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


@handle_errors
def list_cmd() -> None:
    """List all SCC-managed Docker containers."""
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner="dots"):
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


@handle_errors
def stop_cmd(
    container: str = typer.Argument(
        None,
        help="Container name or ID to stop (omit to stop all running)",
    ),
    all_containers: bool = typer.Option(
        False, "--all", "-a", help="Stop all running Claude Code sandboxes"
    ),
) -> None:
    """Stop running Docker sandbox(es).

    Examples:
        scc stop                         # Stop all running sandboxes
        scc stop claude-sandbox-2025...  # Stop specific container
        scc stop --all                   # Stop all (explicit)
    """
    with Status("[cyan]Fetching sandboxes...[/cyan]", console=console, spinner="dots"):
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

    # Stop all running containers
    console.print(f"[cyan]Stopping {len(running)} container(s)...[/cyan]")

    stopped = []
    failed = []
    for c in running:
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
        False, "--yes", "-y", "-f", help="Skip confirmation prompt (for scripts/CI)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only show what would be removed, don't prompt"
    ),
) -> None:
    """Remove stopped SCC containers.

    Shows stopped containers and prompts for confirmation before removing.
    Use --yes/-f to skip confirmation (for scripts).
    Use --dry-run to only preview without prompting.

    Only removes STOPPED containers. Running containers are never affected.

    Examples:
        scc prune              # Show containers, prompt to remove
        scc prune --yes        # Remove without prompting (CI/scripts)
        scc prune --dry-run    # Only show what would be removed
    """
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner="dots"):
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

    # Always show what will be removed
    console.print(f"\n[bold]Found {len(stopped)} stopped container(s):[/bold]")
    for c in stopped:
        console.print(f"  • {c.name}")
    console.print()

    # Dry-run mode: just show and exit
    if dry_run:
        console.print("[dim]Dry run complete. No containers removed.[/dim]")
        return

    # Interactive confirmation (unless --yes/-f)
    if not yes:
        if not typer.confirm("Remove these containers?", default=False):
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
        selected = ui.select_session(console, recent)
        if selected:
            console.print(f"[green]Selected session:[/green] {selected.get('name', '-')}")
            console.print(f"[dim]Workspace: {selected.get('workspace', '-')}[/dim]")
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
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner="dots"):
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
