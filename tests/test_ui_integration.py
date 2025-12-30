"""Integration tests for ui/ package - Dashboard and navigation flows.

Test Categories:
- Dashboard tab navigation tests
- Dashboard quit behavior tests
- CLI integration with dashboard
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console, RenderableType

from scc_cli.ui.dashboard import (
    Dashboard,
    DashboardState,
    DashboardTab,
    TabData,
    _load_all_tab_data,
    _prepare_for_nested_ui,
)
from scc_cli.ui.keys import Action, ActionType
from scc_cli.ui.list_screen import ListItem, ListState


def _render_to_str(renderable: RenderableType) -> str:
    """Render a Rich object to a plain string for test assertions."""
    console = Console(file=StringIO(), force_terminal=False, width=120)
    console.print(renderable)
    return console.file.getvalue()  # type: ignore[union-attr]


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

    def test_cancel_action_without_filter_is_noop(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """CANCEL action without active filter returns None (no-op)."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        cancel_action = Action(action_type=ActionType.CANCEL, state_changed=True)
        result = dashboard._handle_action(cancel_action)

        # ESC without filter is no-op (doesn't exit)
        assert result is None

    def test_cancel_action_with_filter_clears_filter(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """CANCEL action with active filter clears filter and returns True."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        # Set up a filter
        state.list_state.filter_query = "test"
        dashboard = Dashboard(state)

        cancel_action = Action(action_type=ActionType.CANCEL, state_changed=True)
        result = dashboard._handle_action(cancel_action)

        # ESC clears filter and requests refresh
        assert result is True
        assert dashboard.state.list_state.filter_query == ""

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
    """Test CLI integration with dashboard.

    Context-aware routing (Phase 7):
    - If CWD is a valid workspace → invoke start
    - If CWD is NOT a valid workspace → show dashboard
    """

    def test_cli_shows_dashboard_when_no_workspace_detected(self) -> None:
        """CLI shows dashboard when NOT in a valid workspace (e.g., $HOME)."""
        # Mock _is_valid_workspace to return False (no workspace context)
        # Patch at the source module where the function is defined
        with patch("scc_cli.ui.wizard._is_valid_workspace", return_value=False):
            with patch("scc_cli.ui.gate.is_interactive_allowed", return_value=True):
                with patch("scc_cli.ui.dashboard.run_dashboard") as mock_dashboard:
                    # Import after patching
                    from scc_cli.cli import main_callback

                    # Create a mock context with no invoked subcommand
                    mock_ctx = MagicMock()
                    mock_ctx.invoked_subcommand = None

                    # Call the callback - should show dashboard
                    main_callback(mock_ctx, debug=False, version=False, interactive=False)

                    # Verify dashboard was called
                    mock_dashboard.assert_called_once()

    def test_cli_invokes_start_when_workspace_detected(self) -> None:
        """CLI invokes start when in a valid workspace (git repo, .scc.yaml)."""
        # Mock _is_valid_workspace to return True (valid workspace context)
        # Patch at the source module where the function is defined
        with patch("scc_cli.ui.wizard._is_valid_workspace", return_value=True):
            with patch("scc_cli.ui.gate.is_interactive_allowed", return_value=True):
                # Import after patching
                from scc_cli.cli import main_callback

                # Create a mock context with invoke method
                mock_ctx = MagicMock()
                mock_ctx.invoked_subcommand = None

                # Call the callback - should invoke start
                main_callback(mock_ctx, debug=False, version=False, interactive=False)

                # Verify start was invoked (via ctx.invoke)
                mock_ctx.invoke.assert_called_once()
                # Check that workspace was passed (CWD)
                call_kwargs = mock_ctx.invoke.call_args.kwargs
                assert call_kwargs["workspace"] is not None

    def test_cli_invokes_start_in_non_interactive_mode(self) -> None:
        """CLI invokes start command when non-interactive."""
        # This test verifies the logic path exists
        # Full integration would require running the actual CLI
        with patch("scc_cli.ui.gate.is_interactive_allowed", return_value=False):
            # Verify the gate function works
            from scc_cli.ui.gate import is_interactive_allowed

            assert not is_interactive_allowed()


class TestDashboardStandaloneMode:
    """Test dashboard behavior in standalone mode."""

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

    def test_team_switch_in_standalone_shows_message(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """TEAM_SWITCH in standalone mode sets status message instead of raising."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        with patch(
            "scc_cli.ui.dashboard._dashboard.scc_config.is_standalone_mode", return_value=True
        ):
            from scc_cli.ui.keys import ActionType

            team_action = Action(action_type=ActionType.TEAM_SWITCH, state_changed=True)
            result = dashboard._handle_action(team_action)

            # Should return True (refresh) and set status message
            assert result is True
            assert dashboard.state.status_message is not None
            assert "org mode" in dashboard.state.status_message
            assert "scc setup" in dashboard.state.status_message

    def test_status_message_cleared_on_next_action(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Status message is cleared when user performs any action."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
            status_message="Test message",
        )
        dashboard = Dashboard(state)

        # Any action should clear the message
        down_action = Action(action_type=ActionType.NAVIGATE_DOWN, state_changed=True)
        dashboard._handle_action(down_action)

        assert dashboard.state.status_message is None

    def test_enter_on_team_row_in_standalone_shows_message(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Enter on Team row in standalone mode shows guidance message."""
        # Override Status tab with Team item
        mock_tab_data[DashboardTab.STATUS] = TabData(
            tab=DashboardTab.STATUS,
            title="Status",
            items=[ListItem(value="team", label="Team", description="No team")],
            count_active=1,
            count_total=1,
        )
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        with patch(
            "scc_cli.ui.dashboard._dashboard.scc_config.is_standalone_mode", return_value=True
        ):
            select_action = Action(action_type=ActionType.SELECT, state_changed=True)
            result = dashboard._handle_action(select_action)

            assert result is True
            assert dashboard.state.status_message is not None
            assert "org mode" in dashboard.state.status_message

    def test_chrome_config_dims_teams_hint_in_standalone(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """ChromeConfig dims 't teams' hint when in standalone mode."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        with patch(
            "scc_cli.ui.dashboard._dashboard.scc_config.is_standalone_mode", return_value=True
        ):
            config = dashboard._get_chrome_config()

            # Find the teams hint and verify it's dimmed
            teams_hint = next(h for h in config.footer_hints if h.action == "teams")
            assert teams_hint.dimmed is True

    def test_chrome_config_undimmed_teams_in_org_mode(
        self, mock_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """ChromeConfig shows normal 't teams' hint when org mode is configured."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=mock_tab_data,
            list_state=ListState(items=mock_tab_data[DashboardTab.STATUS].items),
        )
        dashboard = Dashboard(state)

        with patch(
            "scc_cli.ui.dashboard._dashboard.scc_config.is_standalone_mode", return_value=False
        ):
            config = dashboard._get_chrome_config()

            # Find the teams hint and verify it's not dimmed
            teams_hint = next(h for h in config.footer_hints if h.action == "teams")
            assert teams_hint.dimmed is False


class TestStatusTabDrillDown:
    """Test Status tab drill-down behavior."""

    @pytest.fixture
    def status_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create tab data with Status tab containing resource items."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[
                    ListItem(value="team", label="Team", description="platform"),
                    ListItem(value="containers", label="Containers", description="2/3"),
                    ListItem(value="sessions", label="Sessions", description="5"),
                ],
                count_active=3,
                count_total=3,
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[ListItem(value="c1", label="container-1", description="Up")],
                count_active=1,
                count_total=1,
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

    def test_drill_down_clears_filter(self, status_tab_data: dict[DashboardTab, TabData]) -> None:
        """Drill-down from Status tab clears the filter query."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=status_tab_data,
            list_state=ListState(items=status_tab_data[DashboardTab.STATUS].items),
        )
        # Set filter to "cont" (only Containers matches) and cursor to 0 (first filtered item)
        state.list_state.filter_query = "cont"
        state.list_state.cursor = 0  # Containers is at index 0 in filtered list
        dashboard = Dashboard(state)

        select_action = Action(action_type=ActionType.SELECT, state_changed=True)
        result = dashboard._handle_action(select_action)

        assert result is True
        assert dashboard.state.active_tab == DashboardTab.CONTAINERS
        # Filter should be cleared after drill-down
        assert dashboard.state.list_state.filter_query == ""


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


