"""Tests for Quick Resume gating."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestShouldShowQuickResume:
    """Tests for should_show_quick_resume()."""

    def test_returns_true_by_default(self):
        """Returns True when no bypass conditions."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume()
        assert result is True

    def test_returns_false_when_json_mode(self):
        """Returns False when --json is set."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(json_mode=True)
        assert result is False

    def test_returns_false_when_non_interactive(self):
        """Returns False when --non-interactive is set."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(non_interactive=True)
        assert result is False

    def test_returns_false_when_resume(self):
        """Returns False when --resume is set."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(resume=True)
        assert result is False

    def test_returns_false_when_select(self):
        """Returns False when --select is set."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(select=True)
        assert result is False

    def test_returns_false_when_fresh(self):
        """Returns False when --fresh is set."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(fresh=True)
        assert result is False

    def test_returns_false_when_interactive_flag(self):
        """Returns False when --interactive is set (forces wizard, bypasses QR)."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(interactive_flag=True)
        assert result is False

    def test_multiple_flags_still_false(self):
        """Returns False with multiple bypass flags."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        result = should_show_quick_resume(
            json_mode=True,
            resume=True,
            fresh=True,
        )
        assert result is False


class TestLoadContextsForWorkspaceAndTeam:
    """Tests for load_contexts_for_workspace_and_team()."""

    def test_filters_by_workspace(self, tmp_path):
        """Only returns contexts matching workspace."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "myproject"
        workspace.mkdir()
        other = tmp_path / "other"
        other.mkdir()

        # Mock contexts with different workspaces
        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
            MagicMock(spec=WorkContext, repo_root=str(other), team=None),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
        ]

        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(
                workspace_root=workspace,
                team=None,
                limit=10,
            )

        assert len(result) == 2
        for ctx in result:
            assert Path(ctx.repo_root).resolve() == workspace.resolve()

    def test_standalone_only_shows_no_team(self, tmp_path):
        """Standalone mode (team=None) only shows contexts with no team."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "myproject"
        workspace.mkdir()

        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="platform"),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
        ]

        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(
                workspace_root=workspace,
                team=None,  # Standalone
                limit=10,
            )

        assert len(result) == 2
        for ctx in result:
            assert ctx.team is None

    def test_team_filter_only_shows_matching_team(self, tmp_path):
        """Team filter only shows contexts matching that team."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "myproject"
        workspace.mkdir()

        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="platform"),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="data"),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="platform"),
        ]

        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(
                workspace_root=workspace,
                team="platform",
                limit=10,
            )

        assert len(result) == 2
        for ctx in result:
            assert ctx.team == "platform"

    def test_respects_limit(self, tmp_path):
        """Respects the limit parameter."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "myproject"
        workspace.mkdir()

        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None) for _ in range(20)
        ]

        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(
                workspace_root=workspace,
                team=None,
                limit=5,
            )

        assert len(result) == 5

    def test_handles_empty_contexts(self, tmp_path):
        """Handles case with no contexts."""
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "myproject"
        workspace.mkdir()

        with patch("scc_cli.contexts.load_recent_contexts", return_value=[]):
            result = load_contexts_for_workspace_and_team(
                workspace_root=workspace,
                team=None,
                limit=10,
            )

        assert result == []
