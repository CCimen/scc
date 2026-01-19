"""State machine for the interactive start wizard."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from scc_cli.application.interaction_requests import (
    ConfirmRequest,
    InputRequest,
    SelectOption,
    SelectRequest,
)
from scc_cli.contexts import WorkContext


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


class WorkspaceSource(str, Enum):
    """Workspace source options for the start wizard."""

    CURRENT_DIR = "current_dir"
    RECENT = "recent"
    TEAM_REPOS = "team_repos"
    CUSTOM = "custom"
    CLONE = "clone"


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
        workspace_source: Selected workspace source, if any.
        workspace: Selected workspace path, if any.
        worktree_name: Selected worktree name, if any.
        session_name: Selected session name, if any.
    """

    team: str | None = None
    workspace_source: WorkspaceSource | None = None
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

    source: WorkspaceSource


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
            workspace_source=None,
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
            workspace_source=state.context.workspace_source,
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
        context = StartWizardContext(
            team=state.context.team,
            workspace_source=event.source,
            workspace=state.context.workspace,
            worktree_name=state.context.worktree_name,
            session_name=state.context.session_name,
        )
        return StartWizardState(
            step=StartWizardStep.WORKSPACE_PICKER,
            context=context,
            config=state.config,
        )
    msg = f"Invalid event for workspace source: {event}"
    raise ValueError(msg)


