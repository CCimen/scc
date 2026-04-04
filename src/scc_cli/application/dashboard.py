"""Dashboard view models and flow orchestration.

This module is the public API surface for dashboard types and logic.
Models are defined in dashboard_models, loaders in dashboard_loaders.
All public names are re-exported here to preserve backward compatibility.
"""

from __future__ import annotations

from dataclasses import replace

# Re-export all loaders from dashboard_loaders
from scc_cli.application.dashboard_loaders import (
    load_all_tab_data,
    load_containers_tab_data,
    load_sessions_tab_data,
    load_status_tab_data,
    load_worktrees_tab_data,
)

# Re-export all models and types from dashboard_models
from scc_cli.application.dashboard_models import (
    TAB_ORDER,
    ContainerActionMenuEvent,
    ContainerItem,
    ContainerRemoveEvent,
    ContainerResumeEvent,
    ContainerStopEvent,
    ContainerSummary,
    CreateWorktreeEvent,
    DashboardDataLoader,
    DashboardEffect,
    DashboardEffectRequest,
    DashboardEvent,
    DashboardFlowOutcome,
    DashboardFlowState,
    DashboardItem,
    DashboardNextStep,
    DashboardTab,
    DashboardTabData,
    DashboardViewModel,
    GitInitEvent,
    PlaceholderItem,
    PlaceholderKind,
    ProfileMenuEvent,
    RecentWorkspacesEvent,
    RefreshEvent,
    SandboxImportEvent,
    SessionActionMenuEvent,
    SessionItem,
    SessionResumeEvent,
    SettingsEvent,
    StartFlowDecision,
    StartFlowEvent,
    StartFlowResult,
    StatusAction,
    StatusItem,
    StatuslineInstallEvent,
    TeamSwitchEvent,
    VerboseToggleEvent,
    WorktreeActionMenuEvent,
    WorktreeItem,
)

__all__ = [
    # Models and types
    "ContainerActionMenuEvent",
    "ContainerItem",
    "ContainerRemoveEvent",
    "ContainerResumeEvent",
    "ContainerStopEvent",
    "ContainerSummary",
    "CreateWorktreeEvent",
    "DashboardDataLoader",
    "DashboardEffect",
    "DashboardEffectRequest",
    "DashboardEvent",
    "DashboardFlowOutcome",
    "DashboardFlowState",
    "DashboardItem",
    "DashboardNextStep",
    "DashboardTab",
    "DashboardTabData",
    "DashboardViewModel",
    "GitInitEvent",
    "PlaceholderItem",
    "PlaceholderKind",
    "ProfileMenuEvent",
    "RecentWorkspacesEvent",
    "RefreshEvent",
    "SandboxImportEvent",
    "SessionActionMenuEvent",
    "SessionItem",
    "SessionResumeEvent",
    "SettingsEvent",
    "StartFlowDecision",
    "StartFlowEvent",
    "StartFlowResult",
    "StatusAction",
    "StatusItem",
    "StatuslineInstallEvent",
    "TAB_ORDER",
    "TeamSwitchEvent",
    "VerboseToggleEvent",
    "WorktreeActionMenuEvent",
    "WorktreeItem",
    # Loaders
    "load_all_tab_data",
    "load_containers_tab_data",
    "load_sessions_tab_data",
    "load_status_tab_data",
    "load_worktrees_tab_data",
    # Functions
    "apply_dashboard_effect_result",
    "build_dashboard_view",
    "handle_dashboard_event",
    "placeholder_start_reason",
    "placeholder_tip",
]


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
