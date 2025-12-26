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
from typing import Any, cast

import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.table import Table

from . import config, deps, docker, git, sessions, setup, teams
from . import platform as platform_module
from . import ui_legacy as ui
from .cli_common import (
    MAX_DISPLAY_PATH_LENGTH,
    PATH_TRUNCATE_LENGTH,
    console,
    handle_errors,
)
from .constants import WORKTREE_BRANCH_PREFIX
from .contexts import WorkContext, load_recent_contexts, record_context
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .exit_codes import EXIT_CONFIG
from .json_output import build_envelope
from .kinds import Kind
from .marketplace.sync import SyncError, SyncResult, sync_marketplace_settings
from .output_mode import json_output_mode, print_json, set_pretty_mode
from .panels import create_info_panel, create_success_panel, create_warning_panel
from .ui.picker import (
    QuickResumeResult,
    TeamSwitchRequested,
    pick_context_quick_resume,
)
from .ui.wizard import (
    BACK,
    WorkspaceSource,
    pick_recent_workspace,
    pick_team_repo,
    pick_workspace_source,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions (extracted for maintainability)
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_session_selection(
    workspace: str | None,
    team: str | None,
    resume: bool,
    select: bool,
    cfg: dict[str, Any],
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


def _configure_team_settings(team: str | None, cfg: dict[str, Any]) -> None:
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
                    "Run 'scc team list' to see available profiles",
                )
            )
            raise typer.Exit(1)

        docker.inject_team_settings(team, org_config=org_config)


def _sync_marketplace_settings(
    workspace_path: Path | None,
    team: str | None,
    org_config_url: str | None = None,
) -> SyncResult | None:
    """
    Sync marketplace settings for the workspace.

    Orchestrates the full marketplace pipeline:
    1. Compute effective plugins for team
    2. Materialize required marketplaces
    3. Render and merge settings
    4. Write settings.local.json

    Args:
        workspace_path: Path to the workspace directory.
        team: Selected team profile name.
        org_config_url: URL of the org config (for tracking).

    Returns:
        SyncResult with details, or None if no sync needed.

    Raises:
        typer.Exit: If marketplace sync fails critically.
    """
    if workspace_path is None or team is None:
        return None

    org_config = config.load_cached_org_config()
    if org_config is None:
        return None

    with Status("[cyan]Syncing marketplace settings...[/cyan]", console=console, spinner="dots"):
        try:
            result = sync_marketplace_settings(
                project_dir=workspace_path,
                org_config_data=org_config,
                team_id=team,
                org_config_url=org_config_url,
            )

            # Display any warnings
            if result.warnings:
                console.print()
                for warning in result.warnings:
                    console.print(f"[yellow]{warning}[/yellow]")
                console.print()

            # Log success
            if result.plugins_enabled:
                console.print(
                    f"[green]✓ Enabled {len(result.plugins_enabled)} team plugin(s)[/green]"
                )
            if result.marketplaces_materialized:
                console.print(
                    f"[green]✓ Materialized {len(result.marketplaces_materialized)} marketplace(s)[/green]"
                )

            return result

        except SyncError as e:
            console.print(
                create_warning_panel(
                    "Marketplace Sync Failed",
                    str(e),
                    "Team plugins may not be available. Use --dry-run to diagnose.",
                )
            )
            # Non-fatal: continue without marketplace sync
            return None


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

    # Record session and context
    if workspace_path:
        sessions.record_session(
            workspace=str(workspace_path),
            team=team,
            session_name=session_name,
            container_name=container_name,
            branch=current_branch,
        )
        # Record context for quick resume feature
        # Determine repo root (may be same as workspace for non-worktrees)
        repo_root = git.get_worktree_main_repo(workspace_path) or workspace_path
        worktree_name = workspace_path.name
        context = WorkContext(
            team=team or "base",
            repo_root=repo_root,
            worktree_path=workspace_path,
            worktree_name=worktree_name,
            last_session_id=session_name,
        )
        record_context(context)

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

        # ── Step 6.5: Sync marketplace settings ────────────────────────────────
        _sync_marketplace_settings(workspace_path, team)

    # ── Step 6.6: Handle --dry-run (preview without launching) ────────────────
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


