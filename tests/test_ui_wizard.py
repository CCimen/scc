"""Unit tests for ui/wizard.py - Wizard navigation with BACK semantics.

Test Categories:
- BACK sentinel behavior (identity, repr)
- Top-level picker: Esc/q → None (cancel wizard)
- Sub-screen pickers: Esc → BACK, q → None (three-state contract)
- pick_workspace_source() - Top-level workspace source selection
- pick_recent_workspace() - Sub-screen recent workspaces
- pick_team_repo() - Sub-screen team repositories
- Path normalization helpers
- Time formatting helpers

Golden Navigation Contract:
- Top-level screens: Esc/q cancels entire wizard (returns None)
- Sub-screens (three-state):
  - Esc: goes back to previous screen (returns BACK)
  - q: quits app entirely (returns None)
- "← Back" menu item always returns BACK
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scc_cli.ui.wizard import (
    BACK,
    WorkspaceSource,
    _format_relative_time,
    _is_valid_workspace,
    _normalize_path,
    pick_recent_workspace,
    pick_team_repo,
    pick_workspace_source,
)


class TestBackSentinel:
    """Test BACK sentinel behavior."""

    def test_back_is_singleton(self) -> None:
        """BACK sentinel uses identity comparison."""
        assert BACK is BACK

    def test_back_repr(self) -> None:
        """BACK has clear string representation."""
        assert repr(BACK) == "BACK"

    def test_back_is_not_none(self) -> None:
        """BACK is distinct from None."""
        assert BACK is not None
        assert BACK != None  # noqa: E711 - intentional None comparison

    def test_back_identity_comparison(self) -> None:
        """BACK supports identity comparison pattern."""
        result = BACK
        # This is the recommended usage pattern
        assert result is BACK


class TestWorkspaceSourceEnum:
    """Test WorkspaceSource enum values."""

    def test_enum_values(self) -> None:
        """WorkspaceSource has expected values."""
        assert WorkspaceSource.CURRENT_DIR.value == "current_dir"
        assert WorkspaceSource.RECENT.value == "recent"
        assert WorkspaceSource.TEAM_REPOS.value == "team_repos"
        assert WorkspaceSource.CUSTOM.value == "custom"
        assert WorkspaceSource.CLONE.value == "clone"

    def test_current_dir_enum_exists(self) -> None:
        """WorkspaceSource.CURRENT_DIR is defined for CWD option."""
        # This value is used when user selects "Use current directory"
        assert hasattr(WorkspaceSource, "CURRENT_DIR")
        assert WorkspaceSource.CURRENT_DIR.value == "current_dir"


class TestPickWorkspaceSourceTopLevel:
    """Test pick_workspace_source() - top-level picker.

    Golden rule: Top-level screens return None on cancel (Esc/q).
    """

    def test_escape_returns_none(self) -> None:
        """Esc on top-level picker cancels wizard (returns None)."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates Esc/cancel

            result = pick_workspace_source()

            assert result is None

    def test_quit_returns_none(self) -> None:
        """Q on top-level picker cancels wizard (returns None)."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates q/quit

            result = pick_workspace_source()

            assert result is None

    def test_selection_returns_workspace_source(self) -> None:
        """Valid selection returns WorkspaceSource enum."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = WorkspaceSource.RECENT

            result = pick_workspace_source()

            assert result == WorkspaceSource.RECENT

    def test_includes_all_standard_options(self) -> None:
        """Top-level includes recent, custom, clone options."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source()

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            values = [item.value for item in items]

            assert WorkspaceSource.RECENT in values
            assert WorkspaceSource.CUSTOM in values
            assert WorkspaceSource.CLONE in values

    def test_team_repos_shown_when_available(self) -> None:
        """Team repositories option shown when has_team_repos=True."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(has_team_repos=True)

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            values = [item.value for item in items]

            assert WorkspaceSource.TEAM_REPOS in values

    def test_team_repos_hidden_when_unavailable(self) -> None:
        """Team repositories option hidden when has_team_repos=False."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(has_team_repos=False)

            call_args = mock_picker.call_args
            items = call_args.kwargs["items"]
            values = [item.value for item in items]

            assert WorkspaceSource.TEAM_REPOS not in values

    def test_context_label_shows_team_name(self) -> None:
        """Context label shows team name when provided."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(team="platform")

            call_args = mock_picker.call_args
            context_label = call_args.kwargs["context_label"]

            assert context_label == "Team: platform"

    def test_subtitle_default_without_team(self) -> None:
        """Subtitle has default when no team specified."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(team=None)

            call_args = mock_picker.call_args
            subtitle = call_args.kwargs["subtitle"]

            assert subtitle == "Pick a project source"


class TestPickWorkspaceSourceWithAllowBack:
    """Test pick_workspace_source() three-state return contract.

    When allow_back=True (used from Dashboard context):
    - Esc → BACK (go back to Dashboard)
    - q → None (quit app entirely)
    - Selection → WorkspaceSource value

    When allow_back=False (default, CLI context):
    - Esc → None (cancel wizard)
    - q → None (cancel wizard)
    - Selection → WorkspaceSource value
    """

    def test_allow_back_false_escape_returns_none(self) -> None:
        """With allow_back=False (default), Esc returns None."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates Esc

            result = pick_workspace_source(allow_back=False)

            assert result is None
            assert result is not BACK

    def test_allow_back_true_escape_returns_back(self) -> None:
        """With allow_back=True, Esc returns BACK sentinel."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = BACK  # Simulates Esc with allow_back

            result = pick_workspace_source(allow_back=True)

            assert result is BACK
            assert result is not None

    def test_allow_back_passed_to_underlying_picker(self) -> None:
        """allow_back parameter is passed to _run_single_select_picker."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None

            pick_workspace_source(allow_back=True)

            call_args = mock_picker.call_args
            assert call_args.kwargs.get("allow_back") is True

    def test_selection_works_regardless_of_allow_back(self) -> None:
        """Valid selection returns WorkspaceSource regardless of allow_back."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = WorkspaceSource.RECENT

            result_with_back = pick_workspace_source(allow_back=True)
            result_without_back = pick_workspace_source(allow_back=False)

            assert result_with_back == WorkspaceSource.RECENT
            assert result_without_back == WorkspaceSource.RECENT


class TestPickWorkspaceSourceCurrentDir:
    """Test pick_workspace_source() CWD detection and option.

    When CWD is a valid workspace (has .git or .scc.yaml):
    - "Use current directory" option appears first in list
    - Selecting it returns WorkspaceSource.CURRENT_DIR
    """

    def test_cwd_option_shown_when_valid_workspace(self, tmp_path: Path) -> None:
        """CWD option shown when current directory is valid workspace."""
        # Create a valid workspace with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch("scc_cli.ui.wizard.Path.cwd", return_value=tmp_path):
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = None
                pick_workspace_source()

                call_args = mock_picker.call_args
                items = call_args.kwargs["items"]
                values = [item.value for item in items]

                assert WorkspaceSource.CURRENT_DIR in values

    def test_cwd_option_is_first_when_valid(self, tmp_path: Path) -> None:
        """CWD option appears first in list when valid."""
        # Create a valid workspace with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch("scc_cli.ui.wizard.Path.cwd", return_value=tmp_path):
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = None
                pick_workspace_source()

                call_args = mock_picker.call_args
                items = call_args.kwargs["items"]

                # First item should be CURRENT_DIR
                assert items[0].value == WorkspaceSource.CURRENT_DIR
                assert "current" in items[0].label.lower()

    def test_cwd_option_shows_directory_name(self, tmp_path: Path) -> None:
        """CWD option shows current directory name in description."""
        # Create a valid workspace with .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch("scc_cli.ui.wizard.Path.cwd", return_value=tmp_path):
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = None
                pick_workspace_source()

                call_args = mock_picker.call_args
                items = call_args.kwargs["items"]

                # First item description should contain dir name
                assert tmp_path.name in items[0].description

    def test_cwd_option_not_shown_for_non_workspace(self, tmp_path: Path) -> None:
        """CWD option not shown when current directory is not a workspace."""
        # tmp_path has no .git or .scc.yaml, so it's NOT a valid workspace
        # The "Use current directory" option should NOT appear
        with patch("scc_cli.ui.wizard.Path.cwd", return_value=tmp_path):
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = None
                pick_workspace_source()

                call_args = mock_picker.call_args
                items = call_args.kwargs["items"]
                values = [item.value for item in items]

                # Non-workspace directory should NOT show CWD option
                assert WorkspaceSource.CURRENT_DIR not in values

    def test_selecting_cwd_returns_current_dir_enum(self) -> None:
        """Selecting CWD option returns WorkspaceSource.CURRENT_DIR."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = WorkspaceSource.CURRENT_DIR

            result = pick_workspace_source()

            assert result == WorkspaceSource.CURRENT_DIR


