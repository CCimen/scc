"""Tests for ui/dashboard.py - Tabbed dashboard navigation.

Test Categories:
- DashboardTab tests
- DashboardState tests
- Tab navigation tests
- Tab data loading tests
- run_dashboard integration tests
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from scc_cli.ui.dashboard import (
    Dashboard,
    DashboardState,
    DashboardTab,
    TabData,
    _load_all_tab_data,
    _load_containers_tab_data,
    _load_sessions_tab_data,
    _load_status_tab_data,
    _load_worktrees_tab_data,
)
from scc_cli.ui.list_screen import ListItem, ListState


class TestDashboardTab:
    """Test DashboardTab enum."""

    def test_status_tab_exists(self) -> None:
        """STATUS tab is defined."""
        assert DashboardTab.STATUS is not None

    def test_containers_tab_exists(self) -> None:
        """CONTAINERS tab is defined."""
        assert DashboardTab.CONTAINERS is not None

    def test_sessions_tab_exists(self) -> None:
        """SESSIONS tab is defined."""
        assert DashboardTab.SESSIONS is not None

    def test_worktrees_tab_exists(self) -> None:
        """WORKTREES tab is defined."""
        assert DashboardTab.WORKTREES is not None

    def test_all_tabs_distinct(self) -> None:
        """All tabs have distinct values."""
        tabs = [
            DashboardTab.STATUS,
            DashboardTab.CONTAINERS,
            DashboardTab.SESSIONS,
            DashboardTab.WORKTREES,
        ]
        assert len(set(tabs)) == 4

    def test_tab_display_names(self) -> None:
        """Tabs have display names for chrome."""
        assert DashboardTab.STATUS.display_name == "Status"
        assert DashboardTab.CONTAINERS.display_name == "Containers"
        assert DashboardTab.SESSIONS.display_name == "Sessions"
        assert DashboardTab.WORKTREES.display_name == "Worktrees"


class TestTabData:
    """Test TabData dataclass."""

    def _make_items(self, labels: list[str]) -> list[ListItem[str]]:
        """Helper to create list items."""
        return [ListItem(value=label, label=label) for label in labels]

    def test_tab_data_creation(self) -> None:
        """TabData can be created with required fields."""
        items = self._make_items(["Item 1", "Item 2"])
        data = TabData(
            tab=DashboardTab.CONTAINERS,
            title="Running Containers",
            items=items,
            count_active=2,
            count_total=5,
        )

        assert data.tab == DashboardTab.CONTAINERS
        assert data.title == "Running Containers"
        assert len(data.items) == 2
        assert data.count_active == 2
        assert data.count_total == 5

    def test_tab_data_subtitle_property(self) -> None:
        """TabData generates subtitle from counts."""
        items = self._make_items(["A"])
        data = TabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=items,
            count_active=3,
            count_total=10,
        )

        assert "3" in data.subtitle
        assert "10" in data.subtitle


class TestDashboardState:
    """Test DashboardState navigation."""

    def _make_tab_data(self, tab: DashboardTab, count: int = 2) -> TabData:
        """Helper to create tab data."""
        items = [
            ListItem(value=f"{tab.name}_{i}", label=f"{tab.name} Item {i}") for i in range(count)
        ]
        return TabData(
            tab=tab,
            title=tab.display_name,
            items=items,
            count_active=count,
            count_total=count,
        )

    def test_initial_tab_is_status(self) -> None:
        """Dashboard starts on STATUS tab."""
        tabs = {
            DashboardTab.STATUS: self._make_tab_data(DashboardTab.STATUS),
            DashboardTab.CONTAINERS: self._make_tab_data(DashboardTab.CONTAINERS),
        }
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )

        assert state.active_tab == DashboardTab.STATUS

    def test_switch_tab_changes_active(self) -> None:
        """switch_tab changes the active tab."""
        tabs = {
            DashboardTab.STATUS: self._make_tab_data(DashboardTab.STATUS),
            DashboardTab.CONTAINERS: self._make_tab_data(DashboardTab.CONTAINERS),
        }
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )

        new_state = state.switch_tab(DashboardTab.CONTAINERS)

        assert new_state.active_tab == DashboardTab.CONTAINERS

    def test_switch_tab_resets_list_state(self) -> None:
        """switch_tab resets the list state for new tab."""
        tabs = {
            DashboardTab.STATUS: self._make_tab_data(DashboardTab.STATUS, count=3),
            DashboardTab.CONTAINERS: self._make_tab_data(DashboardTab.CONTAINERS, count=5),
        }
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )
        # Modify list state
        state.list_state.cursor = 2
        state.list_state.filter_query = "test"

        new_state = state.switch_tab(DashboardTab.CONTAINERS)

        assert new_state.list_state.cursor == 0
        assert new_state.list_state.filter_query == ""
        assert len(new_state.list_state.items) == 5

    def test_switch_tab_preserves_tabs_data(self) -> None:
        """switch_tab preserves all tab data."""
        tabs = {
            DashboardTab.STATUS: self._make_tab_data(DashboardTab.STATUS),
            DashboardTab.CONTAINERS: self._make_tab_data(DashboardTab.CONTAINERS),
        }
        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )

        new_state = state.switch_tab(DashboardTab.CONTAINERS)

        assert new_state.tabs == state.tabs

    def test_current_tab_data(self) -> None:
        """current_tab_data returns data for active tab."""
        tabs = {
            DashboardTab.STATUS: self._make_tab_data(DashboardTab.STATUS),
            DashboardTab.CONTAINERS: self._make_tab_data(DashboardTab.CONTAINERS),
        }
        state = DashboardState(
            active_tab=DashboardTab.CONTAINERS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.CONTAINERS].items),
        )

        assert state.current_tab_data == tabs[DashboardTab.CONTAINERS]


class TestDashboardTabCycling:
    """Test tab cycling behavior."""

    def _make_state_with_all_tabs(self) -> DashboardState:
        """Helper to create state with all tabs."""
        tabs = {}
        for tab in DashboardTab:
            items = [ListItem(value=tab.name, label=tab.name)]
            tabs[tab] = TabData(
                tab=tab,
                title=tab.display_name,
                items=items,
                count_active=1,
                count_total=1,
            )

        return DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )

    def test_next_tab_cycles_forward(self) -> None:
        """next_tab cycles to the next tab."""
        state = self._make_state_with_all_tabs()

        state = state.next_tab()
        assert state.active_tab == DashboardTab.CONTAINERS

        state = state.next_tab()
        assert state.active_tab == DashboardTab.SESSIONS

        state = state.next_tab()
        assert state.active_tab == DashboardTab.WORKTREES

    def test_next_tab_wraps_to_start(self) -> None:
        """next_tab wraps from last to first tab."""
        state = self._make_state_with_all_tabs()
        state = state.switch_tab(DashboardTab.WORKTREES)

        state = state.next_tab()
        assert state.active_tab == DashboardTab.STATUS

    def test_prev_tab_cycles_backward(self) -> None:
        """prev_tab cycles to the previous tab."""
        state = self._make_state_with_all_tabs()
        state = state.switch_tab(DashboardTab.WORKTREES)

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.SESSIONS

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.CONTAINERS

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.STATUS

    def test_prev_tab_wraps_to_end(self) -> None:
        """prev_tab wraps from first to last tab."""
        state = self._make_state_with_all_tabs()

        state = state.prev_tab()
        assert state.active_tab == DashboardTab.WORKTREES


class TestDashboardChromeConfig:
    """Test Dashboard chrome configuration."""

    def _make_dashboard(self) -> Dashboard:
        """Helper to create a dashboard instance."""
        tabs = {}
        for tab in DashboardTab:
            items = [ListItem(value=tab.name, label=tab.name)]
            tabs[tab] = TabData(
                tab=tab,
                title=tab.display_name,
                items=items,
                count_active=1,
                count_total=1,
            )

        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )
        return Dashboard(state)

    def test_chrome_config_shows_tabs(self) -> None:
        """Dashboard chrome config enables tabs display."""
        dashboard = self._make_dashboard()
        config = dashboard._get_chrome_config()

        assert config.show_tabs is True

    def test_chrome_config_has_all_tab_names(self) -> None:
        """Chrome config includes all tab display names."""
        dashboard = self._make_dashboard()
        config = dashboard._get_chrome_config()

        assert "Status" in config.tabs
        assert "Containers" in config.tabs
        assert "Sessions" in config.tabs
        assert "Worktrees" in config.tabs

    def test_chrome_config_tracks_active_tab(self) -> None:
        """Chrome config indicates active tab index."""
        dashboard = self._make_dashboard()

        # Initial: STATUS is active (index 0)
        config = dashboard._get_chrome_config()
        assert config.active_tab_index == 0

        # Switch to CONTAINERS (index 1)
        dashboard.state = dashboard.state.switch_tab(DashboardTab.CONTAINERS)
        config = dashboard._get_chrome_config()
        assert config.active_tab_index == 1

    def test_chrome_config_has_dashboard_hints(self) -> None:
        """Chrome config has dashboard-appropriate footer hints."""
        dashboard = self._make_dashboard()
        config = dashboard._get_chrome_config()

        hint_keys = [h.key for h in config.footer_hints]
        assert "Tab" in hint_keys  # Tab switching
        assert "q" in hint_keys  # Quit


class TestDashboardRendering:
    """Test Dashboard rendering."""

    def _render_to_string(self, renderable: object) -> str:
        """Helper to render Rich content to plain string."""
        console = Console(file=StringIO(), force_terminal=True, width=80)
        console.print(renderable)
        return console.file.getvalue()  # type: ignore[union-attr]

    def _make_dashboard(self) -> Dashboard:
        """Helper to create a dashboard instance."""
        tabs = {}
        for tab in DashboardTab:
            items = [
                ListItem(value=f"{tab.name}_1", label=f"{tab.display_name} Item 1"),
                ListItem(value=f"{tab.name}_2", label=f"{tab.display_name} Item 2"),
            ]
            tabs[tab] = TabData(
                tab=tab,
                title=tab.display_name,
                items=items,
                count_active=2,
                count_total=2,
            )

        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )
        return Dashboard(state)

    def test_render_includes_tab_labels(self) -> None:
        """Rendered dashboard includes tab labels."""
        dashboard = self._make_dashboard()
        rendered = dashboard._render()
        output = self._render_to_string(rendered)

        assert "Status" in output
        assert "Containers" in output

    def test_render_shows_active_tab_items(self) -> None:
        """Rendered dashboard shows items from active tab."""
        dashboard = self._make_dashboard()
        rendered = dashboard._render()
        output = self._render_to_string(rendered)

        assert "Status Item 1" in output

    def test_render_after_tab_switch(self) -> None:
        """Rendered dashboard updates after tab switch."""
        dashboard = self._make_dashboard()
        dashboard.state = dashboard.state.switch_tab(DashboardTab.CONTAINERS)

        rendered = dashboard._render()
        output = self._render_to_string(rendered)

        assert "Containers Item 1" in output


class TestLoadStatusTabData:
    """Test _load_status_tab_data function."""

    def test_returns_tab_data_with_status_tab(self) -> None:
        """Returns TabData for STATUS tab."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            with patch("scc_cli.sessions.list_recent") as mock_sessions:
                with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
                    mock_config.return_value = {
                        "selected_profile": "team-a",
                        "standalone": False,
                    }
                    mock_docker.return_value = []
                    mock_sessions.return_value = []

                    data = _load_status_tab_data()

                    assert data.tab == DashboardTab.STATUS
                    assert data.title == "Status"

    def test_includes_team_info_when_selected(self) -> None:
        """Includes team info when a team is selected."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            with patch("scc_cli.sessions.list_recent") as mock_sessions:
                with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
                    mock_config.return_value = {
                        "selected_profile": "production-team",
                    }
                    mock_docker.return_value = []
                    mock_sessions.return_value = []

                    data = _load_status_tab_data()

                    team_item = next((item for item in data.items if item.value == "team"), None)
                    assert team_item is not None
                    assert "production-team" in team_item.description

    def test_handles_no_team_selected(self) -> None:
        """Shows 'No team selected' when no team configured."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            with patch("scc_cli.sessions.list_recent") as mock_sessions:
                with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
                    mock_config.return_value = {}
                    mock_docker.return_value = []
                    mock_sessions.return_value = []

                    data = _load_status_tab_data()

                    team_item = next((item for item in data.items if item.value == "team"), None)
                    assert team_item is not None
                    assert "No team selected" in team_item.description

    def test_includes_container_count(self) -> None:
        """Includes container count in status."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            with patch("scc_cli.sessions.list_recent") as mock_sessions:
                with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
                    mock_config.return_value = {}
                    # Create mock containers
                    container1 = MagicMock()
                    container1.status = "Up 2 hours"
                    container2 = MagicMock()
                    container2.status = "Exited"
                    mock_docker.return_value = [container1, container2]
                    mock_sessions.return_value = []

                    data = _load_status_tab_data()

                    containers_item = next(
                        (item for item in data.items if item.value == "containers"), None
                    )
                    assert containers_item is not None
                    assert "1 running" in containers_item.description
                    assert "2 total" in containers_item.description

    def test_handles_config_error_gracefully(self) -> None:
        """Shows error message when config fails to load."""
        with patch("scc_cli.config.load_user_config") as mock_config:
            mock_config.side_effect = Exception("Config error")

            data = _load_status_tab_data()

            error_item = next((item for item in data.items if item.value == "config_error"), None)
            assert error_item is not None
            assert "Error loading config" in error_item.description


class TestLoadContainersTabData:
    """Test _load_containers_tab_data function."""

    def test_returns_tab_data_with_containers_tab(self) -> None:
        """Returns TabData for CONTAINERS tab."""
        with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
            mock_docker.return_value = []

            data = _load_containers_tab_data()

            assert data.tab == DashboardTab.CONTAINERS
            assert data.title == "Containers"

    def test_lists_containers_with_status(self) -> None:
        """Lists containers with their status information."""
        with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
            container = MagicMock()
            container.id = "abc123"
            container.name = "scc-myproject"
            container.profile = "dev"
            container.workspace = "/home/user/projects/myproject"
            container.status = "Up 2 hours"
            mock_docker.return_value = [container]

            data = _load_containers_tab_data()

            assert len(data.items) == 1
            assert data.items[0].value == "abc123"
            assert data.items[0].label == "scc-myproject"
            assert "dev" in data.items[0].description
            assert "myproject" in data.items[0].description

    def test_counts_running_containers(self) -> None:
        """Correctly counts running vs total containers."""
        with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
            running = MagicMock()
            running.id = "run1"
            running.name = "running"
            running.profile = ""
            running.workspace = ""
            running.status = "Up 1 hour"

            stopped = MagicMock()
            stopped.id = "stop1"
            stopped.name = "stopped"
            stopped.profile = ""
            stopped.workspace = ""
            stopped.status = "Exited (0)"

            mock_docker.return_value = [running, stopped]

            data = _load_containers_tab_data()

            assert data.count_active == 1
            assert data.count_total == 2

    def test_shows_no_containers_message(self) -> None:
        """Shows message when no containers exist."""
        with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
            mock_docker.return_value = []

            data = _load_containers_tab_data()

            assert len(data.items) == 1
            assert "No containers" in data.items[0].label

    def test_handles_docker_error_gracefully(self) -> None:
        """Shows error message when Docker query fails."""
        with patch("scc_cli.docker.core.list_scc_containers") as mock_docker:
            mock_docker.side_effect = Exception("Docker error")

            data = _load_containers_tab_data()

            assert len(data.items) == 1
            assert data.items[0].value == "error"
            assert "Unable to query Docker" in data.items[0].description


class TestLoadSessionsTabData:
    """Test _load_sessions_tab_data function."""

    def test_returns_tab_data_with_sessions_tab(self) -> None:
        """Returns TabData for SESSIONS tab."""
        with patch("scc_cli.sessions.list_recent") as mock_sessions:
            mock_sessions.return_value = []

            data = _load_sessions_tab_data()

            assert data.tab == DashboardTab.SESSIONS
            assert data.title == "Sessions"

    def test_lists_recent_sessions(self) -> None:
        """Lists recent sessions with metadata."""
        with patch("scc_cli.sessions.list_recent") as mock_sessions:
            mock_sessions.return_value = [
                {
                    "name": "feature-work",
                    "container_name": "scc-feature",
                    "team": "dev-team",
                    "branch": "feature/new-ui",
                    "last_used": "2h ago",
                }
            ]

            data = _load_sessions_tab_data()

            assert len(data.items) == 1
            assert data.items[0].label == "feature-work"
            assert "dev-team" in data.items[0].description

    def test_shows_no_sessions_message(self) -> None:
        """Shows message when no sessions exist."""
        with patch("scc_cli.sessions.list_recent") as mock_sessions:
            mock_sessions.return_value = []

            data = _load_sessions_tab_data()

            assert len(data.items) == 1
            assert "No sessions" in data.items[0].label

    def test_handles_sessions_error_gracefully(self) -> None:
        """Shows error message when sessions fail to load."""
        with patch("scc_cli.sessions.list_recent") as mock_sessions:
            mock_sessions.side_effect = Exception("Sessions error")

            data = _load_sessions_tab_data()

            assert len(data.items) == 1
            assert data.items[0].value == "error"


class TestLoadWorktreesTabData:
    """Test _load_worktrees_tab_data function."""

    def test_returns_tab_data_with_worktrees_tab(self) -> None:
        """Returns TabData for WORKTREES tab."""
        with patch("scc_cli.git.list_worktrees") as mock_git:
            mock_git.return_value = []

            data = _load_worktrees_tab_data()

            assert data.tab == DashboardTab.WORKTREES
            assert data.title == "Worktrees"

    def test_lists_worktrees_with_branch_info(self) -> None:
        """Lists worktrees with branch and status."""
        with patch("scc_cli.git.list_worktrees") as mock_git:
            worktree = MagicMock()
            worktree.path = "/home/user/project-main"
            worktree.branch = "main"
            worktree.is_current = True
            worktree.has_changes = False
            mock_git.return_value = [worktree]

            data = _load_worktrees_tab_data()

            assert len(data.items) == 1
            assert data.items[0].label == "project-main"
            assert "main" in data.items[0].description
            assert "(current)" in data.items[0].description

    def test_shows_modified_indicator(self) -> None:
        """Shows modified indicator for worktrees with changes."""
        with patch("scc_cli.git.list_worktrees") as mock_git:
            worktree = MagicMock()
            worktree.path = "/home/user/feature"
            worktree.branch = "feature/test"
            worktree.is_current = False
            worktree.has_changes = True
            mock_git.return_value = [worktree]

            data = _load_worktrees_tab_data()

            assert "*modified" in data.items[0].description

    def test_shows_no_worktrees_message_when_not_git_repo(self) -> None:
        """Shows message when not in a git repository."""
        with patch("scc_cli.git.list_worktrees") as mock_git:
            mock_git.return_value = []

            data = _load_worktrees_tab_data()

            assert len(data.items) == 1
            assert "No worktrees" in data.items[0].label

    def test_handles_git_error_gracefully(self) -> None:
        """Shows error message when git query fails."""
        with patch("scc_cli.git.list_worktrees") as mock_git:
            mock_git.side_effect = Exception("Git error")

            data = _load_worktrees_tab_data()

            assert len(data.items) == 1
            assert "Not available" in data.items[0].label


class TestLoadAllTabData:
    """Test _load_all_tab_data function."""

    def test_returns_dict_with_all_tabs(self) -> None:
        """Returns data for all dashboard tabs."""
        with patch("scc_cli.ui.dashboard._load_status_tab_data") as mock_status:
            with patch("scc_cli.ui.dashboard._load_containers_tab_data") as mock_containers:
                with patch("scc_cli.ui.dashboard._load_sessions_tab_data") as mock_sessions:
                    with patch("scc_cli.ui.dashboard._load_worktrees_tab_data") as mock_worktrees:
                        mock_status.return_value = TabData(
                            tab=DashboardTab.STATUS,
                            title="Status",
                            items=[],
                            count_active=0,
                            count_total=0,
                        )
                        mock_containers.return_value = TabData(
                            tab=DashboardTab.CONTAINERS,
                            title="Containers",
                            items=[],
                            count_active=0,
                            count_total=0,
                        )
                        mock_sessions.return_value = TabData(
                            tab=DashboardTab.SESSIONS,
                            title="Sessions",
                            items=[],
                            count_active=0,
                            count_total=0,
                        )
                        mock_worktrees.return_value = TabData(
                            tab=DashboardTab.WORKTREES,
                            title="Worktrees",
                            items=[],
                            count_active=0,
                            count_total=0,
                        )

                        data = _load_all_tab_data()

                        assert DashboardTab.STATUS in data
                        assert DashboardTab.CONTAINERS in data
                        assert DashboardTab.SESSIONS in data
                        assert DashboardTab.WORKTREES in data
