"""Typed quick-resume helper flows for the interactive start wizard."""

from __future__ import annotations

from pathlib import Path

from ...application.launch import (
    QuickResumeDismissed,
    QuickResumeViewModel,
    StartWizardContext,
    StartWizardState,
    StartWizardStep,
    WorkspaceSource,
    apply_start_wizard_event,
    build_cross_team_resume_prompt,
    build_quick_resume_prompt,
)
from ...cli_common import console
from ...contexts import WorkContext, load_recent_contexts, normalize_path
from ...ui.wizard import (
    BACK,
    StartWizardAction,
    StartWizardAnswer,
    StartWizardAnswerKind,
    render_start_wizard_prompt,
)
from .flow_types import (
    QuickResumeResolution,
    WizardResumeContext,
    WorkspaceResumeResolution,
    filter_contexts_for_workspace,
    reset_for_team_switch,
    set_team_context,
    set_workspace,
)


class ResumeWizardError(ValueError):
    """Raised when a wizard resume helper receives an impossible answer shape."""


def _require_selected_context(answer: StartWizardAnswer) -> WorkContext:
    if answer.kind is not StartWizardAnswerKind.SELECTED or not isinstance(
        answer.value, WorkContext
    ):
        raise ResumeWizardError("Quick resume expected a selected WorkContext answer.")
    return answer.value


def _require_confirmation_value(answer: StartWizardAnswer) -> bool:
    if answer.kind is not StartWizardAnswerKind.SELECTED or not isinstance(answer.value, bool):
        raise ResumeWizardError("Cross-team resume confirmation expected a boolean answer.")
    return answer.value


def _confirm_cross_team_resume(selected_context: WorkContext, *, current_team: str | None) -> bool:
    if (
        current_team is None
        or selected_context.team is None
        or selected_context.team == current_team
    ):
        return True

    console.print()
    prompt = build_cross_team_resume_prompt(selected_context.team)
    confirm_answer = render_start_wizard_prompt(prompt, console=console)
    return _require_confirmation_value(confirm_answer)


def _load_workspace_contexts(
    workspace: Path,
    *,
    team_filter: str | None,
    standalone_mode: bool,
) -> list[WorkContext]:
    contexts = filter_contexts_for_workspace(
        workspace,
        load_recent_contexts(limit=30, team_filter=team_filter),
    )
    if not standalone_mode:
        return contexts
    return [ctx for ctx in contexts if ctx.team is None]


def prompt_workspace_quick_resume(
    workspace: str,
    *,
    team: str | None,
    render_context: WizardResumeContext,
    quick_resume_dismissed: bool = False,
) -> StartWizardAnswer | None:
    """Prompt for quick resume within a selected workspace, if matching contexts exist."""
    if quick_resume_dismissed:
        return None

    normalized_workspace = normalize_path(workspace)
    team_filter = None if render_context.standalone_mode else team if team else "all"
    workspace_contexts = _load_workspace_contexts(
        normalized_workspace,
        team_filter=team_filter,
        standalone_mode=render_context.standalone_mode,
    )
    if not workspace_contexts:
        return None

    console.print()
    workspace_show_all_teams = False
    while True:
        displayed_contexts = workspace_contexts
        if workspace_show_all_teams:
            displayed_contexts = _load_workspace_contexts(
                normalized_workspace,
                team_filter="all",
                standalone_mode=render_context.standalone_mode,
            )

        qr_subtitle = "Existing sessions found for this workspace"
        if workspace_show_all_teams:
            qr_subtitle = "All teams for this workspace — resuming uses that team's plugins"

        quick_resume_view = QuickResumeViewModel(
            title=f"Resume session in {Path(workspace).name}?",
            subtitle=qr_subtitle,
            context_label="All teams"
            if workspace_show_all_teams
            else f"Team: {team or render_context.active_team_label}",
            standalone=render_context.standalone_mode,
            effective_team=team or render_context.effective_team,
            contexts=displayed_contexts,
            current_branch=render_context.current_branch,
        )
        prompt = build_quick_resume_prompt(view_model=quick_resume_view)
        answer = render_start_wizard_prompt(
            prompt,
            console=console,
            allow_back=True,
            standalone=render_context.standalone_mode,
            context_label=quick_resume_view.context_label,
            current_branch=render_context.current_branch,
            effective_team=team or render_context.effective_team,
        )

        if answer.kind in {StartWizardAnswerKind.CANCELLED, StartWizardAnswerKind.BACK}:
            return answer
        if answer.value is StartWizardAction.SWITCH_TEAM:
            return answer
        if answer.value is StartWizardAction.NEW_SESSION:
            console.print()
            return answer
        if answer.value is StartWizardAction.TOGGLE_ALL_TEAMS:
            if render_context.standalone_mode:
                console.print("[dim]All teams view is unavailable in standalone mode[/dim]")
                console.print()
                continue
            workspace_show_all_teams = not workspace_show_all_teams
            continue

        selected_context = _require_selected_context(answer)
        current_team = team or render_context.effective_team
        if not _confirm_cross_team_resume(selected_context, current_team=current_team):
            continue
        return answer


