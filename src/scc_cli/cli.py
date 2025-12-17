#!/usr/bin/env python3
"""
SCC - Sandboxed Claude CLI

A command-line tool for safely running Claude Code in Docker sandboxes
with team-specific configurations and worktree management.
"""

from functools import wraps
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_installed_version
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.table import Table

from . import config, deps, docker, doctor, git, sessions, setup, teams, ui
from . import platform as platform_module
from .errors import (
    NotAGitRepoError,
    SCCError,
    WorkspaceNotFoundError,
)
from .panels import create_info_panel, create_success_panel, create_warning_panel

# ─────────────────────────────────────────────────────────────────────────────
# Display Constants
# ─────────────────────────────────────────────────────────────────────────────

# Maximum length for displaying file paths before truncation
MAX_DISPLAY_PATH_LENGTH = 50
# Characters to keep when truncating (MAX - 3 for "...")
PATH_TRUNCATE_LENGTH = 47
# Terminal width threshold for wide mode tables
WIDE_MODE_THRESHOLD = 110


# ─────────────────────────────────────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="scc-cli",
    help="Safely run Claude Code with team configurations and worktree management.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)

console = Console()


# Global state for --debug flag
class AppState:
    debug: bool = False


state = AppState()


# ─────────────────────────────────────────────────────────────────────────────
# UI Helpers (Consistent Aesthetic)
# ─────────────────────────────────────────────────────────────────────────────

# Panel functions imported from .panels module:
# - create_info_panel
# - create_success_panel
# - create_warning_panel


def _render_responsive_table(
    title: str,
    columns: list[tuple[str, str]],  # (header, style)
    rows: list[list[str]],
    wide_columns: list[tuple[str, str]] = None,  # Extra columns for wide mode
) -> None:
    """Render a table that adapts to terminal width."""
    width = console.width
    wide_mode = width >= WIDE_MODE_THRESHOLD

    table = Table(
        title=f"[bold cyan]{title}[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
        show_lines=False,
    )

    # Add base columns
    for header, style in columns:
        table.add_column(header, style=style)

    # Add extra columns in wide mode
    if wide_mode and wide_columns:
        for header, style in wide_columns:
            table.add_column(header, style=style)

    # Add rows
    for row in rows:
        if wide_mode and wide_columns:
            table.add_row(*row)
        else:
            # Truncate to base columns only
            table.add_row(*row[: len(columns)])

    console.print()
    console.print(table)
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Global Callback (--debug flag)
# ─────────────────────────────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show detailed error information for troubleshooting.",
        is_eager=True,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        is_eager=True,
    ),
):
    """
    [bold cyan]SCC[/bold cyan] - Sandboxed Claude CLI

    Safely run Claude Code in Docker sandboxes with team configurations.
    """
    state.debug = debug

    if version:
        try:
            pkg_version = get_installed_version("scc-cli")
        except PackageNotFoundError:
            pkg_version = "unknown"
        console.print(
            Panel(
                f"[cyan]scc-cli[/cyan] [dim]v{pkg_version}[/dim]\n"
                "[dim]Safe development environment manager for Claude Code[/dim]",
                border_style="cyan",
            )
        )
        raise typer.Exit()

    # If no command provided and not showing version, invoke start
    # NOTE: Must pass ALL defaults explicitly - ctx.invoke() doesn't resolve
    # typer.Argument/Option defaults, it passes raw ArgumentInfo/OptionInfo objects
    if ctx.invoked_subcommand is None:
        ctx.invoke(
            start,
            workspace=None,
            team=None,
            session_name=None,
            continue_session=False,
            resume=False,
            worktree_name=None,
            fresh=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Error Boundary Decorator
# ─────────────────────────────────────────────────────────────────────────────


def handle_errors(func):
    """Decorator to catch SCCError and render beautifully."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SCCError as e:
            ui.render_error(console, e, debug=state.debug)
            raise typer.Exit(e.exit_code)
        except KeyboardInterrupt:
            console.print("\n[dim]Operation cancelled.[/dim]")
            raise typer.Exit(130)
        except (typer.Exit, SystemExit):
            # Let typer exits pass through
            raise
        except Exception as e:
            # Unexpected errors
            if state.debug:
                console.print_exception()
            else:
                console.print(
                    create_warning_panel(
                        "Unexpected Error",
                        str(e),
                        "Run with --debug for full traceback",
                    )
                )
            raise typer.Exit(5)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────


@app.command()
@handle_errors
def start(
    workspace: str | None = typer.Argument(None, help="Path to workspace (optional)"),
    team: str | None = typer.Option(None, "-t", "--team", help="Team profile to use"),
    session_name: str | None = typer.Option(None, "-s", "--session", help="Session name"),
    continue_session: bool = typer.Option(False, "-c", "--continue", help="Continue last session"),
    resume: bool = typer.Option(False, "-r", "--resume", help="Show session picker"),
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
):
    """
    Start Claude Code in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    # First-run detection
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            raise typer.Exit(1)

    cfg = config.load_config()

    # Interactive mode if no workspace provided
    if workspace is None and not continue_session and not resume:
        workspace, team, session_name, worktree_name = interactive_start(cfg)
        if workspace is None:
            raise typer.Exit()

    # Auto-select most recent session when --continue without workspace
    if continue_session and workspace is None:
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
    docker_cmd, is_resume = docker.get_or_create_container(
        workspace=mount_path,
        branch=current_branch,
        profile=team,
        force_new=fresh,
        continue_session=continue_session,
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


@app.command(name="worktree")
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
):
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


@app.command(name="worktrees")
@handle_errors
def worktrees_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
):
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