class TestIsValidWorkspace:
    """Test _is_valid_workspace() helper function."""

    def test_valid_with_git_directory(self, tmp_path: Path) -> None:
        """Directory with .git directory is valid workspace."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        assert _is_valid_workspace(tmp_path) is True

    def test_valid_with_git_file(self, tmp_path: Path) -> None:
        """Directory with .git file (worktree) is valid workspace."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /path/to/main/.git/worktrees/branch")

        assert _is_valid_workspace(tmp_path) is True

    def test_valid_with_scc_yaml(self, tmp_path: Path) -> None:
        """Directory with .scc.yaml is valid workspace."""
        scc_config = tmp_path / ".scc.yaml"
        scc_config.write_text("version: 1")

        assert _is_valid_workspace(tmp_path) is True

    def test_invalid_for_directory_without_markers(self, tmp_path: Path) -> None:
        """Directory without .git or .scc.yaml is NOT a valid workspace."""
        # tmp_path exists but has no .git or .scc.yaml
        # Random directories (like $HOME) should NOT be treated as workspaces
        assert _is_valid_workspace(tmp_path) is False

    def test_invalid_for_non_existent_directory(self, tmp_path: Path) -> None:
        """Non-existent directory is not valid."""
        non_existent = tmp_path / "does_not_exist"

        assert _is_valid_workspace(non_existent) is False

    def test_invalid_for_file(self, tmp_path: Path) -> None:
        """File (not directory) is not valid workspace."""
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")

        assert _is_valid_workspace(file_path) is False


