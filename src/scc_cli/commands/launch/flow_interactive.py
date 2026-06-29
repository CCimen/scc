"""Interactive wizard flows for the launch command.

Extracted from flow.py to reduce module size. Contains:
- interactive_start: guides user through interactive session setup
- run_start_wizard_flow: shared entrypoint for dashboard + CLI wizard
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, cast

from rich.status import Status

from scc_cli.commands.launch.wizard_resume import handle_top_level_quick_resume

from ... import config, setup, teams
from ...application.launch import (
    QuickResumeDismissed,
    StartWizardConfig,
    StartWizardContext,
    StartWizardState,
    StartWizardStep,
    apply_start_wizard_event,
    initialize_start_wizard,
)
from ...application.start_session import StartSessionRequest
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console
from ...panels import create_info_panel
from ...ports.git_client import GitClient
from ...presentation.launch_presenter import build_sync_output_view_model, render_launch_output
from ...services.config_normalizer import normalize_org_config
from ...theme import Colors, Spinners, get_brand_header
from ...ui.chrome import render_with_layout
from ...ui.wizard import BACK
from .completion import (
    PreparedLaunchCompletionDecision,
    PreparedLaunchCompletionRequest,
    complete_prepared_launch,
)
from .dependencies import prepare_live_start_plan
from .flow_types import StartWizardResult, WizardExit, WizardResumeContext
from .preflight import collect_launch_readiness, ensure_launch_ready, resolve_launch_provider
from .render import show_auth_bootstrap_panel
from .team_settings import _configure_team_settings
from .wizard_steps import (
    handle_session_name,
    handle_team_selection,
    handle_workspace_picker,
    handle_workspace_source,
    handle_worktree_decision,
)
from .workspace import prepare_workspace, validate_and_resolve_workspace


class StartWizardFlowDecision(Enum):
    """Structured outcomes from the interactive start wizard."""

    LAUNCHED = auto()
    BACK = auto()
    QUIT = auto()
    CANCELLED = auto()
    KEPT_EXISTING = auto()
    FAILED = auto()


@dataclass(frozen=True)
class StartWizardFlowResult:
    """Result returned from ``run_start_wizard_flow``."""

    decision: StartWizardFlowDecision
    message: str | None = None


def interactive_start(
    cfg: dict[str, Any],
    *,
    skip_quick_resume: bool = False,
    allow_back: bool = False,
    standalone_override: bool = False,
    team_override: str | None = None,
    git_client: GitClient | None = None,
) -> StartWizardResult:
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
            directly to project source selection.
        allow_back: If True, Esc at top level returns BACK sentinel instead
            of None.
        standalone_override: If True, force standalone mode regardless of config.
        team_override: If provided, use this team for filtering instead of
            selected_profile.
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
    standalone_mode = standalone_override or config.is_standalone_mode()

    # Calculate effective_team: --team flag takes precedence over selected_profile
    selected_profile = cfg.get("selected_profile")
    effective_team: str | None = team_override or selected_profile

    # Build display label for UI
    if standalone_mode:
        active_team_label = "standalone"
    elif team_override:
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

    show_all_teams = False
    workspace_base = cfg.get("workspace_base", "~/projects")

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

            resume_context = WizardResumeContext(
                standalone_mode=standalone_mode,
                allow_back=allow_back,
                effective_team=effective_team,
                team_override=team_override,
                active_team_label=active_team_label,
                active_team_context=active_team_context,
                current_branch=current_branch,
            )
            resolution, show_all_teams = handle_top_level_quick_resume(
                state,
                render_context=resume_context,
                show_all_teams=show_all_teams,
            )
            if isinstance(resolution, tuple):
                return resolution
            state = resolution
            continue

        if state.step is StartWizardStep.TEAM_SELECTION:
            team_result = handle_team_selection(
                state=state,
                standalone_mode=standalone_mode,
                standalone_override=standalone_override,
                available_teams=available_teams,
                selected_profile=selected_profile,
                effective_team=effective_team,
            )
            if isinstance(team_result, WizardExit):
                return team_result.result
            state, selected_profile, effective_team = team_result
            continue

        if state.step is StartWizardStep.WORKSPACE_SOURCE:
            source_result = handle_workspace_source(
                state=state,
                cfg=cfg,
                active_team_context=active_team_context,
                standalone_mode=standalone_mode,
                allow_back=allow_back,
                effective_team=effective_team,
                team_override=team_override,
                active_team_label=active_team_label,
                current_branch=current_branch,
                show_all_teams=show_all_teams,
            )
            if isinstance(source_result, WizardExit):
                return source_result.result
            state, show_all_teams = source_result
            continue

        if state.step is StartWizardStep.WORKSPACE_PICKER:
            picker_result = handle_workspace_picker(
                state=state,
                cfg=cfg,
                active_team_context=active_team_context,
                standalone_mode=standalone_mode,
                workspace_base=workspace_base,
                allow_back=allow_back,
                effective_team=effective_team,
                team_override=team_override,
                active_team_label=active_team_label,
                current_branch=current_branch,
                show_all_teams=show_all_teams,
            )
            if isinstance(picker_result, WizardExit):
                return picker_result.result
            state, show_all_teams = picker_result
            continue

        if state.step is StartWizardStep.WORKTREE_DECISION:
            worktree_result = handle_worktree_decision(state)
            if isinstance(worktree_result, WizardExit):
                return worktree_result.result
            state = worktree_result
            continue

        if state.step is StartWizardStep.SESSION_NAME:
            session_result = handle_session_name(state)
            if isinstance(session_result, WizardExit):
                return session_result.result
            state = session_result
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


def run_start_wizard_flow(
    *, skip_quick_resume: bool = False, allow_back: bool = False
) -> StartWizardFlowResult:
    """Run the interactive start wizard and launch sandbox.

    This is the shared entrypoint for starting sessions from both the CLI
    (scc start with no args) and the dashboard (Enter on empty containers).

    Args:
        skip_quick_resume: If True, bypass the Quick Resume picker.
        allow_back: If True, Esc returns BACK sentinel (for dashboard context).

    Returns:
        Structured outcome describing whether launch succeeded, was cancelled,
        kept an existing sandbox, returned to the dashboard, or failed.
    """
    # Step 1: First-run detection
    if setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            return StartWizardFlowResult(
                decision=StartWizardFlowDecision.FAILED,
                message="Start failed",
            )

    cfg = config.load_user_config()
    adapters = get_default_adapters()

    # Step 2: Run interactive wizard
    workspace, team, session_name, worktree_name = interactive_start(
        cfg,
        skip_quick_resume=skip_quick_resume,
        allow_back=allow_back,
        git_client=adapters.git_client,
    )

    # Three-state return handling:
    if workspace is BACK:
        return StartWizardFlowResult(
            decision=StartWizardFlowDecision.BACK,
            message="Start cancelled",
        )
    if workspace is None:
        return StartWizardFlowResult(decision=StartWizardFlowDecision.QUIT)

    workspace_value = cast(str, workspace)

    try:
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()
        workspace_path = validate_and_resolve_workspace(workspace_value)
        workspace_path = prepare_workspace(workspace_path, worktree_name, install_deps=False)
        assert workspace_path is not None
        _configure_team_settings(team, cfg)

        standalone_mode = config.is_standalone_mode() or team is None
        raw_org_config = None
        if team and not standalone_mode:
            raw_org_config = config.load_cached_org_config()

        # D032: resolve provider explicitly — never silent-default to Claude.
        normalized_org = (
            normalize_org_config(raw_org_config) if raw_org_config is not None else None
        )
        resolved_provider, _resolution_source = resolve_launch_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_path=workspace_path,
            config_provider=config.get_selected_provider(),
            normalized_org=normalized_org,
            team=team,
            adapters=adapters,
            non_interactive=False,
        )
        if resolved_provider is None:
            console.print("[dim]Cancelled.[/dim]")
            return StartWizardFlowResult(
                decision=StartWizardFlowDecision.CANCELLED,
                message="Start cancelled",
            )

        # Shared preflight: readiness check before plan construction
        readiness = collect_launch_readiness(resolved_provider, _resolution_source, adapters)
        if not readiness.launch_ready:
            ensure_launch_ready(
                readiness,
                adapters=adapters,
                console=console,
                non_interactive=False,
                show_notice=show_auth_bootstrap_panel,
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
            org_config=normalized_org,
            raw_org_config=raw_org_config,
            provider_id=resolved_provider,
        )
        start_dependencies, start_plan = prepare_live_start_plan(
            start_request,
            adapters=adapters,
            console=console,
            provider_id=resolved_provider,
        )

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

        completion_result = complete_prepared_launch(
            PreparedLaunchCompletionRequest(
                workspace_path=workspace_path,
                team=team,
                session_name=session_name,
                current_branch=current_branch,
                provider_id=resolved_provider,
                start_plan=start_plan,
                dependencies=start_dependencies,
                is_resume=False,
                json_mode=False,
                non_interactive=False,
                record_session=True,
            ),
            console=console,
        )
        if completion_result.decision is PreparedLaunchCompletionDecision.KEPT_EXISTING:
            return StartWizardFlowResult(
                decision=StartWizardFlowDecision.KEPT_EXISTING,
                message=completion_result.message,
            )
        if completion_result.decision is PreparedLaunchCompletionDecision.CANCELLED:
            console.print("[dim]Cancelled.[/dim]")
            return StartWizardFlowResult(
                decision=StartWizardFlowDecision.CANCELLED,
                message=completion_result.message,
            )
        return StartWizardFlowResult(decision=StartWizardFlowDecision.LAUNCHED)
    except Exception as e:
        err_console.print(f"[red]Error launching sandbox: {e}[/red]")
        return StartWizardFlowResult(
            decision=StartWizardFlowDecision.FAILED,
            message="Start failed",
        )
