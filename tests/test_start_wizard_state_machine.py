"""Tests for the start wizard state machine."""

from scc_cli.application.launch.start_wizard import (
    BackRequested,
    CancelRequested,
    QuickResumeDismissed,
    QuickResumeSelected,
    SessionNameEntered,
    StartWizardConfig,
    StartWizardStep,
    TeamSelected,
    WorkspaceSelected,
    WorkspaceSourceChosen,
    WorktreeSelected,
    apply_start_wizard_event,
    initialize_start_wizard,
)


def test_wizard_starts_in_quick_resume() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=True,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)

    assert state.step is StartWizardStep.QUICK_RESUME


def test_wizard_skips_quick_resume_when_disabled() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=True,
        allow_back=False,
    )
    state = initialize_start_wizard(config)

    assert state.step is StartWizardStep.TEAM_SELECTION


def test_quick_resume_selection_completes_flow() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=True,
        team_selection_required=True,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(
        state,
        QuickResumeSelected(workspace="/work", team="team-a", session_name="session"),
    )

    assert state.step is StartWizardStep.COMPLETE
    assert state.context.workspace == "/work"
    assert state.context.team == "team-a"
    assert state.context.session_name == "session"


def test_quick_resume_dismissed_moves_to_team_selection() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=True,
        team_selection_required=True,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, QuickResumeDismissed())

    assert state.step is StartWizardStep.TEAM_SELECTION


def test_team_selection_moves_to_workspace_source() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=True,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, TeamSelected(team="team-a"))

    assert state.step is StartWizardStep.WORKSPACE_SOURCE
    assert state.context.team == "team-a"


def test_workspace_source_moves_to_workspace_picker() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, WorkspaceSourceChosen(source_label="recent"))

    assert state.step is StartWizardStep.WORKSPACE_PICKER


def test_workspace_selected_moves_to_worktree_decision() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, WorkspaceSourceChosen(source_label="recent"))
    state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/work"))

    assert state.step is StartWizardStep.WORKTREE_DECISION
    assert state.context.workspace == "/work"


def test_worktree_selected_moves_to_session_name() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, WorkspaceSourceChosen(source_label="recent"))
    state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/work"))
    state = apply_start_wizard_event(state, WorktreeSelected(worktree_name="feature"))

    assert state.step is StartWizardStep.SESSION_NAME
    assert state.context.worktree_name == "feature"


def test_session_name_completes_flow() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, WorkspaceSourceChosen(source_label="recent"))
    state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/work"))
    state = apply_start_wizard_event(state, WorktreeSelected(worktree_name=None))
    state = apply_start_wizard_event(state, SessionNameEntered(session_name="name"))

    assert state.step is StartWizardStep.COMPLETE
    assert state.context.session_name == "name"


def test_back_request_returns_back_when_allowed() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=True,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, BackRequested())

    assert state.step is StartWizardStep.BACK


def test_back_request_cancels_when_disallowed() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, BackRequested())

    assert state.step is StartWizardStep.CANCELLED


def test_cancel_request_ends_flow() -> None:
    config = StartWizardConfig(
        quick_resume_enabled=False,
        team_selection_required=False,
        allow_back=False,
    )
    state = initialize_start_wizard(config)
    state = apply_start_wizard_event(state, CancelRequested())

    assert state.step is StartWizardStep.CANCELLED