@app.command(name="cleanup")
@handle_errors
def cleanup_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name of the worktree to remove"),
    force: bool = typer.Option(False, "-f", "--force", help="Force removal"),
):
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


@app.command(name="teams")
@handle_errors
def teams_cmd(
    team_name: str | None = typer.Argument(None, help="Team name to show details"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Sync team configs from GitHub"),
):
    """List available team profiles or show team details."""
    cfg = config.load_config()

    # Load cached org config (NEW architecture)
    org_config = config.load_cached_org_config()

    # Sync mode
    if sync:
        _sync_teams(cfg, team_name)
        return

    # Detail view for specific team
    if team_name:
        _show_team_details(cfg, team_name, org_config=org_config)
        return

    # List all teams (pass org_config for NEW architecture)
    available_teams = teams.list_teams(cfg, org_config=org_config)

    if not available_teams:
        console.print(
            create_warning_panel(
                "No Teams",
                "No team profiles configured.",
                "Run 'scc setup' to initialize configuration",
            )
        )
        return

    # Build rows for responsive table
    rows = []
    for team in available_teams:
        plugin = team.get("plugin") or "-"
        rows.append([team["name"], team["description"], plugin])

    _render_responsive_table(
        title="Available Team Profiles",
        columns=[
            ("Team", "cyan"),
            ("Description", "white"),
        ],
        rows=rows,
        wide_columns=[
            ("Plugin", "yellow"),
        ],
    )

    console.print("[dim]Use: scc teams <name> for details, scc teams --sync to update[/dim]")


def _show_team_details(cfg: dict, team_name: str, org_config: dict | None = None) -> None:
    """Display detailed information for a team profile."""
    details = teams.get_team_details(team_name, cfg, org_config=org_config)

    if not details:
        console.print(
            create_warning_panel(
                "Team Not Found",
                f"No team profile named '{team_name}'.",
                "Run 'scc teams' to see available profiles",
            )
        )
        return

    # Build detail panel
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    grid.add_row("Description:", details.get("description", "-"))

    # Show plugin info (new simplified schema)
    plugin = details.get("plugin")
    if plugin:
        marketplace = details.get("marketplace", "sundsvall")
        grid.add_row("Plugin:", f"{plugin}@{marketplace}")
        grid.add_row("Marketplace:", details.get("marketplace_repo", "-"))
    else:
        grid.add_row("Plugin:", "[dim]None (base profile)[/dim]")

    panel = Panel(
        grid,
        title=f"[bold cyan]Team: {team_name}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print()
    console.print(f"[dim]Use: scc start -t {team_name} to use this profile[/dim]")


def _sync_teams(cfg: dict, team_name: str | None) -> None:
    """Sync team configurations from GitHub."""
    org_config = cfg.get("organization", {})
    github_org = org_config.get("github_org")
    config_repo = org_config.get("config_repo")

    if not github_org or not config_repo:
        console.print(
            create_warning_panel(
                "Sync Not Configured",
                "No GitHub organization or config repository set.",
                "Configure organization.github_org and organization.config_repo in config",
            )
        )
        return

    if team_name:
        # Sync specific team
        with Status(
            f"[cyan]Syncing {team_name} from GitHub...[/cyan]",
            console=console,
            spinner="dots",
        ):
            success = teams.sync_team_from_github(team_name, cfg)

        if success:
            console.print(
                create_success_panel(
                    "Team Synced",
                    {"Team": team_name, "Source": f"{github_org}/{config_repo}"},
                )
            )
        else:
            console.print(
                create_warning_panel(
                    "Sync Failed",
                    f"Could not sync team '{team_name}'.",
                    f"Check if profiles/{team_name} exists in {github_org}/{config_repo}",
                )
            )
    else:
        # Sync all teams
        profiles = cfg.get("profiles", {})
        synced = []
        failed = []

        for name in profiles.keys():
            with Status(
                f"[cyan]Syncing {name}...[/cyan]",
                console=console,
                spinner="dots",
            ):
                if teams.sync_team_from_github(name, cfg):
                    synced.append(name)
                else:
                    failed.append(name)

        if synced:
            console.print(
                create_success_panel(
                    "Teams Synced",
                    {
                        "Synced": ", ".join(synced),
                        "Source": f"{github_org}/{config_repo}",
                    },
                )
            )

        if failed:
            console.print(
                create_warning_panel(
                    "Some Syncs Failed",
                    f"Could not sync: {', '.join(failed)}",
                    "These teams may not exist in the remote repository",
                )
            )


@app.command(name="sessions")
@handle_errors
def sessions_cmd(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
):
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

    _render_responsive_table(
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


@app.command(name="list")
@handle_errors
def list_cmd():
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

    _render_responsive_table(
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


@app.command(name="stop")
@handle_errors
def stop_cmd(
    container: str = typer.Argument(
        None,
        help="Container name or ID to stop (omit to stop all running)",
    ),
    all_containers: bool = typer.Option(
        False, "--all", "-a", help="Stop all running Claude Code sandboxes"
    ),
):
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


@app.command(name="setup")
@handle_errors
def setup_cmd(
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick setup with defaults"),
    reset: bool = typer.Option(False, "--reset", help="Reset configuration"),
    org_url: str | None = typer.Option(
        None, "--org-url", help="Organization config URL (for non-interactive)"
    ),
    team: str | None = typer.Option(None, "--team", "-t", help="Team profile to select"),
    auth: str | None = typer.Option(None, "--auth", help="Auth spec (env:VAR or command:CMD)"),
    standalone: bool = typer.Option(
        False, "--standalone", help="Standalone mode (no organization)"
    ),
):
    """Run initial setup wizard.

    Examples:
        scc setup                                    # Interactive wizard
        scc setup --standalone                       # Standalone mode
        scc setup --org-url <url> --team dev         # Non-interactive
    """
    if reset:
        setup.reset_setup(console)
        return

    # Non-interactive mode if org_url or standalone specified
    if org_url or standalone:
        success = setup.run_non_interactive_setup(
            console,
            org_url=org_url,
            team=team,
            auth=auth,
            standalone=standalone,
        )
        if not success:
            raise typer.Exit(1)
        return

    if quick:
        setup.run_quick_setup(console)
    else:
        setup.run_setup(console)


@app.command(name="config")
@handle_errors
def config_cmd(
    action: str = typer.Argument(None, help="Action: set, get, show, edit"),
    key: str = typer.Argument(None, help="Config key (for set/get, e.g. hooks.enabled)"),
    value: str = typer.Argument(None, help="Value (for set only)"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
):
    """View or edit configuration.

    Examples:
        scc config --show                    # Show all config
        scc config get selected_profile      # Get specific key
        scc config set hooks.enabled true    # Set a value
        scc config --edit                    # Open in editor
    """
    # Handle action-based commands
    if action == "set":
        if not key or value is None:
            console.print("[red]Usage: scc config set <key> <value>[/red]")
            raise typer.Exit(1)
        _config_set(key, value)
        return

    if action == "get":
        if not key:
            console.print("[red]Usage: scc config get <key>[/red]")
            raise typer.Exit(1)
        _config_get(key)
        return

    # Handle --show and --edit flags
    if show or action == "show":
        cfg = config.load_user_config()
        console.print(
            create_info_panel(
                "Configuration",
                f"Current settings loaded from {config.CONFIG_FILE}",
            )
        )
        console.print()
        console.print_json(data=cfg)
    elif edit or action == "edit":
        config.open_in_editor()
    else:
        console.print(
            create_info_panel(
                "Configuration Help",
                "Commands:\n  scc config --show     View current settings\n  scc config --edit     Edit in your editor\n  scc config get <key>  Get a specific value\n  scc config set <key> <value>  Set a value",
                f"Config location: {config.CONFIG_FILE}",
            )
        )


def _config_set(key: str, value: str) -> None:
    """Set a configuration value by dotted key path."""
    cfg = config.load_user_config()

    # Parse dotted key path (e.g., "hooks.enabled")
    keys = key.split(".")
    obj = cfg
    for k in keys[:-1]:
        if k not in obj:
            obj[k] = {}
        obj = obj[k]

    # Parse value (handle booleans and numbers)
    if value.lower() == "true":
        parsed_value = True
    elif value.lower() == "false":
        parsed_value = False
    elif value.isdigit():
        parsed_value = int(value)
    else:
        parsed_value = value

    obj[keys[-1]] = parsed_value
    config.save_user_config(cfg)
    console.print(f"[green]✓ Set {key} = {parsed_value}[/green]")


def _config_get(key: str) -> None:
    """Get a configuration value by dotted key path."""
    cfg = config.load_user_config()

    # Navigate dotted key path
    keys = key.split(".")
    obj = cfg
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            console.print(f"[yellow]Key '{key}' not found[/yellow]")
            return

    # Display value
    if isinstance(obj, dict):
        console.print_json(data=obj)
    else:
        console.print(str(obj))


@app.command(name="doctor")
@handle_errors
def doctor_cmd(
    workspace: str | None = typer.Argument(None, help="Optional workspace to check"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick status only"),
):
    """Check prerequisites and system health."""
    workspace_path = Path(workspace).expanduser().resolve() if workspace else None

    with Status("[cyan]Running health checks...[/cyan]", console=console, spinner="dots"):
        result = doctor.run_doctor(workspace_path)

    if quick:
        doctor.render_quick_status(console, result)
    else:
        doctor.render_doctor_results(console, result)

    # Return proper exit code
    if not result.all_ok:
        raise typer.Exit(3)  # Prerequisites failed


@app.command(name="update")
@handle_errors
def update_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force check even if recently checked"),
):
    """Check for updates to scc-cli CLI and organization config."""
    from . import update as update_module

    cfg = config.load_config()

    with Status("[cyan]Checking for updates...[/cyan]", console=console, spinner="dots"):
        result = update_module.check_all_updates(cfg, force=force)

    # Render detailed update status panel
    update_module.render_update_status_panel(console, result)


@app.command(name="statusline")
@handle_errors
def statusline_cmd(
    install: bool = typer.Option(
        False, "--install", "-i", help="Install the SCC status line script"
    ),
    uninstall: bool = typer.Option(
        False, "--uninstall", help="Remove the status line configuration"
    ),
    show: bool = typer.Option(False, "--show", "-s", help="Show current status line config"),
):
    """Configure Claude Code status line to show git worktree info.

    The status line displays: Model | Git branch/worktree | Context usage | Cost

    Examples:
        scc statusline --install    # Install the SCC status line
        scc statusline --show       # Show current configuration
        scc statusline --uninstall  # Remove status line config
    """
    import importlib.resources
    import json

    claude_dir = Path.home() / ".claude"  # noqa: F841

    if show:
        # Show current configuration from Docker sandbox volume
        with Status(
            "[cyan]Reading Docker sandbox settings...[/cyan]",
            console=console,
            spinner="dots",
        ):
            settings = docker.get_sandbox_settings()

        if settings and "statusLine" in settings:
            console.print(
                create_info_panel(
                    "Status Line Configuration (Docker Sandbox)",
                    f"Script: {settings['statusLine'].get('command', 'Not set')}",
                    "Run 'scc statusline --uninstall' to remove",
                )
            )
        elif settings:
            console.print(
                create_info_panel(
                    "No Status Line",
                    "Status line is not configured in Docker sandbox.",
                    "Run 'scc statusline --install' to set it up",
                )
            )
        else:
            console.print(
                create_info_panel(
                    "No Configuration",
                    "Docker sandbox settings.json does not exist yet.",
                    "Run 'scc statusline --install' to create it",
                )
            )
        return

    if uninstall:
        # Remove status line configuration from Docker sandbox
        with Status(
            "[cyan]Removing statusline from Docker sandbox...[/cyan]",
            console=console,
            spinner="dots",
        ):
            # Get existing settings
            existing_settings = docker.get_sandbox_settings()

            if existing_settings and "statusLine" in existing_settings:
                del existing_settings["statusLine"]
                # Write updated settings back
                docker.inject_file_to_sandbox_volume(
                    "settings.json", json.dumps(existing_settings, indent=2)
                )
                console.print(
                    create_success_panel(
                        "Status Line Removed (Docker Sandbox)",
                        {"Settings": "Updated"},
                    )
                )
            else:
                console.print(
                    create_info_panel(
                        "Nothing to Remove",
                        "Status line was not configured in Docker sandbox.",
                    )
                )
        return

    if install:
        # SCC philosophy: Everything stays in Docker sandbox, not on host
        # Inject statusline script and settings into Docker sandbox volume

        # Get the status line script from package resources
        try:
            template_files = importlib.resources.files("scc_cli.templates")
            script_content = (template_files / "statusline.sh").read_text()
        except (FileNotFoundError, TypeError):
            # Fallback: read from relative path during development
            dev_path = Path(__file__).parent / "templates" / "statusline.sh"
            if dev_path.exists():
                script_content = dev_path.read_text()
            else:
                console.print(
                    create_warning_panel(
                        "Template Not Found",
                        "Could not find statusline.sh template.",
                    )
                )
                raise typer.Exit(1)

        with Status(
            "[cyan]Injecting statusline into Docker sandbox...[/cyan]",
            console=console,
            spinner="dots",
        ):
            # Inject script into Docker volume (will be at /mnt/claude-data/scc-statusline.sh)
            script_ok = docker.inject_file_to_sandbox_volume("scc-statusline.sh", script_content)

            # Get existing settings from Docker volume (if any)
            existing_settings = docker.get_sandbox_settings() or {}

            # Add statusline config (path inside container)
            existing_settings["statusLine"] = {
                "type": "command",
                "command": "/mnt/claude-data/scc-statusline.sh",
                "padding": 0,
            }

            # Inject settings into Docker volume
            settings_ok = docker.inject_file_to_sandbox_volume(
                "settings.json", json.dumps(existing_settings, indent=2)
            )

        if script_ok and settings_ok:
            console.print(
                create_success_panel(
                    "Status Line Installed (Docker Sandbox)",
                    {
                        "Script": "/mnt/claude-data/scc-statusline.sh",
                        "Settings": "/mnt/claude-data/settings.json",
                    },
                )
            )
            console.print()
            console.print(
                "[dim]The status line shows: "
                "[bold]Model[/bold] | [cyan]🌿 branch[/cyan] or [magenta]⎇ worktree[/magenta]:branch | "
                "[green]Ctx %[/green] | [yellow]$cost[/yellow][/dim]"
            )
            console.print("[dim]Restart Claude Code sandbox to see the changes.[/dim]")
        else:
            console.print(
                create_warning_panel(
                    "Installation Failed",
                    "Could not inject statusline into Docker sandbox volume.",
                    "Ensure Docker Desktop is running",
                )
            )
            raise typer.Exit(1)
        return

    # No flags - show help
    console.print(
        create_info_panel(
            "Status Line",
            "Configure a custom status line for Claude Code.",
            "Use --install to set up, --show to view, --uninstall to remove",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
