"""Prompt step handlers for the interactive start wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer

from ... import config, sessions
from ...application.launch import (
    BackRequested,
    CwdContext,
    SessionNameEntered,
    StartWizardState,
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
)
from ...cli_common import console
from ...core.exit_codes import EXIT_CONFIG
from ...panels import create_warning_panel
from ...services import git
from ...services.workspace import has_project_markers, is_suspicious_directory
from ...ui.wizard import (
    BACK,
    StartWizardAction,
    StartWizardAnswerKind,
    _normalize_path,
    render_start_wizard_prompt,
)
from .flow_types import (
    WizardExit,
    WizardResumeContext,
    reset_for_team_switch,
    set_team_context,
)
from .wizard_resume import resolve_workspace_resume

PickerContinue = tuple[StartWizardState, bool]
PickerResult = PickerContinue | WizardExit
TeamSelectionContinue = tuple[StartWizardState, str | None, str | None]
TeamSelectionResult = TeamSelectionContinue | WizardExit
WizardStepResult = StartWizardState | WizardExit


def handle_team_selection(
    *,
    state: StartWizardState,
    standalone_mode: bool,
    standalone_override: bool,
    available_teams: list[dict[str, Any]],
    selected_profile: str | None,
    effective_team: str | None,
) -> TeamSelectionResult:
    """Handle team selection and return updated profile context."""
    if standalone_mode:
        if not standalone_override:
            console.print("[dim]Running in standalone mode (no organization config)[/dim]")
        console.print()
        return (
            apply_start_wizard_event(state, TeamSelected(team=None)),
            selected_profile,
            effective_team,
        )

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
        return WizardExit((None, None, None, None))
    if answer.value is StartWizardAction.SWITCH_TEAM:
        return (
            apply_start_wizard_event(state, BackRequested()),
            selected_profile,
            effective_team,
        )

    selected = cast(dict[str, Any], answer.value)
    team = selected.get("name")
    if team and team != selected_profile:
        config.set_selected_profile(team)
        selected_profile = team
        effective_team = team
    elif team:
        effective_team = team
    return (
        apply_start_wizard_event(state, TeamSelected(team=team)),
        selected_profile,
        effective_team,
    )


def handle_workspace_source(
    *,
    state: StartWizardState,
    cfg: dict[str, Any],
    active_team_context: str,
    standalone_mode: bool,
    allow_back: bool,
    effective_team: str | None,
    team_override: str | None,
    active_team_label: str,
    current_branch: str | None,
    show_all_teams: bool,
) -> PickerResult:
    """Handle workspace source selection step."""
    team_context_label = active_team_context
    if state.context.team:
        team_context_label = f"Team: {state.context.team}"

    team_config = cfg.get("profiles", {}).get(state.context.team, {}) if state.context.team else {}
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
        return WizardExit((None, None, None, None))
    if answer.value is StartWizardAction.SWITCH_TEAM:
        new_state = reset_for_team_switch(state)
        new_state = set_team_context(new_state, team_override)
        return (new_state, show_all_teams)

    if answer.kind is StartWizardAnswerKind.BACK:
        if state.context.team is not None:
            return (apply_start_wizard_event(state, BackRequested()), show_all_teams)
        if allow_back:
            return WizardExit((BACK, None, None, None))
        return WizardExit((None, None, None, None))

    source = cast(WorkspaceSource, answer.value)
    if source is WorkspaceSource.CURRENT_DIR:
        from ...application.workspace import ResolveWorkspaceRequest, resolve_workspace

        context = resolve_workspace(ResolveWorkspaceRequest(cwd=Path.cwd(), workspace_arg=None))
        if context is not None:
            workspace = str(context.workspace_root)
        else:
            workspace = str(Path.cwd())
        resume_ctx = WizardResumeContext(
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
            render_context=resume_ctx,
            show_all_teams=show_all_teams,
        )
        if resume_state is None:
            return (state, show_all_teams)
        if isinstance(resume_state, tuple):
            return WizardExit(resume_state)
        return (resume_state, show_all_teams)

    return (apply_start_wizard_event(state, WorkspaceSourceChosen(source=source)), show_all_teams)


def handle_workspace_picker(
    *,
    state: StartWizardState,
    cfg: dict[str, Any],
    active_team_context: str,
    standalone_mode: bool,
    workspace_base: str,
    allow_back: bool,
    effective_team: str | None,
    team_override: str | None,
    active_team_label: str,
    current_branch: str | None,
    show_all_teams: bool,
) -> PickerResult:
    """Handle workspace picker step."""
    team_context_label = active_team_context
    if state.context.team:
        team_context_label = f"Team: {state.context.team}"

    team_config = cfg.get("profiles", {}).get(state.context.team, {}) if state.context.team else {}
    team_repos = team_config.get("repositories", [])
    workspace_source = state.context.workspace_source

    resume_ctx = WizardResumeContext(
        standalone_mode=standalone_mode,
        allow_back=allow_back,
        effective_team=effective_team,
        team_override=team_override,
        active_team_label=active_team_label,
        active_team_context=active_team_context,
        current_branch=current_branch,
    )

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
            return WizardExit((None, None, None, None))
        if answer.value is StartWizardAction.SWITCH_TEAM:
            return (reset_for_team_switch(state), show_all_teams)
        if answer.kind is StartWizardAnswerKind.BACK:
            return (apply_start_wizard_event(state, BackRequested()), show_all_teams)
        workspace = cast(str, answer.value)

    elif workspace_source is WorkspaceSource.TEAM_REPOS:
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
            return WizardExit((None, None, None, None))
        if answer.value is StartWizardAction.SWITCH_TEAM:
            return (reset_for_team_switch(state), show_all_teams)
        if answer.kind is StartWizardAnswerKind.BACK:
            return (apply_start_wizard_event(state, BackRequested()), show_all_teams)
        workspace = cast(str, answer.value)

    elif workspace_source is WorkspaceSource.CUSTOM:
        prompt = build_custom_workspace_prompt()
        answer = render_start_wizard_prompt(prompt, console=console)
        if answer.kind is StartWizardAnswerKind.BACK:
            return (apply_start_wizard_event(state, BackRequested()), show_all_teams)
        workspace = cast(str, answer.value)

    elif workspace_source is WorkspaceSource.CLONE:
        prompt = build_clone_repo_prompt()
        answer = render_start_wizard_prompt(
            prompt,
            console=console,
            workspace_base=workspace_base,
        )
        if answer.kind is StartWizardAnswerKind.BACK:
            return (apply_start_wizard_event(state, BackRequested()), show_all_teams)
        workspace = cast(str, answer.value)

    else:
        return (state, show_all_teams)

    resume_state, show_all_teams = resolve_workspace_resume(
        state,
        workspace,
        workspace_source=workspace_source or WorkspaceSource.CUSTOM,
        render_context=resume_ctx,
        show_all_teams=show_all_teams,
    )
    if resume_state is None:
        return (state, show_all_teams)
    if isinstance(resume_state, tuple):
        return WizardExit(resume_state)
    return (resume_state, show_all_teams)


def handle_worktree_decision(state: StartWizardState) -> WizardStepResult:
    """Handle optional worktree creation prompt."""
    prompt = build_confirm_worktree_prompt()
    answer = render_start_wizard_prompt(
        prompt,
        console=console,
        allow_back=True,
    )
    if answer.kind is StartWizardAnswerKind.CANCELLED:
        return WizardExit((None, None, None, None))
    if answer.kind is StartWizardAnswerKind.BACK:
        return apply_start_wizard_event(state, BackRequested())

    wants_worktree = cast(bool, answer.value)
    worktree_name: str | None = None
    if wants_worktree:
        prompt = build_worktree_name_prompt()
        answer = render_start_wizard_prompt(prompt, console=console)
        if answer.kind is StartWizardAnswerKind.BACK:
            return apply_start_wizard_event(state, BackRequested())
        worktree_name = cast(str, answer.value)
    return apply_start_wizard_event(state, WorktreeSelected(worktree_name=worktree_name))


def handle_session_name(state: StartWizardState) -> WizardStepResult:
    """Handle optional session-name prompt."""
    prompt = build_session_name_prompt()
    answer = render_start_wizard_prompt(prompt, console=console)
    if answer.kind is StartWizardAnswerKind.CANCELLED:
        return WizardExit((None, None, None, None))
    if answer.kind is StartWizardAnswerKind.BACK:
        return apply_start_wizard_event(state, BackRequested())
    session_name_value = cast(str | None, answer.value)
    return apply_start_wizard_event(
        state,
        SessionNameEntered(session_name=session_name_value),
    )
