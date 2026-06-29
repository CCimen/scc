"""Orchestration functions for the dashboard module.

This module contains the entry point and flow handlers:
- run_dashboard: Main entry point for `scc` with no arguments
- _apply_event / _run_effect: Event routing and effect execution

Handler implementations live in specialized dashboard handler modules.

The orchestrator manages the dashboard lifecycle including intent exceptions
that exit the Rich Live context before handling nested UI components.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TypeAlias, cast

from scc_cli.application import dashboard as app_dashboard

from ..keys import (
    ContainerActionMenuRequested,
    ContainerRemoveRequested,
    ContainerResumeRequested,
    ContainerStopRequested,
    CreateWorktreeRequested,
    GitInitRequested,
    ProfileMenuRequested,
    RecentWorkspacesRequested,
    RefreshRequested,
    SandboxImportRequested,
    SessionActionMenuRequested,
    SessionResumeRequested,
    SettingsRequested,
    StartRequested,
    StatuslineInstallRequested,
    TeamSwitchRequested,
    VerboseToggleRequested,
    WorktreeActionMenuRequested,
)
from ..list_screen import ListState
from ..time_format import format_relative_time_from_datetime
from . import orchestrator_container_actions, orchestrator_menus
from ._dashboard import Dashboard
from .loaders import _to_tab_data
from .models import DashboardState

# Handler functions used by the dashboard event loop.
from .orchestrator_handlers import (
    _handle_clone,
    _handle_container_action_menu,
    _handle_create_worktree,
    _handle_git_init,
    _handle_recent_workspaces,
    _handle_session_action_menu,
    _handle_session_resume,
    _handle_start_flow,
    _handle_statusline_install,
    _handle_team_switch,
    _handle_worktree_action_menu,
    _handle_worktree_start,
    _prepare_for_nested_ui,
)

__all__ = [
    "_apply_event",
    "_dashboard_event_from_request",
    "_handle_clone",
    "_handle_container_action_menu",
    "_handle_create_worktree",
    "_handle_git_init",
    "_handle_recent_workspaces",
    "_handle_session_action_menu",
    "_handle_session_resume",
    "_handle_start_flow",
    "_handle_statusline_install",
    "_handle_team_switch",
    "_handle_worktree_action_menu",
    "_handle_worktree_start",
    "_prepare_for_nested_ui",
    "_resolve_tab",
    "_run_dashboard_request",
    "_run_effect",
    "run_dashboard",
]

DashboardRequest: TypeAlias = (
    TeamSwitchRequested
    | StartRequested
    | RefreshRequested
    | SessionResumeRequested
    | StatuslineInstallRequested
    | RecentWorkspacesRequested
    | GitInitRequested
    | CreateWorktreeRequested
    | VerboseToggleRequested
    | SettingsRequested
    | ContainerStopRequested
    | ContainerResumeRequested
    | ContainerRemoveRequested
    | ProfileMenuRequested
    | SandboxImportRequested
    | ContainerActionMenuRequested
    | SessionActionMenuRequested
    | WorktreeActionMenuRequested
)

DASHBOARD_REQUEST_TYPES: tuple[type[Exception], ...] = (
    TeamSwitchRequested,
    StartRequested,
    RefreshRequested,
    SessionResumeRequested,
    StatuslineInstallRequested,
    RecentWorkspacesRequested,
    GitInitRequested,
    CreateWorktreeRequested,
    VerboseToggleRequested,
    SettingsRequested,
    ContainerStopRequested,
    ContainerResumeRequested,
    ContainerRemoveRequested,
    ProfileMenuRequested,
    SandboxImportRequested,
    ContainerActionMenuRequested,
    SessionActionMenuRequested,
    WorktreeActionMenuRequested,
)


def _format_last_used(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp
    return format_relative_time_from_datetime(dt)


def _dashboard_event_from_request(request: DashboardRequest) -> app_dashboard.DashboardEvent:
    if isinstance(request, TeamSwitchRequested):
        return app_dashboard.TeamSwitchEvent()
    if isinstance(request, StartRequested):
        return app_dashboard.StartFlowEvent(
            return_to=_resolve_tab(request.return_to),
            reason=request.reason,
        )
    if isinstance(request, RefreshRequested):
        return app_dashboard.RefreshEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, SessionResumeRequested):
        return app_dashboard.SessionResumeEvent(
            return_to=_resolve_tab(request.return_to),
            session=request.session,
        )
    if isinstance(request, StatuslineInstallRequested):
        return app_dashboard.StatuslineInstallEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, RecentWorkspacesRequested):
        return app_dashboard.RecentWorkspacesEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, GitInitRequested):
        return app_dashboard.GitInitEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, CreateWorktreeRequested):
        return app_dashboard.CreateWorktreeEvent(
            return_to=_resolve_tab(request.return_to),
            is_git_repo=request.is_git_repo,
        )
    if isinstance(request, VerboseToggleRequested):
        return app_dashboard.VerboseToggleEvent(
            return_to=_resolve_tab(request.return_to),
            verbose=request.verbose,
        )
    if isinstance(request, SettingsRequested):
        return app_dashboard.SettingsEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, ContainerStopRequested):
        return app_dashboard.ContainerStopEvent(
            return_to=_resolve_tab(request.return_to),
            container_id=request.container_id,
            container_name=request.container_name,
        )
    if isinstance(request, ContainerResumeRequested):
        return app_dashboard.ContainerResumeEvent(
            return_to=_resolve_tab(request.return_to),
            container_id=request.container_id,
            container_name=request.container_name,
        )
    if isinstance(request, ContainerRemoveRequested):
        return app_dashboard.ContainerRemoveEvent(
            return_to=_resolve_tab(request.return_to),
            container_id=request.container_id,
            container_name=request.container_name,
        )
    if isinstance(request, ProfileMenuRequested):
        return app_dashboard.ProfileMenuEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, SandboxImportRequested):
        return app_dashboard.SandboxImportEvent(return_to=_resolve_tab(request.return_to))
    if isinstance(request, ContainerActionMenuRequested):
        return app_dashboard.ContainerActionMenuEvent(
            return_to=_resolve_tab(request.return_to),
            container_id=request.container_id,
            container_name=request.container_name,
        )
    if isinstance(request, SessionActionMenuRequested):
        return app_dashboard.SessionActionMenuEvent(
            return_to=_resolve_tab(request.return_to),
            session=request.session,
        )
    if isinstance(request, WorktreeActionMenuRequested):
        return app_dashboard.WorktreeActionMenuEvent(
            return_to=_resolve_tab(request.return_to),
            worktree_path=request.worktree_path,
        )
    msg = f"Unsupported dashboard request: {request!r}"
    raise TypeError(msg)


def _run_dashboard_request(
    state: app_dashboard.DashboardFlowState,
    request: DashboardRequest,
) -> tuple[app_dashboard.DashboardFlowState, bool]:
    return _apply_event(state, _dashboard_event_from_request(request))


def run_dashboard() -> None:
    """Run the main SCC dashboard.

    This is the entry point for `scc` with no arguments in a TTY.
    It loads current resource data and displays the interactive dashboard.

    Handles intent exceptions by executing the requested flow outside the
    Rich Live context (critical to avoid nested Live conflicts), then
    reloading the dashboard with restored tab state.

    Intent Exceptions:
        - TeamSwitchRequested: Show team picker, reload with new team
        - StartRequested: Run start wizard, return to source tab with fresh data
        - RefreshRequested: Reload tab data, return to source tab
        - VerboseToggleRequested: Toggle verbose worktree status display
    """
    from ... import config as scc_config
    from ... import sessions

    # Show one-time onboarding banner for new users
    if not scc_config.has_seen_onboarding():
        orchestrator_menus._show_onboarding_banner()
        scc_config.mark_onboarding_seen()

    flow_state = app_dashboard.DashboardFlowState()
    session_service = sessions.get_session_service()

    def _load_tabs(
        verbose_worktrees: bool = False,
    ) -> Mapping[
        app_dashboard.DashboardTab,
        app_dashboard.DashboardTabData,
    ]:
        return app_dashboard.load_all_tab_data(
            session_service=session_service,
            format_last_used=_format_last_used,
            verbose_worktrees=verbose_worktrees,
        )

    while True:
        view, flow_state = app_dashboard.build_dashboard_view(
            flow_state,
            _load_tabs,
        )
        tabs = {tab: _to_tab_data(tab_data) for tab, tab_data in view.tabs.items()}
        state = DashboardState(
            active_tab=view.active_tab,
            tabs=tabs,
            list_state=ListState(items=tabs[view.active_tab].items),
            status_message=view.status_message,
            verbose_worktrees=view.verbose_worktrees,
        )

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break
        except DASHBOARD_REQUEST_TYPES as request:
            flow_state, should_exit = _run_dashboard_request(
                flow_state,
                cast(DashboardRequest, request),
            )
            if should_exit:
                break


def _resolve_tab(tab_name: str | None) -> app_dashboard.DashboardTab:
    if not tab_name:
        return app_dashboard.DashboardTab.STATUS
    try:
        return app_dashboard.DashboardTab[tab_name]
    except KeyError:
        return app_dashboard.DashboardTab.STATUS


def _apply_event(
    state: app_dashboard.DashboardFlowState,
    event: app_dashboard.DashboardEvent,
) -> tuple[app_dashboard.DashboardFlowState, bool]:
    step = app_dashboard.handle_dashboard_event(state, event)
    if isinstance(step, app_dashboard.DashboardFlowOutcome):
        return step.state, step.exit_dashboard
    result = _run_effect(step.effect)
    outcome = app_dashboard.apply_dashboard_effect_result(step.state, step.effect, result)
    return outcome.state, outcome.exit_dashboard


def _run_effect(effect: app_dashboard.DashboardEffect) -> object:
    if isinstance(effect, app_dashboard.TeamSwitchEvent):
        _handle_team_switch()
        return None
    if isinstance(effect, app_dashboard.StartFlowEvent):
        return _handle_start_flow(effect.reason)
    if isinstance(effect, app_dashboard.SessionResumeEvent):
        return _handle_session_resume(effect.session)
    if isinstance(effect, app_dashboard.StatuslineInstallEvent):
        return _handle_statusline_install()
    if isinstance(effect, app_dashboard.RecentWorkspacesEvent):
        return _handle_recent_workspaces()
    if isinstance(effect, app_dashboard.GitInitEvent):
        return _handle_git_init()
    if isinstance(effect, app_dashboard.CreateWorktreeEvent):
        if effect.is_git_repo:
            return _handle_create_worktree()
        return _handle_clone()
    if isinstance(effect, app_dashboard.SettingsEvent):
        return orchestrator_menus._handle_settings()
    if isinstance(effect, app_dashboard.ContainerStopEvent):
        return orchestrator_container_actions._handle_container_stop(
            effect.container_id,
            effect.container_name,
        )
    if isinstance(effect, app_dashboard.ContainerResumeEvent):
        return orchestrator_container_actions._handle_container_resume(
            effect.container_id,
            effect.container_name,
        )
    if isinstance(effect, app_dashboard.ContainerRemoveEvent):
        return orchestrator_container_actions._handle_container_remove(
            effect.container_id,
            effect.container_name,
        )
    if isinstance(effect, app_dashboard.ProfileMenuEvent):
        return orchestrator_menus._handle_profile_menu()
    if isinstance(effect, app_dashboard.SandboxImportEvent):
        return orchestrator_menus._handle_sandbox_import()
    if isinstance(effect, app_dashboard.ContainerActionMenuEvent):
        return _handle_container_action_menu(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.SessionActionMenuEvent):
        return _handle_session_action_menu(effect.session)
    if isinstance(effect, app_dashboard.WorktreeActionMenuEvent):
        return _handle_worktree_action_menu(effect.worktree_path)
    msg = f"Unsupported dashboard effect: {effect}"
    raise ValueError(msg)
