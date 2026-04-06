"""Characterization tests for application/dashboard.py.

Lock the current behavior of dashboard view model types, event routing,
and effect application logic before S02 surgery. Complements T02's
orchestrator characterization by covering the application-layer flow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scc_cli.application.dashboard import (
    ContainerStopEvent,
    CreateWorktreeEvent,
    DashboardEffectRequest,
    DashboardFlowOutcome,
    DashboardFlowState,
    DashboardTab,
    DashboardTabData,
    GitInitEvent,
    PlaceholderItem,
    PlaceholderKind,
    RecentWorkspacesEvent,
    RefreshEvent,
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
    WorktreeItem,
    apply_dashboard_effect_result,
    build_dashboard_view,
    handle_dashboard_event,
)
from scc_cli.ports.session_models import SessionSummary

# ═════════════════════════════════════════════��═════════════════════════════════
# View model types
# ═══════════════════════════���═══════════════════════════════════════���═══════════


class TestDashboardTab:
    """Tab enum display names are stable."""

    def test_display_names(self) -> None:
        assert DashboardTab.STATUS.display_name == "Status"
        assert DashboardTab.CONTAINERS.display_name == "Containers"
        assert DashboardTab.SESSIONS.display_name == "Sessions"
        assert DashboardTab.WORKTREES.display_name == "Worktrees"


class TestDashboardTabData:
    """Tab data subtitle generation."""

    def test_subtitle_same_counts(self) -> None:
        data = DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[],
            count_active=3,
            count_total=3,
        )
        assert data.subtitle == "3 total"

    def test_subtitle_different_counts(self) -> None:
        data = DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[],
            count_active=2,
            count_total=5,
        )
        assert data.subtitle == "2 active, 5 total"


class TestStartFlowResult:
    """Legacy bool/None conversion."""

    def test_from_legacy_none_is_quit(self) -> None:
        result = StartFlowResult.from_legacy(None)
        assert result.decision is StartFlowDecision.QUIT

    def test_from_legacy_true_is_launched(self) -> None:
        result = StartFlowResult.from_legacy(True)
        assert result.decision is StartFlowDecision.LAUNCHED

    def test_from_legacy_false_is_cancelled(self) -> None:
        result = StartFlowResult.from_legacy(False)
        assert result.decision is StartFlowDecision.CANCELLED
        assert result.message is None


# ══════════��══════════════════════════════════════════════════════���═════════════
# build_dashboard_view
# ══════════════════════════════════════════════════════��════════════════════════


class TestBuildDashboardView:
    """View building and one-time state clearing."""

    def _make_loader(self) -> MagicMock:
        """Stub loader returning minimal tab data."""
        tab_data = {
            DashboardTab.STATUS: DashboardTabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[],
                count_active=0,
                count_total=0,
            ),
        }
        return MagicMock(return_value=tab_data)

    def test_default_active_tab_is_status(self) -> None:
        state = DashboardFlowState()
        view, next_state = build_dashboard_view(state, self._make_loader())
        assert view.active_tab == DashboardTab.STATUS

    def test_restore_tab_honored(self) -> None:
        loader = self._make_loader()
        loader.return_value[DashboardTab.CONTAINERS] = DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[],
            count_active=0,
            count_total=0,
        )
        state = DashboardFlowState(restore_tab=DashboardTab.CONTAINERS)
        view, _ = build_dashboard_view(state, loader)
        assert view.active_tab == DashboardTab.CONTAINERS

    def test_restore_tab_cleared_after_view(self) -> None:
        state = DashboardFlowState(restore_tab=DashboardTab.SESSIONS)
        _, next_state = build_dashboard_view(state, self._make_loader())
        assert next_state.restore_tab is None

    def test_toast_cleared_after_view(self) -> None:
        state = DashboardFlowState(toast_message="Hello")
        view, next_state = build_dashboard_view(state, self._make_loader())
        assert view.status_message == "Hello"
        assert next_state.toast_message is None

    def test_invalid_restore_tab_falls_back_to_status(self) -> None:
        state = DashboardFlowState(restore_tab=DashboardTab.WORKTREES)
        # Loader only has STATUS tab
        view, _ = build_dashboard_view(state, self._make_loader())
        assert view.active_tab == DashboardTab.STATUS


# ══════════════════════════════��═══════════════════════════════════════��════════
# handle_dashboard_event — routing
# ════════════════════════════════════���══════════════════════════════════════════


class TestHandleDashboardEvent:
    """Event-to-outcome routing."""

    def test_team_switch_returns_effect(self) -> None:
        state = DashboardFlowState()
        result = handle_dashboard_event(state, TeamSwitchEvent())
        assert isinstance(result, DashboardEffectRequest)

    def test_refresh_returns_outcome(self) -> None:
        state = DashboardFlowState()
        result = handle_dashboard_event(state, RefreshEvent(return_to=DashboardTab.STATUS))
        assert isinstance(result, DashboardFlowOutcome)

    def test_verbose_toggle_sets_state(self) -> None:
        state = DashboardFlowState(verbose_worktrees=False)
        result = handle_dashboard_event(
            state, VerboseToggleEvent(return_to=DashboardTab.WORKTREES, verbose=True)
        )
        assert isinstance(result, DashboardFlowOutcome)
        assert result.state.verbose_worktrees is True
        assert result.state.toast_message == "Status on"

    def test_verbose_toggle_off(self) -> None:
        state = DashboardFlowState(verbose_worktrees=True)
        result = handle_dashboard_event(
            state, VerboseToggleEvent(return_to=DashboardTab.WORKTREES, verbose=False)
        )
        assert isinstance(result, DashboardFlowOutcome)
        assert result.state.verbose_worktrees is False
        assert result.state.toast_message == "Status off"

    def test_start_flow_preserves_return_tab(self) -> None:
        state = DashboardFlowState()
        result = handle_dashboard_event(
            state, StartFlowEvent(return_to=DashboardTab.CONTAINERS, reason="test")
        )
        assert isinstance(result, DashboardEffectRequest)
        assert result.state.restore_tab == DashboardTab.CONTAINERS

    def test_settings_returns_effect(self) -> None:
        state = DashboardFlowState()
        result = handle_dashboard_event(state, SettingsEvent(return_to=DashboardTab.STATUS))
        assert isinstance(result, DashboardEffectRequest)

    def test_unsupported_event_raises(self) -> None:
        state = DashboardFlowState()
        with pytest.raises(ValueError, match="Unsupported event"):
            handle_dashboard_event(state, "not_an_event")  # type: ignore[arg-type]


# ════════════════════════════���══════════════════════════════════════════════════
# apply_dashboard_effect_result
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplyDashboardEffectResult:
    """Effect result application to state."""

    def test_start_flow_quit_exits(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StartFlowEvent(return_to=DashboardTab.STATUS, reason="test"),
            StartFlowResult(decision=StartFlowDecision.QUIT),
        )
        assert result.exit_dashboard is True

    def test_start_flow_launched_exits(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StartFlowEvent(return_to=DashboardTab.STATUS, reason="test"),
            StartFlowResult(decision=StartFlowDecision.LAUNCHED),
        )
        assert result.exit_dashboard is True

    def test_start_flow_cancelled_continues(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StartFlowEvent(return_to=DashboardTab.STATUS, reason="test"),
            StartFlowResult(decision=StartFlowDecision.CANCELLED),
        )
        assert result.exit_dashboard is not True
        assert result.state.toast_message == "Start cancelled"

    def test_start_flow_cancelled_uses_specific_message(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StartFlowEvent(return_to=DashboardTab.STATUS, reason="test"),
            StartFlowResult(
                decision=StartFlowDecision.CANCELLED,
                message="Kept existing sandbox",
            ),
        )
        assert result.exit_dashboard is not True
        assert result.state.toast_message == "Kept existing sandbox"

    def test_session_resume_success_exits(self) -> None:
        session = MagicMock(spec=SessionSummary)
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            SessionResumeEvent(return_to=DashboardTab.SESSIONS, session=session),
            True,
        )
        assert result.exit_dashboard is True

    def test_session_resume_failure_shows_toast(self) -> None:
        session = MagicMock(spec=SessionSummary)
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            SessionResumeEvent(return_to=DashboardTab.SESSIONS, session=session),
            False,
        )
        assert result.state.toast_message == "Session resume failed"

    def test_statusline_install_success(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StatuslineInstallEvent(return_to=DashboardTab.STATUS),
            True,
        )
        assert result.state.toast_message is not None
        assert "installed" in result.state.toast_message.lower()

    def test_statusline_install_failure(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            StatuslineInstallEvent(return_to=DashboardTab.STATUS),
            False,
        )
        assert result.state.toast_message is not None
        assert "failed" in result.state.toast_message.lower()

    def test_container_stop_success(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            ContainerStopEvent(
                return_to=DashboardTab.CONTAINERS, container_id="abc", container_name="c1"
            ),
            (True, None),
        )
        assert result.state.toast_message is not None
        assert "stopped" in result.state.toast_message.lower()

    def test_container_stop_failure(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            ContainerStopEvent(
                return_to=DashboardTab.CONTAINERS, container_id="abc", container_name="c1"
            ),
            (False, "Error: connection refused"),
        )
        assert result.state.toast_message is not None
        assert "connection refused" in result.state.toast_message.lower()

    def test_container_stop_invalid_result_raises(self) -> None:
        state = DashboardFlowState()
        with pytest.raises(TypeError, match="Container effect"):
            apply_dashboard_effect_result(
                state,
                ContainerStopEvent(
                    return_to=DashboardTab.CONTAINERS, container_id="a", container_name="c"
                ),
                "not_a_tuple",
            )

    def test_git_init_success(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state, GitInitEvent(return_to=DashboardTab.STATUS), True
        )
        assert result.state.toast_message is not None
        assert "initialized" in result.state.toast_message.lower()

    def test_create_worktree_git_repo(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            CreateWorktreeEvent(return_to=DashboardTab.WORKTREES, is_git_repo=True),
            True,
        )
        assert result.state.toast_message is not None
        assert "worktree created" in result.state.toast_message.lower()

    def test_create_worktree_clone(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            CreateWorktreeEvent(return_to=DashboardTab.WORKTREES, is_git_repo=False),
            True,
        )
        assert result.state.toast_message is not None
        assert "cloned" in result.state.toast_message.lower()

    def test_settings_result_applied(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            SettingsEvent(return_to=DashboardTab.STATUS),
            "Settings saved",
        )
        assert result.state.toast_message == "Settings saved"

    def test_recent_workspaces_selected(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            RecentWorkspacesEvent(return_to=DashboardTab.STATUS),
            "/path/to/workspace",
        )
        assert result.state.toast_message is not None
        assert "/path/to/workspace" in result.state.toast_message

    def test_recent_workspaces_cancelled(self) -> None:
        state = DashboardFlowState()
        result = apply_dashboard_effect_result(
            state,
            RecentWorkspacesEvent(return_to=DashboardTab.STATUS),
            None,
        )
        assert result.state.toast_message == "Cancelled"

    def test_unsupported_effect_raises(self) -> None:
        state = DashboardFlowState()
        with pytest.raises(ValueError, match="Unsupported effect"):
            apply_dashboard_effect_result(state, "not_an_effect", None)  # type: ignore[arg-type]

    def test_start_flow_wrong_type_raises(self) -> None:
        state = DashboardFlowState()
        with pytest.raises(TypeError, match="StartFlowResult"):
            apply_dashboard_effect_result(
                state,
                StartFlowEvent(return_to=DashboardTab.STATUS, reason="test"),
                "wrong_type",
            )


# ═════════════��═════════════════════════════════════════════════════════════════
# Placeholder and item types
# ══════════════════════════════��════════════════════════════════════════════════


class TestItemTypes:
    """View model item frozen dataclass construction."""

    def test_status_item(self) -> None:
        item = StatusItem(label="Start Session", description="Launch a new session")
        assert item.label == "Start Session"
        assert item.action is None

    def test_status_item_with_action(self) -> None:
        item = StatusItem(
            label="Start",
            description="Start",
            action=StatusAction.START_SESSION,
        )
        assert item.action is StatusAction.START_SESSION

    def test_placeholder_item(self) -> None:
        item = PlaceholderItem(
            label="No containers",
            description="No Docker containers running",
            kind=PlaceholderKind.NO_CONTAINERS,
        )
        assert item.startable is False
        assert item.kind is PlaceholderKind.NO_CONTAINERS

    def test_worktree_item(self) -> None:
        item = WorktreeItem(label="main", description="/path/to/main", path="/path/to/main")
        assert item.path == "/path/to/main"
