"""Unit tests for application dashboard flow."""

from __future__ import annotations

from scc_cli.application import dashboard as app_dashboard


def _empty_tab_data(tab: app_dashboard.DashboardTab) -> app_dashboard.DashboardTabData:
    return app_dashboard.DashboardTabData(
        tab=tab,
        title=tab.display_name,
        items=[],
        count_active=0,
        count_total=0,
    )


def test_build_dashboard_view_clears_one_time_state() -> None:
    tabs = {tab: _empty_tab_data(tab) for tab in app_dashboard.DashboardTab}

    def loader(verbose: bool) -> dict[app_dashboard.DashboardTab, app_dashboard.DashboardTabData]:
        assert verbose is True
        return tabs

    state = app_dashboard.DashboardFlowState(
        restore_tab=app_dashboard.DashboardTab.WORKTREES,
        toast_message="Welcome",
        verbose_worktrees=True,
    )

    view, next_state = app_dashboard.build_dashboard_view(state, loader)

    assert view.active_tab is app_dashboard.DashboardTab.WORKTREES
    assert view.status_message == "Welcome"
    assert next_state.restore_tab is None
    assert next_state.toast_message is None


def test_start_flow_event_sets_restore_tab() -> None:
    state = app_dashboard.DashboardFlowState()
    event = app_dashboard.StartFlowEvent(
        return_to=app_dashboard.DashboardTab.SESSIONS,
        reason="dashboard_start",
    )

    step = app_dashboard.handle_dashboard_event(state, event)

    assert isinstance(step, app_dashboard.DashboardEffectRequest)
    assert step.state.restore_tab is app_dashboard.DashboardTab.SESSIONS


def test_start_flow_cancel_sets_toast() -> None:
    state = app_dashboard.DashboardFlowState()
    effect = app_dashboard.StartFlowEvent(
        return_to=app_dashboard.DashboardTab.STATUS,
        reason="dashboard_start",
    )

    outcome = app_dashboard.apply_dashboard_effect_result(
        state,
        effect,
        app_dashboard.StartFlowResult(decision=app_dashboard.StartFlowDecision.CANCELLED),
    )

    assert outcome.exit_dashboard is False
    assert outcome.state.toast_message == "Start cancelled"


def test_session_resume_success_exits_dashboard() -> None:
    state = app_dashboard.DashboardFlowState()
    effect = app_dashboard.SessionResumeEvent(
        return_to=app_dashboard.DashboardTab.SESSIONS,
        session={"name": "session"},
    )

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, True)

    assert outcome.exit_dashboard is True


def test_verbose_toggle_updates_state() -> None:
    state = app_dashboard.DashboardFlowState()
    event = app_dashboard.VerboseToggleEvent(
        return_to=app_dashboard.DashboardTab.WORKTREES,
        verbose=True,
    )

    step = app_dashboard.handle_dashboard_event(state, event)

    assert isinstance(step, app_dashboard.DashboardFlowOutcome)
    assert step.state.verbose_worktrees is True
    assert step.state.toast_message == "Status on"


def test_refresh_event_sets_restore_tab() -> None:
    state = app_dashboard.DashboardFlowState()
    event = app_dashboard.RefreshEvent(return_to=app_dashboard.DashboardTab.CONTAINERS)

    step = app_dashboard.handle_dashboard_event(state, event)

    assert isinstance(step, app_dashboard.DashboardFlowOutcome)
    assert step.state.restore_tab is app_dashboard.DashboardTab.CONTAINERS


def test_statusline_install_effect_sets_message() -> None:
    state = app_dashboard.DashboardFlowState()
    effect = app_dashboard.StatuslineInstallEvent(return_to=app_dashboard.DashboardTab.STATUS)

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, True)

    assert outcome.state.toast_message == "Statusline installed successfully"

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, False)

    assert outcome.state.toast_message == "Statusline installation failed"


def test_create_worktree_effect_messages() -> None:
    state = app_dashboard.DashboardFlowState()
    effect = app_dashboard.CreateWorktreeEvent(
        return_to=app_dashboard.DashboardTab.WORKTREES,
        is_git_repo=True,
    )

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, True)

    assert outcome.state.toast_message == "Worktree created"

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, False)

    assert outcome.state.toast_message == "Worktree creation cancelled"

    clone_effect = app_dashboard.CreateWorktreeEvent(
        return_to=app_dashboard.DashboardTab.WORKTREES,
        is_git_repo=False,
    )

    outcome = app_dashboard.apply_dashboard_effect_result(state, clone_effect, True)

    assert outcome.state.toast_message == "Repository cloned"

    outcome = app_dashboard.apply_dashboard_effect_result(state, clone_effect, False)

    assert outcome.state.toast_message == "Clone cancelled"


def test_container_stop_effect_uses_fallback_message() -> None:
    state = app_dashboard.DashboardFlowState()
    effect = app_dashboard.ContainerStopEvent(
        return_to=app_dashboard.DashboardTab.CONTAINERS,
        container_id="abc",
        container_name="scc-demo",
    )

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, (True, None))

    assert outcome.state.toast_message == "Container stopped"

    outcome = app_dashboard.apply_dashboard_effect_result(state, effect, (False, "Custom"))

    assert outcome.state.toast_message == "Custom"
