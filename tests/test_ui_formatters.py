"""Tests for ui/formatters.py - Display formatting helpers.

Test Categories:
- format_team tests (with/without current, governance status)
- format_container tests (status shortening, metadata)
- format_session tests (governance warnings)
- format_worktree tests (current markers, changes)
- format_context tests (pinned indicator, relative time)
- _shorten_docker_status helper tests
- _format_relative_time helper tests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scc_cli.contexts import WorkContext
from scc_cli.docker.core import ContainerInfo
from scc_cli.git import WorktreeInfo
from scc_cli.ui.formatters import (
    _format_relative_time,
    _shorten_docker_status,
    format_container,
    format_context,
    format_session,
    format_team,
    format_worktree,
)


class TestFormatTeam:
    """Test format_team function."""

    def test_formats_basic_team(self) -> None:
        """Format a basic team without description."""
        team = {"name": "platform"}
        item = format_team(team)

        assert item.label == "platform"
        assert item.value == team
        assert item.governance_status is None

    def test_includes_description(self) -> None:
        """Include team description in output."""
        team = {"name": "platform", "description": "Platform engineering team"}
        item = format_team(team)

        assert item.label == "platform"
        assert "Platform engineering team" in item.description

    def test_marks_current_team_with_checkmark(self) -> None:
        """Current team is marked with checkmark prefix."""
        team = {"name": "platform"}
        item = format_team(team, current_team="platform")

        assert item.label == "✓ platform"

    def test_non_current_team_no_checkmark(self) -> None:
        """Non-current team has no checkmark."""
        team = {"name": "platform"}
        item = format_team(team, current_team="other-team")

        assert item.label == "platform"
        assert "✓" not in item.label

    def test_expired_credentials_blocked_status(self) -> None:
        """Expired credentials result in blocked governance status."""
        team = {"name": "platform", "credential_status": "expired"}
        item = format_team(team)

        assert item.governance_status == "blocked"
        assert "expired" in item.description.lower()

    def test_expiring_credentials_warning_status(self) -> None:
        """Expiring credentials result in warning governance status."""
        team = {"name": "platform", "credential_status": "expiring"}
        item = format_team(team)

        assert item.governance_status == "warning"
        assert "expiring" in item.description.lower()

    def test_valid_credentials_no_governance_status(self) -> None:
        """Valid credentials have no governance status."""
        team = {"name": "platform", "credential_status": "valid"}
        item = format_team(team)

        assert item.governance_status is None

    def test_missing_name_uses_unknown(self) -> None:
        """Missing name defaults to 'unknown'."""
        team = {}
        item = format_team(team)

        assert item.label == "unknown"


class TestFormatContainer:
    """Test format_container function."""

    def test_formats_basic_container(self) -> None:
        """Format a basic container."""
        container = ContainerInfo(id="abc123def456", name="scc-main", status="Up 2 hours")
        item = format_container(container)

        assert item.label == "scc-main"
        assert item.value == container

    def test_includes_profile_in_description(self) -> None:
        """Include profile in description."""
        container = ContainerInfo(
            id="abc123def456",
            name="scc-main",
            status="Up 2 hours",
            profile="team-a",
        )
        item = format_container(container)

        assert "team-a" in item.description

    def test_includes_workspace_name_only(self) -> None:
        """Include just workspace directory name, not full path."""
        container = ContainerInfo(
            id="abc123def456",
            name="scc-main",
            status="Up 2 hours",
            workspace="/home/user/my-project",
        )
        item = format_container(container)

        assert "my-project" in item.description
        assert "/home/user" not in item.description

    def test_shortens_status_hours(self) -> None:
        """Shorten 'hours' to 'h' in status."""
        container = ContainerInfo(id="abc123def456", name="scc-main", status="Up 2 hours")
        item = format_container(container)

        assert "2h" in item.description
        assert "hours" not in item.description

    def test_metadata_includes_running_status(self) -> None:
        """Metadata indicates if container is running."""
        running = ContainerInfo(id="abc123def456", name="scc-running", status="Up 5 minutes")
        stopped = ContainerInfo(
            id="def456abc123", name="scc-stopped", status="Exited (0) 1 hour ago"
        )

        running_item = format_container(running)
        stopped_item = format_container(stopped)

        assert running_item.metadata["running"] == "yes"
        assert stopped_item.metadata["running"] == "no"

    def test_metadata_includes_short_container_id(self) -> None:
        """Metadata includes first 12 chars of container ID."""
        container = ContainerInfo(
            id="abc123def456789xyz",
            name="scc-main",
            status="Up",
        )
        item = format_container(container)

        assert item.metadata["id"] == "abc123def456"


class TestFormatSession:
    """Test format_session function."""

    def test_formats_basic_session(self) -> None:
        """Format a basic session."""
        session = {"name": "my-session"}
        item = format_session(session)

        assert item.label == "my-session"
        assert item.value == session

    def test_includes_team_in_description(self) -> None:
        """Include team name in description."""
        session = {"name": "my-session", "team": "platform"}
        item = format_session(session)

        assert "platform" in item.description

    def test_includes_branch_in_description(self) -> None:
        """Include branch name in description."""
        session = {"name": "my-session", "branch": "feature/auth"}
        item = format_session(session)

        assert "feature/auth" in item.description

    def test_includes_last_used_in_description(self) -> None:
        """Include last used time in description."""
        session = {"name": "my-session", "last_used": "2 hours ago"}
        item = format_session(session)

        assert "2 hours ago" in item.description

    def test_exception_warning_governance_status(self) -> None:
        """Session with exception warning has warning governance status."""
        session = {"name": "my-session", "has_exception_warning": True}
        item = format_session(session)

        assert item.governance_status == "warning"

    def test_no_exception_warning_no_governance_status(self) -> None:
        """Session without exception warning has no governance status."""
        session = {"name": "my-session", "has_exception_warning": False}
        item = format_session(session)

        assert item.governance_status is None

    def test_missing_name_uses_unnamed(self) -> None:
        """Missing name defaults to 'Unnamed'."""
        session = {}
        item = format_session(session)

        assert item.label == "Unnamed"


class TestFormatWorktree:
    """Test format_worktree function."""

    def test_formats_basic_worktree(self) -> None:
        """Format a basic worktree."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main")
        item = format_worktree(wt)

        assert item.label == "my-project"
        assert item.value == wt

    def test_marks_current_worktree_with_checkmark(self) -> None:
        """Current worktree is marked with checkmark prefix."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main", is_current=True)
        item = format_worktree(wt)

        assert item.label == "✓ my-project"

    def test_non_current_worktree_no_checkmark(self) -> None:
        """Non-current worktree has no checkmark."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main", is_current=False)
        item = format_worktree(wt)

        assert item.label == "my-project"
        assert "✓" not in item.label

    def test_includes_branch_in_description(self) -> None:
        """Include branch name in description."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="feature/auth")
        item = format_worktree(wt)

        assert "feature/auth" in item.description

    def test_includes_modified_indicator(self) -> None:
        """Include modified indicator for changed worktrees."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main", has_changes=True)
        item = format_worktree(wt)

        assert "*modified" in item.description

    def test_includes_current_indicator_in_description(self) -> None:
        """Include (current) indicator in description."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main", is_current=True)
        item = format_worktree(wt)

        assert "(current)" in item.description

    def test_metadata_includes_path(self) -> None:
        """Metadata includes full path."""
        wt = WorktreeInfo(path="/home/user/my-project", branch="main")
        item = format_worktree(wt)

        assert item.metadata["path"] == "/home/user/my-project"

    def test_metadata_includes_current_status(self) -> None:
        """Metadata indicates if worktree is current."""
        current = WorktreeInfo(path="/home/user/current", branch="main", is_current=True)
        other = WorktreeInfo(path="/home/user/other", branch="dev", is_current=False)

        current_item = format_worktree(current)
        other_item = format_worktree(other)

        assert current_item.metadata["current"] == "yes"
        assert other_item.metadata["current"] == "no"


class TestShortenDockerStatus:
    """Test _shorten_docker_status helper function."""

    @pytest.mark.parametrize(
        "input_status,expected",
        [
            ("Up 2 hours", "Up 2h"),
            ("Up 1 hour", "Up 1h"),
            ("Up 30 minutes", "Up 30m"),
            ("Up 1 minute", "Up 1m"),
            ("Up 45 seconds", "Up 45s"),
            ("Up 1 second", "Up 1s"),
            ("Up 3 days", "Up 3d"),
            ("Up 1 day", "Up 1d"),
            ("Up 2 weeks", "Up 2w"),
            ("Up 1 week", "Up 1w"),
            ("Exited (0) 5 minutes ago", "Exited (0) 5m ago"),
            ("Created", "Created"),
            ("", ""),
        ],
    )
    def test_shortens_time_units(self, input_status: str, expected: str) -> None:
        """Shorten various time units correctly."""
        assert _shorten_docker_status(input_status) == expected


class TestFormatContext:
    """Test format_context function."""

    def test_formats_basic_context(self) -> None:
        """Format a basic context."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx)

        assert item.label == "platform · api · main"
        assert item.value == ctx

    def test_pinned_context_has_pin_indicator(self) -> None:
        """Pinned context has pin emoji prefix."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        item = format_context(ctx)

        assert item.label == "📌 platform · api · main"

    def test_unpinned_context_no_pin_indicator(self) -> None:
        """Unpinned context has no pin indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=False,
        )
        item = format_context(ctx)

        assert item.label == "platform · api · main"
        assert "📌" not in item.label

    def test_includes_relative_time_in_description(self) -> None:
        """Include relative time in description."""
        now = datetime.now(timezone.utc)
        two_hours_ago = (now - timedelta(hours=2)).isoformat()
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            last_used=two_hours_ago,
        )
        item = format_context(ctx)

        assert "2h ago" in item.description

    def test_includes_session_id_in_description(self) -> None:
        """Include session ID in description when present."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            last_session_id="my-session",
        )
        item = format_context(ctx)

        assert "session: my-session" in item.description

    def test_metadata_includes_team(self) -> None:
        """Metadata includes team name."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx)

        assert item.metadata["team"] == "platform"

    def test_metadata_includes_repo_name(self) -> None:
        """Metadata includes repository name."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api-service"),
            worktree_path=Path("/code/api-service"),
            worktree_name="main",
        )
        item = format_context(ctx)

        assert item.metadata["repo"] == "api-service"

    def test_metadata_includes_worktree_name(self) -> None:
        """Metadata includes worktree name."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api-feature"),
            worktree_name="feature-auth",
        )
        item = format_context(ctx)

        assert item.metadata["worktree"] == "feature-auth"

    def test_metadata_includes_path(self) -> None:
        """Metadata includes worktree path."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api-feature"),
            worktree_name="feature",
        )
        item = format_context(ctx)

        assert item.metadata["path"] == "/code/api-feature"

    def test_metadata_includes_pinned_status(self) -> None:
        """Metadata indicates if context is pinned."""
        pinned = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        unpinned = WorkContext(
            team="data",
            repo_root=Path("/code/ml"),
            worktree_path=Path("/code/ml"),
            worktree_name="main",
            pinned=False,
        )

        pinned_item = format_context(pinned)
        unpinned_item = format_context(unpinned)

        assert pinned_item.metadata["pinned"] == "yes"
        assert unpinned_item.metadata["pinned"] == "no"

    def test_running_container_shows_green_indicator(self) -> None:
        """Running container shows 🟢 indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=True)

        assert "🟢" in item.label
        assert item.label == "🟢 platform · api · main"

    def test_stopped_container_shows_dark_indicator(self) -> None:
        """Stopped container shows ⚫ indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=False)

        assert "⚫" in item.label
        assert item.label == "⚫ platform · api · main"

    def test_unknown_running_status_no_indicator(self) -> None:
        """Unknown running status (None) shows no indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=None)

        assert "🟢" not in item.label
        assert "⚫" not in item.label
        assert item.label == "platform · api · main"

    def test_pinned_and_running_shows_both_indicators(self) -> None:
        """Pinned and running context shows both indicators in correct order."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        item = format_context(ctx, is_running=True)

        # Order: pinned first, then running status
        assert item.label == "📌 🟢 platform · api · main"

    def test_pinned_and_stopped_shows_both_indicators(self) -> None:
        """Pinned and stopped context shows both indicators."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        item = format_context(ctx, is_running=False)

        assert item.label == "📌 ⚫ platform · api · main"

    def test_metadata_includes_running_status_yes(self) -> None:
        """Metadata includes running=yes when container is running."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=True)

        assert item.metadata["running"] == "yes"

    def test_metadata_includes_running_status_no(self) -> None:
        """Metadata includes running=no when container is stopped."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=False)

        assert item.metadata["running"] == "no"

    def test_metadata_running_empty_when_unknown(self) -> None:
        """Metadata includes running='' when status is unknown."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_running=None)

        assert item.metadata["running"] == ""

    # =========================================================================
    # Current branch indicator tests
    # =========================================================================

    def test_current_branch_shows_star_indicator(self) -> None:
        """Current branch context shows ★ indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=True)

        assert "★" in item.label
        assert item.label == "★ platform · api · main"

    def test_non_current_branch_no_star_indicator(self) -> None:
        """Non-current branch context shows no ★ indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=False)

        assert "★" not in item.label
        assert item.label == "platform · api · main"

    def test_unknown_current_branch_no_indicator(self) -> None:
        """Unknown current branch status (None) shows no indicator."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=None)

        assert "★" not in item.label

    def test_pinned_and_current_branch_shows_both_indicators(self) -> None:
        """Pinned and current branch context shows both indicators in correct order."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        item = format_context(ctx, is_current_branch=True)

        # Order: 📌 ★ display_label
        assert item.label == "📌 ★ platform · api · main"

    def test_pinned_running_and_current_branch_shows_all_indicators(self) -> None:
        """Context with all indicators shows them in correct order: 📌 ★ 🟢."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            pinned=True,
        )
        item = format_context(ctx, is_running=True, is_current_branch=True)

        # Order: 📌 ★ 🟢 display_label
        assert item.label == "📌 ★ 🟢 platform · api · main"

    def test_metadata_includes_current_branch_status_yes(self) -> None:
        """Metadata includes current_branch='yes' when is_current_branch=True."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=True)

        assert item.metadata["current_branch"] == "yes"

    def test_metadata_includes_current_branch_status_no(self) -> None:
        """Metadata includes current_branch='no' when is_current_branch=False."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=False)

        assert item.metadata["current_branch"] == "no"

    def test_metadata_current_branch_empty_when_unknown(self) -> None:
        """Metadata includes current_branch='' when status is unknown."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        item = format_context(ctx, is_current_branch=None)

        assert item.metadata["current_branch"] == ""


class TestFormatRelativeTime:
    """Test _format_relative_time helper function."""

    def test_just_now_for_recent(self) -> None:
        """Return 'just now' for times less than a minute ago."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(seconds=30)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == "just now"

    def test_minutes_ago(self) -> None:
        """Format minutes correctly."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(minutes=15)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == "15m ago"

    def test_hours_ago(self) -> None:
        """Format hours correctly."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(hours=3)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == "3h ago"

    def test_days_ago(self) -> None:
        """Format days correctly."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(days=2)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == "2d ago"

    def test_weeks_ago(self) -> None:
        """Format weeks correctly."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(weeks=2)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == "2w ago"

    def test_handles_z_suffix(self) -> None:
        """Handle ISO timestamps with Z suffix."""
        now = datetime.now(timezone.utc)
        timestamp = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        result = _format_relative_time(timestamp)

        assert result == "1h ago"

    def test_returns_empty_for_future_time(self) -> None:
        """Return empty string for future timestamps."""
        now = datetime.now(timezone.utc)
        timestamp = (now + timedelta(hours=1)).isoformat()

        result = _format_relative_time(timestamp)

        assert result == ""

    def test_returns_empty_for_invalid_timestamp(self) -> None:
        """Return empty string for invalid timestamp formats."""
        result = _format_relative_time("not-a-timestamp")

        assert result == ""

    def test_returns_empty_for_empty_string(self) -> None:
        """Return empty string for empty input."""
        result = _format_relative_time("")

        assert result == ""