class TestPickRecentWorkspaceSubScreen:
    """Test pick_recent_workspace() - sub-screen picker.

    Three-state contract for sub-screens:
    - Esc: returns BACK (go back to previous screen)
    - q: returns None (quit app entirely)
    - Selection: returns workspace path string
    """

    def test_escape_returns_back(self) -> None:
        """Esc on sub-screen returns BACK (go back to previous screen)."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns BACK for Esc
            mock_picker.return_value = BACK

            result = pick_recent_workspace(recent)

            assert result is BACK
            assert result is not None

    def test_quit_returns_none(self) -> None:
        """Q on sub-screen returns None (quit app entirely)."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns None for q
            mock_picker.return_value = None

            result = pick_recent_workspace(recent)

            assert result is None

    def test_back_menu_item_returns_back(self) -> None:
        """Selecting '← Back' menu item returns BACK."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = BACK  # User selected "← Back"

            result = pick_recent_workspace(recent)

            assert result is BACK

    def test_selection_returns_workspace_path(self) -> None:
        """Valid selection returns workspace path string."""
        recent = [{"workspace": "/project/myapp", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = "/project/myapp"

            result = pick_recent_workspace(recent)

            assert result == "/project/myapp"
            assert result is not BACK

    def test_includes_back_as_first_item(self) -> None:
        """Back item is first in the list."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_recent_workspace(recent)

            call_args = mock_picker.call_args
            # Items passed as first positional argument
            items = call_args[0][0]

            assert items[0].value is BACK
            assert "Back" in items[0].label

    def test_empty_recent_shows_empty_hint(self) -> None:
        """Empty recent list shows helpful subtitle."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_recent_workspace([])

            call_args = mock_picker.call_args
            subtitle = call_args.kwargs.get("subtitle")

            # Subtitle indicates empty state
            assert subtitle is not None
            assert "no recent" in subtitle.lower()


class TestPickTeamRepoSubScreen:
    """Test pick_team_repo() - sub-screen picker.

    Three-state contract for sub-screens:
    - Esc: returns BACK (go back to previous screen)
    - q: returns None (quit app entirely)
    - Selection: returns workspace path string
    """

    def test_escape_returns_back(self) -> None:
        """Esc on sub-screen returns BACK (go back to previous screen)."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns BACK for Esc
            mock_picker.return_value = BACK

            result = pick_team_repo(repos)

            assert result is BACK
            assert result is not None

    def test_quit_returns_none(self) -> None:
        """Q on sub-screen returns None (quit app entirely)."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns None for q
            mock_picker.return_value = None

            result = pick_team_repo(repos)

            assert result is None

    def test_back_menu_item_returns_back(self) -> None:
        """Selecting '← Back' menu item returns BACK."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = BACK  # User selected "← Back"

            result = pick_team_repo(repos)

            assert result is BACK

    def test_includes_back_as_first_item(self) -> None:
        """Back item is first in the list."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_team_repo(repos)

            call_args = mock_picker.call_args
            # Items passed as first positional argument
            items = call_args[0][0]

            assert items[0].value is BACK
            assert "Back" in items[0].label

    def test_existing_local_path_returns_path(self) -> None:
        """Repo with existing local_path returns that path."""
        repos = [{"name": "api", "url": "https://github.com/org/api", "local_path": "/tmp"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = repos[0]  # User selected repo dict

            result = pick_team_repo(repos)

            # /tmp exists, so should return its path
            assert result == "/tmp"

    def test_empty_repos_shows_empty_hint(self) -> None:
        """Empty repos list shows helpful subtitle."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_team_repo([])

            call_args = mock_picker.call_args
            subtitle = call_args.kwargs.get("subtitle")

            # Subtitle indicates empty state
            assert subtitle is not None
            assert "no team" in subtitle.lower()


