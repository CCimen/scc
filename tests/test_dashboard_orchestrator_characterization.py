"""Characterization tests for ui/dashboard/orchestrator.py and application/dashboard.py.

These tests capture the current behavior of the dashboard orchestration
before S02 surgery decomposes it. They protect against accidental behavior
changes during the split.

Target: src/scc_cli/ui/dashboard/orchestrator.py (run_dashboard 232 lines, 6% coverage)

Because run_dashboard is tightly coupled to Rich Live, TUI keypresses, and
the full config stack, we test the pure application-layer logic that the
orchestrator delegates to:
  - DashboardFlowState lifecycle
  - build_dashboard_view with mock loaders
  - handle_dashboard_event routing
  - apply_dashboard_effect_result state transitions
  - _resolve_tab fallback behavior
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from scc_cli.application.dashboard import (
    ContainerStopEvent,
    DashboardEffectRequest,
    DashboardFlowOutcome,
    DashboardFlowState,
    DashboardTab,
    DashboardTabData,
    PlaceholderItem,
    PlaceholderKind,
    RefreshEvent,
    StartFlowDecision,
    StartFlowEvent,
    StartFlowResult,
    TeamSwitchEvent,
    VerboseToggleEvent,
    apply_dashboard_effect_result,
    build_dashboard_view,
    handle_dashboard_event,
    placeholder_start_reason,
    placeholder_tip,
)
from scc_cli.ui.dashboard.orchestrator import _resolve_tab


def _make_empty_tab_data(tab: DashboardTab) -> DashboardTabData:
    """Build minimal DashboardTabData for testing."""
    return DashboardTabData(
        tab=tab,
        title=tab.display_name,
        items=[],
        count_active=0,
        count_total=0,
    )


def _make_loader(
    tabs: Mapping[DashboardTab, DashboardTabData] | None = None,
) -> object:
    """Build a mock data loader that returns all tabs."""
    if tabs is None:
        tabs = {tab: _make_empty_tab_data(tab) for tab in DashboardTab}

    def loader(verbose: bool = False) -> Mapping[DashboardTab, DashboardTabData]:
        return tabs

    return loader


# ═══════════════════════════════════════════════════════════════════════════════
# build_dashboard_view
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildDashboardView:
    """Characterize build_dashboard_view behavior."""

    def test_default_state_selects_status_tab(self) -> None:
        """Default flow state → STATUS tab is active."""
        state = DashboardFlowState()
        view, next_state = build_dashboard_view(state, _make_loader())
        assert view.active_tab == DashboardTab.STATUS

    def test_restore_tab_is_honored(self) -> None:
        """restore_tab in state → that tab becomes active."""
        state = DashboardFlowState(restore_tab=DashboardTab.SESSIONS)
        view, next_state = build_dashboard_view(state, _make_loader())
        assert view.active_tab == DashboardTab.SESSIONS

    def test_restore_tab_cleared_after_use(self) -> None:
        """restore_tab is consumed (cleared) after building the view."""
        state = DashboardFlowState(restore_tab=DashboardTab.CONTAINERS)
        _, next_state = build_dashboard_view(state, _make_loader())
        assert next_state.restore_tab is None

    def test_toast_message_cleared_after_use(self) -> None:
        """toast_message is consumed (cleared) after building the view."""
        state = DashboardFlowState(toast_message="Hello")
        view, next_state = build_dashboard_view(state, _make_loader())
        assert view.status_message == "Hello"
        assert next_state.toast_message is None

    def test_invalid_restore_tab_falls_back_to_status(self) -> None:
        """If restore_tab is not in the loaded tabs, fall back to STATUS."""
        # Provide only STATUS and CONTAINERS tabs
        partial_tabs = {
            DashboardTab.STATUS: _make_empty_tab_data(DashboardTab.STATUS),
            DashboardTab.CONTAINERS: _make_empty_tab_data(DashboardTab.CONTAINERS),
        }
        state = DashboardFlowState(restore_tab=DashboardTab.WORKTREES)
        view, _ = build_dashboard_view(state, _make_loader(partial_tabs))
        assert view.active_tab == DashboardTab.STATUS


# ═══════════════════════════════════════════════════════════════════════════════
# handle_dashboard_event routing
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleDashboardEvent:
    """Characterize event → effect/outcome routing."""

    def test_team_switch_emits_effect(self) -> None:
        """TeamSwitchEvent → DashboardEffectRequest with the event as effect."""
        state = DashboardFlowState()
        result = handle_dashboard_event(state, TeamSwitchEvent())
        assert isinstance(result, DashboardEffectRequest)
        assert isinstance(result.effect, TeamSwitchEvent)

    def test_start_flow_saves_return_tab(self) -> None:
        """StartFlowEvent → state preserves return_to tab."""
        state = DashboardFlowState()
        event = StartFlowEvent(return_to=DashboardTab.SESSIONS, reason="test")
        result = handle_dashboard_event(state, event)
        assert isinstance(result, DashboardEffectRequest)
        assert result.state.restore_tab == DashboardTab.SESSIONS

    def test_refresh_returns_outcome_not_effect(self) -> None:
        """RefreshEvent → DashboardFlowOutcome (no side effect needed)."""
        state = DashboardFlowState()
        event = RefreshEvent(return_to=DashboardTab.CONTAINERS)
        result = handle_dashboard_event(state, event)
        assert isinstance(result, DashboardFlowOutcome)
        assert result.state.restore_tab == DashboardTab.CONTAINERS

    def test_verbose_toggle_sets_flag_and_toast(self) -> None:
        """VerboseToggleEvent → outcome with verbose flag and toast message."""
        state = DashboardFlowState()
        event = VerboseToggleEvent(return_to=DashboardTab.WORKTREES, verbose=True)
        result = handle_dashboard_event(state, event)
        assert isinstance(result, DashboardFlowOutcome)
        assert result.state.verbose_worktrees is True
        assert result.state.toast_message == "Status on"

    def test_verbose_toggle_off_message(self) -> None:
        """VerboseToggleEvent(verbose=False) → 'Status off' toast."""
        state = DashboardFlowState(verbose_worktrees=True)
        event = VerboseToggleEvent(return_to=DashboardTab.WORKTREES, verbose=False)
        result = handle_dashboard_event(state, event)
        assert isinstance(result, DashboardFlowOutcome)
        assert result.state.verbose_worktrees is False
        assert result.state.toast_message == "Status off"


# ══════════════════════════════════════════════════════════════════════════════
# apply_dashboard_effect_result
# ══════════════════════════════════════════════════════════════════════════════


class TestApplyEffectResult:
    """Characterize effect result → state transitions."""

    def test_start_flow_quit_exits_dashboard(self) -> None:
        """StartFlowResult.QUIT → exit_dashboard=True."""
        state = DashboardFlowState()
        effect = StartFlowEvent(return_to=DashboardTab.STATUS, reason="test")
        result = StartFlowResult(decision=StartFlowDecision.QUIT)
        outcome = apply_dashboard_effect_result(state, effect, result)
        assert outcome.exit_dashboard is True

    def test_start_flow_launched_exits_dashboard(self) -> None:
        """StartFlowResult.LAUNCHED → exit_dashboard=True."""
        state = DashboardFlowState()
        effect = StartFlowEvent(return_to=DashboardTab.STATUS, reason="test")
        result = StartFlowResult(decision=StartFlowDecision.LAUNCHED)
        outcome = apply_dashboard_effect_result(state, effect, result)
        assert outcome.exit_dashboard is True

    def test_start_flow_cancelled_stays_with_toast(self) -> None:
        """StartFlowResult.CANCELLED → stays on dashboard with toast."""
        state = DashboardFlowState()
        effect = StartFlowEvent(return_to=DashboardTab.STATUS, reason="test")
        result = StartFlowResult(decision=StartFlowDecision.CANCELLED)
        outcome = apply_dashboard_effect_result(state, effect, result)
        assert outcome.exit_dashboard is False
        assert outcome.state.toast_message == "Start cancelled"

    def test_container_stop_success_toast(self) -> None:
        """Successful container stop → success toast message."""
        state = DashboardFlowState()
        effect = ContainerStopEvent(
            return_to=DashboardTab.CONTAINERS,
            container_id="abc",
            container_name="test",
        )
        outcome = apply_dashboard_effect_result(state, effect, (True, None))
        assert outcome.state.toast_message == "Container stopped"

    def test_container_stop_failure_toast(self) -> None:
        """Failed container stop → failure toast message."""
        state = DashboardFlowState()
        effect = ContainerStopEvent(
            return_to=DashboardTab.CONTAINERS,
            container_id="abc",
            container_name="test",
        )
        outcome = apply_dashboard_effect_result(state, effect, (False, None))
        assert outcome.state.toast_message == "Stop failed"

    def test_container_stop_custom_message(self) -> None:
        """Container stop with custom message → uses custom message."""
        state = DashboardFlowState()
        effect = ContainerStopEvent(
            return_to=DashboardTab.CONTAINERS,
            container_id="abc",
            container_name="test",
        )
        outcome = apply_dashboard_effect_result(state, effect, (True, "Custom msg"))
        assert outcome.state.toast_message == "Custom msg"

    def test_start_flow_wrong_result_type_raises(self) -> None:
        """StartFlowEvent with wrong result type → TypeError."""
        state = DashboardFlowState()
        effect = StartFlowEvent(return_to=DashboardTab.STATUS, reason="test")
        with pytest.raises(TypeError, match="StartFlowResult"):
            apply_dashboard_effect_result(state, effect, "wrong")


# ═══════════════════════════════════════════════════════════════════════════════
# _resolve_tab fallback
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveTab:
    """Characterize _resolve_tab fallback behavior."""

    def test_none_returns_status(self) -> None:
        """None tab name → STATUS."""
        assert _resolve_tab(None) == DashboardTab.STATUS

    def test_empty_string_returns_status(self) -> None:
        """Empty string → STATUS."""
        assert _resolve_tab("") == DashboardTab.STATUS

    def test_valid_tab_name_resolved(self) -> None:
        """Valid enum name → matching tab."""
        assert _resolve_tab("CONTAINERS") == DashboardTab.CONTAINERS
        assert _resolve_tab("SESSIONS") == DashboardTab.SESSIONS

    def test_invalid_tab_name_returns_status(self) -> None:
        """Invalid tab name → falls back to STATUS."""
        assert _resolve_tab("NONEXISTENT") == DashboardTab.STATUS


# ═══════════════════════════════════════════════════════════════════════════════
# Placeholder helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlaceholderHelpers:
    """Characterize placeholder utility functions."""

    def test_tip_for_no_containers(self) -> None:
        """NO_CONTAINERS placeholder has actionable tip."""
        tip = placeholder_tip(PlaceholderKind.NO_CONTAINERS)
        assert "start" in tip.lower() or "scc start" in tip

    def test_tip_for_no_sessions(self) -> None:
        """NO_SESSIONS placeholder has actionable tip."""
        tip = placeholder_tip(PlaceholderKind.NO_SESSIONS)
        assert "session" in tip.lower()

    def test_start_reason_for_no_containers(self) -> None:
        """NO_CONTAINERS placeholder → 'no_containers' reason."""
        item = PlaceholderItem(
            label="", description="", kind=PlaceholderKind.NO_CONTAINERS, startable=True
        )
        assert placeholder_start_reason(item) == "no_containers"

    def test_start_reason_for_no_sessions(self) -> None:
        """NO_SESSIONS placeholder → 'no_sessions' reason."""
        item = PlaceholderItem(
            label="", description="", kind=PlaceholderKind.NO_SESSIONS, startable=True
        )
        assert placeholder_start_reason(item) == "no_sessions"

    def test_start_reason_unknown_kind(self) -> None:
        """Unrecognized placeholder kind → 'unknown' reason."""
        item = PlaceholderItem(
            label="", description="", kind=PlaceholderKind.ERROR, startable=True
        )
        assert placeholder_start_reason(item) == "unknown"
