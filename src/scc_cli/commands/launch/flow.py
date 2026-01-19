"""
Launch flow helpers for the start command.

This module contains the core logic for starting sessions, interactive
launch flows, and dashboard entrypoints. The CLI wrapper in app.py should
stay thin and delegate to these functions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import typer
from rich.status import Status

from ... import config, git, sessions, setup, teams
from ...application.launch import (
    ApplyPersonalProfileConfirmation,
    ApplyPersonalProfileDependencies,
    ApplyPersonalProfileRequest,
    ApplyPersonalProfileResult,
    BackRequested,
    CwdContext,
    QuickResumeDismissed,
    QuickResumeViewModel,
    SelectSessionDependencies,
    SelectSessionRequest,
    SelectSessionResult,
    SessionNameEntered,
    SessionSelectionItem,
    SessionSelectionMode,
    SessionSelectionPrompt,
    SessionSelectionWarningOutcome,
    StartWizardConfig,
    StartWizardContext,
    StartWizardState,
    StartWizardStep,
    TeamOption,
    TeamRepoPickerViewModel,
    TeamSelected,
    TeamSelectionViewModel,
    WorkspacePickerViewModel,
    WorkspaceSource,
    WorkspaceSourceChosen,
    WorkspaceSourceViewModel,
    WorkspaceSummary,
    WorktreeSelected,
    apply_personal_profile,
    apply_start_wizard_event,
    build_clone_repo_prompt,
    build_confirm_worktree_prompt,
    build_cross_team_resume_prompt,
    build_custom_workspace_prompt,
    build_quick_resume_prompt,
    build_session_name_prompt,
    build_team_repo_prompt,
    build_team_selection_prompt,
    build_workspace_picker_prompt,
    build_workspace_source_prompt,
    build_worktree_name_prompt,
    finalize_launch,
    initialize_start_wizard,
    prepare_launch_plan,
    select_session,
)
from ...application.sessions import SessionService
from ...application.start_session import StartSessionDependencies, StartSessionRequest
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console
from ...contexts import WorkContext, load_recent_contexts, normalize_path, record_context
from ...core.errors import WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_ERROR, EXIT_USAGE
from ...marketplace.materialize import materialize_marketplace
from ...marketplace.resolve import resolve_effective_config
from ...output_mode import json_output_mode, print_human, print_json, set_pretty_mode
from ...panels import create_info_panel, create_warning_panel
from ...ports.git_client import GitClient
from ...ports.personal_profile_service import PersonalProfileService
from ...presentation.json.launch_json import build_start_dry_run_envelope
from ...presentation.launch_presenter import build_sync_output_view_model, render_launch_output
from ...services.workspace import has_project_markers, is_suspicious_directory
from ...theme import Colors, Spinners, get_brand_header
from ...ui.chrome import print_with_layout, render_with_layout
from ...ui.gate import is_interactive_allowed
from ...ui.keys import _BackSentinel
from ...ui.picker import pick_session
from ...ui.prompts import confirm_with_layout
from ...ui.wizard import (
    BACK,
    StartWizardAction,
    StartWizardAnswer,
    StartWizardAnswerKind,
    _normalize_path,
    render_start_wizard_prompt,
)
from .flow_types import (
    UserConfig,
    reset_for_team_switch,
    set_team_context,
    set_workspace,
)
from .render import build_dry_run_data, show_dry_run_panel, show_launch_panel, warn_if_non_worktree
from .team_settings import _configure_team_settings
from .workspace import prepare_workspace, resolve_workspace_team, validate_and_resolve_workspace

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions (extracted for maintainability)
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_session_selection(
    workspace: str | None,
    team: str | None,
    resume: bool,
    select: bool,
    cfg: UserConfig,
    *,
    json_mode: bool = False,
    standalone_override: bool = False,
    no_interactive: bool = False,
    dry_run: bool = False,
    session_service: SessionService,
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

    select_dependencies = SelectSessionDependencies(session_service=session_service)

    # Interactive mode if no workspace provided and no session flags
    if workspace is None and not resume and not select:
        # For --dry-run without workspace, use resolver to auto-detect (skip interactive)
        if dry_run:
            from pathlib import Path

            from ...application.workspace import ResolveWorkspaceRequest, resolve_workspace

            context = resolve_workspace(ResolveWorkspaceRequest(cwd=Path.cwd(), workspace_arg=None))
            if context is not None:
                return str(context.workspace_root), team, None, None, False, True  # auto-detected
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

            from ...application.workspace import ResolveWorkspaceRequest, resolve_workspace

            context = resolve_workspace(ResolveWorkspaceRequest(cwd=Path.cwd(), workspace_arg=None))
            if context is not None:
                return str(context.workspace_root), team, None, None, False, True  # auto-detected

            err_console.print(
                "[red]Error:[/red] Interactive mode requires a terminal (TTY).\n"
                "[dim]Provide a workspace path: scc start /path/to/project[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_USAGE)
        adapters = get_default_adapters()
        workspace_result, team, session_name, worktree_name = cast(
            tuple[str | None, str | None, str | None, str | None],
            interactive_start(
                cfg,
                standalone_override=standalone_override,
                team_override=team,
                git_client=adapters.git_client,
            ),
        )
        if workspace_result is None:
            return None, team, None, None, True, False
        return (
            workspace_result,
            team,
            session_name,
            worktree_name,
            False,
            False,
        )

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

        # Prefer explicit --team, then selected_profile for filtering
        effective_team = team or cfg.get("selected_profile")
        if standalone_override:
            effective_team = None

        # If org mode and no active team, require explicit selection
        if effective_team is None and not standalone_override:
            if not json_mode:
                console.print(
                    "[yellow]No active team selected.[/yellow] "
                    "Run 'scc team switch' or pass --team to select."
                )
            return None, team, None, None, False, False

        outcome = select_session(
            SelectSessionRequest(
                mode=SessionSelectionMode.SELECT,
                team=effective_team,
                include_all=False,
                limit=10,
            ),
            dependencies=select_dependencies,
        )

        if isinstance(outcome, SessionSelectionWarningOutcome):
            if not json_mode:
                console.print("[yellow]No recent sessions found.[/yellow]")
            return None, team, None, None, False, False

        if isinstance(outcome, SessionSelectionPrompt):
            selected_item = _prompt_for_session_selection(outcome)
            if selected_item is None:
                return None, team, None, None, True, False
            outcome = select_session(
                SelectSessionRequest(
                    mode=SessionSelectionMode.SELECT,
                    team=effective_team,
                    include_all=False,
                    limit=10,
                    selection=selected_item,
                ),
                dependencies=select_dependencies,
            )

        if isinstance(outcome, SelectSessionResult):
            selected = outcome.session
            workspace = selected.workspace
            if not team:
                team = selected.team
            # --standalone overrides any team from session (standalone means no team)
            if standalone_override:
                team = None
            if not json_mode:
                print_with_layout(console, f"[dim]Selected: {workspace}[/dim]")

    # Handle --resume: auto-select most recent session
    elif resume and workspace is None:
        # Prefer explicit --team, then selected_profile for resume filtering
        effective_team = team or cfg.get("selected_profile")
        if standalone_override:
            effective_team = None

        # If org mode and no active team, require explicit selection
        if effective_team is None and not standalone_override:
            if not json_mode:
                console.print(
                    "[yellow]No active team selected.[/yellow] "
                    "Run 'scc team switch' or pass --team to resume."
                )
            return None, team, None, None, False, False

        outcome = select_session(
            SelectSessionRequest(
                mode=SessionSelectionMode.RESUME,
                team=effective_team,
                include_all=False,
                limit=50,
            ),
            dependencies=select_dependencies,
        )

        if isinstance(outcome, SessionSelectionWarningOutcome):
            if not json_mode:
                console.print("[yellow]No recent sessions found.[/yellow]")
            return None, team, None, None, False, False

        if isinstance(outcome, SelectSessionResult):
            recent_session = outcome.session
            workspace = recent_session.workspace
            if not team:
                team = recent_session.team
            # --standalone overrides any team from session (standalone means no team)
            if standalone_override:
                team = None
            if not json_mode:
                print_with_layout(console, f"[dim]Resuming: {workspace}[/dim]")

    return workspace, team, session_name, worktree_name, cancelled, False  # explicit workspace


def _apply_personal_profile(
    workspace_path: Path,
    *,
    json_mode: bool,
    non_interactive: bool,
    profile_service: PersonalProfileService,
) -> tuple[str | None, bool]:
    """Apply personal profile if available.

    Returns (profile_id, applied).
    """
    request = _build_personal_profile_request(
        workspace_path,
        json_mode=json_mode,
        non_interactive=non_interactive,
        confirm_apply=None,
    )
    dependencies = ApplyPersonalProfileDependencies(profile_service=profile_service)

    while True:
        outcome = apply_personal_profile(request, dependencies=dependencies)
        if isinstance(outcome, ApplyPersonalProfileConfirmation):
            _render_personal_profile_confirmation(outcome, json_mode=json_mode)
            confirm = confirm_with_layout(
                console,
                outcome.request.prompt,
                default=outcome.default_response,
            )
            request = _build_personal_profile_request(
                workspace_path,
                json_mode=json_mode,
                non_interactive=non_interactive,
                confirm_apply=confirm,
            )
            continue

        if isinstance(outcome, ApplyPersonalProfileResult):
            _render_personal_profile_result(outcome, json_mode=json_mode)
            return outcome.profile_id, outcome.applied

        return None, False


def _build_personal_profile_request(
    workspace_path: Path,
    *,
    json_mode: bool,
    non_interactive: bool,
    confirm_apply: bool | None,
) -> ApplyPersonalProfileRequest:
    return ApplyPersonalProfileRequest(
        workspace_path=workspace_path,
        interactive_allowed=is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=non_interactive,
        ),
        confirm_apply=confirm_apply,
    )


def _render_personal_profile_confirmation(
    outcome: ApplyPersonalProfileConfirmation, *, json_mode: bool
) -> None:
    if json_mode:
        return
    if outcome.message:
        console.print(outcome.message)


def _render_personal_profile_result(
    outcome: ApplyPersonalProfileResult, *, json_mode: bool
) -> None:
    if json_mode:
        return
    if outcome.message:
        console.print(outcome.message)


def _prompt_for_session_selection(prompt: SessionSelectionPrompt) -> SessionSelectionItem | None:
    items = [option.value for option in prompt.request.options if option.value is not None]
    if not items:
        return None
    summaries = [item.summary for item in items]
    selected = pick_session(
        summaries,
        title=prompt.request.title,
        subtitle=prompt.request.subtitle,
    )
    if selected is None:
        return None
    try:
        index = summaries.index(selected)
    except ValueError:
        return None
    return items[index]


def _record_session_and_context(
    workspace_path: Path,
    team: str | None,
    session_name: str | None,
    current_branch: str | None,
) -> None:
    """Record session metadata and quick-resume context."""
    sessions.record_session(
        workspace=str(workspace_path),
        team=team,
        session_name=session_name,
        container_name=None,
        branch=current_branch,
    )
    repo_root = git.get_worktree_main_repo(workspace_path) or workspace_path
    worktree_name = workspace_path.name
    context = WorkContext(
        team=team,
        repo_root=repo_root,
        worktree_path=workspace_path,
        worktree_name=worktree_name,
        branch=current_branch,
        last_session_id=session_name,
    )
    try:
        record_context(context)
    except (OSError, ValueError) as exc:
        print_human(
            "[yellow]Warning:[/yellow] Could not save Quick Resume context.",
            highlight=False,
        )
        print_human(f"[dim]{exc}[/dim]", highlight=False)
        logging.debug(f"Failed to record context for Quick Resume: {exc}")
    if team:
        try:
            config.set_workspace_team(str(workspace_path), team)
        except (OSError, ValueError) as exc:
            print_human(
                "[yellow]Warning:[/yellow] Could not save workspace team preference.",
                highlight=False,
            )
            print_human(f"[dim]{exc}[/dim]", highlight=False)
            logging.debug(f"Failed to store workspace team mapping: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Start Command Flow
# ─────────────────────────────────────────────────────────────────────────────


def start(
    workspace: str | None = typer.Argument(None, help="Path to workspace (optional)"),
    team: str | None = typer.Option(None, "-t", "--team", help="Team profile to use"),
    session_name: str | None = typer.Option(None, "--session", help="Session name"),
    resume: bool = typer.Option(False, "-r", "--resume", help="Resume most recent session"),
    select: bool = typer.Option(False, "-s", "--select", help="Select from recent sessions"),
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
    debug: bool = typer.Option(
        False,
        "--debug",
        hidden=True,
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

    if isinstance(debug, bool) and debug:
        err_console.print(
            "[red]Error:[/red] --debug is a global flag and must be placed before the command.",
            highlight=False,
        )
        err_console.print(
            "[dim]Use: scc --debug start <workspace>[/dim]",
            highlight=False,
        )
        err_console.print(
            "[dim]With uv: uv run scc --debug start <workspace>[/dim]",
            highlight=False,
        )
        raise typer.Exit(EXIT_USAGE)

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

    org_config: dict[str, Any] | None = None

    # ── Step 0.5: Handle --offline mode (cache-only, fail fast) ───────────────
    if offline and not standalone:
        # Check if cached org config exists
        org_config = config.load_cached_org_config()
        if org_config is None:
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

    cfg = config.load_user_config()
    adapters = get_default_adapters()
    session_service = sessions.get_session_service(adapters.filesystem)

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
            session_service=session_service,
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
            adapters.sandbox_runtime.ensure_available()

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
    assert workspace_path is not None

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

    if org_config is None and team and not standalone:
        org_config = config.load_cached_org_config()

    if worktree_name:
        was_auto_detected = False

    start_dependencies = StartSessionDependencies(
        filesystem=adapters.filesystem,
        remote_fetcher=adapters.remote_fetcher,
        clock=adapters.clock,
        git_client=adapters.git_client,
        agent_runner=adapters.agent_runner,
        sandbox_runtime=adapters.sandbox_runtime,
        resolve_effective_config=resolve_effective_config,
        materialize_marketplace=materialize_marketplace,
    )
    workspace_arg = None if was_auto_detected else str(workspace_path)
    start_request = StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=workspace_arg,
        entry_dir=original_cwd,
        team=team,
        session_name=session_name,
        resume=resume,
        fresh=fresh,
        offline=offline,
        standalone=standalone,
        dry_run=dry_run,
        allow_suspicious=allow_suspicious_workspace,
        org_config=org_config,
    )
    should_sync = (
        not dry_run
        and not offline
        and not standalone
        and team is not None
        and org_config is not None
    )
    if should_sync:
        with Status(
            "[cyan]Syncing marketplace settings...[/cyan]",
            console=console,
            spinner=Spinners.NETWORK,
        ):
            start_plan = prepare_launch_plan(start_request, dependencies=start_dependencies)
    else:
        start_plan = prepare_launch_plan(start_request, dependencies=start_dependencies)

    output_view_model = build_sync_output_view_model(start_plan)
    render_launch_output(output_view_model, console=console, json_mode=(json_output or pretty))

    # ── Step 6.55: Apply personal profile (local overlay) ─────────────────────
    personal_profile_id = None
    personal_applied = False
    if not dry_run and workspace_path is not None:
        personal_profile_id, personal_applied = _apply_personal_profile(
            workspace_path,
            json_mode=(json_output or pretty),
            non_interactive=non_interactive,
            profile_service=adapters.personal_profile_service,
        )

    # ── Step 6.6: Active stack summary ───────────────────────────────────────
    if not (json_output or pretty) and workspace_path is not None:
        personal_label = "project" if personal_profile_id else "none"
        if personal_profile_id and not personal_applied:
            personal_label = "skipped"
        workspace_label = (
            "overrides"
            if adapters.personal_profile_service.workspace_has_overrides(workspace_path)
            else "none"
        )
        print_with_layout(
            console,
            "[dim]Active stack:[/dim] "
            f"Team: {team or 'standalone'} | "
            f"Personal: {personal_label} | "
            f"Workspace: {workspace_label}",
        )

    # ── Step 6.7: Resolve mount path for worktrees (needed for dry-run too) ────
    # At this point workspace_path is guaranteed to exist (validated above)
    assert workspace_path is not None
    resolver_result = start_plan.resolver_result
    if resolver_result.is_mount_expanded and not (json_output or pretty):
        console.print()
        print_with_layout(
            console,
            create_info_panel(
                "Worktree Detected",
                f"Mounting parent directory for worktree support:\n{resolver_result.mount_root}",
                "Both worktree and main repo will be accessible",
            ),
            constrain=True,
        )
        console.print()
    current_branch = start_plan.current_branch

    # ── Step 6.8: Handle --dry-run (preview without launching) ────────────────
    if dry_run:
        result = start_plan.resolver_result
        org_config_for_dry_run = config.load_cached_org_config()
        dry_run_data = build_dry_run_data(
            workspace_path=workspace_path,
            team=team,
            org_config=org_config_for_dry_run,
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
                    envelope = build_start_dry_run_envelope(dry_run_data)
                    print_json(envelope)
                finally:
                    if pretty:
                        set_pretty_mode(False)
        else:
            show_dry_run_panel(dry_run_data)

        raise typer.Exit(0)

    warn_if_non_worktree(workspace_path, json_mode=(json_output or pretty))

    # ── Step 8: Launch sandbox ───────────────────────────────────────────────
    _record_session_and_context(
        workspace_path,
        team,
        session_name,
        current_branch,
    )
    show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=False,
    )
    finalize_launch(start_plan, dependencies=start_dependencies)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Flow
# ─────────────────────────────────────────────────────────────────────────────


def interactive_start(
    cfg: UserConfig,
    *,
    skip_quick_resume: bool = False,
    allow_back: bool = False,
    standalone_override: bool = False,
    team_override: str | None = None,
    git_client: GitClient | None = None,
) -> tuple[str | _BackSentinel | None, str | None, str | None, str | None]:
    """Guide user through interactive session setup.

    Prompt for team selection, workspace source, optional worktree creation,
    and session naming.

    The flow prioritizes quick resume by showing recent contexts first:
    0. Global Quick Resume - if contexts exist and skip_quick_resume=False
       (filtered by effective_team: --team > selected_profile)
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
    - 'a' at Quick Resume: Toggle between filtered and all-teams view

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
        team_override: If provided, use this team for filtering instead of
            selected_profile. Set by --team CLI flag.
        git_client: Optional git client for branch detection in Quick Resume.

    Returns:
        Tuple of (workspace, team, session_name, worktree_name).
        - Success: (path, team, session, worktree) with path always set
        - Cancel: (None, None, None, None) if user pressed q
        - Back: (BACK, None, None, None) if allow_back and user pressed Esc
    """
    header = get_brand_header()
    header_renderable = render_with_layout(console, header)
    console.print(header_renderable, style=Colors.BRAND)

    # Determine mode: standalone vs organization
    # CLI --standalone flag overrides config setting
    standalone_mode = standalone_override or config.is_standalone_mode()

    # Calculate effective_team: --team flag takes precedence over selected_profile
    # This is the team used for filtering Quick Resume contexts
    selected_profile = cfg.get("selected_profile")
    effective_team: str | None = team_override or selected_profile

    # Build display label for UI
    if standalone_mode:
        active_team_label = "standalone"
    elif team_override:
        # Show that --team flag is active with "(filtered)" indicator
        active_team_label = f"{team_override} (filtered)"
    elif selected_profile:
        active_team_label = selected_profile
    else:
        active_team_label = "none (press 't' to choose)"
    active_team_context = f"Team: {active_team_label}"

    # Get available teams (from org config if available)
    org_config = config.load_cached_org_config()
    available_teams = teams.list_teams(org_config)

    if git_client is None:
        adapters = get_default_adapters()
        git_client = adapters.git_client

    try:
        current_branch = git_client.get_current_branch(Path.cwd())
    except Exception:
        current_branch = None

    has_active_team = team_override is not None or selected_profile is not None
    wizard_config = StartWizardConfig(
        quick_resume_enabled=not skip_quick_resume,
        team_selection_required=not standalone_mode and not has_active_team,
        allow_back=allow_back,
    )
    state = initialize_start_wizard(wizard_config)
    if team_override:
        state = StartWizardState(
            step=state.step,
            context=StartWizardContext(team=team_override),
            config=state.config,
        )

    user_dismissed_quick_resume = False
    show_all_teams = False
    workspace_base = cfg.get("workspace_base", "~/projects")

    def _prompt_workspace_quick_resume(
        workspace: str, *, team: str | None
    ) -> StartWizardAnswer | None:
        if user_dismissed_quick_resume:
            return None

        normalized_workspace = normalize_path(workspace)
        workspace_contexts: list[WorkContext] = []
        team_filter = None if standalone_mode else team if team else "all"
        for ctx in load_recent_contexts(limit=30, team_filter=team_filter):
            if standalone_mode and ctx.team is not None:
                continue
            if ctx.worktree_path == normalized_workspace:
                workspace_contexts.append(ctx)
                continue
            if ctx.repo_root == normalized_workspace:
                workspace_contexts.append(ctx)
                continue
            try:
                if normalized_workspace.is_relative_to(ctx.worktree_path):
                    workspace_contexts.append(ctx)
                    continue
                if normalized_workspace.is_relative_to(ctx.repo_root):
                    workspace_contexts.append(ctx)
            except ValueError:
                pass

        if not workspace_contexts:
            return None

        console.print()
        workspace_show_all_teams = False
        while True:
            displayed_contexts = workspace_contexts
            if workspace_show_all_teams:
                displayed_contexts = []
                for ctx in load_recent_contexts(limit=30, team_filter="all"):
                    if ctx.worktree_path == normalized_workspace:
                        displayed_contexts.append(ctx)
                        continue
                    if ctx.repo_root == normalized_workspace:
                        displayed_contexts.append(ctx)
                        continue
                    try:
                        if normalized_workspace.is_relative_to(ctx.worktree_path):
                            displayed_contexts.append(ctx)
                            continue
                        if normalized_workspace.is_relative_to(ctx.repo_root):
                            displayed_contexts.append(ctx)
                    except ValueError:
                        pass

            qr_subtitle = "Existing sessions found for this workspace"
            if workspace_show_all_teams:
                qr_subtitle = "All teams for this workspace — resuming uses that team's plugins"

            quick_resume_view = QuickResumeViewModel(
                title=f"Resume session in {Path(workspace).name}?",
                subtitle=qr_subtitle,
                context_label="All teams"
                if workspace_show_all_teams
                else f"Team: {team or active_team_label}",
                standalone=standalone_mode,
                effective_team=team or effective_team,
                contexts=displayed_contexts,
                current_branch=current_branch,
            )
            prompt = build_quick_resume_prompt(view_model=quick_resume_view)
            answer = render_start_wizard_prompt(
                prompt,
                console=console,
                allow_back=True,
                standalone=standalone_mode,
                context_label=quick_resume_view.context_label,
                current_branch=current_branch,
                effective_team=team or effective_team,
            )

            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return answer
            if answer.kind is StartWizardAnswerKind.BACK:
                return answer
            if answer.value is StartWizardAction.SWITCH_TEAM:
                # Signal to caller that team switch was requested
                return answer

            if answer.value is StartWizardAction.NEW_SESSION:
                console.print()
                return answer

            if answer.value is StartWizardAction.TOGGLE_ALL_TEAMS:
                if standalone_mode:
                    console.print("[dim]All teams view is unavailable in standalone mode[/dim]")
                    console.print()
                    continue
                workspace_show_all_teams = not workspace_show_all_teams
                continue

            selected_context = cast(WorkContext, answer.value)
            current_team = team or effective_team
            if current_team and selected_context.team and selected_context.team != current_team:
                console.print()
                prompt = build_cross_team_resume_prompt(selected_context.team)
                confirm_answer = render_start_wizard_prompt(prompt, console=console)
                if not bool(confirm_answer.value):
                    continue
            return answer

    def _resolve_workspace_resume(
        state: StartWizardState,
        workspace: str,
        *,
        workspace_source: WorkspaceSource,
    ) -> (
        StartWizardState
        | tuple[str | _BackSentinel | None, str | None, str | None, str | None]
        | None
    ):
        nonlocal show_all_teams

        resume_answer = _prompt_workspace_quick_resume(workspace, team=state.context.team)

        if resume_answer is None:
            return set_workspace(
                state,
                workspace,
                workspace_source,
                standalone_mode=standalone_mode,
                team_override=team_override,
                effective_team=effective_team,
            )

        if resume_answer.kind is StartWizardAnswerKind.CANCELLED:
            return (None, None, None, None)
        if resume_answer.kind is StartWizardAnswerKind.BACK:
            return None

        if resume_answer.value is StartWizardAction.SWITCH_TEAM:
            show_all_teams = False
            reset_state = reset_for_team_switch(state)
            return set_team_context(reset_state, team_override)

        if resume_answer.value is StartWizardAction.NEW_SESSION:
            return set_workspace(
                state,
                workspace,
                workspace_source,
                standalone_mode=standalone_mode,
                team_override=team_override,
                effective_team=effective_team,
            )

        selected_context = cast(WorkContext, resume_answer.value)
        return (
            str(selected_context.worktree_path),
            selected_context.team,
            selected_context.last_session_id,
            None,
        )

    while state.step not in {
        StartWizardStep.COMPLETE,
        StartWizardStep.CANCELLED,
        StartWizardStep.BACK,
    }:
        if state.step is StartWizardStep.QUICK_RESUME:
            if not standalone_mode and not effective_team and available_teams:
                console.print("[dim]Tip: Select a team first to see team-specific sessions[/dim]")
                console.print()
                state = apply_start_wizard_event(state, QuickResumeDismissed())
                continue

            team_filter = "all" if show_all_teams else effective_team
            recent_contexts = load_recent_contexts(limit=10, team_filter=team_filter)
            qr_subtitle: str | None = None
            if show_all_teams:
                qr_context_label = "All teams"
                qr_title = "Quick Resume — All Teams"
                if recent_contexts:
                    qr_subtitle = (
                        "Showing all teams — resuming uses that team's plugins. "
                        "Press 'a' to filter."
                    )
                else:
                    qr_subtitle = "No sessions yet — start fresh"
            else:
                qr_context_label = active_team_context
                qr_title = "Quick Resume"
                if not recent_contexts:
                    all_contexts = load_recent_contexts(limit=10, team_filter="all")
                    team_label = effective_team or "standalone"
                    if all_contexts:
                        qr_subtitle = (
                            f"No sessions yet for {team_label}. Press 'a' to show all teams."
                        )
                    else:
                        qr_subtitle = "No sessions yet — start fresh"

            quick_resume_view = QuickResumeViewModel(
                title=qr_title,
                subtitle=qr_subtitle,
                context_label=qr_context_label,
                standalone=standalone_mode,
                effective_team=effective_team,
                contexts=recent_contexts,
                current_branch=current_branch,
            )
            prompt = build_quick_resume_prompt(view_model=quick_resume_view)
            answer = render_start_wizard_prompt(
                prompt,
                console=console,
                allow_back=allow_back,
                standalone=standalone_mode,
                context_label=qr_context_label,
                current_branch=current_branch,
                effective_team=effective_team,
            )

            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return (None, None, None, None)
            if answer.kind is StartWizardAnswerKind.BACK:
                if allow_back:
                    return (BACK, None, None, None)
                return (None, None, None, None)

            if answer.value is StartWizardAction.SWITCH_TEAM:
                show_all_teams = False
                state = apply_start_wizard_event(state, QuickResumeDismissed())
                state = set_team_context(state, team_override)
                continue

            if answer.value is StartWizardAction.NEW_SESSION:
                console.print()
                state = apply_start_wizard_event(state, QuickResumeDismissed())
                continue

            if answer.value is StartWizardAction.TOGGLE_ALL_TEAMS:
                if standalone_mode:
                    console.print("[dim]All teams view is unavailable in standalone mode[/dim]")
                    console.print()
                    continue
                show_all_teams = not show_all_teams
                continue

            selected_context = cast(WorkContext, answer.value)
            if effective_team and selected_context.team and selected_context.team != effective_team:
                console.print()
                prompt = build_cross_team_resume_prompt(selected_context.team)
                confirm_answer = render_start_wizard_prompt(prompt, console=console)
                if not bool(confirm_answer.value):
                    continue
            return (
                str(selected_context.worktree_path),
                selected_context.team,
                selected_context.last_session_id,
                None,
            )

        if state.step is StartWizardStep.TEAM_SELECTION:
            if standalone_mode:
                if not standalone_override:
                    console.print("[dim]Running in standalone mode (no organization config)[/dim]")
                console.print()
                state = apply_start_wizard_event(state, TeamSelected(team=None))
                continue

            if not available_teams:
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

            team_options = [
                TeamOption(
                    name=option.get("name", ""),
                    description=option.get("description", ""),
                    credential_status=option.get("credential_status"),
                )
                for option in available_teams
            ]
            team_view = TeamSelectionViewModel(
                title="Select Team",
                subtitle=None,
                current_team=str(selected_profile) if selected_profile else None,
                options=team_options,
            )
            prompt = build_team_selection_prompt(view_model=team_view)
            answer = render_start_wizard_prompt(
                prompt,
                console=console,
                available_teams=available_teams,
            )
            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return (None, None, None, None)
            if answer.value is StartWizardAction.SWITCH_TEAM:
                state = apply_start_wizard_event(state, BackRequested())
                continue

            selected = cast(dict[str, Any], answer.value)
            team = selected.get("name")
            if team and team != selected_profile:
                config.set_selected_profile(team)
                selected_profile = team
                effective_team = team
            state = apply_start_wizard_event(state, TeamSelected(team=team))
            continue

        if state.step is StartWizardStep.WORKSPACE_SOURCE:
            team_context_label = active_team_context
            if state.context.team:
                team_context_label = f"Team: {state.context.team}"

            team_config = (
                cfg.get("profiles", {}).get(state.context.team, {}) if state.context.team else {}
            )
            team_repos = team_config.get("repositories", [])

            # Gather current directory context for UI to build options
            # Command layer does I/O via service functions; application layer
            # receives data flags; UI layer builds presentation options
            cwd = Path.cwd()
            cwd_context: CwdContext | None = None
            if not is_suspicious_directory(cwd):
                cwd_context = CwdContext(
                    path=str(cwd),
                    name=cwd.name or str(cwd),
                    is_git=git.is_git_repo(cwd),
                    has_project_markers=has_project_markers(cwd),
                )

            source_view = WorkspaceSourceViewModel(
                title="Where is your project?",
                subtitle="Pick a project source (press 't' to switch team)",
                context_label=team_context_label,
                standalone=standalone_mode,
                allow_back=allow_back or (state.context.team is not None),
                has_team_repos=bool(team_repos),
                cwd_context=cwd_context,
                options=[],
            )
            prompt = build_workspace_source_prompt(view_model=source_view)
            answer = render_start_wizard_prompt(
                prompt,
                console=console,
                team_repos=team_repos,
                allow_back=allow_back or (state.context.team is not None),
                standalone=standalone_mode,
                context_label=team_context_label,
                effective_team=state.context.team or effective_team,
            )

            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return (None, None, None, None)
            if answer.value is StartWizardAction.SWITCH_TEAM:
                state = reset_for_team_switch(state)
                state = set_team_context(state, team_override)
                continue

            if answer.kind is StartWizardAnswerKind.BACK:
                if state.context.team is not None:
                    state = apply_start_wizard_event(state, BackRequested())
                elif allow_back:
                    return (BACK, None, None, None)
                else:
                    return (None, None, None, None)
                continue

            source = cast(WorkspaceSource, answer.value)
            if source is WorkspaceSource.CURRENT_DIR:
                from ...application.workspace import ResolveWorkspaceRequest, resolve_workspace

                context = resolve_workspace(
                    ResolveWorkspaceRequest(cwd=Path.cwd(), workspace_arg=None)
                )
                if context is not None:
                    workspace = str(context.workspace_root)
                else:
                    workspace = str(Path.cwd())
                resume_state = _resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CURRENT_DIR,
                )
                if resume_state is None:
                    continue
                if isinstance(resume_state, tuple):
                    return resume_state
                state = resume_state
                continue

            state = apply_start_wizard_event(state, WorkspaceSourceChosen(source=source))
            continue

        if state.step is StartWizardStep.WORKSPACE_PICKER:
            team_context_label = active_team_context
            if state.context.team:
                team_context_label = f"Team: {state.context.team}"

            team_config = (
                cfg.get("profiles", {}).get(state.context.team, {}) if state.context.team else {}
            )
            team_repos = team_config.get("repositories", [])
            workspace_source = state.context.workspace_source

            if workspace_source is WorkspaceSource.RECENT:
                recent = sessions.list_recent(limit=10, include_all=True)
                summaries = [
                    WorkspaceSummary(
                        label=_normalize_path(session.workspace),
                        description=session.last_used or "",
                        workspace=session.workspace,
                    )
                    for session in recent
                ]
                recent_view_model = WorkspacePickerViewModel(
                    title="Recent Workspaces",
                    subtitle=None,
                    context_label=team_context_label,
                    standalone=standalone_mode,
                    allow_back=True,
                    options=summaries,
                )
                prompt = build_workspace_picker_prompt(view_model=recent_view_model)
                answer = render_start_wizard_prompt(
                    prompt,
                    console=console,
                    recent_sessions=recent,
                    allow_back=True,
                    standalone=standalone_mode,
                    context_label=team_context_label,
                )
                if answer.kind is StartWizardAnswerKind.CANCELLED:
                    return (None, None, None, None)
                if answer.value is StartWizardAction.SWITCH_TEAM:
                    state = reset_for_team_switch(state)
                    continue
                if answer.kind is StartWizardAnswerKind.BACK:
                    state = apply_start_wizard_event(state, BackRequested())
                    continue
                workspace = cast(str, answer.value)
                resume_state = _resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.RECENT,
                )
                if resume_state is None:
                    continue
                if isinstance(resume_state, tuple):
                    return resume_state
                state = resume_state
                continue

            if workspace_source is WorkspaceSource.TEAM_REPOS:
                repo_view_model = TeamRepoPickerViewModel(
                    title="Team Repositories",
                    subtitle=None,
                    context_label=team_context_label,
                    standalone=standalone_mode,
                    allow_back=True,
                    workspace_base=workspace_base,
                    options=[],
                )
                prompt = build_team_repo_prompt(view_model=repo_view_model)
                answer = render_start_wizard_prompt(
                    prompt,
                    console=console,
                    team_repos=team_repos,
                    workspace_base=workspace_base,
                    allow_back=True,
                    standalone=standalone_mode,
                    context_label=team_context_label,
                )
                if answer.kind is StartWizardAnswerKind.CANCELLED:
                    return (None, None, None, None)
                if answer.value is StartWizardAction.SWITCH_TEAM:
                    state = reset_for_team_switch(state)
                    continue
                if answer.kind is StartWizardAnswerKind.BACK:
                    state = apply_start_wizard_event(state, BackRequested())
                    continue
                workspace = cast(str, answer.value)
                resume_state = _resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.TEAM_REPOS,
                )
                if resume_state is None:
                    continue
                if isinstance(resume_state, tuple):
                    return resume_state
                state = resume_state
                continue

            if workspace_source is WorkspaceSource.CUSTOM:
                prompt = build_custom_workspace_prompt()
                answer = render_start_wizard_prompt(prompt, console=console)
                if answer.kind is StartWizardAnswerKind.BACK:
                    state = apply_start_wizard_event(state, BackRequested())
                    continue
                workspace = cast(str, answer.value)
                resume_state = _resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CUSTOM,
                )
                if resume_state is None:
                    continue
                if isinstance(resume_state, tuple):
                    return resume_state
                state = resume_state
                continue

            if workspace_source is WorkspaceSource.CLONE:
                prompt = build_clone_repo_prompt()
                answer = render_start_wizard_prompt(
                    prompt,
                    console=console,
                    workspace_base=workspace_base,
                )
                if answer.kind is StartWizardAnswerKind.BACK:
                    state = apply_start_wizard_event(state, BackRequested())
                    continue
                workspace = cast(str, answer.value)
                resume_state = _resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CLONE,
                )
                if resume_state is None:
                    continue
                if isinstance(resume_state, tuple):
                    return resume_state
                state = resume_state
                continue

        if state.step is StartWizardStep.WORKTREE_DECISION:
            prompt = build_confirm_worktree_prompt()
            answer = render_start_wizard_prompt(
                prompt,
                console=console,
                allow_back=True,
            )
            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return (None, None, None, None)
            if answer.kind is StartWizardAnswerKind.BACK:
                state = apply_start_wizard_event(state, BackRequested())
                continue

            wants_worktree = cast(bool, answer.value)
            worktree_name: str | None = None
            if wants_worktree:
                prompt = build_worktree_name_prompt()
                answer = render_start_wizard_prompt(prompt, console=console)
                if answer.kind is StartWizardAnswerKind.BACK:
                    state = apply_start_wizard_event(state, BackRequested())
                    continue
                worktree_name = cast(str, answer.value)
            state = apply_start_wizard_event(state, WorktreeSelected(worktree_name=worktree_name))
            continue

        if state.step is StartWizardStep.SESSION_NAME:
            prompt = build_session_name_prompt()
            answer = render_start_wizard_prompt(prompt, console=console)
            if answer.kind is StartWizardAnswerKind.CANCELLED:
                return (None, None, None, None)
            if answer.kind is StartWizardAnswerKind.BACK:
                state = apply_start_wizard_event(state, BackRequested())
                continue
            session_name_value = cast(str | None, answer.value)
            state = apply_start_wizard_event(
                state,
                SessionNameEntered(session_name=session_name_value),
            )
            continue

    if state.step is StartWizardStep.BACK:
        return (BACK, None, None, None)
    if state.step is StartWizardStep.CANCELLED:
        return (None, None, None, None)

    if state.context.workspace is None:
        return (None, state.context.team, state.context.session_name, state.context.worktree_name)
    return (
        cast(str, state.context.workspace),
        state.context.team,
        state.context.session_name,
        state.context.worktree_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Wizard entrypoint (dashboard + CLI)
# ─────────────────────────────────────────────────────────────────────────────


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

    cfg = config.load_user_config()
    adapters = get_default_adapters()

    # Step 2: Run interactive wizard
    # Note: standalone_override=False (default) is correct here - dashboard path
    # doesn't have CLI flags, so we rely on config.is_standalone_mode() inside
    # interactive_start() to detect standalone mode from user's config file.
    workspace, team, session_name, worktree_name = interactive_start(
        cfg,
        skip_quick_resume=skip_quick_resume,
        allow_back=allow_back,
        git_client=adapters.git_client,
    )

    # Three-state return handling:
    # - workspace is BACK → user pressed Esc (go back to dashboard)
    # - workspace is None → user pressed q (quit app)
    if workspace is BACK:
        return False  # Go back to dashboard
    if workspace is None:
        return None  # Quit app

    workspace_value = cast(str, workspace)

    try:
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()
        workspace_path = validate_and_resolve_workspace(workspace_value)
        workspace_path = prepare_workspace(workspace_path, worktree_name, install_deps=False)
        assert workspace_path is not None
        _configure_team_settings(team, cfg)

        standalone_mode = config.is_standalone_mode() or team is None
        org_config = None
        if team and not standalone_mode:
            org_config = config.load_cached_org_config()

        start_dependencies = StartSessionDependencies(
            filesystem=adapters.filesystem,
            remote_fetcher=adapters.remote_fetcher,
            clock=adapters.clock,
            git_client=adapters.git_client,
            agent_runner=adapters.agent_runner,
            sandbox_runtime=adapters.sandbox_runtime,
            resolve_effective_config=resolve_effective_config,
            materialize_marketplace=materialize_marketplace,
        )
        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=team,
            session_name=session_name,
            resume=False,
            fresh=False,
            offline=False,
            standalone=standalone_mode,
            dry_run=False,
            allow_suspicious=False,
            org_config=org_config,
        )
        should_sync = team is not None and org_config is not None and not standalone_mode
        if should_sync:
            with Status(
                "[cyan]Syncing marketplace settings...[/cyan]",
                console=console,
                spinner=Spinners.NETWORK,
            ):
                start_plan = prepare_launch_plan(start_request, dependencies=start_dependencies)
        else:
            start_plan = prepare_launch_plan(start_request, dependencies=start_dependencies)

        output_view_model = build_sync_output_view_model(start_plan)
        render_launch_output(output_view_model, console=console, json_mode=False)

        resolver_result = start_plan.resolver_result
        if resolver_result.is_mount_expanded:
            console.print()
            console.print(
                create_info_panel(
                    "Worktree Detected",
                    f"Mounting parent directory for worktree support:\n{resolver_result.mount_root}",
                    "Both worktree and main repo will be accessible",
                )
            )
            console.print()
        current_branch = start_plan.current_branch
        _record_session_and_context(
            workspace_path,
            team,
            session_name,
            current_branch,
        )
        show_launch_panel(
            workspace=workspace_path,
            team=team,
            session_name=session_name,
            branch=current_branch,
            is_resume=False,
        )
        finalize_launch(start_plan, dependencies=start_dependencies)
        return True
    except Exception as e:
        err_console.print(f"[red]Error launching sandbox: {e}[/red]")
        return False
