"""
CLI Launch Commands.

Commands for starting Claude Code in Docker sandboxes.

This module handles the `scc start` command, orchestrating:
- Session selection (--resume, --select, interactive)
- Workspace validation and preparation
- Team profile configuration
- Docker sandbox launch

The main `start()` function delegates to focused helper functions
for maintainability and testability.
"""

from pathlib import Path
from typing import Any

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
from .constants import WORKTREE_BRANCH_PREFIX
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import json_output_mode, print_json, set_pretty_mode
from .panels import create_info_panel, create_success_panel, create_warning_panel

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions (extracted for maintainability)
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_session_selection(
    workspace: str | None,
    team: str | None,
    resume: bool,
    select: bool,
    cfg: dict,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Handle session selection logic for --select, --resume, and interactive modes.

    Returns:
        Tuple of (workspace, team, session_name, worktree_name)
        If user cancels or no session found, workspace will be None.
    """
    session_name = None
    worktree_name = None

    # Interactive mode if no workspace provided and no session flags
    if workspace is None and not resume and not select:
        workspace, team, session_name, worktree_name = interactive_start(cfg)
        return workspace, team, session_name, worktree_name

    # Handle --select: interactive session picker
    if select and workspace is None:
        recent_sessions = sessions.list_recent(limit=10)
        if not recent_sessions:
            console.print("[yellow]No recent sessions found.[/yellow]")
            return None, team, None, None
        selected = ui.select_session(console, recent_sessions)
        if selected is None:
            return None, team, None, None
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
            return None, team, None, None

    return workspace, team, session_name, worktree_name


def _validate_and_resolve_workspace(workspace: str | None) -> Path | None:
    """
    Validate workspace path and handle platform-specific warnings.

    Raises:
        WorkspaceNotFoundError: If workspace path doesn't exist.
        typer.Exit: If user declines to continue after WSL2 warning.
    """
    if workspace is None:
        return None

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # WSL2 performance warning
    if platform_module.is_wsl2():
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

    return workspace_path


def _prepare_workspace(
    workspace_path: Path | None,
    worktree_name: str | None,
    install_deps: bool,
) -> Path | None:
    """
    Prepare workspace: create worktree, install deps, check git safety.

    Returns:
        The (possibly updated) workspace path after worktree creation.
    """
    if workspace_path is None:
        return None

    # Handle worktree creation
    if worktree_name:
        workspace_path = git.create_worktree(workspace_path, worktree_name)
        console.print(
            create_success_panel(
                "Worktree Created",
                {
                    "Path": str(workspace_path),
                    "Branch": f"{WORKTREE_BRANCH_PREFIX}{worktree_name}",
                },
            )
        )

    # Install dependencies if requested
    if install_deps:
        with Status("[cyan]Installing dependencies...[/cyan]", console=console, spinner="dots"):
            success = deps.auto_install_dependencies(workspace_path)
        if success:
            console.print("[green]✓ Dependencies installed[/green]")
        else:
            console.print("[yellow]⚠ Could not detect package manager or install failed[/yellow]")

    # Check git safety (handles protected branch warnings)
    if workspace_path.exists():
        git.check_branch_safety(workspace_path, console)

    return workspace_path


def _configure_team_settings(team: str | None, cfg: dict) -> None:
    """
    Validate team profile and inject settings into Docker sandbox.

    Raises:
        typer.Exit: If team profile is not found.
    """
    if not team:
        return

    with Status(f"[cyan]Configuring {team} plugin...[/cyan]", console=console, spinner="dots"):
        org_config = config.load_cached_org_config()

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

        docker.inject_team_settings(team, org_config=org_config)


def _resolve_mount_and_branch(workspace_path: Path | None) -> tuple[Path | None, str | None]:
    """
    Resolve mount path for worktrees and get current branch.

    For worktrees, expands mount scope to include main repo.
    Returns (mount_path, current_branch).
    """
    if workspace_path is None:
        return None, None

    # Get current branch
    current_branch = None
    try:
        current_branch = git.get_current_branch(workspace_path)
    except (NotAGitRepoError, OSError):
        pass

    # Handle worktree mounting
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

    return mount_path, current_branch


def _launch_sandbox(
    workspace_path: Path | None,
    mount_path: Path | None,
    team: str | None,
    session_name: str | None,
    current_branch: str | None,
    should_continue_session: bool,
    fresh: bool,
) -> None:
    """
    Execute the Docker sandbox with all configurations applied.

    Handles container creation, session recording, and process handoff.
    """
    # Prepare sandbox volume for credential persistence
    docker.prepare_sandbox_volume_for_credentials()

    # Get or create container
    docker_cmd, is_resume = docker.get_or_create_container(
        workspace=mount_path,
        branch=current_branch,
        profile=team,
        force_new=fresh,
        continue_session=should_continue_session,
        env_vars=None,
    )

    # Extract container name for session tracking
    container_name = _extract_container_name(docker_cmd, is_resume)

    # Record session
    if workspace_path:
        sessions.record_session(
            workspace=str(workspace_path),
            team=team,
            session_name=session_name,
            container_name=container_name,
            branch=current_branch,
        )

    # Show launch info and execute
    _show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=is_resume,
    )

    docker.run(docker_cmd)


def _extract_container_name(docker_cmd: list[str], is_resume: bool) -> str | None:
    """Extract container name from docker command for session tracking."""
    if "--name" in docker_cmd:
        try:
            name_idx = docker_cmd.index("--name") + 1
            return docker_cmd[name_idx]
        except (ValueError, IndexError):
            pass
    elif is_resume and docker_cmd:
        # For resume, container name is the last arg
        if docker_cmd[-1].startswith("scc-"):
            return docker_cmd[-1]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Dry Run Data Builder (Pure Function)
# ─────────────────────────────────────────────────────────────────────────────


def build_dry_run_data(
    workspace_path: Path,
    team: str | None,
    org_config: dict[str, Any] | None,
    project_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Build dry run data showing resolved configuration.

    This pure function assembles configuration information for preview
    without performing any side effects like Docker launch.

    Args:
        workspace_path: Path to the workspace directory.
        team: Selected team profile name (or None).
        org_config: Organization configuration dict (or None).
        project_config: Project-level .scc.yaml config (or None).

    Returns:
        Dictionary with resolved configuration data.
    """
    plugins: list[dict[str, Any]] = []
    blocked_items: list[str] = []

    # Extract plugins from org config if team is specified
    if org_config and team:
        profiles = org_config.get("profiles", [])
        for profile in profiles:
            if profile.get("name") == team:
                profile_plugins = profile.get("plugins", [])
                for plugin in profile_plugins:
                    plugins.append({"name": plugin.get("name", "unknown"), "source": "team"})

    # Extract plugins from project config
    if project_config:
        project_plugins = project_config.get("plugins", [])
        for plugin in project_plugins:
            if isinstance(plugin, dict):
                plugins.append({"name": plugin.get("name", "unknown"), "source": "project"})
            elif isinstance(plugin, str):
                plugins.append({"name": plugin, "source": "project"})

    return {
        "workspace": str(workspace_path),
        "team": team,
        "plugins": plugins,
        "blocked_items": blocked_items,
        "ready_to_start": len(blocked_items) == 0,
    }


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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview resolved configuration without launching"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """
    Start Claude Code in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    # ── Step 1: First-run detection ──────────────────────────────────────────
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            raise typer.Exit(1)

    cfg = config.load_config()

    # Treat --continue as alias for --resume (backward compatibility)
    if continue_session:
        resume = True

    # ── Step 2: Session selection (interactive, --select, --resume) ──────────
    workspace, team, session_name, worktree_name = _resolve_session_selection(
        workspace=workspace,
        team=team,
        resume=resume,
        select=select,
        cfg=cfg,
    )
    if workspace is None and (select or resume):
        raise typer.Exit(1)
    if workspace is None:
        raise typer.Exit()

    # ── Step 3: Docker availability check ────────────────────────────────────
    with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner="dots"):
        docker.check_docker_available()

    # ── Step 4: Workspace validation and platform checks ─────────────────────
    workspace_path = _validate_and_resolve_workspace(workspace)

    # ── Step 5: Workspace preparation (worktree, deps, git safety) ───────────
    workspace_path = _prepare_workspace(workspace_path, worktree_name, install_deps)

    # ── Step 6: Team configuration ───────────────────────────────────────────
    if not dry_run:
        _configure_team_settings(team, cfg)

    # ── Step 6.5: Handle --dry-run (preview without launching) ────────────────
    if dry_run:
        org_config = config.load_cached_org_config()
        project_config = None  # TODO: Load from .scc.yaml if present

        dry_run_data = build_dry_run_data(
            workspace_path=workspace_path,  # type: ignore[arg-type]
            team=team,
            org_config=org_config,
            project_config=project_config,
        )

        # Handle --pretty implies --json
        if pretty:
            json_output = True

        if json_output:
            with json_output_mode():
                if pretty:
                    set_pretty_mode(True)
                try:
                    envelope = build_envelope(Kind.START_DRY_RUN, data=dry_run_data)
                    print_json(envelope)
                finally:
                    if pretty:
                        set_pretty_mode(False)
        else:
            _show_dry_run_panel(dry_run_data)

        raise typer.Exit(0)

    # ── Step 7: Resolve mount path and branch for worktrees ──────────────────
    mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

    # ── Step 8: Launch sandbox ───────────────────────────────────────────────
    should_continue_session = resume or continue_session
    _launch_sandbox(
        workspace_path=workspace_path,
        mount_path=mount_path,
        team=team,
        session_name=session_name,
        current_branch=current_branch,
        should_continue_session=should_continue_session,
        fresh=fresh,
    )


