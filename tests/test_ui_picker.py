"""Unit tests for ui/picker.py - Interactive picker functions.

Test Categories:
- pick_team() - Team selection picker (single-select)
- pick_container() - Container selection picker (single-select)
- pick_containers() - Container selection picker (multi-select)
- pick_session() - Session selection picker (single-select)
- pick_worktree() - Worktree selection picker (single-select)
- _run_single_select_picker() - Core picker loop mechanics
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scc_cli.ui.keys import Action, ActionType
from scc_cli.ui.list_screen import ListItem
from scc_cli.ui.picker import (
    QuickResumeResult,
    _get_running_workspaces,
    _run_single_select_picker,
    pick_container,
    pick_containers,
    pick_session,
    pick_team,
    pick_worktree,
)


class TestPickTeam:
    """Test pick_team() function."""

    def test_empty_teams_returns_none(self) -> None:
        """Empty teams list returns None without interaction."""
        result = pick_team([])
        assert result is None

    def test_teams_converted_to_list_items(self) -> None:
        """Teams are converted using format_team formatter."""
        teams = [
            {"name": "platform", "description": "Platform team"},
            {"name": "backend", "description": "Backend team"},
        ]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = teams[0]
            pick_team(teams, current_team="platform")

            # Verify items were passed to picker
            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            assert len(items) == 2
            assert all(isinstance(item, ListItem) for item in items)

    def test_default_title_and_subtitle(self) -> None:
        """Default title and subtitle are used when not provided."""
        teams = [{"name": "test"}]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_team(teams)

            call_args = mock_picker.call_args
            assert call_args.kwargs["title"] == "Select Team"
            assert call_args.kwargs["subtitle"] == "1 teams available"

    def test_custom_title_and_subtitle(self) -> None:
        """Custom title and subtitle override defaults."""
        teams = [{"name": "test"}]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_team(teams, title="Switch Team", subtitle="Choose wisely")

            call_args = mock_picker.call_args
            assert call_args.kwargs["title"] == "Switch Team"
            assert call_args.kwargs["subtitle"] == "Choose wisely"

    def test_returns_selected_team(self) -> None:
        """Returns the team dict selected by user."""
        teams = [
            {"name": "platform", "description": "Platform team"},
            {"name": "backend", "description": "Backend team"},
        ]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = teams[1]
            result = pick_team(teams)

            assert result == teams[1]
            assert result["name"] == "backend"

    def test_returns_none_on_cancel(self) -> None:
        """Returns None when user cancels picker."""
        teams = [{"name": "test"}]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            result = pick_team(teams)

            assert result is None


class TestPickContainer:
    """Test pick_container() function."""

    def test_empty_containers_returns_none(self) -> None:
        """Empty containers list returns None without interaction."""
        result = pick_container([])
        assert result is None

    def test_containers_converted_to_list_items(self) -> None:
        """Containers are converted using format_container formatter."""
        # Mock container objects with required string attributes
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up 2 hours"
        container1.workspace = "/project/main"
        container1.profile = "platform"
        container1.id = "abc123def456"

        containers = [container1]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = container1
            pick_container(containers)

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            assert len(items) == 1
            assert isinstance(items[0], ListItem)

    def test_default_subtitle_uses_count(self) -> None:
        """Default subtitle shows container count."""
        container1 = MagicMock()
        container1.name = "test1"
        container1.status = "Up 1 hour"
        container1.workspace = "/project"
        container1.profile = "team1"
        container1.id = "abc123def456"

        container2 = MagicMock()
        container2.name = "test2"
        container2.status = "Exited"
        container2.workspace = "/other"
        container2.profile = "team2"
        container2.id = "def456abc123"

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_container([container1, container2])

            call_args = mock_picker.call_args
            assert call_args.kwargs["subtitle"] == "2 containers"


class TestPickContainers:
    """Test pick_containers() function (multi-select)."""

    def test_empty_containers_returns_empty_list(self) -> None:
        """Empty containers list returns empty list without interaction."""
        result = pick_containers([])
        assert result == []

    def test_uses_multi_select_mode(self) -> None:
        """Containers picker uses ListScreen in MULTI_SELECT mode."""
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up 2 hours"
        container1.workspace = "/project/main"
        container1.profile = "platform"
        container1.id = "abc123def456"

        containers = [container1]

        with patch("scc_cli.ui.picker.ListScreen") as mock_screen_cls:
            mock_screen = MagicMock()
            mock_screen_cls.return_value = mock_screen
            mock_screen.run.return_value = []

            pick_containers(containers)

            # Verify ListScreen was called with MULTI_SELECT mode
            call_args = mock_screen_cls.call_args
            from scc_cli.ui.list_screen import ListMode

            assert call_args.kwargs.get("mode") == ListMode.MULTI_SELECT

    def test_returns_selected_containers(self) -> None:
        """Returns list of selected containers from multi-select."""
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up 2 hours"
        container1.workspace = "/project/main"
        container1.profile = "platform"
        container1.id = "abc123"

        container2 = MagicMock()
        container2.name = "scc-feature"
        container2.status = "Up 1 hour"
        container2.workspace = "/project/feature"
        container2.profile = "backend"
        container2.id = "def456"

        containers = [container1, container2]

        with patch("scc_cli.ui.picker.ListScreen") as mock_screen_cls:
            mock_screen = MagicMock()
            mock_screen_cls.return_value = mock_screen
            # Simulate selecting both containers
            mock_screen.run.return_value = [container1, container2]

            result = pick_containers(containers)

            assert result == [container1, container2]
            assert len(result) == 2

    def test_returns_partial_selection(self) -> None:
        """Returns only selected containers, not all."""
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up"
        container1.workspace = "/project"
        container1.profile = "team1"
        container1.id = "abc"

        container2 = MagicMock()
        container2.name = "scc-other"
        container2.status = "Up"
        container2.workspace = "/other"
        container2.profile = "team2"
        container2.id = "def"

        with patch("scc_cli.ui.picker.ListScreen") as mock_screen_cls:
            mock_screen = MagicMock()
            mock_screen_cls.return_value = mock_screen
            # Simulate selecting only first container
            mock_screen.run.return_value = [container1]

            result = pick_containers([container1, container2])

            assert result == [container1]
            assert len(result) == 1

    def test_returns_empty_list_on_cancel(self) -> None:
        """Returns empty list when user cancels (ESC/q)."""
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up"
        container1.workspace = "/project"
        container1.profile = "team"
        container1.id = "abc"

        with patch("scc_cli.ui.picker.ListScreen") as mock_screen_cls:
            mock_screen = MagicMock()
            mock_screen_cls.return_value = mock_screen
            # Simulate cancel (returns None)
            mock_screen.run.return_value = None

            result = pick_containers([container1])

            assert result == []

    def test_returns_empty_list_on_empty_selection(self) -> None:
        """Returns empty list when user confirms with no selection."""
        container1 = MagicMock()
        container1.name = "scc-main"
        container1.status = "Up"
        container1.workspace = "/project"
        container1.profile = "team"
        container1.id = "abc"

        with patch("scc_cli.ui.picker.ListScreen") as mock_screen_cls:
            mock_screen = MagicMock()
            mock_screen_cls.return_value = mock_screen
            # Simulate empty selection (returns [])
            mock_screen.run.return_value = []

            result = pick_containers([container1])

            assert result == []


class TestPickSession:
    """Test pick_session() function."""

    def test_empty_sessions_returns_none(self) -> None:
        """Empty sessions list returns None without interaction."""
        result = pick_session([])
        assert result is None

    def test_sessions_converted_to_list_items(self) -> None:
        """Sessions are converted using format_session formatter."""
        sessions = [
            {"name": "session-1", "team": "platform", "branch": "main"},
            {"name": "session-2", "team": "backend", "branch": "feature"},
        ]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = sessions[0]
            pick_session(sessions)

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            assert len(items) == 2
            assert all(isinstance(item, ListItem) for item in items)

    def test_default_subtitle_uses_count(self) -> None:
        """Default subtitle shows session count."""
        sessions = [{"name": "s1"}]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_session(sessions)

            call_args = mock_picker.call_args
            assert call_args.kwargs["subtitle"] == "1 sessions"


class TestPickWorktree:
    """Test pick_worktree() function."""

    def test_empty_worktrees_returns_none(self) -> None:
        """Empty worktrees list returns None without interaction."""
        result = pick_worktree([])
        assert result is None

    def test_worktrees_converted_to_list_items(self) -> None:
        """Worktrees are converted using format_worktree formatter."""
        worktree1 = MagicMock()
        worktree1.path = "/project/main"
        worktree1.branch = "main"
        worktree1.is_bare = False

        worktrees = [worktree1]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = worktree1
            pick_worktree(worktrees)

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            assert len(items) == 1
            assert isinstance(items[0], ListItem)


class TestRunSingleSelectPicker:
    """Test _run_single_select_picker() core function."""

    def test_empty_items_returns_none(self) -> None:
        """Empty items list returns None without interaction."""
        result = _run_single_select_picker(items=[], title="Test")
        assert result is None

    def test_enter_selects_current_item(self) -> None:
        """Enter key selects the current item."""
        items = [
            ListItem(value="item1", label="Item 1", description="First"),
            ListItem(value="item2", label="Item 2", description="Second"),
        ]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live"):
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader

                    # Simulate: Enter key
                    mock_reader.read.return_value = Action(
                        action_type=ActionType.SELECT, state_changed=True
                    )

                    result = _run_single_select_picker(
                        items=items, title="Test", subtitle="Pick one"
                    )

                    assert result == "item1"  # First item selected by default

    def test_escape_cancels_and_returns_none(self) -> None:
        """Escape key cancels selection and returns None."""
        items = [ListItem(value="item1", label="Item 1", description="")]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live"):
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader

                    mock_reader.read.return_value = Action(
                        action_type=ActionType.CANCEL, state_changed=True
                    )

                    result = _run_single_select_picker(items=items, title="Test")

                    assert result is None

    def test_quit_action_returns_none(self) -> None:
        """Q key cancels selection and returns None."""
        items = [ListItem(value="item1", label="Item 1", description="")]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live"):
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader

                    mock_reader.read.return_value = Action(
                        action_type=ActionType.QUIT, state_changed=True
                    )

                    result = _run_single_select_picker(items=items, title="Test")

                    assert result is None

    def test_navigate_down_moves_cursor(self) -> None:
        """Down arrow moves cursor, then Enter selects moved position."""
        items = [
            ListItem(value="item1", label="Item 1", description=""),
            ListItem(value="item2", label="Item 2", description=""),
        ]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live") as mock_live_cls:
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader
                    mock_live = MagicMock()
                    mock_live_cls.return_value.__enter__ = MagicMock(return_value=mock_live)
                    mock_live_cls.return_value.__exit__ = MagicMock(return_value=None)

                    # Simulate: Down, Enter
                    mock_reader.read.side_effect = [
                        Action(action_type=ActionType.NAVIGATE_DOWN, state_changed=True),
                        Action(action_type=ActionType.SELECT, state_changed=True),
                    ]

                    result = _run_single_select_picker(items=items, title="Test")

                    assert result == "item2"  # Second item after down arrow

    def test_navigate_up_moves_cursor(self) -> None:
        """Up arrow moves cursor up from current position."""
        items = [
            ListItem(value="item1", label="Item 1", description=""),
            ListItem(value="item2", label="Item 2", description=""),
        ]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live") as mock_live_cls:
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader
                    mock_live = MagicMock()
                    mock_live_cls.return_value.__enter__ = MagicMock(return_value=mock_live)
                    mock_live_cls.return_value.__exit__ = MagicMock(return_value=None)

                    # Simulate: Down, Down (at end), Up, Enter
                    mock_reader.read.side_effect = [
                        Action(action_type=ActionType.NAVIGATE_DOWN, state_changed=True),
                        Action(action_type=ActionType.NAVIGATE_UP, state_changed=True),
                        Action(action_type=ActionType.SELECT, state_changed=True),
                    ]

                    result = _run_single_select_picker(items=items, title="Test")

                    # Started at 0, down to 1, up back to 0
                    assert result == "item1"

    def test_filter_char_adds_to_query(self) -> None:
        """Filter characters are added to the filter query."""
        items = [
            ListItem(value="alpha", label="Alpha", description=""),
            ListItem(value="beta", label="Beta", description=""),
        ]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live") as mock_live_cls:
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader
                    mock_live = MagicMock()
                    mock_live_cls.return_value.__enter__ = MagicMock(return_value=mock_live)
                    mock_live_cls.return_value.__exit__ = MagicMock(return_value=None)

                    # Simulate: type 'b', then Enter
                    mock_reader.read.side_effect = [
                        Action(
                            action_type=ActionType.FILTER_CHAR,
                            state_changed=True,
                            filter_char="b",
                        ),
                        Action(action_type=ActionType.SELECT, state_changed=True),
                    ]

                    result = _run_single_select_picker(items=items, title="Test")

                    # 'b' filters to only Beta
                    assert result == "beta"

    def test_filter_delete_removes_char(self) -> None:
        """Backspace removes character from filter query."""
        items = [
            ListItem(value="alpha", label="Alpha", description=""),
            ListItem(value="beta", label="Beta", description=""),
        ]

        with patch("scc_cli.ui.picker.KeyReader") as mock_reader_cls:
            with patch("scc_cli.console.get_err_console"):
                with patch("scc_cli.ui.picker.Live") as mock_live_cls:
                    mock_reader = MagicMock()
                    mock_reader_cls.return_value = mock_reader
                    mock_live = MagicMock()
                    mock_live_cls.return_value.__enter__ = MagicMock(return_value=mock_live)
                    mock_live_cls.return_value.__exit__ = MagicMock(return_value=None)

                    # Type 'b', delete, then Enter (back to unfiltered)
                    mock_reader.read.side_effect = [
                        Action(
                            action_type=ActionType.FILTER_CHAR,
                            state_changed=True,
                            filter_char="b",
                        ),
                        Action(action_type=ActionType.FILTER_DELETE, state_changed=True),
                        Action(action_type=ActionType.SELECT, state_changed=True),
                    ]

                    result = _run_single_select_picker(items=items, title="Test")

                    # After delete, filter is empty, first item selected
                    assert result == "alpha"


class TestPickerIntegration:
    """Integration tests for picker functions with formatters."""

    def test_team_picker_with_current_team_marked(self) -> None:
        """Team picker marks current team in items."""
        teams = [
            {"name": "platform", "description": "Platform team"},
            {"name": "backend", "description": "Backend team"},
        ]

        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_team(teams, current_team="platform")

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]

            # format_team adds checkmark to current team label
            platform_item = next(i for i in items if "platform" in i.label.lower())
            assert "✓" in platform_item.label or "current" in platform_item.label.lower()

    def test_picker_subtitle_pluralization(self) -> None:
        """Picker handles singular/plural in subtitle."""
        with patch("scc_cli.ui.picker._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None

            # Single team
            pick_team([{"name": "only"}])
            assert "1 teams" in mock_picker.call_args.kwargs["subtitle"]

            # Multiple teams
            pick_team([{"name": "a"}, {"name": "b"}])
            assert "2 teams" in mock_picker.call_args.kwargs["subtitle"]


class TestGetRunningWorkspaces:
    """Test _get_running_workspaces() helper function."""

    def test_returns_running_container_workspaces(self) -> None:
        """Returns set of workspace paths from running containers."""
        mock_containers = [
            MagicMock(workspace="/code/project-a", status="Up 2 hours"),
            MagicMock(workspace="/code/project-b", status="Up 5 minutes"),
        ]

        with patch("scc_cli.docker.list_scc_containers", return_value=mock_containers):
            result = _get_running_workspaces()

        assert result == {"/code/project-a", "/code/project-b"}

    def test_excludes_stopped_containers(self) -> None:
        """Excludes containers that are not running."""
        mock_containers = [
            MagicMock(workspace="/code/running", status="Up 2 hours"),
            MagicMock(workspace="/code/stopped", status="Exited (0) 1 hour ago"),
            MagicMock(workspace="/code/created", status="Created"),
        ]

        with patch("scc_cli.docker.list_scc_containers", return_value=mock_containers):
            result = _get_running_workspaces()

        assert result == {"/code/running"}

    def test_excludes_containers_without_workspace(self) -> None:
        """Excludes containers with no workspace path."""
        mock_containers = [
            MagicMock(workspace="/code/project", status="Up 2 hours"),
            MagicMock(workspace=None, status="Up 1 hour"),
            MagicMock(workspace="", status="Up 30 minutes"),
        ]

        with patch("scc_cli.docker.list_scc_containers", return_value=mock_containers):
            result = _get_running_workspaces()

        assert result == {"/code/project"}

    def test_returns_empty_set_on_docker_error(self) -> None:
        """Returns empty set when Docker is not available."""
        with patch(
            "scc_cli.docker.list_scc_containers",
            side_effect=Exception("Docker not available"),
        ):
            result = _get_running_workspaces()

        assert result == set()

    def test_returns_empty_set_when_no_containers(self) -> None:
        """Returns empty set when no containers exist."""
        with patch("scc_cli.docker.list_scc_containers", return_value=[]):
            result = _get_running_workspaces()

        assert result == set()

    def test_returns_empty_set_on_import_error(self) -> None:
        """Returns empty set gracefully when docker module import fails."""
        with patch(
            "scc_cli.docker.list_scc_containers",
            side_effect=ImportError("No module named docker"),
        ):
            result = _get_running_workspaces()

        assert result == set()


class TestQuickResumeCurrentBranch:
    """Test pick_context_quick_resume current_branch highlighting."""

    def test_current_branch_highlights_matching_context(self) -> None:
        """Context matching current_branch gets is_current_branch=True."""
        from pathlib import Path

        from scc_cli.contexts import WorkContext
        from scc_cli.ui.formatters import format_context

        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="feature-auth",
        )

        # Simulate the logic in pick_context_quick_resume
        current_branch = "feature-auth"
        is_current = current_branch is not None and ctx.worktree_name == current_branch

        item = format_context(ctx, is_current_branch=is_current)

        assert "★" in item.label
        assert item.metadata["current_branch"] == "yes"

    def test_current_branch_no_highlight_when_different(self) -> None:
        """Context not matching current_branch gets is_current_branch=False."""
        from pathlib import Path

        from scc_cli.contexts import WorkContext
        from scc_cli.ui.formatters import format_context

        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )

        # Simulate the logic in pick_context_quick_resume
        current_branch = "feature-auth"
        is_current = current_branch is not None and ctx.worktree_name == current_branch

        item = format_context(ctx, is_current_branch=is_current)

        assert "★" not in item.label
        assert item.metadata["current_branch"] == "no"

    def test_current_branch_none_no_highlights(self) -> None:
        """When current_branch is None, no contexts are highlighted."""
        from pathlib import Path

        from scc_cli.contexts import WorkContext
        from scc_cli.ui.formatters import format_context

        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )

        # Simulate the logic in pick_context_quick_resume
        current_branch = None
        is_current = current_branch is not None and ctx.worktree_name == current_branch

        item = format_context(ctx, is_current_branch=is_current)

        assert "★" not in item.label
        assert item.metadata["current_branch"] == "no"

    def test_pick_context_quick_resume_accepts_current_branch(self) -> None:
        """pick_context_quick_resume accepts current_branch parameter."""
        from pathlib import Path

        from scc_cli.contexts import WorkContext
        from scc_cli.ui.picker import pick_context_quick_resume

        contexts = [
            WorkContext(
                team="platform",
                repo_root=Path("/code/api"),
                worktree_path=Path("/code/api"),
                worktree_name="main",
            ),
        ]

        # Mock the picker and container check to avoid terminal interaction
        with patch("scc_cli.docker.list_scc_containers", return_value=[]):
            with patch("scc_cli.ui.picker._run_quick_resume_picker") as mock_picker:
                mock_picker.return_value = (QuickResumeResult.CANCELLED, None)

                # Should not raise - current_branch is a valid parameter
                pick_context_quick_resume(
                    contexts,
                    title="Quick Resume",
                    current_branch="main",
                )

                # Verify format_context was called with is_current_branch=True
                mock_picker.assert_called_once()
                items = mock_picker.call_args.kwargs["items"]
                assert len(items) == 1
                # The item should have ★ indicator since worktree_name == current_branch
                assert "★" in items[0].label
