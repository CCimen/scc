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

import sys
from pathlib import Path
from typing import Any, cast

import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.table import Table

from . import config, deps, docker, git, sessions, setup, teams
from . import platform as platform_module
from .cli_common import (
    MAX_DISPLAY_PATH_LENGTH,
    PATH_TRUNCATE_LENGTH,
    console,
    handle_errors,
)
from .constants import WORKTREE_BRANCH_PREFIX
from .contexts import WorkContext, load_recent_contexts, normalize_path, record_context
from .errors import NotAGitRepoError, WorkspaceNotFoundError
from .exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_ERROR, EXIT_USAGE
from .json_output import build_envelope
from .kinds import Kind
from .marketplace.sync import SyncError, SyncResult, sync_marketplace_settings
from .output_mode import json_output_mode, print_human, print_json, set_pretty_mode
from .panels import create_info_panel, create_success_panel, create_warning_panel
from .theme import Colors, Indicators, Spinners, get_brand_header
from .ui.gate import is_interactive_allowed
from .ui.picker import (
    QuickResumeResult,
    TeamSwitchRequested,
    pick_context_quick_resume,
)
from .ui.prompts import (
    prompt_custom_workspace,
    prompt_repo_url,
    select_session,
    select_team,
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
    *,
    json_mode: bool = False,
    standalone_override: bool = False,
    no_interactive: bool = False,
) -> tuple[str | None, str | None, str | None, str | None, bool]:
    """
    Handle session selection logic for --select, --resume, and interactive modes.

    Args:
        workspace: Workspace path from command line.
        team: Team name from command line.
        resume: Whether --resume flag is set.
        select: Whether --select flag is set.
        cfg: Loaded configuration.
        json_mode: Whether --json output is requested (blocks interactive).
        standalone_override: Whether --standalone flag is set (overrides config).

    Returns:
        Tuple of (workspace, team, session_name, worktree_name, cancelled)
        If user cancels or no session found, workspace will be None.
        cancelled is True only for explicit user cancellation.

    Raises:
        typer.Exit: If interactive mode required but not allowed (non-TTY, CI, --json).
    """
    session_name = None
    worktree_name = None
    cancelled = False

    # Interactive mode if no workspace provided and no session flags
    if workspace is None and not resume and not select:
        # Check TTY gating before entering interactive mode
        if not is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=no_interactive,
        ):
            console.print(
                "[red]Error:[/red] Interactive mode requires a terminal (TTY).\n"
                "[dim]Provide a workspace path: scc start /path/to/project[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_USAGE)
        workspace, team, session_name, worktree_name = interactive_start(
            cfg, standalone_override=standalone_override
        )
        if workspace is None:
            return None, team, None, None, True
        return workspace, team, session_name, worktree_name, False

    # Handle --select: interactive session picker
    if select and workspace is None:
        # Check TTY gating before showing session picker
        if not is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=no_interactive,
        ):
            console.print(
                "[red]Error:[/red] --select requires a terminal (TTY).\n"
                "[dim]Use --resume to auto-select most recent session.[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_USAGE)
        recent_sessions = sessions.list_recent(limit=10)
        if not recent_sessions:
            if not json_mode:
                console.print("[yellow]No recent sessions found.[/yellow]")
            return None, team, None, None, False
        selected = select_session(console, recent_sessions)
        if selected is None:
            return None, team, None, None, True
        workspace = selected.get("workspace")
        if not team:
            team = selected.get("team")
        # --standalone overrides any team from session (standalone means no team)
        if standalone_override:
            team = None
        if not json_mode:
            console.print(f"[dim]Selected: {workspace}[/dim]")

    # Handle --resume: auto-select most recent session
    elif resume and workspace is None:
        recent_session = sessions.get_most_recent()
        if recent_session:
            workspace = recent_session.get("workspace")
            if not team:
                team = recent_session.get("team")
            # --standalone overrides any team from session (standalone means no team)
            if standalone_override:
                team = None
            if not json_mode:
                console.print(f"[dim]Resuming: {workspace}[/dim]")
        else:
            if not json_mode:
                console.print("[yellow]No recent sessions found.[/yellow]")
            return None, team, None, None, False

    return workspace, team, session_name, worktree_name, cancelled


def _validate_and_resolve_workspace(
    workspace: str | None, *, no_interactive: bool = False
) -> Path | None:
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
            print_human(
                "[yellow]Warning:[/yellow] Workspace is on the Windows filesystem."
                " Performance may be slow.",
                file=sys.stderr,
                highlight=False,
            )
            if is_interactive_allowed(no_interactive_flag=no_interactive):
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
                    console.print("[dim]Cancelled.[/dim]")
                    raise typer.Exit(EXIT_CANCELLED)

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
        with Status(
            "[cyan]Installing dependencies...[/cyan]", console=console, spinner=Spinners.SETUP
        ):
            success = deps.auto_install_dependencies(workspace_path)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Dependencies installed[/green]")
        else:
            console.print("[yellow]⚠ Could not detect package manager or install failed[/yellow]")

    # Check git safety (handles protected branch warnings)
    if workspace_path.exists():
        git.check_branch_safety(workspace_path, console)

    return workspace_path


def _resolve_workspace_team(
    workspace_path: Path | None,
    team: str | None,
    cfg: dict[str, Any],
    *,
    json_mode: bool = False,
    standalone: bool = False,
    no_interactive: bool = False,
) -> str | None:
    """Resolve team selection using workspace pinning when available.

    Prefers explicit team, then workspace-pinned team, then global selected profile.
    Prompts if pinned team differs from the global profile in interactive mode.
    """
    if standalone or workspace_path is None:
        return team

    if team:
        return team

    pinned_team = config.get_workspace_team_from_config(cfg, workspace_path)
    selected_profile = cfg.get("selected_profile")

    if pinned_team and selected_profile and pinned_team != selected_profile:
        if is_interactive_allowed(json_mode=json_mode, no_interactive_flag=no_interactive):
            message = (
                f"Workspace '{workspace_path}' was last used with team '{pinned_team}'."
                " Use that team for this session?"
            )
            if Confirm.ask(message, default=True):
                return pinned_team
            return selected_profile

        if not json_mode:
            print_human(
                "[yellow]Notice:[/yellow] "
                f"Workspace '{workspace_path}' was last used with team '{pinned_team}'. "
                "Using it. Pass --team to override.",
                file=sys.stderr,
                highlight=False,
            )
        return pinned_team

    if pinned_team:
        return pinned_team

    return selected_profile


def _warn_if_non_worktree(workspace_path: Path | None, *, json_mode: bool = False) -> None:
    """Warn when running from a main repo without a worktree."""
    if json_mode or workspace_path is None:
        return

    if not git.is_git_repo(workspace_path):
        return

    if git.is_worktree(workspace_path):
        return

    print_human(
        "[yellow]Tip:[/yellow] You're working in the main repo. "
        "For isolation, try: scc worktree create . <feature> or "
        "scc start --worktree <feature>",
        file=sys.stderr,
        highlight=False,
    )


def _configure_team_settings(team: str | None, cfg: dict[str, Any]) -> None:
    """
    Validate team profile and inject settings into Docker sandbox.

    IMPORTANT: This function must remain cache-only (no network calls).
    It's called in offline mode where only cached org config is available.
    If you need to add network operations, gate them with an offline check
    or move them to _sync_marketplace_settings() which is already offline-aware.

    Raises:
        typer.Exit: If team profile is not found.
    """
    if not team:
        return

    with Status(
        f"[cyan]Configuring {team} plugin...[/cyan]", console=console, spinner=Spinners.SETUP
    ):
        # load_cached_org_config() reads from local cache only - safe for offline mode
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

    with Status(
        "[cyan]Syncing marketplace settings...[/cyan]", console=console, spinner=Spinners.NETWORK
    ):
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
                    f"[green]{Indicators.get('PASS')} Enabled {len(result.plugins_enabled)} team plugin(s)[/green]"
                )
            if result.marketplaces_materialized:
                console.print(
                    f"[green]{Indicators.get('PASS')} Materialized {len(result.marketplaces_materialized)} marketplace(s)[/green]"
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
    Safety-net policy from org config is extracted and mounted read-only.
    """
    # Load org config for safety-net policy injection
    # This is already cached by _configure_team_settings(), so it's a fast read
    org_config = config.load_cached_org_config()

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
            team=team,  # Keep None for standalone mode (don't use "base")
            repo_root=repo_root,
            worktree_path=workspace_path,
            worktree_name=worktree_name,
            branch=current_branch,  # For Quick Resume branch highlighting
            last_session_id=session_name,
        )
        # Context recording is best-effort - failure should never block sandbox launch
        # (Quick Resume is a convenience feature, not critical path)
        try:
            record_context(context)
        except (OSError, ValueError) as e:
            import logging

            print_human(
                "[yellow]Warning:[/yellow] Could not save Quick Resume context.",
                highlight=False,
            )
            print_human(f"[dim]{e}[/dim]", highlight=False)
            logging.debug(f"Failed to record context for Quick Resume: {e}")

        if team:
            try:
                config.set_workspace_team(str(workspace_path), team)
            except (OSError, ValueError) as e:
                import logging

                print_human(
                    "[yellow]Warning:[/yellow] Could not save workspace team preference.",
                    highlight=False,
                )
                print_human(f"[dim]{e}[/dim]", highlight=False)
                logging.debug(f"Failed to store workspace team mapping: {e}")

    # Show launch info and execute
    _show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=is_resume,
    )

    # Pass org_config for safety-net policy injection (mounted read-only)
    docker.run(docker_cmd, org_config=org_config)


def _extract_container_name(docker_cmd: list[str], is_resume: bool) -> str | None:
    """Extract container name from docker command for session tracking."""
    for idx, arg in enumerate(docker_cmd):
        if arg == "--name" and idx + 1 < len(docker_cmd):
            return docker_cmd[idx + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]

    if is_resume and docker_cmd:
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

    if org_config and team:
        from . import profiles

        workspace_for_project = None if project_config is not None else workspace_path
        effective = profiles.compute_effective_config(
            org_config,
            team,
            project_config=project_config,
            workspace_path=workspace_for_project,
        )

        for plugin in sorted(effective.plugins):
            plugins.append({"name": plugin, "source": "resolved"})

        for blocked in effective.blocked_items:
            if blocked.blocked_by:
                blocked_items.append(f"{blocked.item} (blocked by '{blocked.blocked_by}')")
            else:
                blocked_items.append(blocked.item)

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
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--no-interactive",
        help="Fail fast if interactive input would be required",
    ),
) -> None:
    """
    Start Claude Code in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    # ── Fast Fail: Validate mode flags before any processing ──────────────────
    from scc_cli.ui.gate import validate_mode_flags

    validate_mode_flags(
        json_mode=(json_output or pretty),
        select=select,
    )

    # ── Step 0: Handle --standalone mode (skip org config entirely) ───────────
    if standalone:
        # In standalone mode, never ask for team and never load org config
        team = None
        if not json_output and not pretty:
            console.print("[dim]Running in standalone mode (no organization config)[/dim]")

    # ── Step 0.5: Handle --offline mode (cache-only, fail fast) ───────────────
    if offline and not standalone:
        # Check if cached org config exists
        cached = config.load_cached_org_config()
        if cached is None:
            console.print(
                "[red]Error:[/red] --offline requires cached organization config.\n"
                "[dim]Run 'scc setup' first to cache your org config.[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_CONFIG)
        if not json_output and not pretty:
            console.print("[dim]Using cached organization config (offline mode)[/dim]")

    # ── Step 1: First-run detection ──────────────────────────────────────────
    # Skip setup wizard in standalone mode (no org config needed)
    # Skip in offline mode (can't fetch remote - already validated cache exists)
    if not standalone and not offline and setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            raise typer.Exit(1)

    cfg = config.load_config()

    # Treat --continue as alias for --resume (backward compatibility)
    if continue_session:
        resume = True

    # ── Step 2: Session selection (interactive, --select, --resume) ──────────
    workspace, team, session_name, worktree_name, cancelled = _resolve_session_selection(
        workspace=workspace,
        team=team,
        resume=resume,
        select=select,
        cfg=cfg,
        json_mode=(json_output or pretty),
        standalone_override=standalone,
        no_interactive=non_interactive,
    )
    if workspace is None:
        if cancelled:
            if not json_output and not pretty:
                console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(EXIT_CANCELLED)
        if select or resume:
            raise typer.Exit(EXIT_ERROR)
        raise typer.Exit(EXIT_CANCELLED)

    # ── Step 3: Docker availability check ────────────────────────────────────
    with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
        docker.check_docker_available()

    # ── Step 4: Workspace validation and platform checks ─────────────────────
    workspace_path = _validate_and_resolve_workspace(workspace, no_interactive=non_interactive)
    if workspace_path is None:
        if not json_output and not pretty:
            console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(EXIT_CANCELLED)
    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # ── Step 5: Workspace preparation (worktree, deps, git safety) ───────────
    workspace_path = _prepare_workspace(workspace_path, worktree_name, install_deps)

    # ── Step 5.5: Resolve team from workspace pinning ────────────────────────
    team = _resolve_workspace_team(
        workspace_path,
        team,
        cfg,
        json_mode=(json_output or pretty),
        standalone=standalone,
        no_interactive=non_interactive,
    )

    # ── Step 6: Team configuration ───────────────────────────────────────────
    # Skip team config in standalone mode (no org config to apply)
    # In offline mode, team config still applies from cached org config
    if not dry_run and not standalone:
        _configure_team_settings(team, cfg)

        # ── Step 6.5: Sync marketplace settings ────────────────────────────────
        # Skip sync in offline mode (can't fetch remote data)
        if not offline:
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

    _warn_if_non_worktree(workspace_path, json_mode=(json_output or pretty))

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

    grid.add_row("Team:", team or "standalone")

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
    grid.add_row("Team:", data.get("team") or "standalone")

    # Plugins
    plugins = data.get("plugins", [])
    if plugins:
        plugin_list = ", ".join(p.get("name", "unknown") for p in plugins)
        grid.add_row("Plugins:", plugin_list)
    else:
        grid.add_row("Plugins:", "[dim]none[/dim]")

    # Ready status
    ready = data.get("ready_to_start", True)
    status = (
        f"[green]{Indicators.get('PASS')} Ready to start[/green]"
        if ready
        else f"[red]{Indicators.get('FAIL')} Blocked[/red]"
    )
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
    cfg: dict[str, Any],
    *,
    skip_quick_resume: bool = False,
    allow_back: bool = False,
    standalone_override: bool = False,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Guide user through interactive session setup.

    Prompt for team selection, workspace source, optional worktree creation,
    and session naming.

    The flow prioritizes quick resume by showing recent contexts first:
    0. Global Quick Resume - if contexts exist and skip_quick_resume=False
    1. Team selection - if no context selected (skipped in standalone mode)
    2. Workspace source selection
    2.5. Workspace-scoped Quick Resume - if contexts exist for selected workspace
    3. Worktree creation (optional)
    4. Session naming (optional)

    Navigation Semantics:
    - 'q' anywhere: Quit wizard entirely (returns None)
    - Esc at Step 0: BACK to dashboard (if allow_back) or skip to Step 1
    - Esc at Step 2: Go back to Step 1 (if team exists) or BACK to dashboard
    - Esc at Step 2.5: Go back to Step 2 workspace picker
    - 't' anywhere: Restart at Step 1 (team selection)

    Args:
        cfg: Application configuration dictionary containing workspace_base
            and other settings.
        skip_quick_resume: If True, bypass the Quick Resume picker and go
            directly to project source selection. Used when starting from
            dashboard empty states (no_containers, no_sessions) where resume
            doesn't make sense.
        allow_back: If True, Esc at top level returns BACK sentinel instead
            of None. Used when called from Dashboard to enable return to
            dashboard on Esc.
        standalone_override: If True, force standalone mode regardless of
            config. Used when --standalone CLI flag is passed.

    Returns:
        Tuple of (workspace, team, session_name, worktree_name).
        - Success: (path, team, session, worktree) with path always set
        - Cancel: (None, None, None, None) if user pressed q
        - Back: (BACK, None, None, None) if allow_back and user pressed Esc
    """
    console.print(get_brand_header(), style=Colors.BRAND)

    # Determine mode: standalone vs organization
    # CLI --standalone flag overrides config setting
    standalone_mode = standalone_override or config.is_standalone_mode()

    active_team_label = cfg.get("selected_profile")
    if standalone_mode:
        active_team_label = "standalone"
    elif not active_team_label:
        active_team_label = "none"
    active_team_context = f"Team: {active_team_label}"

    # Get available teams (from org config if available)
    org_config = config.load_cached_org_config()
    available_teams = teams.list_teams(cfg, org_config)

    # Track if user dismissed global Quick Resume (to skip workspace-scoped QR)
    user_dismissed_quick_resume = False

    # Step 0: Global Quick Resume
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
                    context_label=active_team_context,
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

                    case QuickResumeResult.BACK:
                        # User pressed Esc - go back if we can (Dashboard context)
                        if allow_back:
                            return (BACK, None, None, None)  # type: ignore[return-value]
                        # CLI context: no previous screen, treat as cancel
                        return (None, None, None, None)

                    case QuickResumeResult.NEW_SESSION:
                        # User pressed 'n' - continue with normal wizard flow
                        user_dismissed_quick_resume = True
                        console.print()

                    case QuickResumeResult.CANCELLED:
                        # User pressed q - cancel entire wizard
                        return (None, None, None, None)

            except TeamSwitchRequested:
                # User pressed 't' - skip to team selection (Step 1)
                # Reset Quick Resume dismissal so new team's contexts are shown
                user_dismissed_quick_resume = False
                console.print()
        else:
            # First-time hint: no recent contexts yet
            console.print(
                "[dim]💡 Tip: Your recent contexts will appear here for quick resume[/dim]"
            )
            console.print()

    # ─────────────────────────────────────────────────────────────────────────
    # MEGA-LOOP: Wraps Steps 1-2.5 to handle 't' key (TeamSwitchRequested)
    # When user presses 't' anywhere, we restart from Step 1 (team selection)
    # ─────────────────────────────────────────────────────────────────────────
    while True:
        # Step 1: Select team (mode-aware handling)
        team: str | None = None

        if standalone_mode:
            # P0.1: Standalone mode - skip team picker entirely
            # Solo devs don't need team selection friction
            # Only print banner if detected from config (CLI --standalone already printed in start())
            if not standalone_override:
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
            team = select_team(console, cfg)

        # Step 2: Select workspace source (with back navigation support)
        workspace: str | None = None
        team_context_label = active_team_context
        if team:
            team_context_label = f"Team: {team}"

        # Check if team has repositories configured (must be inside mega-loop since team can change)
        team_config = cfg.get("profiles", {}).get(team, {}) if team else {}
        team_repos: list[dict[str, Any]] = team_config.get("repositories", [])
        has_team_repos = bool(team_repos)

        try:
            # Outer loop: allows Step 2.5 to go BACK to Step 2 (workspace picker)
            while True:
                # Step 2: Workspace selection loop
                while workspace is None:
                    # Top-level picker: supports three-state contract
                    source = pick_workspace_source(
                        has_team_repos=has_team_repos,
                        team=team,
                        standalone=standalone_mode,
                        allow_back=allow_back or (team is not None),
                        context_label=team_context_label,
                    )

                    # Handle three-state return contract
                    if source is BACK:
                        if team is not None:
                            # Esc in org mode: go back to Step 1 (team selection)
                            raise TeamSwitchRequested()  # Will be caught by mega-loop
                        elif allow_back:
                            # Esc in standalone mode with allow_back: return to dashboard
                            return (BACK, None, None, None)  # type: ignore[return-value]
                        else:
                            # Esc in standalone CLI mode: cancel wizard
                            return (None, None, None, None)

                    if source is None:
                        # q pressed: quit entirely
                        return (None, None, None, None)

                    if source == WorkspaceSource.CURRENT_DIR:
                        # Detect workspace root from CWD (handles subdirs + worktrees)
                        detected_root, _start_cwd = git.detect_workspace_root(Path.cwd())
                        if detected_root:
                            workspace = str(detected_root)
                        else:
                            # Fall back to CWD if no workspace root detected
                            workspace = str(Path.cwd())

                    elif source == WorkspaceSource.RECENT:
                        recent = sessions.list_recent(10)
                        picker_result = pick_recent_workspace(
                            recent,
                            standalone=standalone_mode,
                            context_label=team_context_label,
                        )
                        if picker_result is None:
                            return (None, None, None, None)  # User pressed q - quit wizard
                        if picker_result is BACK:
                            continue  # User pressed Esc - go back to source picker
                        workspace = cast(str, picker_result)

                    elif source == WorkspaceSource.TEAM_REPOS:
                        workspace_base = cfg.get("workspace_base", "~/projects")
                        picker_result = pick_team_repo(
                            team_repos,
                            workspace_base,
                            standalone=standalone_mode,
                            context_label=team_context_label,
                        )
                        if picker_result is None:
                            return (None, None, None, None)  # User pressed q - quit wizard
                        if picker_result is BACK:
                            continue  # User pressed Esc - go back to source picker
                        workspace = cast(str, picker_result)

                    elif source == WorkspaceSource.CUSTOM:
                        workspace = prompt_custom_workspace(console)
                        # Empty input means go back
                        if workspace is None:
                            continue

                    elif source == WorkspaceSource.CLONE:
                        repo_url = prompt_repo_url(console)
                        if repo_url:
                            workspace = git.clone_repo(
                                repo_url, cfg.get("workspace_base", "~/projects")
                            )
                        # Empty URL means go back
                        if workspace is None:
                            continue

                # ─────────────────────────────────────────────────────────────────
                # Step 2.5: Workspace-scoped Quick Resume
                # After selecting a workspace, check if existing contexts exist
                # and offer to resume one instead of starting fresh
                # ─────────────────────────────────────────────────────────────────
                normalized_workspace = normalize_path(workspace)

                # Smart filter: Match contexts related to this workspace AND team
                workspace_contexts = []
                for ctx in load_recent_contexts(limit=30):
                    # Filter by team in org mode (prevents cross-team resume confusion)
                    if team is not None and ctx.team != team:
                        continue

                    # Case 1: Exact worktree match (fastest check)
                    if ctx.worktree_path == normalized_workspace:
                        workspace_contexts.append(ctx)
                        continue

                    # Case 2: User picked repo root - show all worktree contexts for this repo
                    if ctx.repo_root == normalized_workspace:
                        workspace_contexts.append(ctx)
                        continue

                    # Case 3: User picked a subdir - match if inside a known worktree/repo
                    try:
                        if normalized_workspace.is_relative_to(ctx.worktree_path):
                            workspace_contexts.append(ctx)
                            continue
                        if normalized_workspace.is_relative_to(ctx.repo_root):
                            workspace_contexts.append(ctx)
                    except ValueError:
                        # is_relative_to raises ValueError if paths are on different drives
                        pass

                # Skip workspace-scoped Quick Resume if user already dismissed global Quick Resume
                if workspace_contexts and not user_dismissed_quick_resume:
                    console.print()

                    # Use flag pattern for control flow (avoid continue inside match block)
                    go_back_to_workspace = False

                    result, selected_context = pick_context_quick_resume(
                        workspace_contexts,
                        title=f"Resume session in {Path(workspace).name}?",
                        subtitle="Existing sessions found for this workspace",
                        standalone=standalone_mode,
                        context_label=f"Team: {team or active_team_label}",
                    )
                    # Note: TeamSwitchRequested bubbles up to mega-loop handler

                    match result:
                        case QuickResumeResult.SELECTED:
                            # User wants to resume - return context info immediately
                            if selected_context is not None:
                                return (
                                    str(selected_context.worktree_path),
                                    selected_context.team,
                                    selected_context.last_session_id,
                                    None,  # worktree_name - not creating new worktree
                                )

                        case QuickResumeResult.NEW_SESSION:
                            # User pressed 'n' - continue with fresh session
                            pass  # Fall through to break below

                        case QuickResumeResult.BACK:
                            # User pressed Esc - go back to workspace picker (Step 2)
                            go_back_to_workspace = True

                        case QuickResumeResult.CANCELLED:
                            # User pressed q - cancel entire wizard
                            return (None, None, None, None)

                    # Handle flag-based control flow outside match block
                    if go_back_to_workspace:
                        workspace = None
                        continue  # Continue outer loop to re-enter Step 2

                # No contexts or user dismissed global Quick Resume - proceed to Step 3
                break  # Exit outer loop (Step 2 + 2.5)

        except TeamSwitchRequested:
            # User pressed 't' somewhere - restart at Step 1 (team selection)
            # Reset Quick Resume dismissal so new team's contexts are shown
            user_dismissed_quick_resume = False
            console.print()
            continue  # Continue mega-loop

        # Successfully got a workspace - exit mega-loop
        break

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


def run_start_wizard_flow(
    *, skip_quick_resume: bool = False, allow_back: bool = False
) -> bool | None:
    """Run the interactive start wizard and launch sandbox.

    This is the shared entrypoint for starting sessions from both the CLI
    (scc start with no args) and the dashboard (Enter on empty containers).

    The function runs outside any Rich Live context to avoid nested Live
    conflicts. It handles the complete flow:
    1. Run interactive wizard to get user selections
    2. If user cancels, return False/None
    3. Otherwise, validate and launch the sandbox

    Args:
        skip_quick_resume: If True, bypass the Quick Resume picker and go
            directly to project source selection. Used when starting from
            dashboard empty states where "resume" doesn't make sense.
        allow_back: If True, Esc returns BACK sentinel (for dashboard context).
            If False, Esc returns None (for CLI context).

    Returns:
        True if sandbox was launched successfully.
        False if user pressed Esc to go back (only when allow_back=True).
        None if user pressed q to quit or an error occurred.
    """
    # Step 1: First-run detection
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            return None  # Error during setup

    cfg = config.load_config()

    # Step 2: Run interactive wizard
    # Note: standalone_override=False (default) is correct here - dashboard path
    # doesn't have CLI flags, so we rely on config.is_standalone_mode() inside
    # interactive_start() to detect standalone mode from user's config file.
    workspace, team, session_name, worktree_name = interactive_start(
        cfg, skip_quick_resume=skip_quick_resume, allow_back=allow_back
    )

    # Three-state return handling:
    # - workspace is BACK → user pressed Esc (go back to dashboard)
    # - workspace is None → user pressed q (quit app)
    if workspace is BACK:
        return False  # Go back to dashboard
    if workspace is None:
        return None  # Quit app

    try:
        # Step 3: Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
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
