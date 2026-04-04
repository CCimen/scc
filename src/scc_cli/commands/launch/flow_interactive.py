"""Interactive wizard flows for the launch command.

Extracted from flow.py to reduce module size. Contains:
- interactive_start: guides user through interactive session setup
- run_start_wizard_flow: shared entrypoint for dashboard + CLI wizard
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer
from rich.status import Status

from scc_cli.commands.launch.wizard_resume import (
    handle_top_level_quick_resume,
    resolve_workspace_resume,
)

from ... import config, git, sessions, setup, teams
from ...application.launch import (
    BackRequested,
    CwdContext,
    QuickResumeDismissed,
    SessionNameEntered,
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
    apply_start_wizard_event,
    build_clone_repo_prompt,
    build_confirm_worktree_prompt,
    build_custom_workspace_prompt,
    build_session_name_prompt,
    build_team_repo_prompt,
    build_team_selection_prompt,
    build_workspace_picker_prompt,
    build_workspace_source_prompt,
    build_worktree_name_prompt,
    finalize_launch,
    initialize_start_wizard,
)
from ...application.start_session import StartSessionRequest
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console
from ...core.exit_codes import EXIT_CONFIG
from ...panels import create_info_panel, create_warning_panel
from ...ports.config_models import NormalizedOrgConfig
from ...ports.git_client import GitClient
from ...presentation.launch_presenter import build_sync_output_view_model, render_launch_output
from ...services.workspace import has_project_markers, is_suspicious_directory
from ...theme import Colors, Spinners, get_brand_header
from ...ui.chrome import render_with_layout
from ...ui.keys import _BackSentinel
from ...ui.wizard import (
    BACK,
    StartWizardAction,
    StartWizardAnswerKind,
    _normalize_path,
    render_start_wizard_prompt,
)
from .dependencies import prepare_live_start_plan
from .flow_session import _record_session_and_context
from .flow_types import (
    WizardResumeContext,
    reset_for_team_switch,
    set_team_context,
)
from .render import show_launch_panel
from .team_settings import _configure_team_settings
from .workspace import prepare_workspace, validate_and_resolve_workspace


def interactive_start(
    cfg: dict[str, Any],
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
                resume_context = WizardResumeContext(
                    standalone_mode=standalone_mode,
                    allow_back=allow_back,
                    effective_team=effective_team,
                    team_override=team_override,
                    active_team_label=active_team_label,
                    active_team_context=active_team_context,
                    current_branch=current_branch,
                )
                resume_state, show_all_teams = resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CURRENT_DIR,
                    render_context=resume_context,
                    show_all_teams=show_all_teams,
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
                resume_context = WizardResumeContext(
                    standalone_mode=standalone_mode,
                    allow_back=allow_back,
                    effective_team=effective_team,
                    team_override=team_override,
                    active_team_label=active_team_label,
                    active_team_context=active_team_context,
                    current_branch=current_branch,
                )
                resume_state, show_all_teams = resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.RECENT,
                    render_context=resume_context,
                    show_all_teams=show_all_teams,
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
                resume_context = WizardResumeContext(
                    standalone_mode=standalone_mode,
                    allow_back=allow_back,
                    effective_team=effective_team,
                    team_override=team_override,
                    active_team_label=active_team_label,
                    active_team_context=active_team_context,
                    current_branch=current_branch,
                )
                resume_state, show_all_teams = resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.TEAM_REPOS,
                    render_context=resume_context,
                    show_all_teams=show_all_teams,
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
                resume_context = WizardResumeContext(
                    standalone_mode=standalone_mode,
                    allow_back=allow_back,
                    effective_team=effective_team,
                    team_override=team_override,
                    active_team_label=active_team_label,
                    active_team_context=active_team_context,
                    current_branch=current_branch,
                )
                resume_state, show_all_teams = resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CUSTOM,
                    render_context=resume_context,
                    show_all_teams=show_all_teams,
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
                resume_context = WizardResumeContext(
                    standalone_mode=standalone_mode,
                    allow_back=allow_back,
                    effective_team=effective_team,
                    team_override=team_override,
                    active_team_label=active_team_label,
                    active_team_context=active_team_context,
                    current_branch=current_branch,
                )
                resume_state, show_all_teams = resolve_workspace_resume(
                    state,
                    workspace,
                    workspace_source=WorkspaceSource.CLONE,
                    render_context=resume_context,
                    show_all_teams=show_all_teams,
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


def run_start_wizard_flow(
    *, skip_quick_resume: bool = False, allow_back: bool = False
) -> bool | None:
    """Run the interactive start wizard and launch sandbox.

    This is the shared entrypoint for starting sessions from both the CLI
    (scc start with no args) and the dashboard (Enter on empty containers).

    Args:
        skip_quick_resume: If True, bypass the Quick Resume picker.
        allow_back: If True, Esc returns BACK sentinel (for dashboard context).

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
    workspace, team, session_name, worktree_name = interactive_start(
        cfg,
        skip_quick_resume=skip_quick_resume,
        allow_back=allow_back,
        git_client=adapters.git_client,
    )

    # Three-state return handling:
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
        raw_org_config = None
        if team and not standalone_mode:
            raw_org_config = config.load_cached_org_config()

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
            org_config=NormalizedOrgConfig.from_dict(raw_org_config) if raw_org_config is not None else None,
            raw_org_config=raw_org_config,
        )
        start_dependencies, start_plan = prepare_live_start_plan(
            start_request,
            adapters=adapters,
            console=console,
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
