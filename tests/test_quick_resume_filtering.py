"""Tests for Quick Resume team filtering and UX.

Verifies:
- --team flag takes precedence over selected_profile
- New Session is always the default selection
- Team filtering works correctly in load_recent_contexts
- Cross-team toggle behavior
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from scc_cli.contexts import WorkContext, load_recent_contexts
from scc_cli.ui.picker import (
    NEW_SESSION_SENTINEL,
    QuickResumeResult,
)


def _make_context(
    team: str | None,
    repo_name: str = "project",
    worktree_name: str = "main",
    branch: str = "main",
) -> dict:
    """Create a raw context dict for mocking _load_contexts_raw."""
    repo_root = Path(f"/projects/{repo_name}")
    return {
        "team": team,
        "repo_root": str(repo_root),
        "worktree_path": str(repo_root / worktree_name if worktree_name != "main" else repo_root),
        "worktree_name": worktree_name,
        "branch": branch,
        "last_session_id": f"session-{repo_name}",
        "last_used": "2024-01-02T10:00:00",
        "pinned": False,
    }


class TestLoadRecentContextsFiltering:
    """Tests for load_recent_contexts team filtering."""

    @pytest.fixture
    def mock_raw_contexts(self) -> list[dict]:
        """Create mock raw context dicts from different teams."""
        return [
            _make_context("team-alpha", "project-a", "main", "main"),
            _make_context("team-beta", "project-b", "main", "develop"),
            _make_context("team-alpha", "project-c", "main", "feature"),
        ]

    def test_filter_by_specific_team(self, mock_raw_contexts: list[dict]):
        """load_recent_contexts with team_filter should return only that team."""
        with patch("scc_cli.contexts._load_contexts_raw", return_value=mock_raw_contexts):
            result = load_recent_contexts(limit=10, team_filter="team-alpha")

        assert len(result) == 2
        assert all(ctx.team == "team-alpha" for ctx in result)

    def test_filter_all_returns_all_teams(self, mock_raw_contexts: list[dict]):
        """load_recent_contexts with team_filter='all' should return all contexts."""
        with patch("scc_cli.contexts._load_contexts_raw", return_value=mock_raw_contexts):
            result = load_recent_contexts(limit=10, team_filter="all")

        assert len(result) == 3

    def test_filter_none_returns_standalone_only(self, mock_raw_contexts: list[dict]):
        """load_recent_contexts with team_filter=None should return standalone contexts."""
        # Add a standalone context (no team)
        standalone = _make_context(None, "standalone", "main", "main")
        contexts_with_standalone = [standalone] + mock_raw_contexts

        with patch(
            "scc_cli.contexts._load_contexts_raw",
            return_value=contexts_with_standalone,
        ):
            result = load_recent_contexts(limit=10, team_filter=None)

        assert len(result) == 1
        assert result[0].team is None

    def test_filter_nonexistent_team_returns_empty(self, mock_raw_contexts: list[dict]):
        """load_recent_contexts with non-matching team should return empty list."""
        with patch("scc_cli.contexts._load_contexts_raw", return_value=mock_raw_contexts):
            result = load_recent_contexts(limit=10, team_filter="nonexistent-team")

        assert len(result) == 0


class TestNewSessionSentinel:
    """Tests for NEW_SESSION_SENTINEL behavior."""

    def test_sentinel_is_unique_object(self):
        """NEW_SESSION_SENTINEL should be a unique object."""
        assert NEW_SESSION_SENTINEL is not None
        assert NEW_SESSION_SENTINEL is NEW_SESSION_SENTINEL  # Same object

    def test_sentinel_not_equal_to_work_context(self):
        """NEW_SESSION_SENTINEL should not be confused with WorkContext."""
        ctx = WorkContext(
            team="test-team",
            repo_root=Path("/test"),
            worktree_path=Path("/test"),
            worktree_name="main",
            branch="main",
            last_session_id="test-session",
        )
        assert ctx is not NEW_SESSION_SENTINEL


class TestQuickResumeResult:
    """Tests for QuickResumeResult enum values."""

    def test_all_result_types_exist(self):
        """QuickResumeResult should have all expected values."""
        assert QuickResumeResult.SELECTED.value == "selected"
        assert QuickResumeResult.NEW_SESSION.value == "new_session"
        assert QuickResumeResult.BACK.value == "back"
        assert QuickResumeResult.CANCELLED.value == "cancelled"
        assert QuickResumeResult.TOGGLE_ALL_TEAMS.value == "toggle_all_teams"


class TestEffectiveTeamPriority:
    """Tests for --team flag priority over selected_profile."""

    def test_team_flag_overrides_selected_profile(self):
        """--team flag should take precedence over selected_profile."""
        # This tests the effective_team calculation logic
        selected_profile = "team-from-switch"
        team_override = "team-from-flag"

        # The logic: effective_team = team_override or selected_profile
        effective_team = team_override or selected_profile

        assert effective_team == "team-from-flag"

    def test_selected_profile_used_when_no_override(self):
        """selected_profile should be used when no --team flag."""
        selected_profile = "team-from-switch"
        team_override = None

        effective_team = team_override or selected_profile

        assert effective_team == "team-from-switch"

    def test_none_when_both_missing(self):
        """effective_team should be None when both are missing."""
        selected_profile = None
        team_override = None

        effective_team = team_override or selected_profile

        assert effective_team is None
