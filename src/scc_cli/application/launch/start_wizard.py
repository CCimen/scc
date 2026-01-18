"""State machine for the interactive start wizard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StartWizardStep(str, Enum):
    """Explicit steps for the start wizard state machine."""

    QUICK_RESUME = "quick_resume"
    TEAM_SELECTION = "team_selection"
    WORKSPACE_SOURCE = "workspace_source"
    WORKSPACE_PICKER = "workspace_picker"
    WORKTREE_DECISION = "worktree_decision"
    SESSION_NAME = "session_name"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    BACK = "back"


@dataclass(frozen=True)
class StartWizardConfig:
    """Configuration flags for the start wizard state machine.

    Invariants:
        - quick_resume_enabled determines whether the wizard starts in quick resume.
        - team_selection_required determines whether a team step is required.
        - allow_back controls whether BACK is a valid terminal state.

    Args:
        quick_resume_enabled: Whether to start with quick resume.
        team_selection_required: Whether a team selection step is required.
        allow_back: Whether the UI can return a BACK outcome.
    """

    quick_resume_enabled: bool
    team_selection_required: bool
    allow_back: bool


@dataclass(frozen=True)
class StartWizardContext:
    """Captured selections from the start wizard flow.

    Invariants:
        - Values reflect the same selections used by the CLI flow.

    Args:
        team: Selected team, if any.
        workspace: Selected workspace path, if any.
        worktree_name: Selected worktree name, if any.
        session_name: Selected session name, if any.
    """

    team: str | None = None
    workspace: str | None = None
    worktree_name: str | None = None
    session_name: str | None = None


@dataclass(frozen=True)
class StartWizardState:
    """Current state for the start wizard state machine.

    Invariants:
        - step always matches an explicit StartWizardStep.
        - config remains constant for the life of the wizard.

    Args:
        step: Current wizard step.
        context: Captured wizard selections.
        config: Wizard configuration flags.
    """

    step: StartWizardStep
    context: StartWizardContext
    config: StartWizardConfig


@dataclass(frozen=True)
class QuickResumeSelected:
    """Event for selecting a session via quick resume.

    Args:
        workspace: Selected workspace path.
        team: Associated team, if any.
        session_name: Optional session name from the selection.
    """

    workspace: str
    team: str | None
    session_name: str | None


@dataclass(frozen=True)
class QuickResumeDismissed:
    """Event for skipping quick resume to start a new session."""


@dataclass(frozen=True)
class TeamSelected:
    """Event for selecting a team."""

    team: str | None


@dataclass(frozen=True)
class WorkspaceSourceChosen:
    """Event for selecting a workspace source."""

    source_label: str


@dataclass(frozen=True)
class WorkspaceSelected:
    """Event for selecting a workspace."""

    workspace: str


@dataclass(frozen=True)
class WorktreeSelected:
    """Event for selecting a worktree name."""

    worktree_name: str | None


@dataclass(frozen=True)
class SessionNameEntered:
    """Event for entering a session name."""

    session_name: str | None


@dataclass(frozen=True)
class BackRequested:
    """Event for requesting a BACK navigation action."""


@dataclass(frozen=True)
class CancelRequested:
    """Event for cancelling the wizard."""


StartWizardEvent = (
    QuickResumeSelected
    | QuickResumeDismissed
    | TeamSelected
    | WorkspaceSourceChosen
    | WorkspaceSelected
    | WorktreeSelected
    | SessionNameEntered
    | BackRequested
    | CancelRequested
)


def initialize_start_wizard(config: StartWizardConfig) -> StartWizardState:
    """Initialize the start wizard state.

    Invariants:
        - Initial step honors quick resume and team selection requirements.

    Args:
        config: Wizard configuration flags.

    Returns:
        Initial StartWizardState.
    """

    if config.quick_resume_enabled:
        step = StartWizardStep.QUICK_RESUME
    elif config.team_selection_required:
        step = StartWizardStep.TEAM_SELECTION
    else:
        step = StartWizardStep.WORKSPACE_SOURCE
    return StartWizardState(step=step, context=StartWizardContext(), config=config)


def apply_start_wizard_event(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    """Apply an event to the start wizard state machine.

    Invariants:
        - Terminal states remain stable once reached.
        - Transitions are deterministic and side-effect free.

    Args:
        state: Current wizard state.
        event: Event emitted by the UI/command layer.

    Returns:
        Updated StartWizardState after applying the event.

    Raises:
        ValueError: When an event is invalid for the current state.
    """

    if state.step in {
        StartWizardStep.COMPLETE,
        StartWizardStep.CANCELLED,
        StartWizardStep.BACK,
    }:
        return state

    if isinstance(event, CancelRequested):
        return StartWizardState(
            step=StartWizardStep.CANCELLED,
            context=state.context,
            config=state.config,
        )

    if isinstance(event, BackRequested):
        return _handle_back_request(state)

    if state.step is StartWizardStep.QUICK_RESUME:
        return _handle_quick_resume(state, event)
    if state.step is StartWizardStep.TEAM_SELECTION:
        return _handle_team_selection(state, event)
    if state.step is StartWizardStep.WORKSPACE_SOURCE:
        return _handle_workspace_source(state, event)
    if state.step is StartWizardStep.WORKSPACE_PICKER:
        return _handle_workspace_picker(state, event)
    if state.step is StartWizardStep.WORKTREE_DECISION:
        return _handle_worktree_decision(state, event)
    if state.step is StartWizardStep.SESSION_NAME:
        return _handle_session_name(state, event)

    msg = f"Unsupported state: {state.step}"
    raise ValueError(msg)


def _handle_back_request(state: StartWizardState) -> StartWizardState:
    if state.step is StartWizardStep.QUICK_RESUME:
        return _terminal_back_or_cancel(state)
    if state.step is StartWizardStep.TEAM_SELECTION:
        return _terminal_back_or_cancel(state)
    if state.step is StartWizardStep.WORKSPACE_SOURCE:
        if state.config.team_selection_required:
            return StartWizardState(
                step=StartWizardStep.TEAM_SELECTION,
                context=state.context,
                config=state.config,
            )
        return _terminal_back_or_cancel(state)
    if state.step is StartWizardStep.WORKSPACE_PICKER:
        return StartWizardState(
            step=StartWizardStep.WORKSPACE_SOURCE,
            context=state.context,
            config=state.config,
        )
    if state.step is StartWizardStep.WORKTREE_DECISION:
        return StartWizardState(
            step=StartWizardStep.WORKSPACE_PICKER,
            context=state.context,
            config=state.config,
        )
    if state.step is StartWizardStep.SESSION_NAME:
        return StartWizardState(
            step=StartWizardStep.WORKTREE_DECISION,
            context=state.context,
            config=state.config,
        )
    return state


def _handle_quick_resume(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, QuickResumeSelected):
        context = StartWizardContext(
            team=event.team,
            workspace=event.workspace,
            session_name=event.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.COMPLETE,
            context=context,
            config=state.config,
        )
    if isinstance(event, QuickResumeDismissed):
        next_step = (
            StartWizardStep.TEAM_SELECTION
            if state.config.team_selection_required
            else StartWizardStep.WORKSPACE_SOURCE
        )
        return StartWizardState(step=next_step, context=state.context, config=state.config)
    msg = f"Invalid event for quick resume: {event}"
    raise ValueError(msg)


def _handle_team_selection(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, TeamSelected):
        context = StartWizardContext(
            team=event.team,
            workspace=state.context.workspace,
            worktree_name=state.context.worktree_name,
            session_name=state.context.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.WORKSPACE_SOURCE,
            context=context,
            config=state.config,
        )
    msg = f"Invalid event for team selection: {event}"
    raise ValueError(msg)


def _handle_workspace_source(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, WorkspaceSourceChosen):
        return StartWizardState(
            step=StartWizardStep.WORKSPACE_PICKER,
            context=state.context,
            config=state.config,
        )
    msg = f"Invalid event for workspace source: {event}"
    raise ValueError(msg)


def _handle_workspace_picker(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, WorkspaceSelected):
        context = StartWizardContext(
            team=state.context.team,
            workspace=event.workspace,
            worktree_name=state.context.worktree_name,
            session_name=state.context.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.WORKTREE_DECISION,
            context=context,
            config=state.config,
        )
    msg = f"Invalid event for workspace picker: {event}"
    raise ValueError(msg)


def _handle_worktree_decision(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, WorktreeSelected):
        context = StartWizardContext(
            team=state.context.team,
            workspace=state.context.workspace,
            worktree_name=event.worktree_name,
            session_name=state.context.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.SESSION_NAME,
            context=context,
            config=state.config,
        )
    msg = f"Invalid event for worktree decision: {event}"
    raise ValueError(msg)


def _handle_session_name(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, SessionNameEntered):
        context = StartWizardContext(
            team=state.context.team,
            workspace=state.context.workspace,
            worktree_name=state.context.worktree_name,
            session_name=event.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.COMPLETE,
            context=context,
            config=state.config,
        )
    msg = f"Invalid event for session name: {event}"
    raise ValueError(msg)


def _terminal_back_or_cancel(state: StartWizardState) -> StartWizardState:
    step = StartWizardStep.BACK if state.config.allow_back else StartWizardStep.CANCELLED
    return StartWizardState(step=step, context=state.context, config=state.config)
