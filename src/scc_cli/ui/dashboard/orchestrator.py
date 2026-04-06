"""Orchestration functions for the dashboard module.

This module contains the entry point and flow handlers:
- run_dashboard: Main entry point for `scc` with no arguments
- _apply_event / _run_effect: Event routing and effect execution

Handler implementations live in orchestrator_handlers.py.

The orchestrator manages the dashboard lifecycle including intent exceptions
that exit the Rich Live context before handling nested UI components.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

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
from ._dashboard import Dashboard
from .loaders import _to_tab_data
from .models import DashboardState

# Re-export handler functions for backward compatibility and __init__.py
from .orchestrator_handlers import (
    _handle_clone,
    _handle_container_action_menu,
    _handle_container_remove,
    _handle_container_resume,
    _handle_container_stop,
    _handle_create_worktree,
    _handle_git_init,
    _handle_profile_menu,
    _handle_recent_workspaces,
    _handle_sandbox_import,
    _handle_session_action_menu,
    _handle_session_resume,
    _handle_settings,
    _handle_start_flow,
    _handle_statusline_install,
    _handle_team_switch,
    _handle_worktree_action_menu,
    _handle_worktree_start,
    _prepare_for_nested_ui,
    _show_onboarding_banner,
)

__all__ = [
    "_apply_event",
    "_handle_clone",
    "_handle_container_action_menu",
    "_handle_container_remove",
    "_handle_container_resume",
    "_handle_container_stop",
    "_handle_create_worktree",
    "_handle_git_init",
    "_handle_profile_menu",
    "_handle_recent_workspaces",
    "_handle_sandbox_import",
    "_handle_session_action_menu",
    "_handle_session_resume",
    "_handle_settings",
    "_handle_start_flow",
    "_handle_statusline_install",
    "_handle_team_switch",
    "_handle_worktree_action_menu",
    "_handle_worktree_start",
    "_prepare_for_nested_ui",
    "_resolve_tab",
    "_run_effect",
    "_show_onboarding_banner",
    "run_dashboard",
]


def _format_last_used(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp
    return format_relative_time_from_datetime(dt)


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
        _show_onboarding_banner()
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
        except TeamSwitchRequested:
            flow_state, should_exit = _apply_event(flow_state, app_dashboard.TeamSwitchEvent())
            if should_exit:
                break

        except StartRequested as start_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.StartFlowEvent(
                    return_to=_resolve_tab(start_req.return_to),
                    reason=start_req.reason,
                ),
            )
            if should_exit:
                break

        except RefreshRequested as refresh_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.RefreshEvent(return_to=_resolve_tab(refresh_req.return_to)),
            )
            if should_exit:
                break

        except SessionResumeRequested as resume_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SessionResumeEvent(
                    return_to=_resolve_tab(resume_req.return_to),
                    session=resume_req.session,
                ),
            )
            if should_exit:
                break

        except StatuslineInstallRequested as statusline_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.StatuslineInstallEvent(
                    return_to=_resolve_tab(statusline_req.return_to)
                ),
            )
            if should_exit:
                break

        except RecentWorkspacesRequested as recent_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.RecentWorkspacesEvent(return_to=_resolve_tab(recent_req.return_to)),
            )
            if should_exit:
                break

        except GitInitRequested as init_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.GitInitEvent(return_to=_resolve_tab(init_req.return_to)),
            )
            if should_exit:
                break

        except CreateWorktreeRequested as create_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.CreateWorktreeEvent(
                    return_to=_resolve_tab(create_req.return_to),
                    is_git_repo=create_req.is_git_repo,
                ),
            )
            if should_exit:
                break

        except VerboseToggleRequested as verbose_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.VerboseToggleEvent(
                    return_to=_resolve_tab(verbose_req.return_to),
                    verbose=verbose_req.verbose,
                ),
            )
            if should_exit:
                break

        except SettingsRequested as settings_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SettingsEvent(return_to=_resolve_tab(settings_req.return_to)),
            )
            if should_exit:
                break

        except ContainerStopRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerStopEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ContainerResumeRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerResumeEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ContainerRemoveRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerRemoveEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ProfileMenuRequested as profile_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ProfileMenuEvent(return_to=_resolve_tab(profile_req.return_to)),
            )
            if should_exit:
                break

        except SandboxImportRequested as import_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SandboxImportEvent(return_to=_resolve_tab(import_req.return_to)),
            )
            if should_exit:
                break

        except ContainerActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    container_id=action_req.container_id,
                    container_name=action_req.container_name,
                ),
            )
            if should_exit:
                break

        except SessionActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SessionActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    session=action_req.session,
                ),
            )
            if should_exit:
                break

        except WorktreeActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.WorktreeActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    worktree_path=action_req.worktree_path,
                ),
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
        return _handle_settings()
    if isinstance(effect, app_dashboard.ContainerStopEvent):
        return _handle_container_stop(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ContainerResumeEvent):
        return _handle_container_resume(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ContainerRemoveEvent):
        return _handle_container_remove(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ProfileMenuEvent):
        return _handle_profile_menu()
    if isinstance(effect, app_dashboard.SandboxImportEvent):
        return _handle_sandbox_import()
    if isinstance(effect, app_dashboard.ContainerActionMenuEvent):
        return _handle_container_action_menu(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.SessionActionMenuEvent):
        return _handle_session_action_menu(effect.session)
    if isinstance(effect, app_dashboard.WorktreeActionMenuEvent):
        return _handle_worktree_action_menu(effect.worktree_path)
    msg = f"Unsupported dashboard effect: {effect}"
    raise ValueError(msg)