def _handle_workspace_picker(state: StartWizardState, event: StartWizardEvent) -> StartWizardState:
    if isinstance(event, WorkspaceSelected):
        context = StartWizardContext(
            team=state.context.team,
            workspace_source=state.context.workspace_source,
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
            workspace_source=state.context.workspace_source,
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
            workspace_source=state.context.workspace_source,
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


@dataclass(frozen=True)
class TeamOption:
    """Team option for selection prompts."""

    name: str
    description: str = ""
    credential_status: str | None = None


@dataclass(frozen=True)
class TeamSelectionViewModel:
    """View model for team selection prompts."""

    title: str
    subtitle: str | None
    current_team: str | None
    options: Sequence[TeamOption]


@dataclass(frozen=True)
class WorkspaceSourceOption:
    """Workspace source option for selection prompts."""

    source: WorkspaceSource
    label: str
    description: str


@dataclass(frozen=True)
class CwdContext:
    """Current working directory context for workspace source selection.

    This dataclass captures the runtime state of the current working directory
    so the UI layer can build appropriate presentation options. The command
    layer gathers this data (via service functions), filters out suspicious
    directories upstream, and the UI layer uses it to build picker options.

    Invariants:
        - If cwd_context is None in a view model, cwd is suspicious or unavailable.
        - If cwd_context is provided, the directory has passed suspicious checks.
        - UI should show "Current directory" option iff cwd_context is not None.

    Args:
        path: Absolute path to the current working directory.
        name: Display name for the directory (typically the folder name).
        is_git: Whether the directory is a git repository.
        has_project_markers: Whether the directory has recognizable project markers.
    """

    path: str
    name: str
    is_git: bool
    has_project_markers: bool


@dataclass(frozen=True)
class WorkspaceSummary:
    """Workspace option summary for picker prompts."""

    label: str
    description: str
    workspace: str


@dataclass(frozen=True)
class TeamRepoOption:
    """Team repository option for selection prompts."""

    name: str
    description: str
    url: str | None = None
    local_path: str | None = None


@dataclass(frozen=True)
class QuickResumeOption:
    """Quick resume option for selection prompts."""

    option_id: str
    label: str
    description: str
    is_new_session: bool = False
    is_switch_team: bool = False
    is_context: bool = False
    context: WorkContext | None = None


@dataclass(frozen=True)
class QuickResumeViewModel:
    """View model for quick resume selection prompts."""

    title: str
    subtitle: str | None
    context_label: str | None
    standalone: bool
    effective_team: str | None
    contexts: Sequence[WorkContext]
    current_branch: str | None = None


@dataclass(frozen=True)
class WorkspaceSourceViewModel:
    """View model for workspace source selection prompts.

    This view model carries data flags that the UI layer uses to build
    presentation options. The application layer provides context about
    the current directory and team repositories, but does not build
    the actual picker options - that's the UI layer's responsibility.

    Invariants:
        - cwd_context is None if the current directory is suspicious (UI should not show it).
        - If options is empty, UI layer builds options from cwd_context/has_team_repos.

    Args:
        title: Picker title text.
        subtitle: Optional subtitle text.
        context_label: Team context label (e.g., "Team: platform").
        standalone: Whether running in standalone mode (no org config).
        allow_back: Whether back navigation is allowed.
        has_team_repos: Whether team repositories are available.
        cwd_context: Current directory context, or None if cwd is suspicious.
        options: Prebuilt options (empty = UI builds from data flags).
    """

    title: str
    subtitle: str | None
    context_label: str | None
    standalone: bool
    allow_back: bool
    has_team_repos: bool = False
    cwd_context: CwdContext | None = None
    options: Sequence[WorkspaceSourceOption] = ()


@dataclass(frozen=True)
class WorkspacePickerViewModel:
    """View model for workspace picker prompts."""

    title: str
    subtitle: str | None
    context_label: str | None
    standalone: bool
    allow_back: bool
    options: Sequence[WorkspaceSummary]


@dataclass(frozen=True)
class TeamRepoPickerViewModel:
    """View model for team repository picker prompts."""

    title: str
    subtitle: str | None
    context_label: str | None
    standalone: bool
    allow_back: bool
    workspace_base: str
    options: Sequence[TeamRepoOption]


StartWizardViewModel = (
    QuickResumeViewModel
    | WorkspaceSourceViewModel
    | WorkspacePickerViewModel
    | TeamRepoPickerViewModel
    | TeamSelectionViewModel
    | None
)


@dataclass(frozen=True)
class StartWizardPrompt:
    """Prompt returned for the start wizard UI layer.

    Invariants:
        - Prompts are data-only and rendered at the UI edge.
    """

    step: StartWizardStep
    request: ConfirmRequest | SelectRequest[object] | InputRequest
    select_options: Sequence[SelectOption[object]] | None = None
    view_model: StartWizardViewModel = None
    allow_team_switch: bool = False
    default_response: bool | None = None


@dataclass(frozen=True)
class StartWizardProgress:
    """Non-terminal wizard state prompting user input."""

    state: StartWizardState
    prompt: StartWizardPrompt


StartWizardOutcome = StartWizardProgress | StartWizardState


WORKSPACE_SOURCE_REQUEST_ID = "start-workspace-source"
WORKSPACE_PICKER_REQUEST_ID = "start-workspace-picker"
TEAM_SELECTION_REQUEST_ID = "start-team-selection"
WORKTREE_CONFIRM_REQUEST_ID = "start-worktree-confirm"
WORKTREE_NAME_REQUEST_ID = "start-worktree-name"
SESSION_NAME_REQUEST_ID = "start-session-name"
QUICK_RESUME_REQUEST_ID = "start-quick-resume"
CROSS_TEAM_RESUME_REQUEST_ID = "start-cross-team-resume"
TEAM_REPO_REQUEST_ID = "start-team-repo"
CUSTOM_WORKSPACE_REQUEST_ID = "start-workspace-path"
CLONE_REPO_REQUEST_ID = "start-clone-repo"


def _build_quick_resume_options(
    contexts: Sequence[WorkContext],
    *,
    include_switch_team: bool,
    new_session_label: str,
    new_session_description: str,
    current_branch: str | None = None,
) -> list[QuickResumeOption]:
    options: list[QuickResumeOption] = [
        QuickResumeOption(
            option_id="quick-resume:new-session",
            label=new_session_label,
            description=new_session_description,
            is_new_session=True,
        )
    ]
    if include_switch_team:
        options.append(
            QuickResumeOption(
                option_id="quick-resume:switch-team",
                label="Switch team",
                description="Choose a different team",
                is_switch_team=True,
            )
        )
    for index, context in enumerate(contexts, start=1):
        description_parts: list[str] = []
        if context.last_session_id:
            description_parts.append(f"session: {context.last_session_id}")
        if current_branch and context.worktree_name == current_branch:
            description_parts.append("current branch")
        options.append(
            QuickResumeOption(
                option_id=f"quick-resume:context:{index}",
                label=context.display_label,
                description="  ".join(description_parts),
                is_context=True,
                context=context,
            )
        )
    return options


def build_team_selection_prompt(*, view_model: TeamSelectionViewModel) -> StartWizardPrompt:
    options: list[SelectOption[TeamOption]] = []
    for team in view_model.options:
        options.append(
            SelectOption(
                option_id=f"team:{team.name}",
                label=team.name,
                description=team.description,
                value=team,
            )
        )
    subtitle = view_model.subtitle
    if subtitle is None:
        subtitle = f"{len(options)} teams available" if options else None
    request = SelectRequest(
        request_id=TEAM_SELECTION_REQUEST_ID,
        title=view_model.title,
        subtitle=subtitle,
        options=options,
        allow_back=False,
    )
    return StartWizardPrompt(
        step=StartWizardStep.TEAM_SELECTION,
        request=request,
        view_model=view_model,
        allow_team_switch=False,
        select_options=request.options,
    )


def build_workspace_source_prompt(*, view_model: WorkspaceSourceViewModel) -> StartWizardPrompt:
    """Build a workspace source selection prompt.

    This function passes through the view model data to the UI layer, which
    is responsible for building picker options from the data flags
    (cwd_context, has_team_repos) when options is empty.

    The application layer provides:
        - cwd_context: Current directory data (None if suspicious/unavailable)
        - has_team_repos: Whether team repositories are available
        - options: Pre-built options (empty = UI builds from data flags)

    The UI layer:
        - Builds picker options from data flags if options is empty
        - Renders the picker with appropriate labels and descriptions
    """
    options = list(view_model.options)
    select_options: list[SelectOption[WorkspaceSourceOption]] = []
    for option in options:
        select_options.append(
            SelectOption(
                option_id=f"workspace-source:{option.source.value}",
                label=option.label,
                description=option.description,
                value=option,
            )
        )
    request = SelectRequest(
        request_id=WORKSPACE_SOURCE_REQUEST_ID,
        title=view_model.title,
        subtitle=view_model.subtitle,
        options=select_options,
        allow_back=view_model.allow_back,
    )
    # Pass through the view model unchanged - UI layer will use cwd_context
    # and has_team_repos to build options if options list is empty
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_SOURCE,
        request=request,
        view_model=view_model,
        allow_team_switch=True,
        select_options=request.options,
    )


