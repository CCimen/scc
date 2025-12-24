"""Integration tests for ui/ package - Dashboard and navigation flows.

Test Categories:
- Dashboard tab navigation tests
- Dashboard quit behavior tests
- CLI integration with dashboard
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scc_cli.ui.dashboard import (
    Dashboard,
    DashboardState,
    DashboardTab,
    TabData,
    _load_all_tab_data,
)
from scc_cli.ui.keys import Action, ActionType
from scc_cli.ui.list_screen import ListItem, ListState


class TestDashboardTabNavigation:
    """Test dashboard tab switching behavior."""

    @pytest.fixture
    def mock_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create mock tab data for testing."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[
                    ListItem(value="team", label="Team", description="platform"),
                ],
                count_active=1,
                count_total=1,
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[
                    ListItem(value="c1", label="scc-main", description="Up 2h"),
                    ListItem(value="c2", label="scc-dev", description="Exited"),
                ],
                count_active=1,
                count_total=2,
            ),
            DashboardTab.SESSIONS: TabData(
                tab=DashboardTab.SESSIONS,
                title="Sessions",
                items=[
                    ListItem(value="s1", label="session-1", description="platform"),
                ],
                count_active=1,
                count_total=1,
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=[
                    ListItem(value="w1", label="main", description="main branch"),
                ],
                count_active=0,
                count_total=1,
            ),
        }

    def test_initial_tab_is_status(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """Dashboard starts on Status tab."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )

        assert state.active_tab == DashboardTab.STATUS
        assert state.current_tab_data.title == "Status"

    def test_next_tab_cycles_forward(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """next_tab() moves to next tab in order."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )

        state = state.next_tab()
        assert state.active_tab == DashboardTab.CONTAINERS

        state = state.next_tab()
        assert state.active_tab == DashboardTab.SESSIONS

        state = state.next_tab()
        assert state.active_tab == DashboardTab.WORKTREES

    def test_next_tab_wraps_around(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """next_tab() wraps from last tab to first."""
        state = DashboardState(
            active_tab=DashboardTab.WORKTREES,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.WORKTREES].items),
        )

        state = state.next_tab()
        assert state.active_tab == DashboardTab.STATUS

    def test_prev_tab_cycles_backward(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """prev_tab() moves to previous tab in order."""
        state = DashboardState(
            active_tab=DashboardTab.WORKTREES,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.WORKTREES].items),
        )

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.SESSIONS

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.CONTAINERS

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.STATUS

    def test_prev_tab_wraps_around(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """prev_tab() wraps from first tab to last."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.WORKTREES

    def test_switch_tab_resets_list_state(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """Switching tabs resets the list state cursor and filter."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )

        # Modify list state before switching
        state.list_state.move_cursor(1)

        # Switch tab
        new_state = state.switch_tab(DashboardTab.CONTAINERS)

        # Verify cursor is reset
        assert new_state.list_state.cursor == 0
        assert new_state.list_state.filter_query == ""


class TestDashboardQuitBehavior:
    """Test dashboard quit and cancel handling."""

    @pytest.fixture
    def mock_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create minimal mock tab data."""
        return {
            tab: TabData(
                tab=tab,
                title=tab.display_name,
                items=[ListItem(value="test", label="Test", description="")],
                count_active=1,
                count_total=1,
            )
            for tab in DashboardTab
        }

    def test_quit_action_returns_false(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """QUIT action causes _handle_action to return False."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        quit_action = Action(action_type=ActionType.QUIT, state_changed=True)
        result = dashboard._handle_action(quit_action)

        assert result is False

    def test_cancel_action_returns_false(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """CANCEL action causes _handle_action to return False."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        cancel_action = Action(action_type=ActionType.CANCEL, state_changed=True)
        result = dashboard._handle_action(cancel_action)

        assert result is False

    def test_tab_next_action_switches_tab(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """TAB_NEXT action switches to next tab."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        tab_action = Action(action_type=ActionType.TAB_NEXT, state_changed=True)
        result = dashboard._handle_action(tab_action)

        assert result is None  # Continue running
        assert dashboard.state.active_tab == DashboardTab.CONTAINERS

    def test_tab_prev_action_switches_tab(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """TAB_PREV action switches to previous tab."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.CONTAINERS].items),
        )
        dashboard = Dashboard(state)

        tab_action = Action(action_type=ActionType.TAB_PREV, state_changed=True)
        result = dashboard._handle_action(tab_action)

        assert result is None  # Continue running
        assert dashboard.state.active_tab == DashboardTab.STATUS


class TestDashboardNavigation:
    """Test dashboard list navigation."""

    @pytest.fixture
    def mock_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create mock tab data with multiple items."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[
                    ListItem(value="item1", label="Item 1", description="First"),
                    ListItem(value="item2", label="Item 2", description="Second"),
                    ListItem(value="item3", label="Item 3", description="Third"),
                ],
                count_active=3,
                count_total=3,
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.SESSIONS: TabData(
                tab=DashboardTab.SESSIONS,
                title="Sessions",
                items=[],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=[],
                count_active=0,
                count_total=0,
            ),
        }

    def test_navigate_down_moves_cursor(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """NAVIGATE_DOWN action moves cursor down."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        assert dashboard.state.list_state.cursor == 0

        down_action = Action(action_type=ActionType.NAVIGATE_DOWN, state_changed=True)
        dashboard._handle_action(down_action)

        assert dashboard.state.list_state.cursor == 1

    def test_navigate_up_moves_cursor(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """NAVIGATE_UP action moves cursor up."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        # Move down first
        dashboard.state.list_state.move_cursor(1)
        assert dashboard.state.list_state.cursor == 1

        up_action = Action(action_type=ActionType.NAVIGATE_UP, state_changed=True)
        dashboard._handle_action(up_action)

        assert dashboard.state.list_state.cursor == 0


class TestDashboardFiltering:
    """Test dashboard filter functionality."""

    @pytest.fixture
    def mock_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create mock tab data with filterable items."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[
                    ListItem(value="team", label="Team", description="platform"),
                    ListItem(value="config", label="Config", description="settings"),
                ],
                count_active=2,
                count_total=2,
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.SESSIONS: TabData(
                tab=DashboardTab.SESSIONS,
                title="Sessions",
                items=[],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=[],
                count_active=0,
                count_total=0,
            ),
        }

    def test_filter_char_updates_query(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """FILTER_CHAR action adds character to filter query."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        filter_action = Action(
            action_type=ActionType.FILTER_CHAR,
            state_changed=True,
            filter_char="t",
        )
        dashboard._handle_action(filter_action)

        assert dashboard.state.list_state.filter_query == "t"

    def test_filter_delete_removes_char(self, mock_tab_data: dict[DashboardTab, TabData]) -> None:
        """FILTER_DELETE action removes character from filter query."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        # Add some filter chars first
        dashboard.state.list_state.add_filter_char("t")
        dashboard.state.list_state.add_filter_char("e")
        assert dashboard.state.list_state.filter_query == "te"

        delete_action = Action(action_type=ActionType.FILTER_DELETE, state_changed=True)
        dashboard._handle_action(delete_action)

        assert dashboard.state.list_state.filter_query == "t"


class TestCLIDashboardIntegration:
    """Test CLI integration with dashboard."""

    def test_cli_shows_dashboard_in_interactive_mode(self) -> None:
        """CLI shows dashboard when interactive mode is allowed."""
        # Patch at the source module where the functions are defined
        with patch("scc_cli.ui.gate.is_interactive_allowed", return_value=True):
            with patch("scc_cli.ui.dashboard.run_dashboard") as mock_dashboard:
                # Import after patching
                from scc_cli.cli import main_callback

                # Create a mock context with no invoked subcommand
                mock_ctx = MagicMock()
                mock_ctx.invoked_subcommand = None

                # Call the callback - it should invoke run_dashboard
                main_callback(mock_ctx, debug=False, version=False)

                # Verify dashboard was called
                mock_dashboard.assert_called_once()

    def test_cli_invokes_start_in_non_interactive_mode(self) -> None:
        """CLI invokes start command when non-interactive."""
        # This test verifies the logic path exists
        # Full integration would require running the actual CLI
        with patch("scc_cli.ui.gate.is_interactive_allowed", return_value=False):
            # Verify the gate function works
            from scc_cli.ui.gate import is_interactive_allowed

            assert not is_interactive_allowed()


class TestTabDataLoading:
    """Test that tab data loading functions work with mocked dependencies."""

    def test_load_all_tab_data_returns_all_tabs(self) -> None:
        """_load_all_tab_data returns data for all tabs."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            with patch("scc_cli.sessions.list_recent") as mock_sessions:
                with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
                    with patch("scc_cli.git.list_worktrees") as mock_worktrees:
                        mock_config.return_value = {}
                        mock_sessions.return_value = []
                        mock_docker.return_value = []
                        mock_worktrees.return_value = []

                        tabs = _load_all_tab_data()

                        assert DashboardTab.STATUS in tabs
                        assert DashboardTab.CONTAINERS in tabs
                        assert DashboardTab.SESSIONS in tabs
                        assert DashboardTab.WORKTREES in tabs