def resolve_workspace_resume(
    state: StartWizardState,
    workspace: str,
    *,
    workspace_source: WorkspaceSource,
    render_context: WizardResumeContext,
    show_all_teams: bool,
    quick_resume_dismissed: bool = False,
) -> tuple[WorkspaceResumeResolution, bool]:
    """Resolve workspace-scoped quick resume and return next state or exit result."""
    resume_answer = prompt_workspace_quick_resume(
        workspace,
        team=state.context.team,
        render_context=render_context,
        quick_resume_dismissed=quick_resume_dismissed,
    )

    if resume_answer is None:
        return (
            set_workspace(
                state,
                workspace,
                workspace_source,
                standalone_mode=render_context.standalone_mode,
                team_override=render_context.team_override,
                effective_team=render_context.effective_team,
            ),
            show_all_teams,
        )

    if resume_answer.kind is StartWizardAnswerKind.CANCELLED:
        return ((None, None, None, None), show_all_teams)
    if resume_answer.kind is StartWizardAnswerKind.BACK:
        return (None, show_all_teams)

    if resume_answer.value is StartWizardAction.SWITCH_TEAM:
        reset_state = reset_for_team_switch(state)
        return (set_team_context(reset_state, render_context.team_override), False)

    if resume_answer.value is StartWizardAction.NEW_SESSION:
        return (
            set_workspace(
                state,
                workspace,
                workspace_source,
                standalone_mode=render_context.standalone_mode,
                team_override=render_context.team_override,
                effective_team=render_context.effective_team,
            ),
            show_all_teams,
        )

    selected_context = _require_selected_context(resume_answer)
    return (
        (
            str(selected_context.worktree_path),
            selected_context.team,
            selected_context.last_session_id,
            None,
        ),
        show_all_teams,
    )


def handle_top_level_quick_resume(
    state: StartWizardState,
    *,
    render_context: WizardResumeContext,
    show_all_teams: bool,
) -> tuple[QuickResumeResolution, bool]:
    """Resolve the top-level quick resume step and return next state or exit result."""
    team_filter = "all" if show_all_teams else render_context.effective_team
    recent_contexts = load_recent_contexts(limit=10, team_filter=team_filter)

    qr_subtitle: str | None = None
    if show_all_teams:
        qr_context_label = "All teams"
        qr_title = "Quick Resume — All Teams"
        if recent_contexts:
            qr_subtitle = (
                "Showing all teams — resuming uses that team's plugins. Press 'a' to filter."
            )
        else:
            qr_subtitle = "No sessions yet — start fresh"
    else:
        qr_context_label = render_context.active_team_context
        qr_title = "Quick Resume"
        if not recent_contexts:
            all_contexts = load_recent_contexts(limit=10, team_filter="all")
            team_label = render_context.effective_team or "standalone"
            if all_contexts:
                qr_subtitle = f"No sessions yet for {team_label}. Press 'a' to show all teams."
            else:
                qr_subtitle = "No sessions yet — start fresh"

    quick_resume_view = QuickResumeViewModel(
        title=qr_title,
        subtitle=qr_subtitle,
        context_label=qr_context_label,
        standalone=render_context.standalone_mode,
        effective_team=render_context.effective_team,
        contexts=recent_contexts,
        current_branch=render_context.current_branch,
    )
    prompt = build_quick_resume_prompt(view_model=quick_resume_view)
    answer = render_start_wizard_prompt(
        prompt,
        console=console,
        allow_back=render_context.allow_back,
        standalone=render_context.standalone_mode,
        context_label=qr_context_label,
        current_branch=render_context.current_branch,
        effective_team=render_context.effective_team,
    )

    if answer.kind is StartWizardAnswerKind.CANCELLED:
        return ((None, None, None, None), show_all_teams)
    if answer.kind is StartWizardAnswerKind.BACK:
        if render_context.allow_back:
            return ((BACK, None, None, None), show_all_teams)
        return ((None, None, None, None), show_all_teams)

    if answer.value is StartWizardAction.SWITCH_TEAM:
        dismissed_state = apply_start_wizard_event(state, QuickResumeDismissed())
        return (
            StartWizardState(
                step=StartWizardStep.TEAM_SELECTION,
                context=StartWizardContext(team=None),
                config=dismissed_state.config,
            ),
            False,
        )

    if answer.value is StartWizardAction.NEW_SESSION:
        console.print()
        return (apply_start_wizard_event(state, QuickResumeDismissed()), show_all_teams)

    if answer.value is StartWizardAction.TOGGLE_ALL_TEAMS:
        if render_context.standalone_mode:
            console.print("[dim]All teams view is unavailable in standalone mode[/dim]")
            console.print()
            return (state, show_all_teams)
        return (state, not show_all_teams)

    selected_context = _require_selected_context(answer)
    if not _confirm_cross_team_resume(selected_context, current_team=render_context.effective_team):
        return (state, show_all_teams)

    return (
        (
            str(selected_context.worktree_path),
            selected_context.team,
            selected_context.last_session_id,
            None,
        ),
        show_all_teams,
    )