class TestNormalizePath:
    """Test _normalize_path() helper."""

    def test_collapses_home_to_tilde(self) -> None:
        """Paths under home directory collapse to ~."""
        home = Path.home()
        path = str(home / "projects" / "myapp")

        result = _normalize_path(path)

        assert result.startswith("~/")
        assert "myapp" in result

    def test_preserves_non_home_paths(self) -> None:
        """Paths outside home are preserved."""
        result = _normalize_path("/opt/data/files")

        assert not result.startswith("~")
        assert "opt" in result or "data" in result

    def test_truncates_long_paths(self) -> None:
        """Very long paths are truncated with ellipsis."""
        home = Path.home()
        # Create a path that is definitely longer than 50 chars after ~ normalization
        # ~/very/deeply/nested/directory/structure/to/final/project = ~55+ chars
        long_path = str(
            home
            / "very"
            / "deeply"
            / "nested"
            / "directory"
            / "structure"
            / "to"
            / "final"
            / "project"
        )

        result = _normalize_path(long_path)

        # Path should be truncated and contain ellipsis
        assert len(result) <= 50 or "…" in result

    def test_keeps_last_two_segments(self) -> None:
        """Truncation keeps last 2 path segments for context."""
        home = Path.home()
        path = str(home / "a" / "b" / "c" / "d" / "final" / "project")

        result = _normalize_path(path)

        # Should contain the last two segments
        assert "project" in result


