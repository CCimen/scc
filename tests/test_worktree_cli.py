"""
Tests for worktree CLI commands (Phase 5).

TDD approach: Tests written before implementation.
These tests define the contract for:
- scc worktree create
- scc worktree list (with --json)
- scc worktree remove
- Deprecated aliases (scc worktrees, scc cleanup)
"""

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from scc_cli.git import WorktreeInfo, render_worktrees

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree CLI Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeAppStructure:
    """Test worktree app Typer structure."""

    def test_worktree_app_exists(self) -> None:
        """worktree_app Typer should exist."""
        from scc_cli.cli_worktree import worktree_app

        assert worktree_app is not None

    def test_worktree_app_has_create_command(self) -> None:
        """worktree_app should have 'create' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "create" in command_names

    def test_worktree_app_has_list_command(self) -> None:
        """worktree_app should have 'list' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "list" in command_names

    def test_worktree_app_has_remove_command(self) -> None:
        """worktree_app should have 'remove' subcommand."""
        from scc_cli.cli_worktree import worktree_app

        command_names = [cmd.name for cmd in worktree_app.registered_commands]
        assert "remove" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Create Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeCreate:
    """Test scc worktree create command."""

    def test_create_calls_git_create_worktree(self, tmp_path: Path) -> None:
        """create should call git.create_worktree with correct args."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree") as mock_create,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),
        ):
            mock_create.return_value = tmp_path / "worktrees" / "feature"
            try:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch=None,
                    start_claude=False,
                    install_deps=False,
                )
            except click.exceptions.Exit:
                pass

            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][1] == "feature"

    def test_create_with_base_branch(self, tmp_path: Path) -> None:
        """create with --base should pass branch to git.create_worktree."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree") as mock_create,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),
        ):
            mock_create.return_value = tmp_path / "worktrees" / "feature"
            try:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch="develop",
                    start_claude=False,
                    install_deps=False,
                )
            except click.exceptions.Exit:
                pass

            call_args = mock_create.call_args
            assert call_args[0][2] == "develop"

    def test_create_raises_for_non_repo(self, tmp_path: Path) -> None:
        """create should exit with error for non-git directories."""
        from scc_cli.cli_worktree import worktree_create_cmd

        with patch("scc_cli.cli_worktree.git.is_git_repo", return_value=False):
            # @handle_errors decorator converts NotAGitRepoError to typer.Exit(4)
            with pytest.raises(click.exceptions.Exit) as exc_info:
                worktree_create_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    base_branch=None,
                    start_claude=False,
                    install_deps=False,
                )
            assert exc_info.value.exit_code == 4


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree List Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeList:
    """Test scc worktree list command."""

    def test_list_calls_git_list_worktrees(self, tmp_path: Path) -> None:
        """list should call git.list_worktrees."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = [
                WorktreeInfo(path=str(tmp_path), branch="main", status="clean")
            ]
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

            mock_list.assert_called_once()

    def test_list_json_has_correct_kind(self, tmp_path: Path, capsys) -> None:
        """list --json should output JSON with kind=WorktreeList."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = [
                WorktreeInfo(path=str(tmp_path), branch="main", status="clean")
            ]
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "WorktreeList"
        assert output["apiVersion"] == "scc.cli/v1"

    def test_list_json_contains_worktrees(self, tmp_path: Path, capsys) -> None:
        """list --json should contain worktree data."""
        from scc_cli.cli_worktree import worktree_list_cmd

        worktrees = [
            WorktreeInfo(path=str(tmp_path), branch="main", status="clean"),
            WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/x", status="clean"),
        ]

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = worktrees
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "worktrees" in output["data"]
        assert len(output["data"]["worktrees"]) == 2

    def test_list_json_empty_worktrees(self, tmp_path: Path, capsys) -> None:
        """list --json with no worktrees should return empty array."""
        from scc_cli.cli_worktree import worktree_list_cmd

        with (
            patch("scc_cli.cli_worktree.git.list_worktrees") as mock_list,
            patch("scc_cli.cli_worktree.git.render_worktrees"),
        ):
            mock_list.return_value = []
            try:
                worktree_list_cmd(
                    workspace=str(tmp_path),
                    json_output=True,
                    pretty=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["data"]["worktrees"] == []
        assert output["data"]["count"] == 0

    def test_render_worktrees_detached_branch_shows_label(self) -> None:
        """Detached worktrees should show a 'detached' label instead of blank."""
        from rich.console import Console

        console = Console(record=True, width=120)
        worktrees = [WorktreeInfo(path="/repo", branch="", status="")]

        render_worktrees(worktrees, console)

        output = console.export_text()
        assert "detached" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Worktree Remove Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeRemove:
    """Test scc worktree remove command."""

    def test_remove_calls_git_cleanup_worktree(self, tmp_path: Path) -> None:
        """remove should call git.cleanup_worktree with correct args."""
        from scc_cli.cli_worktree import worktree_remove_cmd

        with patch("scc_cli.cli_worktree.git.cleanup_worktree") as mock_cleanup:
            mock_cleanup.return_value = True
            try:
                worktree_remove_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    force=False,
                )
            except click.exceptions.Exit:
                pass

            mock_cleanup.assert_called_once()
            call_args = mock_cleanup.call_args
            assert call_args[0][1] == "feature"

    def test_remove_with_force_flag(self, tmp_path: Path) -> None:
        """remove with --force should pass force=True to cleanup."""
        from scc_cli.cli_worktree import worktree_remove_cmd

        with patch("scc_cli.cli_worktree.git.cleanup_worktree") as mock_cleanup:
            mock_cleanup.return_value = True
            try:
                worktree_remove_cmd(
                    workspace=str(tmp_path),
                    name="feature",
                    force=True,
                )
            except click.exceptions.Exit:
                pass

            call_args = mock_cleanup.call_args
            assert call_args[0][2] is True  # force=True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CLI Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeAppRegistration:
    """Test worktree app is registered in main CLI."""

    def test_worktree_app_registered_in_main_cli(self) -> None:
        """worktree_app should be registered as subcommand in main CLI."""
        from scc_cli.cli import app

        # Typer apps added via add_typer appear in registered_groups, not registered_commands
        group_names = [group.name for group in app.registered_groups if group.name]
        assert "worktree" in group_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Pure Functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildWorktreeListData:
    """Test build_worktree_list_data pure function."""

    def test_builds_correct_structure(self) -> None:
        """build_worktree_list_data should return correct structure."""
        from scc_cli.cli_worktree import build_worktree_list_data

        worktrees = [
            {"path": "/home/user/repo", "branch": "main", "head": "abc123"},
            {"path": "/home/user/repo-feature", "branch": "feature/x", "head": "def456"},
        ]
        result = build_worktree_list_data(worktrees, workspace="/home/user/repo")

        assert "worktrees" in result
        assert "count" in result
        assert "workspace" in result
        assert result["count"] == 2
        assert result["workspace"] == "/home/user/repo"

    def test_handles_empty_list(self) -> None:
        """build_worktree_list_data should handle empty list."""
        from scc_cli.cli_worktree import build_worktree_list_data

        result = build_worktree_list_data([], workspace="/home/user/repo")

        assert result["worktrees"] == []
        assert result["count"] == 0
