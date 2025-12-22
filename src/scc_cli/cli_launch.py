"""
CLI Launch Commands.

Commands for starting Claude Code in Docker sandboxes.
"""

from pathlib import Path

import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.table import Table

from . import config, deps, docker, git, sessions, setup, teams, ui
from . import platform as platform_module
from .cli_common import (
    MAX_DISPLAY_PATH_LENGTH,
    PATH_TRUNCATE_LENGTH,
    console,
    handle_errors,
)
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .panels import create_info_panel, create_success_panel, create_warning_panel

# ─────────────────────────────────────────────────────────────────────────────
# Launch App
# ─────────────────────────────────────────────────────────────────────────────

launch_app = typer.Typer(
    name="launch",
    help="Start Claude Code in sandboxes.",
    no_args_is_help=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Start Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def start(
    workspace: str | None = typer.Argument(None, help="Path to workspace (optional)"),
    team: str | None = typer.Option(None, "-t", "--team", help="Team profile to use"),
    session_name: str | None = typer.Option(None, "--session", help="Session name"),
    resume: bool = typer.Option(False, "-r", "--resume", help="Resume most recent session"),
    select: bool = typer.Option(False, "-s", "--select", help="Select from recent sessions"),
    continue_session: bool = typer.Option(
        False, "-c", "--continue", hidden=True, help="Alias for --resume (deprecated)"
    ),
    worktree_name: str | None = typer.Option(
        None, "-w", "--worktree", help="Create worktree with this name"
    ),
    fresh: bool = typer.Option(
        False, "--fresh", help="Force new container (don't resume existing)"
    ),
    install_deps: bool = typer.Option(
        False, "--install-deps", help="Install dependencies before starting"
    ),
    offline: bool = typer.Option(False, "--offline", help="Use cached config only (error if none)"),
    standalone: bool = typer.Option(False, "--standalone", help="Run without organization config"),
) -> None:
    """
    Start Claude Code in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    # First-run detection
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            raise typer.Exit(1)

    cfg = config.load_config()

    # Treat --continue as alias for --resume (backward compatibility)
    if continue_session:
        resume = True

    # Interactive mode if no workspace provided and no session flags
    if workspace is None and not resume and not select:
        workspace, team, session_name, worktree_name = interactive_start(cfg)
        if workspace is None:
            raise typer.Exit()

    # Handle --select: interactive session picker
    if select and workspace is None:
        recent_sessions = sessions.list_recent(limit=10)
        if not recent_sessions:
            console.print("[yellow]No recent sessions found.[/yellow]")
            raise typer.Exit(1)
        selected = ui.select_session(console, recent_sessions)
        if selected is None:
            # User cancelled
            raise typer.Exit()
        workspace = selected.get("workspace")
        if not team:
            team = selected.get("team")
        console.print(f"[dim]Selected: {workspace}[/dim]")

    # Handle --resume: auto-select most recent session
    elif resume and workspace is None:
        recent_session = sessions.get_most_recent()
        if recent_session:
            workspace = recent_session.get("workspace")
            if not team:
                team = recent_session.get("team")
            console.print(f"[dim]Resuming: {workspace}[/dim]")
        else:
            console.print("[yellow]No recent sessions found.[/yellow]")
            raise typer.Exit(1)

    # Validate Docker with spinner
    with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner="dots"):
        docker.check_docker_available()

    # Resolve workspace path
    workspace_path = Path(workspace).expanduser().resolve() if workspace else None

    # Validate workspace exists
    if workspace_path and not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # WSL2 performance warning
    if workspace_path and platform_module.is_wsl2():
        is_optimal, warning = platform_module.check_path_performance(workspace_path)
        if not is_optimal and warning:
            console.print()
            console.print(
                create_warning_panel(
                    "Performance Warning",
                    "Your workspace is on the Windows filesystem.",
                    "For better performance, move to ~/projects inside WSL.",
                )
            )
            console.print()
            if not Confirm.ask("[cyan]Continue anyway?[/cyan]", default=True):
                raise typer.Exit()

    # Handle worktree creation
    if worktree_name and workspace_path:
        workspace_path = git.create_worktree(workspace_path, worktree_name)
        console.print(
            create_success_panel(
                "Worktree Created",
                {
                    "Path": str(workspace_path),
                    "Branch": f"claude/{worktree_name}",
                },
            )
        )

    # Install dependencies if requested
    if install_deps and workspace_path:
        with Status("[cyan]Installing dependencies...[/cyan]", console=console, spinner="dots"):
            success = deps.auto_install_dependencies(workspace_path)
        if success:
            console.print("[green]✓ Dependencies installed[/green]")
        else:
            console.print("[yellow]⚠ Could not detect package manager or install failed[/yellow]")

    # Check git safety (handles protected branch warnings)
    if workspace_path and workspace_path.exists():
        git.check_branch_safety(workspace_path, console)

    # Inject team plugin settings into Docker sandbox
    if team:
        with Status(f"[cyan]Configuring {team} plugin...[/cyan]", console=console, spinner="dots"):
            # Load cached org config (NEW architecture)
            org_config = config.load_cached_org_config()

            # Validate team profile exists
            validation = teams.validate_team_profile(team, cfg, org_config=org_config)
            if not validation["valid"]:
                console.print(
                    create_warning_panel(
                        "Team Not Found",
                        f"No team profile named '{team}'.",
                        "Run 'scc teams' to see available profiles",
                    )
                )
                raise typer.Exit(1)

            # Inject team settings (extraKnownMarketplaces + enabledPlugins)
            # This happens in the Docker volume, Claude Code handles the rest
            docker.inject_team_settings(team, org_config=org_config)

    # Get current branch for container naming
    current_branch = None
    if workspace_path:
        try:
            current_branch = git.get_current_branch(workspace_path)
        except (NotAGitRepoError, OSError):
            # Not a git repo or filesystem error - continue without branch
            pass

    # Handle worktree mounting - expand mount scope to include main repo
    # Git worktrees use absolute paths in .git file that point to main repo
    mount_path = workspace_path
    if workspace_path:
        mount_path, is_expanded = git.get_workspace_mount_path(workspace_path)
        if is_expanded:
            console.print()
            console.print(
                create_info_panel(
                    "Worktree Detected",
                    f"Mounting parent directory for worktree support:\n{mount_path}",
                    "Both worktree and main repo will be accessible",
                )
            )
            console.print()

    # Prepare sandbox volume for credential persistence
    # This fixes a Docker Desktop bug where credentials.json permissions are wrong
    docker.prepare_sandbox_volume_for_credentials()

    # Get or create container (re-use pattern)
    # Unify resume flags: --resume and --continue both enable Claude session continuity
    should_continue_session = resume or continue_session
    docker_cmd, is_resume = docker.get_or_create_container(
        workspace=mount_path,
        branch=current_branch,
        profile=team,
        force_new=fresh,
        continue_session=should_continue_session,
        env_vars=None,
    )

    # Extract container name from command for session tracking
    container_name = None
    if "--name" in docker_cmd:
        try:
            name_idx = docker_cmd.index("--name") + 1
            container_name = docker_cmd[name_idx]
        except (ValueError, IndexError):
            pass
    elif is_resume and docker_cmd:
        # For resume, container name is the last arg
        container_name = docker_cmd[-1] if docker_cmd[-1].startswith("scc-") else None

    # Record session with container linking
    if workspace_path:
        sessions.record_session(
            workspace=str(workspace_path),
            team=team,
            session_name=session_name,
            container_name=container_name,
            branch=current_branch,
        )

    # Show launch info
    _show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=is_resume,
    )

    # Execute
    docker.run(docker_cmd)


def _show_launch_panel(
    workspace: Path | None,
    team: str | None,
    session_name: str | None,
    branch: str | None,
    is_resume: bool,
) -> None:
    """Display beautiful launch info panel."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    if workspace:
        # Shorten path for display
        display_path = str(workspace)
        if len(display_path) > MAX_DISPLAY_PATH_LENGTH:
            display_path = "..." + display_path[-PATH_TRUNCATE_LENGTH:]
        grid.add_row("Workspace:", display_path)

    grid.add_row("Team:", team or "base")

    if branch:
        grid.add_row("Branch:", branch)

    if session_name:
        grid.add_row("Session:", session_name)

    mode = "[green]Resume existing[/green]" if is_resume else "[cyan]New container[/cyan]"
    grid.add_row("Mode:", mode)

    panel = Panel(
        grid,
        title="[bold green]Launching Claude Code[/bold green]",
        border_style="green",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()
    console.print("[dim]Starting Docker sandbox...[/dim]")
    console.print()


def interactive_start(cfg: dict) -> tuple:
    """Interactive mode for starting Claude Code."""
    ui.show_header(console)

    # Step 1: Select team
    team = ui.select_team(console, cfg)

    # Step 2: Select workspace source
    workspace_source = ui.select_workspace_source(console, cfg, team)

    if workspace_source == "cancel":
        return None, None, None, None
    elif workspace_source == "recent":
        workspace = ui.select_recent_workspace(console, cfg)
    elif workspace_source == "team_repos":
        workspace = ui.select_team_repo(console, cfg, team)
    elif workspace_source == "custom":
        workspace = ui.prompt_custom_workspace(console)
    elif workspace_source == "clone":
        repo_url = ui.prompt_repo_url(console)
        if repo_url:
            workspace = git.clone_repo(repo_url, cfg.get("workspace_base", "~/projects"))
        else:
            workspace = None
    else:
        return None, None, None, None

    if workspace is None:
        return None, None, None, None

    # Step 3: Worktree option
    worktree_name = None
    console.print()
    if Confirm.ask(
        "[cyan]Create a worktree for isolated feature development?[/cyan]",
        default=False,
    ):
        worktree_name = Prompt.ask("[cyan]Feature/worktree name[/cyan]")

    # Step 4: Session name
    session_name = (
        Prompt.ask(
            "\n[cyan]Session name[/cyan] [dim](optional, for easy resume)[/dim]",
            default="",
        )
        or None
    )

    return workspace, team, session_name, worktree_name
