"""
CLI Worktree and Session Commands.

Commands for managing git worktrees, sessions, and containers.
"""

from pathlib import Path

import typer
from rich.prompt import Confirm
from rich.status import Status

from . import deps, docker, git, sessions, ui
from .cli_common import console, handle_errors, render_responsive_table
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .panels import create_info_panel, create_success_panel, create_warning_panel

# ─────────────────────────────────────────────────────────────────────────────
# Worktree App
# ─────────────────────────────────────────────────────────────────────────────

worktree_app = typer.Typer(
    name="worktree",
    help="Manage git worktrees for parallel development.",
    no_args_is_help=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Worktree Commands
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def worktree_cmd(
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
                "Branch": f"claude/{name}",
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
                branch=f"claude/{name}",
            )
            docker.run(docker_cmd)


@handle_errors
def worktrees_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
) -> None:
    """List all worktrees for a repository."""
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    worktree_list = git.list_worktrees(workspace_path)

    if not worktree_list:
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No worktrees found for this repository.",
                "Create one with: scc worktree <repo> <name>",
            )
        )
        return

    # Use the beautiful worktree rendering from git.py
    git.render_worktrees(worktree_list, console)


@handle_errors
def cleanup_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name of the worktree to remove"),
    force: bool = typer.Option(False, "-f", "--force", help="Force removal"),
) -> None:
    """Clean up a worktree."""
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
                    "Status": "Successfully cleaned up",
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
        False, "--yes", "-y", help="Actually remove containers (default is dry-run)"
    ),
) -> None:
    """Remove stopped SCC containers.

    By default, shows what would be removed (dry-run).
    Use --yes to actually remove containers.

    Only removes STOPPED containers with scc.managed=true label.
    Running containers are never affected.

    Examples:
        scc prune              # Show what would be removed
        scc prune --yes        # Actually remove stopped containers
        scc stop && scc prune --yes  # Stop then remove all
    """
    with Status("[cyan]Fetching containers...[/cyan]", console=console, spinner="dots"):
        all_containers = docker.list_scc_containers()

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

    # Dry-run mode (default)
    if not yes:
        console.print(
            create_info_panel(
                "Dry Run - Would Remove",
                f"{len(stopped)} stopped container(s):",
                "\n".join(f"  • {c.name}" for c in stopped),
            )
        )
        console.print("\n[dim]Run with --yes to actually remove.[/dim]")
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