def interactive_start(
    cfg: dict[str, Any], *, skip_quick_resume: bool = False
) -> tuple[str | None, str | None, str | None, str | None]:
    """Guide user through interactive session setup.

    Prompt for team selection, workspace source, optional worktree creation,
    and session naming.

    The flow prioritizes quick resume by showing recent contexts first:
    1. Recent Contexts (quick resume) - if contexts exist and skip_quick_resume=False
    2. Team selection - if no context selected (skipped in standalone mode)
    3. Workspace source selection
    4. Worktree creation (optional)
    5. Session naming (optional)

    Args:
        cfg: Application configuration dictionary containing workspace_base
            and other settings.
        skip_quick_resume: If True, bypass the Quick Resume picker and go
            directly to project source selection. Used when starting from
            dashboard empty states (no_containers, no_sessions) where resume
            doesn't make sense.

    Returns:
        Tuple of (workspace, team, session_name, worktree_name). All values
        may be None if user cancels at any step.
    """
    ui.show_header(console)

    # Determine mode: standalone vs organization
    standalone_mode = config.is_standalone_mode()

    # Get available teams (from org config if available)
    org_config = config.load_cached_org_config()
    available_teams = teams.list_teams(cfg, org_config)

    # Step 0: Recent Contexts (quick resume)
    # Skip when: entering from dashboard empty state (skip_quick_resume=True)
    # User can press 't' to switch teams (raises TeamSwitchRequested → skip to Step 1)
    if not skip_quick_resume:
        recent_contexts = load_recent_contexts(limit=10)
        if recent_contexts:
            try:
                result, selected_context = pick_context_quick_resume(
                    recent_contexts,
                    title="Quick Resume",
                    standalone=standalone_mode,
                )

                match result:
                    case QuickResumeResult.SELECTED:
                        # User pressed Enter - resume selected context
                        if selected_context is not None:
                            return (
                                str(selected_context.worktree_path),
                                selected_context.team,
                                selected_context.last_session_id,
                                None,  # worktree_name - not creating new worktree
                            )

                    case QuickResumeResult.NEW_SESSION:
                        # User pressed Esc - continue with normal wizard flow
                        console.print()

                    case QuickResumeResult.CANCELLED:
                        # User pressed q - cancel entire wizard
                        return (None, None, None, None)

            except TeamSwitchRequested:
                # User pressed 't' - skip to team selection (Step 1)
                console.print()
        else:
            # First-time hint: no recent contexts yet
            console.print(
                "[dim]💡 Tip: Your recent contexts will appear here for quick resume[/dim]"
            )
            console.print()

    # Step 1: Select team (mode-aware handling)
    team: str | None = None

    if standalone_mode:
        # P0.1: Standalone mode - skip team picker entirely
        # Solo devs don't need team selection friction
        console.print("[dim]Running in standalone mode (no organization config)[/dim]")
        console.print()
    elif not available_teams:
        # P0.2: Org mode with no teams configured - exit with clear error
        # Get org URL for context in error message
        user_cfg = config.load_user_config()
        org_source = user_cfg.get("organization_source", {})
        org_url = org_source.get("url", "unknown")

        console.print()
        console.print(
            create_warning_panel(
                "No Teams Configured",
                f"Organization config from: {org_url}\n"
                "No team profiles are defined in this organization.",
                "Contact your admin to add profiles, or use: scc start --standalone",
            )
        )
        console.print()
        raise typer.Exit(EXIT_CONFIG)
    else:
        # Normal flow: org mode with teams available
        team = ui.select_team(console, cfg)

    # Step 2: Select workspace source (with back navigation support)
    # Using new wizard pickers with clean BACK semantics:
    # - Top-level: None = cancel wizard
    # - Sub-screens: BACK = go back, never None
    workspace: str | None = None

    # Check if team has repositories configured
    team_config = cfg.get("profiles", {}).get(team, {}) if team else {}
    team_repos: list[dict[str, Any]] = team_config.get("repositories", [])
    has_team_repos = bool(team_repos)

    while workspace is None:
        # Top-level picker: None = cancel
        source = pick_workspace_source(
            has_team_repos=has_team_repos, team=team, standalone=standalone_mode
        )

        if source is None:
            return None, None, None, None

        if source == WorkspaceSource.RECENT:
            recent = sessions.list_recent(10)
            picker_result = pick_recent_workspace(recent, standalone=standalone_mode)
            if picker_result is BACK:
                continue  # Go back to source picker
            workspace = cast(str, picker_result)  # Type narrowing after BACK check

        elif source == WorkspaceSource.TEAM_REPOS:
            workspace_base = cfg.get("workspace_base", "~/projects")
            picker_result = pick_team_repo(team_repos, workspace_base, standalone=standalone_mode)
            if picker_result is BACK:
                continue  # Go back to source picker
            workspace = cast(str, picker_result)  # Type narrowing after BACK check

        elif source == WorkspaceSource.CUSTOM:
            workspace = ui.prompt_custom_workspace(console)
            # Empty input means go back
            if workspace is None:
                continue

        elif source == WorkspaceSource.CLONE:
            repo_url = ui.prompt_repo_url(console)
            if repo_url:
                workspace = git.clone_repo(repo_url, cfg.get("workspace_base", "~/projects"))
            # Empty URL means go back
            if workspace is None:
                continue

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


def run_start_wizard_flow(*, skip_quick_resume: bool = False) -> bool:
    """Run the interactive start wizard and launch sandbox.

    This is the shared entrypoint for starting sessions from both the CLI
    (scc start with no args) and the dashboard (Enter on empty containers).

    The function runs outside any Rich Live context to avoid nested Live
    conflicts. It handles the complete flow:
    1. Run interactive wizard to get user selections
    2. If user cancels, return False
    3. Otherwise, validate and launch the sandbox

    Args:
        skip_quick_resume: If True, bypass the Quick Resume picker and go
            directly to project source selection. Used when starting from
            dashboard empty states where "resume" doesn't make sense.

    Returns:
        True if sandbox was launched successfully.
        False if user cancelled or an error occurred.
    """
    # Step 1: First-run detection
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            return False

    cfg = config.load_config()

    # Step 2: Run interactive wizard
    workspace, team, session_name, worktree_name = interactive_start(
        cfg, skip_quick_resume=skip_quick_resume
    )

    # User cancelled at some point
    if workspace is None:
        return False

    try:
        # Step 3: Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner="dots"):
            docker.check_docker_available()

        # Step 4: Workspace validation
        workspace_path = _validate_and_resolve_workspace(workspace)

        # Step 5: Workspace preparation (worktree, deps, git safety)
        workspace_path = _prepare_workspace(workspace_path, worktree_name, install_deps=False)

        # Step 6: Team configuration
        _configure_team_settings(team, cfg)

        # Step 6.5: Sync marketplace settings
        _sync_marketplace_settings(workspace_path, team)

        # Step 7: Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Step 8: Launch sandbox (fresh start, not resume)
        _launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=session_name,
            current_branch=current_branch,
            should_continue_session=False,  # Fresh start
            fresh=False,
        )
        return True

    except Exception as e:
        console.print(f"[red]Error launching sandbox: {e}[/red]")
        return False