def build_workspace_picker_prompt(*, view_model: WorkspacePickerViewModel) -> StartWizardPrompt:
    options: list[SelectOption[WorkspaceSummary]] = []
    for option in view_model.options:
        options.append(
            SelectOption(
                option_id=f"workspace:{option.workspace}",
                label=option.label,
                description=option.description,
                value=option,
            )
        )
    request = SelectRequest(
        request_id=WORKSPACE_PICKER_REQUEST_ID,
        title=view_model.title,
        subtitle=view_model.subtitle,
        options=options,
        allow_back=view_model.allow_back,
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_PICKER,
        request=request,
        view_model=view_model,
        allow_team_switch=True,
        select_options=request.options,
    )


def build_team_repo_prompt(*, view_model: TeamRepoPickerViewModel) -> StartWizardPrompt:
    options: list[SelectOption[TeamRepoOption]] = []
    for option in view_model.options:
        options.append(
            SelectOption(
                option_id=f"team-repo:{option.name}",
                label=option.name,
                description=option.description,
                value=option,
            )
        )
    request = SelectRequest(
        request_id=TEAM_REPO_REQUEST_ID,
        title=view_model.title,
        subtitle=view_model.subtitle,
        options=options,
        allow_back=view_model.allow_back,
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_PICKER,
        request=request,
        view_model=view_model,
        allow_team_switch=True,
        select_options=request.options,
    )


