#!/usr/bin/env python3
"""
Sundsvalls Kommun - Claude Code CLI

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

from . import config, docker, doctor, git, sessions, setup, teams, ui
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
    name="sundsvalls-claude",
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
    [bold cyan]Sundsvalls Kommun[/bold cyan] - Claude Code Environment Manager

    Safely run Claude Code in Docker sandboxes with team configurations.
    """
    state.debug = debug

    if version:
        try:
            pkg_version = get_installed_version("sundsvalls-claude")
        except PackageNotFoundError:
            pkg_version = "unknown"
        console.print(
            Panel(
                f"[cyan]sundsvalls-claude[/cyan] [dim]v{pkg_version}[/dim]\n"
                "[dim]Safe development environment manager for Claude Code[/dim]",
                border_style="cyan",
            )
        )
        raise typer.Exit()

    # If no command provided and not showing version, invoke start
    if ctx.invoked_subcommand is None:
        ctx.invoke(start)


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

    # Check git safety (handles protected branch warnings)
    if workspace_path and workspace_path.exists():
        git.check_branch_safety(workspace_path, console)

    # Load team profile
    if team:
        with Status(f"[cyan]Loading {team} profile...[/cyan]", console=console, spinner="dots"):
            team_config = teams.fetch_team_config(team, cfg)
            teams.apply_team_config(workspace_path, team_config)

    # Get current branch for container naming
    current_branch = None
    if workspace_path:
        try:
            current_branch = git.get_current_branch(workspace_path)
        except (NotAGitRepoError, OSError):
            # Not a git repo or filesystem error - continue without branch
            pass

    # Get or create container (re-use pattern)
    docker_cmd, is_resume = docker.get_or_create_container(
        workspace=workspace_path,
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

    # Sync mode
    if sync:
        _sync_teams(cfg, team_name)
        return

    # Detail view for specific team
    if team_name:
        _show_team_details(cfg, team_name)
        return

    # List all teams
    available_teams = teams.list_teams(cfg)

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
        tools = ", ".join(team.get("tools", [])) or "-"
        repos = str(len(team.get("repositories", [])))
        rows.append([team["name"], team["description"], tools, repos])

    _render_responsive_table(
        title="Available Team Profiles",
        columns=[
            ("Team", "cyan"),
            ("Description", "white"),
        ],
        rows=rows,
        wide_columns=[
            ("Tools", "yellow"),
            ("Repos", "dim"),
        ],
    )

    console.print("[dim]Use: scc teams <name> for details, scc teams --sync to update[/dim]")


def _show_team_details(cfg: dict, team_name: str) -> None:
    """Display detailed information for a team profile."""
    details = teams.get_team_details(team_name, cfg)

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
    grid.add_row(
        "Tools:",
        ", ".join(details.get("tools", [])) or "[dim]None configured[/dim]",
    )

    repos = details.get("repositories", [])
    if repos:
        repo_names = [r.get("name", r.get("url", "?")) for r in repos[:5]]
        repos_str = ", ".join(repo_names)
        if len(repos) > 5:
            repos_str += f" [dim]+{len(repos) - 5} more[/dim]"
        grid.add_row("Repositories:", repos_str)
    else:
        grid.add_row("Repositories:", "[dim]None configured[/dim]")

    has_settings = bool(details.get("settings"))
    has_claude_md = bool(details.get("claude_md"))
    extras = []
    if has_settings:
        extras.append("settings.json")
    if has_claude_md:
        extras.append("CLAUDE.md")
    grid.add_row("Includes:", ", ".join(extras) if extras else "[dim]No extras[/dim]")

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
):
    """List recent Claude Code sessions."""
    recent = sessions.list_recent(limit)

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


@app.command(name="setup")
@handle_errors
def setup_cmd(
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick setup with defaults"),
    reset: bool = typer.Option(False, "--reset", help="Reset configuration"),
):
    """Run initial setup wizard."""
    if reset:
        setup.reset_setup(console)
        return

    if quick:
        setup.run_quick_setup(console)
    else:
        setup.run_setup(console)


@app.command(name="config")
@handle_errors
def config_cmd(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
):
    """View or edit configuration."""
    if show:
        cfg = config.load_config()
        console.print(
            create_info_panel(
                "Configuration",
                "Current settings loaded from ~/.config/sundsvalls-claude/",
            )
        )
        console.print()
        console.print_json(data=cfg)
    elif edit:
        config.open_in_editor()
    else:
        console.print(
            create_info_panel(
                "Configuration Help",
                "Use --show to view current settings\nUse --edit to modify in your editor",
                "Config location: ~/.config/sundsvalls-claude/config.json",
            )
        )


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
def update_cmd():
    """Check for updates to sundsvalls-claude CLI."""
    from . import update as update_module

    with Status("[cyan]Checking for updates...[/cyan]", console=console, spinner="dots"):
        info = update_module.check_for_updates()

    console.print()

    if info.latest is None:
        console.print(
            create_warning_panel(
                "Check Failed",
                "Could not reach PyPI to check for updates.",
                "Check your internet connection",
            )
        )
        raise typer.Exit(1)

    if info.update_available:
        cmd = update_module.get_update_command(info.install_method)
        console.print(
            create_info_panel(
                "Update Available",
                f"Current: {info.current}\nLatest:  {info.latest}",
                f"Run: {cmd}",
            )
        )
    else:
        console.print(
            create_success_panel(
                "Up to Date",
                {"Version": info.current},
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