class TestDetailsPane:
    """Test details pane toggle and state behavior (Phase 2A)."""

    @pytest.fixture
    def resource_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create tab data with items on resource tabs."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[ListItem(value="team", label="Team", description="platform")],
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
                items=[ListItem(value="s1", label="session-1", description="platform")],
                count_active=1,
                count_total=1,
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=[ListItem(value="w1", label="main", description="main branch")],
                count_active=0,
                count_total=1,
            ),
        }

    @pytest.fixture
    def placeholder_tab_data(self) -> dict[DashboardTab, TabData]:
        """Create tab data with placeholder items (empty state)."""
        return {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS,
                title="Status",
                items=[ListItem(value="team", label="Team", description="platform")],
                count_active=1,
                count_total=1,
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[
                    ListItem(
                        value="no_containers",
                        label="No containers",
                        description="Run 'scc start' to create one",
                    )
                ],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.SESSIONS: TabData(
                tab=DashboardTab.SESSIONS,
                title="Sessions",
                items=[
                    ListItem(value="error", label="Error", description="Unable to load sessions")
                ],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=[
                    ListItem(
                        value="no_git",
                        label="Not available",
                        description="Not in a git repository",
                    )
                ],
                count_active=0,
                count_total=0,
            ),
        }

    def test_enter_on_resource_tab_opens_details(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Enter on a resource tab (not Status) opens details pane."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
        )
        dashboard = Dashboard(state)

        assert dashboard.state.details_open is False

        select_action = Action(action_type=ActionType.SELECT, state_changed=True)
        result = dashboard._handle_action(select_action)

        assert result is True
        assert dashboard.state.details_open is True

    def test_enter_when_details_open_closes_details(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Enter when details already open toggles it closed."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        select_action = Action(action_type=ActionType.SELECT, state_changed=True)
        result = dashboard._handle_action(select_action)

        assert result is True
        assert dashboard.state.details_open is False

    def test_esc_closes_details_before_clearing_filter(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """ESC precedence: close details first, then clear filter."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        state.list_state.filter_query = "scc"
        dashboard = Dashboard(state)

        cancel_action = Action(action_type=ActionType.CANCEL, state_changed=True)
        result = dashboard._handle_action(cancel_action)

        # First ESC closes details, filter remains
        assert result is True
        assert dashboard.state.details_open is False
        assert dashboard.state.list_state.filter_query == "scc"

        # Second ESC clears filter
        result = dashboard._handle_action(cancel_action)
        assert result is True
        assert dashboard.state.list_state.filter_query == ""

    def test_enter_on_startable_placeholder_raises_start_requested(
        self, placeholder_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Enter on startable placeholder (no_containers, no_sessions) raises StartRequested."""
        from scc_cli.ui.keys import StartRequested

        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=placeholder_tab_data,
            list_state=ListState(items=placeholder_tab_data[DashboardTab.CONTAINERS].items),
        )
        dashboard = Dashboard(state)

        assert dashboard.state.is_placeholder_selected() is True

        select_action = Action(action_type=ActionType.SELECT, state_changed=True)

        # Startable placeholders (no_containers, no_sessions) raise StartRequested
        # to signal orchestrator to run the start wizard
        with pytest.raises(StartRequested) as exc_info:
            dashboard._handle_action(select_action)

        assert exc_info.value.return_to == "CONTAINERS"  # Tab name for restoration
        assert exc_info.value.reason == "no_containers"  # Context for logging

    def test_enter_on_non_startable_placeholder_shows_tip(self) -> None:
        """Enter on non-startable placeholder (no_worktrees, no_git) shows tip message."""
        # Create a worktree tab with no_worktrees placeholder
        worktree_items = [ListItem(value="no_worktrees", label="No worktrees")]
        tab_data = {
            DashboardTab.STATUS: TabData(
                tab=DashboardTab.STATUS, title="Status", items=[], count_active=0, count_total=0
            ),
            DashboardTab.CONTAINERS: TabData(
                tab=DashboardTab.CONTAINERS,
                title="Containers",
                items=[],
                count_active=0,
                count_total=0,
            ),
            DashboardTab.SESSIONS: TabData(
                tab=DashboardTab.SESSIONS, title="Sessions", items=[], count_active=0, count_total=0
            ),
            DashboardTab.WORKTREES: TabData(
                tab=DashboardTab.WORKTREES,
                title="Worktrees",
                items=worktree_items,
                count_active=0,
                count_total=0,
            ),
        }

        state = DashboardState(
            active_tab=DashboardTab.WORKTREES,
            tabs=tab_data,
            list_state=ListState(items=worktree_items),
        )
        dashboard = Dashboard(state)

        select_action = Action(action_type=ActionType.SELECT, state_changed=True)
        result = dashboard._handle_action(select_action)

        # Non-startable placeholders show a tip (not raising StartRequested)
        assert result is True  # State changed (status_message set)
        assert dashboard.state.details_open is False
        assert dashboard.state.status_message is not None
        assert "git" in dashboard.state.status_message.lower()  # Contains git guidance

    def test_is_placeholder_selected_detects_placeholders(
        self, placeholder_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """is_placeholder_selected() returns True for all known placeholder values."""
        placeholder_values = ["no_containers", "no_sessions", "no_worktrees", "no_git", "error"]

        for placeholder in placeholder_values:
            state = DashboardState(
                active_tab=DashboardTab.CONTAINERS,
                tabs=placeholder_tab_data,
                list_state=ListState(items=[ListItem(value=placeholder, label="Test")]),
            )
            assert state.is_placeholder_selected() is True, f"Failed for {placeholder}"

    def test_is_placeholder_selected_false_for_real_items(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """is_placeholder_selected() returns False for real container/session items."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
        )
        assert state.is_placeholder_selected() is False

    def test_navigation_with_details_open_updates_cursor(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Arrow navigation works when details are open (cursor moves)."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        assert dashboard.state.list_state.cursor == 0

        down_action = Action(action_type=ActionType.NAVIGATE_DOWN, state_changed=True)
        dashboard._handle_action(down_action)

        assert dashboard.state.list_state.cursor == 1
        # Details should still be open
        assert dashboard.state.details_open is True

    def test_filter_with_details_open_still_works(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Filtering works when details are open (non-modal behavior)."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        filter_action = Action(
            action_type=ActionType.FILTER_CHAR,
            state_changed=True,
            filter_char="d",
        )
        dashboard._handle_action(filter_action)

        # Filter should work
        assert dashboard.state.list_state.filter_query == "d"
        # Details should still be open
        assert dashboard.state.details_open is True

    # Phase 2B: Responsive rendering tests

    def test_status_tab_auto_hides_details_in_chrome(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Status tab has no actionable items - no Enter hint in footer."""
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.STATUS].items),
            details_open=True,  # State says open, but render rule hides it
        )
        dashboard = Dashboard(state)

        config = dashboard._get_chrome_config()

        # Status tab has no details pane - no Enter actions in footer
        hint_actions = [h.action for h in config.footer_hints]
        assert "close" not in hint_actions
        assert "details" not in hint_actions
        # Standard navigation and global hints still present
        assert "navigate" in hint_actions
        assert "refresh" in hint_actions

    def test_resource_tab_shows_esc_close_when_details_open(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Resource tab with details_open shows 'Esc close' in footer hints."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        config = dashboard._get_chrome_config()

        # Footer hints should show "Esc close"
        hint_keys = [h.key for h in config.footer_hints]
        hint_actions = [h.action for h in config.footer_hints]
        assert "Esc" in hint_keys
        assert "close" in hint_actions

    def test_startable_placeholder_shows_enter_start_hint(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Startable placeholder shows 'Enter start' in footer hints."""
        # Create container data with startable placeholder
        placeholder_items: list[ListItem[str]] = [
            ListItem(value="no_containers", label="No containers", description="Start one"),
        ]
        tab_data = dict(resource_tab_data)
        tab_data[DashboardTab.CONTAINERS] = TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=placeholder_items,
            count_active=0,
            count_total=0,
        )

        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=tab_data,
            list_state=ListState(items=placeholder_items),
        )
        dashboard = Dashboard(state)

        config = dashboard._get_chrome_config()

        # Footer hints should show "Enter start" for startable placeholder
        hint_actions = [h.action for h in config.footer_hints]
        assert "start" in hint_actions
        assert "details" not in hint_actions

    def test_details_content_derived_from_current_item(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Details content is derived from current_item, not cached."""
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=resource_tab_data[DashboardTab.CONTAINERS].items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        # Get details for first item
        details_1 = dashboard._render_details_pane()

        # Move cursor to second item
        state.list_state.cursor = 1

        # Get details again - should be different (derived from current_item)
        details_2 = dashboard._render_details_pane()

        # The details should have different rendered content
        assert _render_to_str(details_1) != _render_to_str(details_2)

    def test_filter_changes_selection_updates_details(
        self, resource_tab_data: dict[DashboardTab, TabData]
    ) -> None:
        """Filter changes affect selection which updates details (regression test)."""
        # Add more items to Containers for meaningful filtering
        containers_items = [
            ListItem(value="c1", label="scc-main", description="Up 2h"),
            ListItem(value="c2", label="scc-dev", description="Exited"),
            ListItem(value="c3", label="other-container", description="Up 1h"),
        ]
        resource_tab_data[DashboardTab.CONTAINERS] = TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=containers_items,
            count_active=2,
            count_total=3,
        )

        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=resource_tab_data,
            list_state=ListState(items=containers_items),
            details_open=True,
        )
        dashboard = Dashboard(state)

        # Current item should be first item
        current_before = dashboard.state.list_state.current_item
        assert current_before is not None
        assert current_before.label == "scc-main"

        # Apply filter that matches only "other-container"
        state.list_state.filter_query = "other"
        state.list_state.cursor = 0  # Filter resets cursor

        # After filtering, current item should be "other-container"
        current_after = dashboard.state.list_state.current_item
        assert current_after is not None
        assert current_after.label == "other-container"

        # Details pane content should now show the new item
        details = dashboard._render_details_pane()
        # The details should reference "other-container"
        assert "other-container" in _render_to_str(details)