class TestFormatRelativeTime:
    """Test _format_relative_time() helper."""

    def test_just_now(self) -> None:
        """Timestamps within 60 seconds show 'just now'."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()

        result = _format_relative_time(recent)

        assert result == "just now"

    def test_minutes_ago(self) -> None:
        """Timestamps within an hour show minutes."""
        now = datetime.now(timezone.utc)
        five_min_ago = (now - timedelta(minutes=5)).isoformat()

        result = _format_relative_time(five_min_ago)

        assert "5m ago" in result

    def test_hours_ago(self) -> None:
        """Timestamps within a day show hours."""
        now = datetime.now(timezone.utc)
        three_hours_ago = (now - timedelta(hours=3)).isoformat()

        result = _format_relative_time(three_hours_ago)

        assert "3h ago" in result

    def test_yesterday(self) -> None:
        """Timestamps ~1 day ago show 'yesterday'."""
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(hours=30)).isoformat()

        result = _format_relative_time(yesterday)

        assert result == "yesterday"

    def test_days_ago(self) -> None:
        """Timestamps 2-7 days ago show days."""
        now = datetime.now(timezone.utc)
        five_days_ago = (now - timedelta(days=5)).isoformat()

        result = _format_relative_time(five_days_ago)

        assert "5d ago" in result

    def test_older_shows_date(self) -> None:
        """Timestamps older than 7 days show month/day."""
        now = datetime.now(timezone.utc)
        two_weeks_ago = (now - timedelta(days=14)).isoformat()

        result = _format_relative_time(two_weeks_ago)

        # Should be "Dec 11" format or similar
        assert "ago" not in result

    def test_handles_z_suffix(self) -> None:
        """Handles ISO timestamps with Z suffix."""
        now = datetime.now(timezone.utc)
        recent = now.isoformat().replace("+00:00", "Z")

        result = _format_relative_time(recent)

        assert result == "just now"

    def test_invalid_timestamp_returns_empty(self) -> None:
        """Invalid timestamps return empty string."""
        result = _format_relative_time("not-a-date")

        assert result == ""


class TestNavigationContract:
    """Golden tests for the navigation contract.

    These tests protect the fundamental navigation semantics:
    - Top-level (allow_back=False): cancel → None
    - Top-level (allow_back=True): Esc → BACK, q → None
    - Sub-screen: Esc → BACK, q → None (three-state contract)
    """

    def test_top_level_cancel_is_none_not_back(self) -> None:
        """CRITICAL: Top-level cancel (allow_back=False) must be None, never BACK."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None

            result = pick_workspace_source()

            assert result is None
            assert result is not BACK

    def test_subscreen_escape_returns_back(self) -> None:
        """CRITICAL: Sub-screen Esc must return BACK (go back to previous)."""
        recent = [{"workspace": "/tmp", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns BACK for Esc
            mock_picker.return_value = BACK

            result = pick_recent_workspace(recent)

            assert result is BACK
            assert result is not None

    def test_subscreen_quit_returns_none(self) -> None:
        """CRITICAL: Sub-screen q must return None (quit app entirely)."""
        recent = [{"workspace": "/tmp", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # With allow_back=True, underlying picker returns None for q
            mock_picker.return_value = None

            result = pick_recent_workspace(recent)

            assert result is None

    def test_back_sentinel_distinguishes_back_from_quit(self) -> None:
        """BACK sentinel allows type-safe distinction from quit (None)."""
        # This test documents the three-state contract usage pattern

        # Simulating wizard flow with proper three-state handling
        def wizard_step() -> str | None:
            """Outer wizard returns None on quit/cancel, str on success."""
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = WorkspaceSource.RECENT
                source = pick_workspace_source()

                if source is None:
                    return None  # User cancelled wizard (Esc or q at top level)

                if source == WorkspaceSource.RECENT:
                    # Simulate Esc on sub-screen → BACK
                    mock_picker.return_value = BACK
                    result = pick_recent_workspace(
                        [{"workspace": "/tmp", "last_used": "2025-01-01T00:00:00Z"}]
                    )
                    if result is None:
                        return None  # User pressed q - quit app
                    if result is BACK:
                        # Go back to source picker (handled by outer loop)
                        return None  # For this test, just return None
                    return str(result)

                return None

        # The pattern works - no type errors, clear semantics
        outcome = wizard_step()
        assert outcome is None  # BACK was handled correctly

    def test_three_state_contract_with_allow_back(self) -> None:
        """CRITICAL: With allow_back=True, picker returns three distinct values.

        This test documents the three-state contract:
        - WorkspaceSource: User selected an option (Success)
        - BACK: User pressed Esc (go back to previous screen)
        - None: User pressed q (quit app entirely)
        """
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            # Test 1: Selection returns WorkspaceSource
            mock_picker.return_value = WorkspaceSource.RECENT
            result = pick_workspace_source(allow_back=True)
            assert isinstance(result, WorkspaceSource)
            assert result == WorkspaceSource.RECENT

            # Test 2: Esc returns BACK (via picker returning BACK)
            mock_picker.return_value = BACK
            result = pick_workspace_source(allow_back=True)
            assert result is BACK
            assert result is not None

            # Test 3: q returns None (via picker returning None)
            # Note: This requires the underlying picker to distinguish,
            # but from wizard's perspective, None means quit
            # The actual None case is tested in TestPickWorkspaceSourceTopLevel
