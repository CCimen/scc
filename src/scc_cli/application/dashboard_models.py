"""Dashboard view models, events, and type definitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias

from scc_cli.ports.session_models import SessionSummary


class DashboardTab(Enum):
    """Available dashboard tabs."""

    STATUS = auto()
    CONTAINERS = auto()
    SESSIONS = auto()
    WORKTREES = auto()

    @property
    def display_name(self) -> str:
        """Human-readable name for display in chrome."""
        names = {
            DashboardTab.STATUS: "Status",
            DashboardTab.CONTAINERS: "Containers",
            DashboardTab.SESSIONS: "Sessions",
            DashboardTab.WORKTREES: "Worktrees",
        }
        return names[self]


TAB_ORDER: tuple[DashboardTab, ...] = (
    DashboardTab.STATUS,
    DashboardTab.CONTAINERS,
    DashboardTab.SESSIONS,
    DashboardTab.WORKTREES,
)


class StatusAction(Enum):
    """Supported actions for status tab items."""

    START_SESSION = auto()
    RESUME_SESSION = auto()
    SWITCH_TEAM = auto()
    OPEN_TAB = auto()
    INSTALL_STATUSLINE = auto()
    OPEN_PROFILE = auto()
    OPEN_SETTINGS = auto()


class PlaceholderKind(Enum):
    """Placeholder rows for empty or error states."""

    NO_CONTAINERS = auto()
    NO_SESSIONS = auto()
    NO_WORKTREES = auto()
    NO_GIT = auto()
    ERROR = auto()
    CONFIG_ERROR = auto()


@dataclass(frozen=True)
class ContainerSummary:
    """Application-layer container metadata.

    Mirrors the fields of docker.core.ContainerInfo without coupling
    the application layer to the docker package.
    """

    id: str
    name: str
    status: str
    profile: str | None = None
    workspace: str | None = None
    branch: str | None = None
    created: str | None = None


@dataclass(frozen=True)
class StatusItem:
    """Status tab row with optional action metadata."""

    label: str
    description: str
    action: StatusAction | None = None
    action_tab: DashboardTab | None = None
    session: SessionSummary | None = None


@dataclass(frozen=True)
class PlaceholderItem:
    """Placeholder row for empty/error states."""

    label: str
    description: str
    kind: PlaceholderKind
    startable: bool = False


@dataclass(frozen=True)
class ContainerItem:
    """Container row backed by container metadata."""

    label: str
    description: str
    container: ContainerSummary


@dataclass(frozen=True)
class SessionItem:
    """Session row backed by session metadata."""

    label: str
    description: str
    session: SessionSummary


@dataclass(frozen=True)
class WorktreeItem:
    """Worktree row backed by git worktree data."""

    label: str
    description: str
    path: str


DashboardItem: TypeAlias = StatusItem | PlaceholderItem | ContainerItem | SessionItem | WorktreeItem


@dataclass(frozen=True)
class DashboardTabData:
    """View model for a single dashboard tab."""

    tab: DashboardTab
    title: str
    items: Sequence[DashboardItem]
    count_active: int
    count_total: int

    @property
    def subtitle(self) -> str:
        """Generate subtitle from counts."""
        if self.count_active == self.count_total:
            return f"{self.count_total} total"
        return f"{self.count_active} active, {self.count_total} total"


@dataclass(frozen=True)
class DashboardViewModel:
    """View model for a full dashboard render."""

    active_tab: DashboardTab
    tabs: Mapping[DashboardTab, DashboardTabData]
    status_message: str | None
    verbose_worktrees: bool


@dataclass(frozen=True)
class DashboardFlowState:
    """Flow state preserved between dashboard runs."""

    restore_tab: DashboardTab | None = None
    toast_message: str | None = None
    verbose_worktrees: bool = False


class StartFlowDecision(Enum):
    """Decision outcomes from the start flow."""

    LAUNCHED = auto()
    CANCELLED = auto()
    QUIT = auto()


@dataclass(frozen=True)
class StartFlowResult:
    """Result from executing the start flow."""

    decision: StartFlowDecision

    @classmethod
    def from_legacy(cls, result: bool | None) -> StartFlowResult:
        """Convert legacy bool/None start result into a structured outcome."""
        if result is None:
            return cls(decision=StartFlowDecision.QUIT)
        if result is True:
            return cls(decision=StartFlowDecision.LAUNCHED)
        return cls(decision=StartFlowDecision.CANCELLED)


@dataclass(frozen=True)
class TeamSwitchEvent:
    """Event for switching teams."""


@dataclass(frozen=True)
class StartFlowEvent:
    """Event for starting a new session flow."""

    return_to: DashboardTab
    reason: str


@dataclass(frozen=True)
class RefreshEvent:
    """Event for refreshing dashboard data."""

    return_to: DashboardTab


@dataclass(frozen=True)
class SessionResumeEvent:
    """Event for resuming a session."""

    return_to: DashboardTab
    session: SessionSummary


@dataclass(frozen=True)
class StatuslineInstallEvent:
    """Event for installing statusline."""

    return_to: DashboardTab


@dataclass(frozen=True)
class RecentWorkspacesEvent:
    """Event for picking a recent workspace."""

    return_to: DashboardTab


@dataclass(frozen=True)
class GitInitEvent:
    """Event for initializing git."""

    return_to: DashboardTab


@dataclass(frozen=True)
class CreateWorktreeEvent:
    """Event for creating a worktree or cloning."""

    return_to: DashboardTab
    is_git_repo: bool


@dataclass(frozen=True)
class VerboseToggleEvent:
    """Event for toggling verbose worktree status."""

    return_to: DashboardTab
    verbose: bool


@dataclass(frozen=True)
class SettingsEvent:
    """Event for opening settings."""

    return_to: DashboardTab


@dataclass(frozen=True)
class ContainerStopEvent:
    """Event for stopping a container."""

    return_to: DashboardTab
    container_id: str
    container_name: str


@dataclass(frozen=True)
class ContainerResumeEvent:
    """Event for resuming a container."""

    return_to: DashboardTab
    container_id: str
    container_name: str


@dataclass(frozen=True)
class ContainerRemoveEvent:
    """Event for removing a container."""

    return_to: DashboardTab
    container_id: str
    container_name: str


@dataclass(frozen=True)
class ProfileMenuEvent:
    """Event for opening the profile menu."""

    return_to: DashboardTab


@dataclass(frozen=True)
class SandboxImportEvent:
    """Event for importing sandbox plugins."""

    return_to: DashboardTab


@dataclass(frozen=True)
class ContainerActionMenuEvent:
    """Event for the container action menu."""

    return_to: DashboardTab
    container_id: str
    container_name: str


@dataclass(frozen=True)
class SessionActionMenuEvent:
    """Event for the session action menu."""

    return_to: DashboardTab
    session: SessionSummary


@dataclass(frozen=True)
class WorktreeActionMenuEvent:
    """Event for the worktree action menu."""

    return_to: DashboardTab
    worktree_path: str


DashboardEvent: TypeAlias = (
    TeamSwitchEvent
    | StartFlowEvent
    | RefreshEvent
    | SessionResumeEvent
    | StatuslineInstallEvent
    | RecentWorkspacesEvent
    | GitInitEvent
    | CreateWorktreeEvent
    | VerboseToggleEvent
    | SettingsEvent
    | ContainerStopEvent
    | ContainerResumeEvent
    | ContainerRemoveEvent
    | ProfileMenuEvent
    | SandboxImportEvent
    | ContainerActionMenuEvent
    | SessionActionMenuEvent
    | WorktreeActionMenuEvent
)

DashboardEffect: TypeAlias = (
    TeamSwitchEvent
    | StartFlowEvent
    | SessionResumeEvent
    | StatuslineInstallEvent
    | RecentWorkspacesEvent
    | GitInitEvent
    | CreateWorktreeEvent
    | SettingsEvent
    | ContainerStopEvent
    | ContainerResumeEvent
    | ContainerRemoveEvent
    | ProfileMenuEvent
    | SandboxImportEvent
    | ContainerActionMenuEvent
    | SessionActionMenuEvent
    | WorktreeActionMenuEvent
)


@dataclass(frozen=True)
class DashboardEffectRequest:
    """Effect request emitted from a dashboard event."""

    state: DashboardFlowState
    effect: DashboardEffect


@dataclass(frozen=True)
class DashboardFlowOutcome:
    """Outcome after handling an event or effect."""

    state: DashboardFlowState
    exit_dashboard: bool = False


DashboardNextStep: TypeAlias = DashboardEffectRequest | DashboardFlowOutcome

DashboardDataLoader: TypeAlias = Callable[[bool], Mapping[DashboardTab, DashboardTabData]]