def _show_launch_panel(
    workspace: Path | None,
    team: str | None,
    session_name: str | None,
    branch: str | None,
    is_resume: bool,
) -> None:
    """Display launch info panel with session details.

    Args:
        workspace: Path to the workspace directory, or None.
        team: Team profile name, or None for base profile.
        session_name: Optional session name for identification.
        branch: Current git branch, or None if not in a git repo.
        is_resume: True if resuming an existing container.
    """
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


def _show_dry_run_panel(data: dict[str, Any]) -> None:
    """Display dry run configuration preview.

    Args:
        data: Dictionary containing workspace, team, plugins, and ready_to_start status.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    # Workspace
    workspace = data.get("workspace", "")
    if len(workspace) > MAX_DISPLAY_PATH_LENGTH:
        workspace = "..." + workspace[-PATH_TRUNCATE_LENGTH:]
    grid.add_row("Workspace:", workspace)

    # Team
    grid.add_row("Team:", data.get("team") or "base")

    # Plugins
    plugins = data.get("plugins", [])
    if plugins:
        plugin_list = ", ".join(p.get("name", "unknown") for p in plugins)
        grid.add_row("Plugins:", plugin_list)
    else:
        grid.add_row("Plugins:", "[dim]none[/dim]")

    # Ready status
    ready = data.get("ready_to_start", True)
    status = "[green]✓ Ready to start[/green]" if ready else "[red]✗ Blocked[/red]"
    grid.add_row("Status:", status)

    # Blocked items
    blocked = data.get("blocked_items", [])
    if blocked:
        for item in blocked:
            grid.add_row("[red]Blocked:[/red]", item)

    panel = Panel(
        grid,
        title="[bold cyan]Dry Run Preview[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()
    if ready:
        console.print("[dim]Remove --dry-run to launch[/dim]")
    console.print()


def interactive_start(cfg: dict) -> tuple:
    """Guide user through interactive session setup.

    Prompt for team selection, workspace source, optional worktree creation,
    and session naming.

    Args:
        cfg: Application configuration dictionary containing workspace_base
            and other settings.

    Returns:
        Tuple of (workspace, team, session_name, worktree_name). All values
        may be None if user cancels at any step.
    """
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
