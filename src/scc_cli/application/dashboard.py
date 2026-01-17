"""Dashboard view models and flow orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, auto
from typing import TypeAlias

from scc_cli.application.sessions import SessionService
from scc_cli.docker.core import ContainerInfo
from scc_cli.ports.session_models import SessionFilter, SessionSummary
from scc_cli.services.git.worktree import WorktreeInfo


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
    """Container row backed by Docker metadata."""

    label: str
    description: str
    container: ContainerInfo


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


def placeholder_tip(kind: PlaceholderKind) -> str:
    """Return contextual help for placeholder rows."""
    tips = {
        PlaceholderKind.NO_CONTAINERS: "No containers running. Press n to start or run `scc start <path>`.",
        PlaceholderKind.NO_SESSIONS: "No sessions yet. Press n to create your first session.",
        PlaceholderKind.NO_WORKTREES: "No worktrees yet. Press c to create, w for recent, v for status.",
        PlaceholderKind.NO_GIT: "Not a git repository. Press i to init or c to clone.",
        PlaceholderKind.ERROR: "Unable to load data. Run `scc doctor` to diagnose.",
        PlaceholderKind.CONFIG_ERROR: "Configuration issue detected. Run `scc doctor` to fix it.",
    }
    return tips.get(kind, "No details available for this item.")


def placeholder_start_reason(item: PlaceholderItem) -> str:
    """Return start flow reason for a startable placeholder."""
    mapping = {
        PlaceholderKind.NO_CONTAINERS: "no_containers",
        PlaceholderKind.NO_SESSIONS: "no_sessions",
    }
    return mapping.get(item.kind, "unknown")


def build_dashboard_view(
    state: DashboardFlowState,
    loader: DashboardDataLoader,
) -> tuple[DashboardViewModel, DashboardFlowState]:
    """Build the dashboard view and clear one-time state."""
    tabs = loader(state.verbose_worktrees)
    active_tab = state.restore_tab or DashboardTab.STATUS
    if active_tab not in tabs:
        active_tab = DashboardTab.STATUS
    view = DashboardViewModel(
        active_tab=active_tab,
        tabs=tabs,
        status_message=state.toast_message,
        verbose_worktrees=state.verbose_worktrees,
    )
    next_state = replace(state, restore_tab=None, toast_message=None)
    return view, next_state


def handle_dashboard_event(state: DashboardFlowState, event: DashboardEvent) -> DashboardNextStep:
    """Translate a dashboard event into an effect or state update."""
    if isinstance(event, TeamSwitchEvent):
        return DashboardEffectRequest(state=state, effect=event)

    if isinstance(event, StartFlowEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, RefreshEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(event, SessionResumeEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, StatuslineInstallEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, RecentWorkspacesEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, GitInitEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, CreateWorktreeEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, VerboseToggleEvent):
        message = "Status on" if event.verbose else "Status off"
        next_state = replace(
            state,
            restore_tab=event.return_to,
            verbose_worktrees=event.verbose,
            toast_message=message,
        )
        return DashboardFlowOutcome(state=next_state)

    if isinstance(event, SettingsEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, ContainerStopEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, ContainerResumeEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, ContainerRemoveEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, ProfileMenuEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, SandboxImportEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, ContainerActionMenuEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, SessionActionMenuEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    if isinstance(event, WorktreeActionMenuEvent):
        next_state = replace(state, restore_tab=event.return_to)
        return DashboardEffectRequest(state=next_state, effect=event)

    msg = f"Unsupported event: {event}"
    raise ValueError(msg)


def apply_dashboard_effect_result(
    state: DashboardFlowState,
    effect: DashboardEffect,
    result: object,
) -> DashboardFlowOutcome:
    """Apply effect results to dashboard state."""
    if isinstance(effect, TeamSwitchEvent):
        return DashboardFlowOutcome(state=state)

    if isinstance(effect, StartFlowEvent):
        if not isinstance(result, StartFlowResult):
            msg = "Start flow effect requires StartFlowResult"
            raise TypeError(msg)
        if result.decision is StartFlowDecision.QUIT:
            return DashboardFlowOutcome(state=state, exit_dashboard=True)
        if result.decision is StartFlowDecision.LAUNCHED:
            return DashboardFlowOutcome(state=state, exit_dashboard=True)
        next_state = replace(state, toast_message="Start cancelled")
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, SessionResumeEvent):
        if not isinstance(result, bool):
            msg = "Session resume effect requires bool result"
            raise TypeError(msg)
        if result:
            return DashboardFlowOutcome(state=state, exit_dashboard=True)
        next_state = replace(state, toast_message="Session resume failed")
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, StatuslineInstallEvent):
        if not isinstance(result, bool):
            msg = "Statusline install effect requires bool result"
            raise TypeError(msg)
        message = (
            "Statusline installed successfully" if result else "Statusline installation failed"
        )
        next_state = replace(state, toast_message=message)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, RecentWorkspacesEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Recent workspaces effect requires str or None"
            raise TypeError(msg)
        if result is None:
            message = "Cancelled"
        else:
            message = f"Selected: {result}"
        next_state = replace(state, toast_message=message)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, GitInitEvent):
        if not isinstance(result, bool):
            msg = "Git init effect requires bool result"
            raise TypeError(msg)
        message = "Git repository initialized" if result else "Git init cancelled or failed"
        next_state = replace(state, toast_message=message)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, CreateWorktreeEvent):
        if not isinstance(result, bool):
            msg = "Create worktree effect requires bool result"
            raise TypeError(msg)
        if effect.is_git_repo:
            message = "Worktree created" if result else "Worktree creation cancelled"
        else:
            message = "Repository cloned" if result else "Clone cancelled"
        next_state = replace(state, toast_message=message)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, SettingsEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Settings effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, ContainerStopEvent):
        return _apply_container_message(state, result, "Container stopped", "Stop failed")

    if isinstance(effect, ContainerResumeEvent):
        return _apply_container_message(state, result, "Container resumed", "Resume failed")

    if isinstance(effect, ContainerRemoveEvent):
        return _apply_container_message(state, result, "Container removed", "Remove failed")

    if isinstance(effect, ProfileMenuEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Profile menu effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, SandboxImportEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Sandbox import effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, ContainerActionMenuEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Container action menu effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, SessionActionMenuEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Session action menu effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    if isinstance(effect, WorktreeActionMenuEvent):
        if not isinstance(result, (str, type(None))):
            msg = "Worktree action menu effect requires str or None"
            raise TypeError(msg)
        next_state = replace(state, toast_message=result)
        return DashboardFlowOutcome(state=next_state)

    msg = f"Unsupported effect: {effect}"
    raise ValueError(msg)


def _apply_container_message(
    state: DashboardFlowState,
    result: object,
    success_message: str,
    failure_message: str,
) -> DashboardFlowOutcome:
    if not isinstance(result, tuple) or len(result) != 2:
        msg = "Container effect requires tuple[bool, str | None]"
        raise TypeError(msg)
    success, message = result
    if not isinstance(success, bool):
        msg = "Container effect success flag must be bool"
        raise TypeError(msg)
    if message is not None and not isinstance(message, str):
        msg = "Container effect message must be str or None"
        raise TypeError(msg)
    fallback = success_message if success else failure_message
    next_state = replace(state, toast_message=message or fallback)
    return DashboardFlowOutcome(state=next_state)


def load_status_tab_data(
    refresh_at: datetime | None = None,
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
) -> DashboardTabData:
    """Load Status tab data showing quick actions and context."""
    import os
    from pathlib import Path

    from scc_cli import config
    from scc_cli.core.personal_profiles import get_profile_status
    from scc_cli.docker import core as docker_core

    _ = refresh_at

    items: list[DashboardItem] = []

    items.append(
        StatusItem(
            label="New session",
            description="",
            action=StatusAction.START_SESSION,
        )
    )

    try:
        recent_result = session_service.list_recent(SessionFilter(limit=1, include_all=True))
        recent_session = recent_result.sessions[0] if recent_result.sessions else None
        if recent_session:
            workspace = recent_session.workspace
            workspace_name = workspace.split("/")[-1] if workspace else "unknown"
            last_used = recent_session.last_used
            last_used_display = ""
            if last_used:
                last_used_display = format_last_used(last_used) if format_last_used else last_used
            desc_parts = [workspace_name]
            if recent_session.branch:
                desc_parts.append(str(recent_session.branch))
            if last_used_display:
                desc_parts.append(last_used_display)
            items.append(
                StatusItem(
                    label="Resume last",
                    description=" · ".join(desc_parts),
                    action=StatusAction.RESUME_SESSION,
                    session=recent_session,
                )
            )
    except Exception:
        pass

    try:
        user_config = config.load_user_config()
        team = user_config.get("selected_profile")
        org_source = user_config.get("organization_source")

        if team:
            items.append(
                StatusItem(
                    label=f"Team: {team}",
                    description="",
                    action=StatusAction.SWITCH_TEAM,
                )
            )
        else:
            items.append(
                StatusItem(
                    label="Team: none",
                    description="",
                    action=StatusAction.SWITCH_TEAM,
                )
            )

        try:
            workspace_path = Path(os.getcwd())
            profile_status = get_profile_status(workspace_path)

            if profile_status.exists:
                if profile_status.import_count > 0:
                    profile_label = f"Profile: saved · ↓ {profile_status.import_count} importable"
                elif profile_status.has_drift:
                    profile_label = "Profile: saved · ◇ drifted"
                else:
                    profile_label = "Profile: saved · ✓ synced"
                items.append(
                    StatusItem(
                        label=profile_label,
                        description="",
                        action=StatusAction.OPEN_PROFILE,
                    )
                )
            else:
                items.append(
                    StatusItem(
                        label="Profile: none",
                        description="",
                        action=StatusAction.OPEN_PROFILE,
                    )
                )
        except Exception:
            pass

        if org_source and isinstance(org_source, dict):
            org_url = org_source.get("url", "")
            if org_url:
                org_name = None
                try:
                    org_config = config.load_cached_org_config()
                    if org_config:
                        org_name = org_config.get("organization", {}).get("name")
                except Exception:
                    org_name = None

                if not org_name:
                    org_name = org_url.replace("https://", "").replace("http://", "").split("/")[0]

                items.append(
                    StatusItem(
                        label=f"Organization: {org_name}",
                        description="",
                    )
                )
        elif user_config.get("standalone"):
            items.append(
                StatusItem(
                    label="Mode: standalone",
                    description="",
                )
            )

    except Exception:
        items.append(
            StatusItem(
                label="Config: error",
                description="",
            )
        )

    try:
        containers = docker_core.list_scc_containers()
        running = sum(1 for container in containers if "Up" in container.status)
        total = len(containers)
        items.append(
            StatusItem(
                label=f"Containers: {running}/{total} running",
                description="",
                action=StatusAction.OPEN_TAB,
                action_tab=DashboardTab.CONTAINERS,
            )
        )
    except Exception:
        pass

    items.append(
        StatusItem(
            label="Settings",
            description="",
            action=StatusAction.OPEN_SETTINGS,
        )
    )

    return DashboardTabData(
        tab=DashboardTab.STATUS,
        title="Status",
        items=items,
        count_active=len(items),
        count_total=len(items),
    )


def load_containers_tab_data() -> DashboardTabData:
    """Load Containers tab data showing SCC-managed containers."""
    from scc_cli.docker import core as docker_core

    items: list[DashboardItem] = []

    try:
        containers = docker_core.list_scc_containers()
        running_count = 0

        for container in containers:
            is_running = "Up" in container.status if container.status else False
            if is_running:
                running_count += 1
            label = container.name
            description = _format_container_description(container)
            items.append(ContainerItem(label=label, description=description, container=container))

        if not items:
            items.append(
                PlaceholderItem(
                    label="No containers",
                    description="Press 'n' to start or run `scc start <path>`",
                    kind=PlaceholderKind.NO_CONTAINERS,
                    startable=True,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=items,
            count_active=running_count,
            count_total=len(containers),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[
                PlaceholderItem(
                    label="Error",
                    description="Unable to query Docker",
                    kind=PlaceholderKind.ERROR,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_sessions_tab_data(
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
) -> DashboardTabData:
    """Load Sessions tab data showing recent Claude sessions."""
    items: list[DashboardItem] = []

    try:
        recent_result = session_service.list_recent(SessionFilter(limit=20, include_all=True))
        recent = recent_result.sessions

        for session in recent:
            desc_parts = []

            if session.team:
                desc_parts.append(str(session.team))
            if session.branch:
                desc_parts.append(str(session.branch))
            if session.last_used:
                desc_parts.append(
                    format_last_used(session.last_used) if format_last_used else session.last_used
                )

            items.append(
                SessionItem(
                    label=session.name or "Unnamed",
                    description=" · ".join(desc_parts),
                    session=session,
                )
            )

        if not items:
            items.append(
                PlaceholderItem(
                    label="No sessions",
                    description="Press Enter to start",
                    kind=PlaceholderKind.NO_SESSIONS,
                    startable=True,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=items,
            count_active=len(recent),
            count_total=len(recent),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=[
                PlaceholderItem(
                    label="Error",
                    description="Unable to load sessions",
                    kind=PlaceholderKind.ERROR,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_worktrees_tab_data(verbose: bool = False) -> DashboardTabData:
    """Load Worktrees tab data showing git worktrees."""
    import os
    from pathlib import Path

    from scc_cli.services.git.worktree import get_worktree_status, get_worktrees_data

    items: list[DashboardItem] = []

    try:
        cwd = Path(os.getcwd())
        worktrees = get_worktrees_data(cwd)
        current_path = os.path.realpath(cwd)

        for worktree in worktrees:
            if os.path.realpath(worktree.path) == current_path:
                worktree.is_current = True

            if verbose:
                staged, modified, untracked, timed_out = get_worktree_status(worktree.path)
                worktree.staged_count = staged
                worktree.modified_count = modified
                worktree.untracked_count = untracked
                worktree.status_timed_out = timed_out
                worktree.has_changes = (staged + modified + untracked) > 0

        current_count = sum(1 for worktree in worktrees if worktree.is_current)

        for worktree in worktrees:
            description = _format_worktree_description(worktree, verbose=verbose)
            items.append(
                WorktreeItem(
                    label=Path(worktree.path).name,
                    description=description,
                    path=worktree.path,
                )
            )

        if not items:
            items.append(
                PlaceholderItem(
                    label="No worktrees",
                    description="Press w for recent · i to init · c to clone",
                    kind=PlaceholderKind.NO_WORKTREES,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=items,
            count_active=current_count,
            count_total=len(worktrees),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=[
                PlaceholderItem(
                    label="Not available",
                    description="Press w for recent · i to init · c to clone",
                    kind=PlaceholderKind.NO_GIT,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_all_tab_data(
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
    verbose_worktrees: bool = False,
) -> Mapping[DashboardTab, DashboardTabData]:
    """Load data for all dashboard tabs."""
    return {
        DashboardTab.STATUS: load_status_tab_data(
            session_service=session_service,
            format_last_used=format_last_used,
        ),
        DashboardTab.CONTAINERS: load_containers_tab_data(),
        DashboardTab.SESSIONS: load_sessions_tab_data(
            session_service=session_service,
            format_last_used=format_last_used,
        ),
        DashboardTab.WORKTREES: load_worktrees_tab_data(verbose=verbose_worktrees),
    }


def _format_container_description(container: ContainerInfo) -> str:
    desc_parts: list[str] = []

    if container.workspace:
        workspace_name = container.workspace.split("/")[-1]
        desc_parts.append(workspace_name)

    if container.status:
        time_str = _extract_container_time(container.status)
        if container.status.startswith("Up"):
            desc_parts.append(f"● {time_str}")
        else:
            desc_parts.append("○ stopped")

    return " · ".join(desc_parts)


def _extract_container_time(status: str) -> str:
    import re

    match = re.search(r"Up\s+(.+)", status)
    if match:
        return match.group(1)
    return status


def _format_worktree_description(worktree: WorktreeInfo, *, verbose: bool) -> str:
    from scc_cli import git

    desc_parts: list[str] = []
    if worktree.branch:
        desc_parts.append(git.get_display_branch(worktree.branch))

    if verbose:
        if worktree.status_timed_out:
            desc_parts.append("status timeout")
        else:
            status_parts = []
            if worktree.staged_count > 0:
                status_parts.append(f"+{worktree.staged_count}")
            if worktree.modified_count > 0:
                status_parts.append(f"!{worktree.modified_count}")
            if worktree.untracked_count > 0:
                status_parts.append(f"?{worktree.untracked_count}")
            if status_parts:
                desc_parts.append(" ".join(status_parts))
            elif not worktree.has_changes:
                desc_parts.append("clean")
    elif worktree.has_changes:
        desc_parts.append("modified")

    if worktree.is_current:
        desc_parts.append("(current)")

    return "  ".join(desc_parts)
