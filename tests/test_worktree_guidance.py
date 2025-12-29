"""Tests for non-worktree guidance warnings."""

from pathlib import Path
from unittest.mock import patch

from scc_cli.cli_launch import _warn_if_non_worktree


def test_warns_when_in_main_repo() -> None:
    """Warn when running in a git repo without a worktree."""
    workspace = Path("/repo")

    with (
        patch("scc_cli.cli_launch.git.is_git_repo", return_value=True),
        patch("scc_cli.cli_launch.git.is_worktree", return_value=False),
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        _warn_if_non_worktree(workspace, json_mode=False)

    assert mock_print.called


def test_no_warning_for_worktree() -> None:
    """No warning for worktree paths."""
    workspace = Path("/repo-worktrees/feature")

    with (
        patch("scc_cli.cli_launch.git.is_git_repo", return_value=True),
        patch("scc_cli.cli_launch.git.is_worktree", return_value=True),
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        _warn_if_non_worktree(workspace, json_mode=False)

    assert not mock_print.called


def test_no_warning_for_non_repo() -> None:
    """No warning for paths outside git repos."""
    workspace = Path("/tmp/project")

    with (
        patch("scc_cli.cli_launch.git.is_git_repo", return_value=False),
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        _warn_if_non_worktree(workspace, json_mode=False)

    assert not mock_print.called
