"""Tests for Quick Resume navigation semantics."""

from pathlib import Path
from unittest.mock import patch

from scc_cli.contexts import WorkContext
from scc_cli.ui.picker import QuickResumeResult


def test_quick_resume_shows_active_team_in_header() -> None:
    """Quick Resume header should include active team label."""
    from scc_cli.cli_launch import interactive_start

    context = WorkContext(
        team="platform",
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
    )

    with (
        patch("scc_cli.cli_launch.config.is_standalone_mode", return_value=False),
        patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}),
        patch("scc_cli.cli_launch.teams.list_teams", return_value=[]),
        patch("scc_cli.cli_launch.load_recent_contexts", return_value=[context]),
        patch("scc_cli.cli_launch.pick_context_quick_resume") as mock_picker,
    ):
        mock_picker.side_effect = RuntimeError("stop")
        try:
            interactive_start(cfg={"selected_profile": "platform"}, allow_back=False)
        except RuntimeError:
            pass

    context_label = mock_picker.call_args.kwargs["context_label"]
    assert context_label == "Team: platform"


def test_quick_resume_back_cancels_at_top_level() -> None:
    """Esc at top-level Quick Resume should cancel the wizard."""
    from scc_cli.cli_launch import interactive_start

    context = WorkContext(
        team="platform",
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
    )

    with (
        patch("scc_cli.cli_launch.config.is_standalone_mode", return_value=False),
        patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}),
        patch("scc_cli.cli_launch.teams.list_teams", return_value=[]),
        patch("scc_cli.cli_launch.load_recent_contexts", return_value=[context]),
        patch(
            "scc_cli.cli_launch.pick_context_quick_resume",
            return_value=(QuickResumeResult.BACK, None),
        ),
    ):
        result = interactive_start(cfg={}, allow_back=False)

    assert result == (None, None, None, None)
