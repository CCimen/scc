"""Unit tests for ui/wizard.py - Wizard navigation with BACK semantics.

Test Categories:
- BACK sentinel behavior (identity, repr)
- Top-level picker: Esc/q → None (cancel wizard)
- Sub-screen pickers: Esc/q → BACK (never None)
- pick_workspace_source() - Top-level workspace source selection
- pick_recent_workspace() - Sub-screen recent workspaces
- pick_team_repo() - Sub-screen team repositories
- Path normalization helpers
- Time formatting helpers

Golden Navigation Contract:
- Top-level screens: Esc/q cancels entire wizard (returns None)
- Sub-screens: Esc/q goes back to previous screen (returns BACK)
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
        assert WorkspaceSource.RECENT.value == "recent"
        assert WorkspaceSource.TEAM_REPOS.value == "team_repos"
        assert WorkspaceSource.CUSTOM.value == "custom"
        assert WorkspaceSource.CLONE.value == "clone"


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

    def test_subtitle_shows_team_name(self) -> None:
        """Subtitle shows team name when provided."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(team="platform")

            call_args = mock_picker.call_args
            subtitle = call_args.kwargs["subtitle"]

            assert "platform" in subtitle.lower()

    def test_subtitle_default_without_team(self) -> None:
        """Subtitle has default when no team specified."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None
            pick_workspace_source(team=None)

            call_args = mock_picker.call_args
            subtitle = call_args.kwargs["subtitle"]

            assert subtitle is not None
            assert len(subtitle) > 0


class TestPickRecentWorkspaceSubScreen:
    """Test pick_recent_workspace() - sub-screen picker.

    Golden rule: Sub-screens return BACK on cancel (Esc/q), never None.
    """

    def test_escape_returns_back(self) -> None:
        """Esc on sub-screen returns BACK (not None)."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates Esc

            result = pick_recent_workspace(recent)

            assert result is BACK
            assert result is not None

    def test_quit_returns_back(self) -> None:
        """Q on sub-screen returns BACK (not None)."""
        recent = [{"workspace": "/project", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates q

            result = pick_recent_workspace(recent)

            assert result is BACK

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

    Golden rule: Sub-screens return BACK on cancel (Esc/q), never None.
    """

    def test_escape_returns_back(self) -> None:
        """Esc on sub-screen returns BACK (not None)."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates Esc

            result = pick_team_repo(repos)

            assert result is BACK
            assert result is not None

    def test_quit_returns_back(self) -> None:
        """Q on sub-screen returns BACK (not None)."""
        repos = [{"name": "api", "url": "https://github.com/org/api"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None  # Simulates q

            result = pick_team_repo(repos)

            assert result is BACK

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
    - Top-level: cancel → None
    - Sub-screen: cancel → BACK
    """

    def test_top_level_cancel_is_none_not_back(self) -> None:
        """CRITICAL: Top-level cancel must be None, never BACK."""
        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None

            result = pick_workspace_source()

            assert result is None
            assert result is not BACK

    def test_subscreen_cancel_is_back_not_none(self) -> None:
        """CRITICAL: Sub-screen cancel must be BACK, never None."""
        recent = [{"workspace": "/tmp", "last_used": "2025-01-01T00:00:00Z"}]

        with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
            mock_picker.return_value = None

            result = pick_recent_workspace(recent)

            assert result is BACK
            assert result is not None

    def test_back_sentinel_distinguishes_cancel_from_data(self) -> None:
        """BACK sentinel allows type-safe distinction from valid data."""
        # This test documents the expected usage pattern

        # Simulating wizard flow
        def wizard_step() -> str | None:
            """Outer wizard returns None on cancel, str on success."""
            with patch("scc_cli.ui.wizard._run_single_select_picker") as mock_picker:
                mock_picker.return_value = WorkspaceSource.RECENT
                source = pick_workspace_source()

                if source is None:
                    return None  # User cancelled wizard

                if source == WorkspaceSource.RECENT:
                    mock_picker.return_value = None  # Simulate Esc
                    result = pick_recent_workspace(
                        [{"workspace": "/tmp", "last_used": "2025-01-01T00:00:00Z"}]
                    )
                    if result is BACK:
                        # Go back to source picker (handled by outer loop)
                        return None  # For this test, just return None
                    return str(result)

                return None

        # The pattern works - no type errors, clear semantics
        outcome = wizard_step()
        assert outcome is None  # BACK was handled correctly
