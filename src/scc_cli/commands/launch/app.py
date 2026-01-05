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
from rich.prompt import Prompt
from rich.status import Status

from ... import config, docker, git, sessions, setup, teams
from ...cli_common import (
    console,
    err_console,
    handle_errors,
)
from ...confirm import Confirm
from ...contexts import load_recent_contexts, normalize_path
from ...core.errors import WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_ERROR, EXIT_USAGE
from ...json_output import build_envelope
from ...kinds import Kind
from ...marketplace.sync import SyncError, SyncResult, sync_marketplace_settings
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_warning_panel
from ...theme import Colors, Indicators, Spinners, get_brand_header
from ...ui.gate import is_interactive_allowed
from ...ui.picker import (
    QuickResumeResult,
    TeamSwitchRequested,
    pick_context_quick_resume,
)
from ...ui.prompts import (
    prompt_custom_workspace,
    prompt_repo_url,
    select_session,
    select_team,
)
from ...ui.wizard import (
    BACK,
    WorkspaceSource,
    pick_recent_workspace,
    pick_team_repo,
    pick_workspace_source,
)
from .render import (
    build_dry_run_data,
    show_dry_run_panel,
    warn_if_non_worktree,
)
from .sandbox import launch_sandbox
from .workspace import (
    prepare_workspace,
    resolve_mount_and_branch,
    resolve_workspace_team,
    validate_and_resolve_workspace,
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
    dry_run: bool = False,
) -> tuple[str | None, str | None, str | None, str | None, bool, bool]:
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
        Tuple of (workspace, team, session_name, worktree_name, cancelled, was_auto_detected)
        If user cancels or no session found, workspace will be None.
        cancelled is True only for explicit user cancellation.
        was_auto_detected is True if workspace was found via resolver (git/.scc.yaml).

    Raises:
        typer.Exit: If interactive mode required but not allowed (non-TTY, CI, --json).
    """
    session_name = None
    worktree_name = None
    cancelled = False

    # Interactive mode if no workspace provided and no session flags
    if workspace is None and not resume and not select:
        # For --dry-run without workspace, use resolver to auto-detect (skip interactive)
        if dry_run:
            from pathlib import Path

            from ...services.workspace import resolve_launch_context

            result = resolve_launch_context(Path.cwd(), workspace_arg=None)
            if result is not None:
                return str(result.workspace_root), team, None, None, False, True  # auto-detected
            # No auto-detect possible, fall through to error
            err_console.print(
                "[red]Error:[/red] No workspace could be auto-detected.\n"
                "[dim]Provide a workspace path: scc start --dry-run /path/to/project[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_USAGE)

        # Check TTY gating before entering interactive mode
        if not is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=no_interactive,
        ):
            # Try auto-detect before failing
            from pathlib import Path

            from ...services.workspace import resolve_launch_context

            result = resolve_launch_context(Path.cwd(), workspace_arg=None)
            if result is not None:
                return str(result.workspace_root), team, None, None, False, True  # auto-detected

            err_console.print(
                "[red]Error:[/red] Interactive mode requires a terminal (TTY).\n"
                "[dim]Provide a workspace path: scc start /path/to/project[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_USAGE)
        workspace, team, session_name, worktree_name = interactive_start(
            cfg, standalone_override=standalone_override
        )
        if workspace is None:
            return None, team, None, None, True, False
        return workspace, team, session_name, worktree_name, False, False  # user picked

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
            return None, team, None, None, False, False
        selected = select_session(console, recent_sessions)
        if selected is None:
            return None, team, None, None, True, False
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
            return None, team, None, None, False, False

    return workspace, team, session_name, worktree_name, cancelled, False  # explicit workspace


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


# ─────────────────────────────────────────────────────────────────────────────
# Launch App
# ─────────────────────────────────────────────────────────────────────────────

launch_app = typer.Typer(
    name="launch",
    help="Start Claude Code in sandboxes.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
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
    continue_session: bool = typer.Option(False, "-c", "--continue", hidden=True),
    worktree_name: str | None = typer.Option(None, "-w", "--worktree", help="Worktree name"),
    fresh: bool = typer.Option(False, "--fresh", help="Force new container"),
    install_deps: bool = typer.Option(False, "--install-deps", help="Install dependencies"),
    offline: bool = typer.Option(False, "--offline", help="Use cached config only (error if none)"),
    standalone: bool = typer.Option(False, "--standalone", help="Run without organization config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview config without launching"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--no-interactive",
        help="Fail fast if interactive input would be required",
    ),
    allow_suspicious_workspace: bool = typer.Option(
        False,
        "--allow-suspicious-workspace",
        help="Allow starting in suspicious directories (e.g., home, /tmp) in non-interactive mode",
    ),
) -> None:
    """
    Start Claude Code in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    from pathlib import Path

    # Capture original CWD for entry_dir tracking (before any directory changes)
    original_cwd = Path.cwd()

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
            err_console.print(
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
    workspace, team, session_name, worktree_name, cancelled, was_auto_detected = (
        _resolve_session_selection(
            workspace=workspace,
            team=team,
            resume=resume,
            select=select,
            cfg=cfg,
            json_mode=(json_output or pretty),
            standalone_override=standalone,
            no_interactive=non_interactive,
            dry_run=dry_run,
        )
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
    # Skip Docker check for dry-run (just previewing config)
    if not dry_run:
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()

    # ── Step 4: Workspace validation and platform checks ─────────────────────
    workspace_path = validate_and_resolve_workspace(
        workspace,
        no_interactive=non_interactive,
        allow_suspicious=allow_suspicious_workspace,
        json_mode=(json_output or pretty),
    )
    if workspace_path is None:
        if not json_output and not pretty:
            console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(EXIT_CANCELLED)
    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # ── Step 5: Workspace preparation (worktree, deps, git safety) ───────────
    # Skip for dry-run (no worktree creation, no deps, no branch safety prompts)
    if not dry_run:
        workspace_path = prepare_workspace(workspace_path, worktree_name, install_deps)

    # ── Step 5.5: Resolve team from workspace pinning ────────────────────────
    team = resolve_workspace_team(
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

    # ── Step 6.6: Resolve mount path for worktrees (needed for dry-run too) ────
    # At this point workspace_path is guaranteed to exist (validated above)
    assert workspace_path is not None
    mount_path, current_branch = resolve_mount_and_branch(
        workspace_path, json_mode=(json_output or pretty)
    )

    # ── Step 6.7: Handle --dry-run (preview without launching) ────────────────
    if dry_run:
        # Use resolver for consistent ED/MR/CW (single source of truth)
        from ...services.workspace import resolve_launch_context

        # Pass None for workspace_arg if auto-detected (resolver finds it again)
        # Pass explicit path if user provided one (preserves their intent)
        workspace_arg = None if was_auto_detected else str(workspace_path)
        result = resolve_launch_context(
            original_cwd, workspace_arg, allow_suspicious=allow_suspicious_workspace
        )
        # Workspace already validated, resolver must succeed
        assert result is not None, f"Resolver failed for validated workspace: {workspace_path}"

        org_config = config.load_cached_org_config()
        dry_run_data = build_dry_run_data(
            workspace_path=workspace_path,
            team=team,
            org_config=org_config,
            project_config=None,
            entry_dir=result.entry_dir,
            mount_root=result.mount_root,
            container_workdir=result.container_workdir,
            resolution_reason=result.reason,
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
            show_dry_run_panel(dry_run_data)

        raise typer.Exit(0)

    warn_if_non_worktree(workspace_path, json_mode=(json_output or pretty))

    # ── Step 8: Launch sandbox ───────────────────────────────────────────────
    should_continue_session = resume or continue_session
    launch_sandbox(
        workspace_path=workspace_path,
        mount_path=mount_path,
        team=team,
        session_name=session_name,
        current_branch=current_branch,
        should_continue_session=should_continue_session,
        fresh=fresh,
    )


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
        workspace_path = Path(workspace)
        can_create_worktree = True

        # Check if directory is a git repository
        if not git.is_git_repo(workspace_path):
            console.print()
            if Confirm.ask(
                "[yellow]⚠️ Not a git repository. Initialize git?[/yellow]",
                default=False,
            ):
                if git.init_repo(workspace_path):
                    console.print(
                        f"  [green]{Indicators.get('PASS')}[/green] Initialized git repository"
                    )
                else:
                    err_console.print(
                        f"  [red]{Indicators.get('FAIL')}[/red] Failed to initialize git"
                    )
                    can_create_worktree = False
            else:
                # User declined git init - can't create worktree
                console.print(
                    f"  [dim]{Indicators.get('INFO')}[/dim] "
                    "Skipping worktree (requires git repository)"
                )
                can_create_worktree = False

        # Check if repository has commits (worktree requires at least one)
        if can_create_worktree and git.is_git_repo(workspace_path):
            if not git.has_commits(workspace_path):
                console.print()
                if Confirm.ask(
                    "[yellow]⚠️ Worktree requires initial commit. "
                    "Create empty initial commit?[/yellow]",
                    default=True,
                ):
                    success, error_msg = git.create_empty_initial_commit(workspace_path)
                    if success:
                        console.print(
                            f"  [green]{Indicators.get('PASS')}[/green] Created initial commit"
                        )
                    else:
                        err_console.print(f"  [red]{Indicators.get('FAIL')}[/red] {error_msg}")
                        can_create_worktree = False
                else:
                    # User declined empty commit - can't create worktree
                    console.print(
                        f"  [dim]{Indicators.get('INFO')}[/dim] "
                        "Skipping worktree (requires initial commit)"
                    )
                    can_create_worktree = False

        # Only ask for worktree name if we have a valid git repo with commits
        if can_create_worktree:
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
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()
        workspace_path = validate_and_resolve_workspace(workspace)
        workspace_path = prepare_workspace(workspace_path, worktree_name, install_deps=False)
        _configure_team_settings(team, cfg)
        _sync_marketplace_settings(workspace_path, team)
        mount_path, current_branch = resolve_mount_and_branch(workspace_path)
        launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=session_name,
            current_branch=current_branch,
            should_continue_session=False,
            fresh=False,
        )
        return True
    except Exception as e:
        err_console.print(f"[red]Error launching sandbox: {e}[/red]")
        return False