def build_quick_resume_prompt(*, view_model: QuickResumeViewModel) -> StartWizardPrompt:
    team_label = view_model.effective_team or "standalone"
    if view_model.standalone:
        team_label = "standalone"
    new_session_label = f"+ New session ({team_label})"
    new_session_description = "Start fresh"
    if not view_model.contexts:
        new_session_description = "No sessions yet — press Enter to start"

    options = _build_quick_resume_options(
        view_model.contexts,
        include_switch_team=not view_model.standalone,
        new_session_label=new_session_label,
        new_session_description=new_session_description,
        current_branch=view_model.current_branch,
    )
    select_options: list[SelectOption[QuickResumeOption]] = []
    for option in options:
        select_options.append(
            SelectOption(
                option_id=option.option_id,
                label=option.label,
                description=option.description,
                value=option,
            )
        )
    request = SelectRequest(
        request_id=QUICK_RESUME_REQUEST_ID,
        title=view_model.title,
        subtitle=view_model.subtitle,
        options=select_options,
        allow_back=True,
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_PICKER,
        request=request,
        view_model=view_model,
        allow_team_switch=True,
        select_options=request.options,
    )


def build_confirm_worktree_prompt() -> StartWizardPrompt:
    request = ConfirmRequest(
        request_id=WORKTREE_CONFIRM_REQUEST_ID,
        prompt="Create a worktree for isolated feature development?",
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKTREE_DECISION,
        request=request,
        view_model=None,
        allow_team_switch=False,
    )


def build_cross_team_resume_prompt(team: str) -> StartWizardPrompt:
    request = ConfirmRequest(
        request_id=CROSS_TEAM_RESUME_REQUEST_ID,
        prompt=(
            f"[yellow]Resume session from team '{team}'?[/yellow]\n"
            f"[dim]This will use {team} plugins for this session.[/dim]"
        ),
    )
    return StartWizardPrompt(
        step=StartWizardStep.QUICK_RESUME,
        request=request,
        view_model=None,
        allow_team_switch=False,
        default_response=False,
    )


def build_worktree_name_prompt() -> StartWizardPrompt:
    request = InputRequest(
        request_id=WORKTREE_NAME_REQUEST_ID,
        prompt="Feature/worktree name",
        default="",
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKTREE_DECISION,
        request=request,
        view_model=None,
        allow_team_switch=False,
    )


def build_session_name_prompt() -> StartWizardPrompt:
    request = InputRequest(
        request_id=SESSION_NAME_REQUEST_ID,
        prompt="Session name (optional, for easy resume)",
        default="",
    )
    return StartWizardPrompt(
        step=StartWizardStep.SESSION_NAME,
        request=request,
        view_model=None,
        allow_team_switch=False,
    )


def build_custom_workspace_prompt() -> StartWizardPrompt:
    request = InputRequest(
        request_id=CUSTOM_WORKSPACE_REQUEST_ID,
        prompt="Enter workspace path",
        default="",
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_PICKER,
        request=request,
        view_model=None,
        allow_team_switch=True,
    )


def build_clone_repo_prompt() -> StartWizardPrompt:
    request = InputRequest(
        request_id=CLONE_REPO_REQUEST_ID,
        prompt="Repository URL (HTTPS or SSH)",
        default="",
    )
    return StartWizardPrompt(
        step=StartWizardStep.WORKSPACE_PICKER,
        request=request,
        view_model=None,
        allow_team_switch=True,
    )
