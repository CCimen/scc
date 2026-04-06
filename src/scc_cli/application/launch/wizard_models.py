"""ViewModel and Option dataclasses for the start wizard UI layer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from scc_cli.application.interaction_requests import (
    ConfirmRequest,
    InputRequest,
    SelectOption,
    SelectRequest,
)
from scc_cli.application.launch.start_wizard import (
    StartWizardState,
    StartWizardStep,
    WorkspaceSource,
)
from scc_cli.contexts import WorkContext


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