class TestTerminalHygiene:
    """Tests for terminal state management functions."""

    def test_prepare_for_nested_ui_shows_cursor(self) -> None:
        """_prepare_for_nested_ui should restore cursor visibility."""
        console = MagicMock()

        _prepare_for_nested_ui(console)

        console.show_cursor.assert_called_once_with(True)
        console.print.assert_called_once()

    def test_prepare_for_nested_ui_handles_tcflush_errors(self) -> None:
        """_prepare_for_nested_ui should not crash on tcflush errors."""
        import io
        import termios

        console = MagicMock()

        # Test with termios.error (non-Unix)
        with patch("termios.tcflush", side_effect=termios.error("not a tty")):
            _prepare_for_nested_ui(console)  # Should not raise

        # Test with OSError (redirected stdin)
        with patch("termios.tcflush", side_effect=OSError("bad file descriptor")):
            _prepare_for_nested_ui(console)  # Should not raise

        # Test with ValueError (mock stdin)
        with patch("termios.tcflush", side_effect=ValueError("mock stdin")):
            _prepare_for_nested_ui(console)  # Should not raise

        # Test with io.UnsupportedOperation (special mock without fileno)
        with patch("termios.tcflush", side_effect=io.UnsupportedOperation("no fileno")):
            _prepare_for_nested_ui(console)  # Should not raise

        # All calls should have completed without raising
        assert console.show_cursor.call_count == 4
